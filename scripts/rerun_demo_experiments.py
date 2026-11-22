"""Rerun the README's exploratory experiments on the demo repository and record them.

Runs three stages on demo_repo (v1 -> v2):
  1. cohere-versions  (Embed)
  2. cohere-rerank    (Rerank, code and metadata formats)
  3. cohere-agent     (Command, every answer-key question at targets v2 and v1)

Each stage writes one folder under experiments/exploratory/ containing
raw-output.jsonl, console.txt and metadata.json. Records never contain API keys.

With --no-git-filter, only the agent stage runs, without the Git filter
(configuration 7, the ablation), and writes exp-<date>-demo-agent-nofilter.

Usage:
    python scripts/rerun_demo_experiments.py                  # live, spends Cohere credits
    python scripts/rerun_demo_experiments.py --offline        # practice, writes to a temp folder
    python scripts/rerun_demo_experiments.py --no-git-filter  # live ablation, agent stage only
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo_repo"
ANSWER_KEY = ROOT / "experiments" / "answer-keys" / "demo-repo-agent.json"
TARGETS = ("v2", "v1")
# Command A+ is capped at 1,000 calls a month even on production keys, so the
# rerun defaults to Command A. Pass --command-model to change it.
DEFAULT_COMMAND_MODEL = "command-a-03-2025"


def git(repository: Path, *arguments: str) -> str:
    """Run a read-only Git command and return its output."""
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def application_state() -> dict[str, object]:
    """Commit and cleanliness of this repository, so the run can be traced to code."""
    status = git(ROOT, "status", "--porcelain")
    return {
        "application_commit": git(ROOT, "rev-parse", "HEAD"),
        "working_tree_clean": status == "",
    }


def demo_state() -> dict[str, object]:
    """Commits and tree hashes of the demo tags. Tree hashes are identical on every machine."""
    return {
        tag: {
            "commit": git(DEMO, "rev-parse", f"{tag}^{{commit}}"),
            "tree": git(DEMO, "rev-parse", f"{tag}^{{tree}}"),
        }
        for tag in ("v1", "v2")
    }


def run_stage(command: list[str], console: Path) -> float:
    """Run one CLI command, append its console output, return seconds taken."""
    started = time.perf_counter()
    completed = subprocess.run(command, check=False, cwd=ROOT, capture_output=True, text=True)
    seconds = round(time.perf_counter() - started, 3)

    with console.open("a", encoding="utf-8") as file:
        file.write(f"$ {' '.join(command)}\n")
        file.write(completed.stdout)
        if completed.stderr:
            file.write("\n[stderr]\n" + completed.stderr)
        file.write(f"\n[exit code {completed.returncode}, {seconds} s]\n\n")

    if completed.returncode != 0:
        raise SystemExit(f"Stage failed: {' '.join(command)}\nSee {console}")
    return seconds


def write_metadata(folder: Path, metadata: dict[str, object]) -> None:
    (folder / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="Practice run, no Cohere calls.")
    parser.add_argument(
        "--command-model",
        default=DEFAULT_COMMAND_MODEL,
        help=f"Command model for the agent stage. Default: {DEFAULT_COMMAND_MODEL}.",
    )
    parser.add_argument(
        "--no-git-filter",
        action="store_true",
        help="Run only the agent stage, without the Git filter (ablation).",
    )
    options = parser.parse_args()
    git_filter = not options.no_git_filter

    if not DEMO.exists():
        raise SystemExit("demo_repo is missing. Run: cohere-demo-repo")
    if not ANSWER_KEY.exists():
        raise SystemExit(f"Answer key is missing: {ANSWER_KEY}")

    app = application_state()
    if not options.offline and not app["working_tree_clean"]:
        raise SystemExit("Commit your changes first, so the run is tied to an exact app commit.")

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    base = (
        Path(tempfile.mkdtemp(prefix="practice-"))
        if options.offline
        else ROOT / "experiments" / "exploratory"
    )
    offline_flag = ["--offline"] if options.offline else []
    key = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))

    common = {
        "status": "practice" if options.offline else "exploratory",
        "date": today,
        "researcher": "Fatuma Yattani",
        **app,
        "python_version": platform.python_version(),
        "cohere_sdk_version": version("cohere"),
        "repository": "demo_repo (created by cohere-demo-repo)",
        "revisions": {"old": "v1", "new": "v2"},
        "demo_tags": demo_state(),
        "api_usage": "not_recorded",
        "final_evaluation_eligible": False,
        "notes": (
            [
                "Rerun of the exploratory findings stated in README.md.",
                "The original runs behind those findings were not preserved in the repository.",
            ]
            if git_filter
            else [
                "Ablation: agent without the Git filter (configuration 7).",
                "Candidates are sent whether or not they are valid at the target.",
                "Each candidate is labelled with the revisions it exists in.",
            ]
        ),
    }
    models = (
        {"embed": "offline-word-hashing", "rerank": "offline-word-overlap", "command": "offline"}
        if options.offline
        else {"embed": "embed-v4.0", "rerank": "rerank-v4.0-pro", "command": options.command_model}
    )

    stages = []

    if git_filter:
        # 1. Embed
        folder = base / f"exp-{today}-demo-embed"
        folder.mkdir(parents=True, exist_ok=False)
        command = ["cohere-versions", str(DEMO), "--old", "v1", "--new", "v2",
                   "--output", str(folder / "raw-output.jsonl"), *offline_flag]
        seconds = run_stage(command, folder / "console.txt")
        write_metadata(folder, {**common, "experiment_id": folder.name, "stage": "embed",
                                "models": {"embed": models["embed"]}, "command": command,
                                "settings": {"level": "symbol", "top_k": 5},
                                "latency_seconds": {"total": seconds}})
        stages.append(folder)

        # 2. Rerank
        folder = base / f"exp-{today}-demo-rerank"
        folder.mkdir(parents=True, exist_ok=False)
        command = ["cohere-rerank", str(DEMO), "--old", "v1", "--new", "v2", "--format", "both",
                   "--output", str(folder / "raw-output.jsonl"), *offline_flag]
        seconds = run_stage(command, folder / "console.txt")
        write_metadata(folder, {**common, "experiment_id": folder.name, "stage": "rerank",
                                "models": {"embed": models["embed"], "rerank": models["rerank"]},
                                "command": command,
                                "settings": {"level": "symbol", "candidates": 10, "k": 3,
                                             "formats": ["code", "metadata"]},
                                "latency_seconds": {"total": seconds}})
        stages.append(folder)

    # 3. Agent
    suffix = "" if git_filter else "-nofilter"
    folder = base / f"exp-{today}-demo-agent{suffix}"
    folder.mkdir(parents=True, exist_ok=False)
    filter_flag = [] if git_filter else ["--no-git-filter"]
    commands, latency = [], {}
    for item in key["questions"]:
        for target in TARGETS:
            command = ["cohere-agent", str(DEMO), "--old", "v1", "--new", "v2",
                       "--target", target, "--question", item["question"],
                       "--command-model", options.command_model, *filter_flag,
                       "--output", str(folder / "raw-output.jsonl"), *offline_flag]
            latency[f"{item['id']}@{target}"] = run_stage(command, folder / "console.txt")
            commands.append(command)
    shutil.copy(ANSWER_KEY, folder / "answer-key.json")
    write_metadata(folder, {**common, "experiment_id": folder.name, "stage": "agent",
                            "models": models, "commands": commands,
                            "settings": {"candidates": 10, "keep": 4, "max_tool_calls": 3,
                                         "temperature": 0, "git_filter": git_filter},
                            "answer_key": str(ANSWER_KEY.relative_to(ROOT)),
                            "answer_key_id": key["answer_key_id"],
                            "scoring": "not_yet_scored",
                            "latency_seconds": latency})
    stages.append(folder)

    print("Done. Records written to:")
    for stage in stages:
        print(f"  {stage}")


if __name__ == "__main__":
    sys.exit(main())
