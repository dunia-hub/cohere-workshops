from pathlib import Path
from types import SimpleNamespace

import pytest

from cohere_workshops.agent_tools import (
    SEARCH_TOOL,
    UNFILTERED_SEARCH_TOOL,
    CodeSearchTool,
    TargetValidator,
    decision_records,
    stale_references,
)
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.versions import build_versioned_corpus, load_revision


class KeywordClient:
    """Fake Embed and Rerank. Prefers old code, so the Git rule must catch it."""

    WORDS = ("fee", "phone", "send", "receipt")

    def __init__(self) -> None:
        self.embed_calls = 0
        self.rerank_calls = 0

    def embed(self, **kwargs: object) -> object:
        self.embed_calls += 1
        vectors = [
            [1.0] + [float(text.lower().count(w)) for w in self.WORDS]
            for text in kwargs["texts"]
        ]
        return SimpleNamespace(embeddings=SimpleNamespace(float=vectors))

    def rerank(self, **kwargs: object) -> object:
        self.rerank_calls += 1
        documents = kwargs["documents"]
        scores = [(0.9 if "0.02" in d or "validate" in d else 0.5) for d in documents]
        order = sorted(range(len(documents)), key=lambda i: -scores[i])
        return SimpleNamespace(
            results=[SimpleNamespace(index=i, relevance_score=scores[i]) for i in order]
        )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


def make_tool(repo: Path, target: str, **options) -> tuple[CodeSearchTool, KeywordClient]:
    corpus = build_versioned_corpus(repo, "v1", "v2")
    validator = TargetValidator(load_revision(repo, target))
    client = KeywordClient()
    return CodeSearchTool(client, corpus, validator, **options), client


def test_tool_schema_is_a_function_with_a_query() -> None:
    function = SEARCH_TOOL["function"]
    assert function["name"] == "search_code"
    assert function["parameters"]["required"] == ["query"]


def test_returns_only_code_valid_at_target_commit(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2")

    documents = tool.search("How is the transfer fee calculated?")

    assert documents
    assert all(doc["valid_at_revision"] == "v2" for doc in documents)
    assert "0.02" not in "".join(str(doc["code"]) for doc in documents)
    assert {"calculate_transfer_fee", "validate_phone_number"} & {
        item.chunk.symbol for item in tool.rejected.values()
    }


def test_older_target_makes_old_code_valid(repo: Path) -> None:
    tool, _ = make_tool(repo, "v1")

    documents = tool.search("How is the transfer fee calculated?")
    symbols = {doc["symbol"] for doc in documents}

    assert "normalize_phone_number" not in symbols
    assert any("0.02" in str(doc["code"]) for doc in documents)


def test_embeds_corpus_once_then_one_query_per_search(repo: Path) -> None:
    tool, client = make_tool(repo, "v2")

    tool.search("fee")
    tool.search("phone")

    assert client.embed_calls == 3
    assert client.rerank_calls == 2
    assert len(tool.calls) == 2


def test_keep_limits_evidence_sent_to_model(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2", keep=1)

    documents = tool.search("fee")

    assert len(documents) == 1


def test_trace_records_every_decision(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2")
    tool.search("fee")

    [record] = decision_records(tool.calls)

    assert record["query"] == "fee"
    assert any(c["valid_at_target"] is False for c in record["candidates"])
    assert all(
        c["evidence_id"] is None for c in record["candidates"] if not c["valid_at_target"]
    )


def test_finds_stale_names_in_an_answer(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2")
    tool.search("Check that a phone number is valid")

    stale = stale_references("Call validate_phone_number first.", tool)
    clean = stale_references("Call normalize_phone_number first.", tool)

    assert stale == ["validate_phone_number"]
    assert clean == []


def test_rejects_empty_query(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2")

    with pytest.raises(ValueError, match="query must not be empty"):
        tool.search("  ")


def test_without_git_filter_sends_invalid_code_with_revision_labels(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2", git_filter=False)

    documents = tool.search("How is the transfer fee calculated?")

    assert tool.definition is UNFILTERED_SEARCH_TOOL
    assert all("valid_at_commit" not in doc for doc in documents)
    assert any(doc["exists_in_revisions"] == ["v1"] for doc in documents)
    assert any("0.02" in str(doc["code"]) for doc in documents)
    assert set(tool.evidence) - set(tool.valid_evidence)


def test_without_git_filter_unchanged_code_is_labelled_with_both_revisions(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2", git_filter=False, keep=10)

    documents = tool.search("receipt")
    labels = {doc["symbol"]: doc["exists_in_revisions"] for doc in documents}

    assert labels["format_receipt"] == ["v1", "v2"]
    assert labels["normalize_phone_number"] == ["v2"]


def test_without_git_filter_trace_still_records_git_decisions(repo: Path) -> None:
    tool, _ = make_tool(repo, "v2", git_filter=False)
    tool.search("fee")

    [record] = decision_records(tool.calls)

    sent = [c for c in record["candidates"] if c["sent_to_model"]]
    assert any(c["valid_at_target"] is False for c in sent)
