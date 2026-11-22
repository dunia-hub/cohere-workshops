import json
from pathlib import Path

import pytest

from cohere_workshops.agent_cli import OfflineAgentClient
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.pilot import (
    RETRIEVAL_CONFIGS,
    RepositoryIndex,
    answering_records,
    cases_by_repository,
    clustered_bootstrap,
    holm,
    mcnemar_exact,
    retrieval_records,
    scoring_sheet,
    summarize_retrieval,
)
from cohere_workshops.versions import resolve_commit


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo")


def case(repo: Path, symbol: str, status: str, answer_key=None) -> dict:
    return {
        "case_id": f"demo-{symbol}",
        "repository": "demo",
        "old": {"revision": "v1", "commit": resolve_commit(repo, "v1")},
        "new": {"revision": "v2", "commit": resolve_commit(repo, "v2")},
        "location": {"path": "payments.py", "kind": "function", "symbol": symbol, "part_index": 1},
        "status": status,
        "query": "How is the transfer fee calculated?",
        "answer_key": answer_key,
    }


def test_retrieval_scores_every_configuration_at_both_targets(repo: Path) -> None:
    fee = case(repo, "calculate_transfer_fee", "superseded")
    index = RepositoryIndex(OfflineAgentClient(), repo, [fee])

    records = retrieval_records(index, fee, run=1)

    assert {(r["target"], r["config"]) for r in records} == {
        (t, c) for t in ("old", "new") for c in RETRIEVAL_CONFIGS
    }
    filtered = [r for r in records if r["config"] == "git_filter" and not r["empty"]]
    assert all(not r["wrong_version_above_valid"] for r in filtered)
    assert all(t["valid_at_target"] for r in filtered for t in r["top"])


def test_removed_location_does_not_exist_at_the_newer_target(repo: Path) -> None:
    gone = case(repo, "validate_phone_number", "removed")
    index = RepositoryIndex(OfflineAgentClient(), repo, [gone])

    records = retrieval_records(index, gone, run=1)

    assert {r["target"]: r["exists_at_target"] for r in records} == {"old": True, "new": False}


def test_index_refuses_a_wrong_commit(repo: Path) -> None:
    fee = case(repo, "calculate_transfer_fee", "superseded")
    fee["new"]["commit"] = "0" * 40

    with pytest.raises(ValueError, match="manifest says"):
        RepositoryIndex(OfflineAgentClient(), repo, [fee])


def test_answering_runs_both_configurations_at_both_targets(repo: Path) -> None:
    key = {"old": ["flat 2 percent"], "new": ["tiered"]}
    fee = case(repo, "calculate_transfer_fee", "superseded", key)
    index = RepositoryIndex(OfflineAgentClient(), repo, [fee])

    records = answering_records(index, fee, command_model="offline")

    assert sorted(r["run_id"] for r in records) == sorted(
        f"demo-calculate_transfer_fee-{t}-{m}" for t in ("old", "new") for m in ("filter", "nofilter")
    )
    assert {r["git_filter"] for r in records} == {True, False}


def test_scoring_sheet_hides_the_configuration(repo: Path) -> None:
    key = {"old": ["flat 2 percent"], "new": ["tiered"]}
    fee = case(repo, "calculate_transfer_fee", "superseded", key)
    index = RepositoryIndex(OfflineAgentClient(), repo, [fee])
    answers = answering_records(index, fee, command_model="offline")

    rows, mapping = scoring_sheet(answers, {"cases": [fee]})

    text = json.dumps(rows)
    assert "filter" not in text and "nofilter" not in text
    assert sorted(mapping) == [1, 2, 3, 4]
    assert {r["target_release"] for r in rows} == {"v1", "v2"}
    assert all(r["outcome"] is None for r in rows)


def test_summary_has_intervals_and_paired_tests(repo: Path) -> None:
    fee = case(repo, "calculate_transfer_fee", "superseded")
    index = RepositoryIndex(OfflineAgentClient(), repo, [fee])
    records = retrieval_records(index, fee, run=1) + retrieval_records(index, fee, run=2)

    summary = summarize_retrieval(records)

    assert set(summary["configs"]) == {f"{c}@{t}" for c in RETRIEVAL_CONFIGS for t in ("old", "new")}
    entry = summary["configs"]["embed@new"]["wrong_version_above_valid"]
    assert entry["cases"] == 1
    assert entry["ci95"][0] <= entry["mean"] <= entry["ci95"][1]
    assert set(summary["tests"]) == {"H2 embed vs rerank_code", "H3 rerank_code vs rerank_metadata"}


def test_statistics_helpers() -> None:
    assert mcnemar_exact([True] * 6 + [False] * 4, [False] * 6 + [False] * 4) == {
        "only_first": 6, "only_second": 0, "p_value": pytest.approx(0.03125)
    }
    assert mcnemar_exact([True], [True])["p_value"] == 1.0
    assert holm({"a": 0.01, "b": 0.04}) == {"a": 0.02, "b": 0.04}
    low, high = clustered_bootstrap({"r1": {"a": 1.0, "b": 0.0}, "r2": {"c": 1.0}})
    assert 0.0 <= low <= high <= 1.0


def test_cases_group_by_repository(repo: Path) -> None:
    a = case(repo, "calculate_transfer_fee", "superseded")
    groups = cases_by_repository({"cases": [a, dict(a, repository="other")]})
    assert sorted(groups) == ["demo", "other"]
