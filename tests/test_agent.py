import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cohere_workshops.agent import (
    AGENT_PROMPT,
    agent_record,
    answer_schema,
    message_text,
    run_agent,
)
from cohere_workshops.agent_tools import CodeSearchTool, TargetValidator
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.versions import build_versioned_corpus, load_revision


class FakeCommandClient:
    """Fake Embed, Rerank and Command. Spends no credits."""

    def __init__(self, *, call_tool: bool = True, answer: str = "Fees are tiered.") -> None:
        self.call_tool = call_tool
        self.answer = answer
        self.chat_calls: list[dict[str, object]] = []

    def embed(self, **kwargs):
        vectors = [[1.0, float("fee" in t.lower())] for t in kwargs["texts"]]
        return SimpleNamespace(embeddings=SimpleNamespace(float=vectors))

    def rerank(self, **kwargs):
        n = len(kwargs["documents"])
        return SimpleNamespace(
            results=[SimpleNamespace(index=i, relevance_score=1 - i / 10) for i in range(n)]
        )

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        messages = kwargs["messages"]
        if "response_format" in kwargs:
            ids = kwargs["response_format"]["schema"]["properties"]["evidence_ids"]["items"]["enum"]
            payload = {
                "answer": self.answer,
                "declined": False,
                "decline_reason": "",
                "evidence_ids": [ids[0], "made-up-id"],
            }
            text = SimpleNamespace(type="text", text=json.dumps(payload))
            thinking = SimpleNamespace(type="thinking", thinking="...")
            return SimpleNamespace(message=SimpleNamespace(content=[thinking, text]))
        if self.call_tool and not any(
            isinstance(m, dict) and m.get("role") == "tool" for m in messages
        ):
            call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="search_code", arguments=json.dumps({"query": "transfer fee"})
                ),
            )
            return SimpleNamespace(
                message=SimpleNamespace(tool_calls=[call], tool_plan="I will search.", content=[])
            )
        done = SimpleNamespace(type="text", text="Done.")
        return SimpleNamespace(message=SimpleNamespace(tool_calls=None, content=[done]))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


def make_tool(repo: Path, client, target: str = "v2") -> CodeSearchTool:
    corpus = build_versioned_corpus(repo, "v1", "v2")
    return CodeSearchTool(client, corpus, TargetValidator(load_revision(repo, target)))


def test_command_calls_the_tool_and_answers_from_valid_evidence(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_tool(repo, client)

    result = run_agent(client, tool, "How is the transfer fee calculated?")

    assert [call.query for call in tool.calls] == ["transfer fee"]
    assert result.tool_plans == ["I will search."]
    assert result.declined is False
    assert result.answer == "Fees are tiered."
    assert result.evidence_ids and "made-up-id" not in result.evidence_ids
    assert result.references[0]["valid_at_commit"] == tool.validator.commit


def test_tool_result_goes_back_to_command_as_documents(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_tool(repo, client)

    run_agent(client, tool, "fee?")

    tool_message = next(m for m in client.chat_calls[1]["messages"] if isinstance(m, dict) and m["role"] == "tool")
    assert tool_message["tool_call_id"] == "call-1"
    assert tool_message["content"][0]["type"] == "document"
    assert "valid_at_commit" in tool_message["content"][0]["document"]["data"]


def test_application_searches_if_command_skips_the_tool(repo: Path) -> None:
    client = FakeCommandClient(call_tool=False)
    tool = make_tool(repo, client)

    result = run_agent(client, tool, "How is the transfer fee calculated?")

    assert result.forced_search is True
    assert len(tool.calls) == 1


def test_declines_without_calling_command_when_no_valid_evidence(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_tool(repo, client)
    tool.validator._keys = set()

    result = run_agent(client, tool, "fee?")

    assert result.declined is True
    assert "No code valid" in result.decline_reason
    assert not any("response_format" in call for call in client.chat_calls)


def test_flags_stale_names_in_the_answer(repo: Path) -> None:
    client = FakeCommandClient(answer="It uses validate_phone_number.")
    tool = make_tool(repo, client)
    tool.search("Check that a phone number is valid")

    result = run_agent(client, tool, "How is a phone number checked?")

    assert result.stale == ["validate_phone_number"]


def test_answer_schema_limits_citations_to_valid_ids() -> None:
    schema = answer_schema(["abc"])

    assert schema["properties"]["evidence_ids"]["items"]["enum"] == ["abc"]


def test_message_text_skips_thinking_blocks() -> None:
    message = SimpleNamespace(content=[SimpleNamespace(type="thinking"), SimpleNamespace(text="hi")])

    assert message_text(message) == "hi"


def test_trace_has_tool_calls_decisions_and_answer(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_tool(repo, client)
    result = run_agent(client, tool, "fee?")

    record = agent_record(result, tool, run_id="r1", models={"command": "x"})

    assert record["tool_calls"][0]["query"] == "transfer fee"
    assert "valid_at_target" in record["tool_calls"][0]["candidates"][0]
    assert record["answer"] == "Fees are tiered."
    assert record["target"]["revision"] == "v2"


def make_unfiltered_tool(repo: Path, client, target: str = "v2") -> CodeSearchTool:
    corpus = build_versioned_corpus(repo, "v1", "v2")
    validator = TargetValidator(load_revision(repo, target))
    return CodeSearchTool(client, corpus, validator, git_filter=False)


def test_without_git_filter_prompts_name_the_target(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_unfiltered_tool(repo, client, target="v1")

    run_agent(client, tool, "fee?")

    planning, answering = client.chat_calls[0], client.chat_calls[-1]
    system = planning["messages"][0]["content"]
    assert "target revision v1" in system
    assert tool.validator.commit[:12] in system
    assert "valid at the target commit" not in system
    assert planning["tools"][0]["function"]["description"].startswith("Searches")
    assert "more than one revision" in planning["tools"][0]["function"]["description"]
    assert "target revision v1" in answering["messages"][0]["content"]
    assert "Every piece of evidence is valid" not in answering["messages"][0]["content"]


def test_without_git_filter_citations_record_whether_they_are_valid(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_unfiltered_tool(repo, client)

    result = run_agent(client, tool, "fee?")
    record = agent_record(result, tool, run_id="r1", models={"command": "x"})

    assert record["git_filter"] is False
    for ref in result.references:
        chunk = tool.evidence[ref["evidence_id"]].chunk
        assert ref["valid_at_target"] is tool.validator.is_valid(chunk)
        assert (ref["valid_at_commit"] is None) is (not ref["valid_at_target"])


def test_with_git_filter_prompts_are_unchanged(repo: Path) -> None:
    client = FakeCommandClient()
    tool = make_tool(repo, client)

    result = run_agent(client, tool, "fee?")
    record = agent_record(result, tool, run_id="r1", models={"command": "x"})

    assert client.chat_calls[0]["messages"][0]["content"] == AGENT_PROMPT
    assert record["git_filter"] is True
    assert all(ref["valid_at_target"] for ref in result.references)
