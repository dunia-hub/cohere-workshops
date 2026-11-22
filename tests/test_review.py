import json
from pathlib import Path

import pytest

from cohere_workshops import review_cli
from cohere_workshops.candidates import build_candidate_list, candidate_list_record
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.review import (
    ACCEPT,
    REJECT,
    CodeLookup,
    decide,
    load_list,
    next_replacement,
    pending,
    save_list,
    summary,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


@pytest.fixture
def listing(repo: Path, tmp_path: Path) -> Path:
    """Demo list with 3 included candidates, 2 sampled and 1 spare."""
    path = tmp_path / "candidates.json"
    record = candidate_list_record(build_candidate_list(repo, "v1", "v2", sample_size=2), None)
    save_list(path, record)
    return path


def answers(*values: str):
    queue = list(values)
    return lambda prompt: queue.pop(0)


def test_accept_records_the_reason(listing: Path) -> None:
    record = load_list(listing)
    first = pending(record)[0]

    assert decide(record, first, ACCEPT, "fee rule changed") is None
    assert first["review"] == {"decision": "accept", "reason": "fee rule changed"}
    assert summary(record)["accepted"] == 1


def test_reject_samples_the_next_candidate_in_order(listing: Path) -> None:
    record = load_list(listing)
    first = pending(record)[0]
    spare = next_replacement(record)

    replacement = decide(record, first, REJECT, "not_behavioural: import alias only")

    assert replacement is spare and replacement["sampled"] is True
    assert replacement["sample_order"] == 3
    assert first["review"]["replaced_by_order"] == 3
    assert next_replacement(record) is None
    assert [c["sample_order"] for c in pending(record)] == [2, 3]


def test_decide_rejects_bad_input(listing: Path) -> None:
    record = load_list(listing)
    first = pending(record)[0]
    unsampled = next_replacement(record)

    with pytest.raises(ValueError, match="reason is required"):
        decide(record, first, ACCEPT, "  ")
    with pytest.raises(ValueError, match="must start with one of"):
        decide(record, first, REJECT, "looks boring")
    with pytest.raises(ValueError, match="decision must be"):
        decide(record, first, "maybe", "x")
    with pytest.raises(ValueError, match="only sampled"):
        decide(record, unsampled, ACCEPT, "x")
    decide(record, first, ACCEPT, "x")
    with pytest.raises(ValueError, match="already has a decision"):
        decide(record, first, ACCEPT, "x")


def test_lookup_finds_exact_code_and_refuses_the_wrong_repository(
    listing: Path,
    tmp_path: Path,
) -> None:
    record = load_list(listing)
    candidate = pending(record)[0]
    lookup = CodeLookup(Path(listing).parent / "demo_repo")

    chunk = lookup.chunk(candidate["old"], candidate["path"])
    assert chunk.symbol == candidate["symbol"]

    other = create_demo_repository(tmp_path / "other")
    (other / "payments.py").write_text("def calculate_transfer_fee(a):\n    return 0\n")
    side = dict(candidate["old"], content_hash="0" * 64)
    with pytest.raises(ValueError, match="not found"):
        CodeLookup(other).chunk(side, candidate["path"])


def test_cli_review_saves_after_each_answer_and_replaces_rejections(
    listing: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    review_cli.review(
        listing,
        repo,
        read=answers("r", "1", "alias only", "a", "fee rule changed", "q"),
    )

    printed = capsys.readouterr().out
    record = json.loads(listing.read_text())
    decisions = {
        c["sample_order"]: c["review"]["decision"] for c in record["candidates"] if c["sampled"]
    }
    assert "Sampled replacement: order 3" in printed
    assert decisions == {1: "reject", 2: "accept", 3: None}
    rejected = next(c for c in record["candidates"] if c["sample_order"] == 1)
    assert rejected["review"]["reason"] == "not_behavioural: alias only"
    assert "1 accepted, 1 rejected, 1 pending, 0 spare" in printed


def test_cli_shows_removed_code_and_skips(
    repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "all.json"
    save_list(path, candidate_list_record(build_candidate_list(repo, "v1", "v2", sample_size=3), None))

    review_cli.review(path, repo, read=answers("s", "s", "s"))

    printed = capsys.readouterr().out
    assert "Removed in v2" in printed
    assert "def validate_phone_number" in printed
    assert "0 accepted, 0 rejected, 3 pending, 0 spare" in printed


def test_cli_ignores_unknown_answers_and_empty_reasons(
    listing: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    review_cli.review(listing, repo, read=answers("x", "a", "", "r", "9", "q"))

    printed = capsys.readouterr().out
    assert "Type a, r, s or q." in printed
    assert "A reason is required. Not recorded." in printed
    assert "Not recorded." in printed
    assert summary(load_list(listing))["pending"] == 2


def test_cli_summary_and_missing_repo(listing: Path, capsys: pytest.CaptureFixture[str]) -> None:
    review_cli.main([str(listing), "--summary"])
    assert "0 accepted, 0 rejected, 2 pending, 1 spare" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="--repo is required"):
        review_cli.main([str(listing)])
