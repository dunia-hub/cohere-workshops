import json
from pathlib import Path

import pytest

from cohere_workshops import agent_cli, rerank_cli
from cohere_workshops.demo_repo import create_demo_repository
from cohere_workshops.versions import resolve_commit


@pytest.fixture
def demo_repository(tmp_path: Path) -> Path:
    return create_demo_repository(tmp_path / "demo_repo")


def run(demo_repository: Path, tmp_path: Path, *extra: str) -> list[dict]:
    output = tmp_path / "trace.jsonl"
    agent_cli.main(
        [
            str(demo_repository),
            "--old", "v1",
            "--new", "v2",
            "--offline",
            "--output", str(output),
            *extra,
        ]
    )
    return [json.loads(line) for line in output.read_text().splitlines()]


def test_offline_run_prints_trace_and_saves_it(
    demo_repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    [record] = run(demo_repository, tmp_path)

    printed = capsys.readouterr().out
    assert "Command's plan: Practice mode: search once." in printed
    assert "Search 1:" in printed
    assert "REJECTED" in printed
    assert "Answer:" in printed
    assert record["models"]["command"] == "offline"
    assert record["target"]["commit"] == resolve_commit(demo_repository, "v2")
    assert record["references"]


def test_target_defaults_to_new_and_can_be_older(
    demo_repository: Path,
    tmp_path: Path,
) -> None:
    [record] = run(demo_repository, tmp_path, "--target", "v1")

    assert record["target"]["revision"] == "v1"
    sent = [
        c for call in record["tool_calls"] for c in call["candidates"] if c["sent_to_model"]
    ]
    assert all(c["valid_at_target"] for c in sent)
    assert "normalize_phone_number" not in {c["symbol"] for c in sent}


def test_live_mode_requires_api_key(
    demo_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.setattr(rerank_cli, "load_dotenv", lambda: None)

    with pytest.raises(RuntimeError, match="COHERE_API_KEY is missing"):
        agent_cli.main([str(demo_repository), "--old", "v1", "--new", "v2"])


def test_command_model_is_used_and_recorded(
    demo_repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingClient(agent_cli.OfflineAgentClient):
        def __init__(self) -> None:
            self.chat_models: list[object] = []

        def chat(self, **kwargs: object) -> object:
            self.chat_models.append(kwargs["model"])
            return super().chat(**kwargs)

    client = RecordingClient()
    monkeypatch.setattr(agent_cli, "create_client", lambda offline: client)
    output = tmp_path / "trace.jsonl"

    agent_cli.main(
        [
            str(demo_repository),
            "--old", "v1",
            "--new", "v2",
            "--command-model", "command-a-03-2025",
            "--output", str(output),
        ]
    )

    [record] = [json.loads(line) for line in output.read_text().splitlines()]
    assert client.chat_models
    assert set(client.chat_models) == {"command-a-03-2025"}
    assert record["models"]["command"] == "command-a-03-2025"


def test_no_git_filter_runs_the_ablation_and_records_it(
    demo_repository: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    [record] = run(demo_repository, tmp_path, "--no-git-filter")

    printed = capsys.readouterr().out
    assert "Git filter: off (ablation)" in printed
    assert "Citations not valid at target:" in printed
    assert record["git_filter"] is False
    sent = [
        c for call in record["tool_calls"] for c in call["candidates"] if c["sent_to_model"]
    ]
    assert any(not c["valid_at_target"] for c in sent)
