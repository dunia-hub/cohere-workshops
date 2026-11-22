from dataclasses import dataclass

import pytest

from cohere_workshops.chunks import RepositoryChunk
from cohere_workshops.rerank_versions import (
    check_ranking,
    format_candidate,
    rerank_hits,
    retrieval_order,
    serialize_rerank_result,
    temporal_filter,
)
from cohere_workshops.version_search import VersionHit
from cohere_workshops.versions import CURRENT, REMOVED, SUPERSEDED, VersionedChunk

OLD_COMMIT = "a" * 40
NEW_COMMIT = "b" * 40


@dataclass
class FakeResult:
    index: int
    relevance_score: float


@dataclass
class FakeResponse:
    results: list[FakeResult]


class MarkerRerankClient:
    """Fake Rerank: scores each document by fixed markers, spends no credits."""

    SCORES = (("flat", 0.9), ("tiered", 0.8), ("receipt", 0.2))

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def rerank(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        documents = kwargs["documents"]
        assert isinstance(documents, list)
        scored = []
        for index, text in enumerate(documents):
            score = next((s for marker, s in self.SCORES if marker in text), 0.1)
            scored.append(FakeResult(index, score))
        scored.sort(key=lambda r: r.relevance_score, reverse=True)
        return FakeResponse(scored)


def make_item(chunk_id: str, content: str, status: str) -> VersionedChunk:
    revision, commit = ("v2", NEW_COMMIT) if status == CURRENT else ("v1", OLD_COMMIT)
    chunk = RepositoryChunk(
        chunk_id=chunk_id,
        path="payments.py",
        language="python",
        kind="function",
        symbol="fee",
        start_line=1,
        end_line=2,
        content=content,
        content_hash=f"hash-{chunk_id}",
        source_hash=f"source-{revision}",
    )
    return VersionedChunk(chunk, revision, commit, status)


@pytest.fixture
def hits() -> tuple[VersionHit, ...]:
    items = (
        make_item("new-fee", "def fee(): tiered", CURRENT),
        make_item("receipt", "def receipt(): pass", CURRENT),
        make_item("old-fee", "def fee(): flat", SUPERSEDED),
    )
    return tuple(
        VersionHit(rank=rank, score=1 - rank / 10, item=item)
        for rank, item in enumerate(items, start=1)
    )


def test_code_format_hides_version_and_metadata_format_shows_it() -> None:
    item = make_item("old-fee", "def fee(): flat", SUPERSEDED)

    code = format_candidate(item, "code")
    meta = format_candidate(item, "metadata", {OLD_COMMIT: "2026-10-01"})

    assert "revision" not in code and OLD_COMMIT[:12] not in code
    assert "revision: v1" in meta
    assert "commit date: 2026-10-01" in meta
    assert code.endswith("def fee(): flat")


def test_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="style must be one of"):
        format_candidate(make_item("x", "x", CURRENT), "html")


def test_rerank_reorders_and_keeps_retrieval_rank(hits) -> None:
    client = MarkerRerankClient()

    ranked = rerank_hits(client, "fee", hits)

    assert [c.item.chunk.chunk_id for c in ranked] == ["old-fee", "new-fee", "receipt"]
    assert [c.retrieval_rank for c in ranked] == [3, 1, 2]
    assert [c.rank for c in ranked] == [1, 2, 3]
    assert client.calls[0]["top_n"] == 3
    assert client.calls[0]["model"] == "rerank-v4.0-pro"


def test_flags_stale_code_above_current_code(hits) -> None:
    before = check_ranking(retrieval_order(hits), k=2)
    after = check_ranking(rerank_hits(MarkerRerankClient(), "fee", hits), k=2)

    assert before.top_result_is_current is True
    assert before.stale_above_current is False
    assert after.top_result_is_current is False
    assert after.stale_above_current is True
    assert after.current_rank == 2
    assert after.best_stale_rank == 1
    assert after.stale_rate_at_k == 0.5


def test_temporal_filter_keeps_only_current_code(hits) -> None:
    ranked = rerank_hits(MarkerRerankClient(), "fee", hits)

    filtered = temporal_filter(ranked)

    assert [c.item.chunk.chunk_id for c in filtered] == ["new-fee", "receipt"]
    assert [c.rank for c in filtered] == [1, 2]


def test_removed_code_counts_as_stale() -> None:
    removed = make_item("old-check", "def check(): flat", REMOVED)
    ranking = retrieval_order([VersionHit(1, 0.9, removed)])

    check = check_ranking(ranking, k=1)

    assert check.current_in_top_k is False
    assert check.current_rank is None
    assert check.stale_above_current is True


def test_rejects_bad_rerank_index(hits) -> None:
    class BadClient:
        def rerank(self, **kwargs):
            return FakeResponse([FakeResult(9, 0.5)])

    with pytest.raises(ValueError, match="invalid document index"):
        rerank_hits(BadClient(), "fee", hits)


def test_record_has_both_checks_and_no_source(hits) -> None:
    reranked = rerank_hits(MarkerRerankClient(), "fee", hits)

    record = serialize_rerank_result(
        run_id="run-1",
        query="fee",
        style="code",
        k=2,
        embed_model="embed-v4.0",
        rerank_model="rerank-v4.0-pro",
        previous=("v1", OLD_COMMIT),
        current=("v2", NEW_COMMIT),
        retrieval=retrieval_order(hits),
        reranked=reranked,
    )

    assert record["retrieval_check"]["stale_above_current"] is False
    assert record["rerank_check"]["stale_above_current"] is True
    assert record["filtered_top"][0]["chunk_id"] == "new-fee"
    assert "def fee" not in str(record)


def test_filter_and_check_accept_a_target_rule(hits) -> None:
    ranking = retrieval_order(hits)

    def old_is_valid(item: VersionedChunk) -> bool:
        return item.revision == "v1"

    kept = temporal_filter(ranking, old_is_valid)
    check = check_ranking(ranking, k=1, is_valid=old_is_valid)

    assert [c.item.chunk.chunk_id for c in kept] == ["old-fee"]
    assert kept[0].rank == 1
    assert check.top_result_is_current is False
    assert check.current_rank == 3


def test_record_marks_validity_at_the_target(hits) -> None:
    ranking = retrieval_order(hits)

    record = serialize_rerank_result(
        run_id="r1",
        query="fee",
        style="code",
        k=3,
        embed_model="e",
        rerank_model="r",
        previous=("v1", OLD_COMMIT),
        current=("v2", NEW_COMMIT),
        retrieval=ranking,
        reranked=ranking,
        target=("v1", OLD_COMMIT),
        is_valid=lambda item: item.revision == "v1",
    )

    assert record["target"] == {"revision": "v1", "commit": OLD_COMMIT}
    assert [r["valid_at_target"] for r in record["reranked"]] == [False, False, True]
    assert record["filtered_top"][0]["chunk_id"] == "old-fee"
