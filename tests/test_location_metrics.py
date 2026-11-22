from pathlib import Path

import pytest

from cohere_workshops.agent_tools import TargetValidator
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.location_metrics import (
    locations_at,
    score_location,
    score_record,
    summarize,
)
from cohere_workshops.rerank_versions import RankedCandidate
from cohere_workshops.versions import (
    build_versioned_corpus,
    load_revision,
    location_key,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


def setup(repo: Path, target: str):
    corpus = build_versioned_corpus(repo, "v1", "v2")
    snapshot = load_revision(repo, target)
    validator = TargetValidator(snapshot)
    items = {
        (item.chunk.symbol, item.revision): item
        for item in corpus.chunks
        if item.chunk.kind != "file"
    }
    return items, snapshot, (lambda item: validator.is_valid(item.chunk))


def ranking(*items) -> list[RankedCandidate]:
    return [
        RankedCandidate(rank=rank, score=1 - rank / 10, retrieval_rank=rank, item=item)
        for rank, item in enumerate(items, start=1)
    ]


def test_old_code_above_new_code_counts_at_newer_target(repo: Path) -> None:
    items, snapshot, is_valid = setup(repo, "v2")
    old, new = items[("calculate_transfer_fee", "v1")], items[("calculate_transfer_fee", "v2")]
    location = location_key(new.chunk)

    score = score_location(
        ranking(old, new, items[("format_receipt", "v2")]),
        location,
        is_valid=is_valid,
        exists_at_target=location in locations_at(snapshot),
    )

    assert score.exists_at_target
    assert (score.valid_rank, score.wrong_rank) == (2, 1)
    assert score.wrong_version_above_valid
    assert not score.valid_at_1
    assert score.recall_at[1] is False and score.recall_at[3] is True
    assert score.reciprocal_rank == 0.5
    assert score.score_gap == pytest.approx(-0.1)
    assert score.wrong_share_at[1] == 1.0


def test_same_ranking_is_correct_at_older_target(repo: Path) -> None:
    items, snapshot, is_valid = setup(repo, "v1")
    old, new = items[("calculate_transfer_fee", "v1")], items[("calculate_transfer_fee", "v2")]
    location = location_key(old.chunk)

    score = score_location(
        ranking(old, new),
        location,
        is_valid=is_valid,
        exists_at_target=location in locations_at(snapshot),
    )

    assert (score.valid_rank, score.wrong_rank) == (1, 2)
    assert not score.wrong_version_above_valid
    assert score.valid_at_1
    assert score.reciprocal_rank == 1.0


def test_valid_chunk_missing_counts_as_wrong_version_above(repo: Path) -> None:
    items, snapshot, is_valid = setup(repo, "v2")
    old = items[("calculate_transfer_fee", "v1")]
    location = location_key(old.chunk)

    score = score_location(
        ranking(items[("format_receipt", "v2")], old),
        location,
        is_valid=is_valid,
        exists_at_target=location in locations_at(snapshot),
    )

    assert score.valid_rank is None
    assert score.wrong_version_above_valid
    assert score.recall_at[10] is False
    assert score.reciprocal_rank == 0.0


def test_removed_location_counts_only_when_it_ranks_first(repo: Path) -> None:
    items, snapshot, is_valid = setup(repo, "v2")
    removed = items[("validate_phone_number", "v1")]
    location = location_key(removed.chunk)
    exists = location in locations_at(snapshot)
    other = items[("normalize_phone_number", "v2")]

    first = score_location(ranking(removed, other), location, is_valid=is_valid, exists_at_target=exists)
    second = score_location(ranking(other, removed), location, is_valid=is_valid, exists_at_target=exists)

    assert not exists
    assert first.wrong_version_above_valid
    assert not second.wrong_version_above_valid


def test_summary_averages_recall_only_where_a_valid_chunk_exists(repo: Path) -> None:
    items, snapshot, is_valid = setup(repo, "v2")
    targets = locations_at(snapshot)
    old_fee, new_fee = items[("calculate_transfer_fee", "v1")], items[("calculate_transfer_fee", "v2")]
    removed = items[("validate_phone_number", "v1")]

    scores = [
        score_location(
            ranking(old_fee, new_fee),
            location_key(new_fee.chunk),
            is_valid=is_valid,
            exists_at_target=location_key(new_fee.chunk) in targets,
        ),
        score_location(
            ranking(removed, new_fee),
            location_key(removed.chunk),
            is_valid=is_valid,
            exists_at_target=location_key(removed.chunk) in targets,
        ),
    ]
    summary = summarize(scores)

    assert summary["cases"] == 2
    assert summary["cases_with_valid_chunk"] == 1
    assert summary["wrong_version_above_valid"] == 1.0
    assert summary["recall_at"][1] == 0.0
    assert summary["mean_reciprocal_rank"] == 0.5


def test_record_is_json_ready(repo: Path) -> None:
    items, _, is_valid = setup(repo, "v2")
    new = items[("calculate_transfer_fee", "v2")]

    record = score_record(
        score_location(
            ranking(new),
            location_key(new.chunk),
            is_valid=is_valid,
            exists_at_target=True,
        )
    )

    assert record["location"]["symbol"] == "calculate_transfer_fee"
    assert record["recall_at"]["1"] is True
    assert record["score_gap"] is None


def test_rejects_empty_ranking_and_bad_k(repo: Path) -> None:
    items, _, is_valid = setup(repo, "v2")
    new = items[("calculate_transfer_fee", "v2")]
    location = location_key(new.chunk)

    with pytest.raises(ValueError, match="ranking must not be empty"):
        score_location([], location, is_valid=is_valid, exists_at_target=True)
    with pytest.raises(ValueError, match="every k"):
        score_location(ranking(new), location, is_valid=is_valid, exists_at_target=True, ks=(0,))
