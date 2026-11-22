import json
from pathlib import Path

import pytest

from cohere_workshops import rerank_cli
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.versions import resolve_commit


@pytest.fixture
def demo_repository(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


def test_reads_commit_dates_from_git(demo_repository: Path) -> None:
    commit = resolve_commit(demo_repository, "v2")

    dates = rerank_cli.commit_dates(demo_repository, [commit])

    assert len(dates[commit]) == 10
    assert dates[commit][4] == "-"


def test_offline_run_prints_and_records_both_formats(
    demo_repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "runs.jsonl"

    rerank_cli.main(
        [
            str(demo_repository),
            "--old", "v1",
            "--new", "v2",
            "--offline",
            "--format", "both",
            "--output", str(output),
        ]
    )

    printed = capsys.readouterr().out
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert "Embed order (before Rerank)" in printed
    assert "Rerank order (format: metadata)" in printed
    assert "After the Git filter, top result:" in printed
    assert len(records) == len(rerank_cli.DEMO_QUERIES) * 2
    assert {r["format"] for r in records} == {"code", "metadata"}
    assert all(r["rerank_model"] == "offline-word-overlap" for r in records)
    assert all(r["filtered_top"][0]["status"] == "current" for r in records)


def test_candidates_limit_what_gets_reranked(
    demo_repository: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "runs.jsonl"

    rerank_cli.main(
        [
            str(demo_repository),
            "--old", "v1",
            "--new", "v2",
            "--offline",
            "--query", "transfer fee",
            "--candidates", "3",
            "--output", str(output),
        ]
    )

    [record] = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(record["reranked"]) == 3
    assert sorted(c["retrieval_rank"] for c in record["reranked"]) == [1, 2, 3]


def test_live_mode_requires_api_key(
    demo_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.setattr(rerank_cli, "load_dotenv", lambda: None)

    with pytest.raises(RuntimeError, match="COHERE_API_KEY is missing"):
        rerank_cli.main([str(demo_repository), "--old", "v1", "--new", "v2"])


def test_target_option_checks_against_the_older_commit(
    demo_repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "runs.jsonl"

    rerank_cli.main(
        [
            str(demo_repository),
            "--old", "v1",
            "--new", "v2",
            "--target", "v1",
            "--offline",
            "--output", str(output),
        ]
    )

    printed = capsys.readouterr().out
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert "Target: v1" in printed
    assert all(r["target"]["revision"] == "v1" for r in records)
    assert all(r["filtered_top"][0]["valid_at_target"] for r in records)
    assert all(
        r["filtered_top"][0]["symbol"] != "normalize_phone_number" for r in records
    )
