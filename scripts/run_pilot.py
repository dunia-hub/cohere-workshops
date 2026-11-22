"""Run the pilot study and analyse it.

Stages:
    run      embed each repository once, then run retrieval (configurations 2-5,
             --runs times) and answering (configurations 7 and 8) for its cases.
             Writes one file per repository and skips repositories already done.
    analyze  summarise retrieval with confidence intervals and paired tests.
    sheet    write the blind scoring sheet for the answers, and its key.

Usage:
    python scripts/run_pilot.py run --repos ~/eval-repos           # live, spends credits
    python scripts/run_pilot.py run --repos ~/eval-repos --offline # practice, temp folder
    python scripts/run_pilot.py analyze
    python scripts/run_pilot.py sheet
"""

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from cohere_workshops.agent_cli import OfflineAgentClient
from cohere_workshops.embeddings import EMBED_MODEL
from cohere_workshops.pilot import (
    RepositoryIndex,
    answering_records,
    cases_by_repository,
    load_manifest,
    retrieval_records,
    scoring_sheet,
    summarize_retrieval,
)
from cohere_workshops.rerank_cli import create_client
from cohere_workshops.reranking import RERANK_MODEL

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "experiments" / "dataset" / "pilot" / "cases.json"
RESULTS = ROOT / "experiments" / "pilot"
COMMAND_MODEL = "command-a-03-2025"


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments], capture_output=True, text=True, check=True
    ).stdout.strip()


def write_jsonl(path: Path, records: list[dict]) -> None:
    temporary = path.with_suffix(".partial")
    temporary.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    temporary.replace(path)


def read_jsonl(paths: list[Path]) -> list[dict]:
    return [json.loads(line) for p in paths for line in p.read_text(encoding="utf-8").splitlines()]


def run(options: argparse.Namespace) -> None:
    if not options.offline and git("status", "--porcelain"):
        raise SystemExit("Commit your changes first, so the run is tied to an exact app commit.")
    out = Path(tempfile.mkdtemp(prefix="pilot-practice-")) if options.offline else RESULTS
    out.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(MANIFEST)
    client = OfflineAgentClient() if options.offline else create_client(False)
    metadata_path = out / "metadata.json"
    metadata = {
        "status": "practice" if options.offline else "pilot",
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "application_commit": git("rev-parse", "HEAD"),
        "python_version": platform.python_version(),
        "cohere_sdk_version": version("cohere"),
        "models": (
            {"embed": "offline", "rerank": "offline", "command": "offline"}
            if options.offline
            else {"embed": EMBED_MODEL, "rerank": RERANK_MODEL, "command": COMMAND_MODEL}
        ),
        "runs": options.runs,
        "candidates": 10,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "repositories": {},
    }
    if metadata_path.exists():
        metadata["repositories"] = json.loads(metadata_path.read_text())["repositories"]

    for repository, cases in sorted(cases_by_repository(manifest).items()):
        retrieval_file = out / f"retrieval-{repository}.jsonl"
        answering_file = out / f"answering-{repository}.jsonl"
        answering_cases = [c for c in cases if c["answer_key"]]
        if retrieval_file.exists() and (answering_file.exists() or not answering_cases):
            print(f"{repository}: already done, skipped")
            continue

        started = time.perf_counter()
        print(f"{repository}: embedding the two-release index...", flush=True)
        index = RepositoryIndex(client, Path(options.repos).expanduser() / repository, cases)

        if not retrieval_file.exists():
            records = []
            for run_number in range(1, options.runs + 1):
                for case in cases:
                    records.extend(retrieval_records(index, case, run_number))
            write_jsonl(retrieval_file, records)
            print(f"{repository}: retrieval, {len(cases)} cases x {options.runs} runs")

        if answering_cases and not answering_file.exists():
            answers = []
            for case in answering_cases:
                answers.extend(answering_records(index, case, command_model=COMMAND_MODEL))
            write_jsonl(answering_file, answers)
            print(f"{repository}: answering, {len(answering_cases)} cases")

        metadata["repositories"][repository] = {
            "old": cases[0]["old"],
            "new": cases[0]["new"],
            "indexed_chunks": len(index.items),
            "cases": len(cases),
            "answering_cases": len(answering_cases),
            "seconds": round(time.perf_counter() - started, 1),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"Done. Results in {out}")


def analyze(options: argparse.Namespace) -> None:
    folder = Path(options.results)
    summary = summarize_retrieval(read_jsonl(sorted(folder.glob("retrieval-*.jsonl"))))
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"{'Configuration':<26} {'Wrong-version above valid':<30} {'Recall@1':<22} Cases")
    for name, metrics in summary["configs"].items():
        wv, r1 = metrics["wrong_version_above_valid"], metrics.get("recall_at_1")
        r1_text = f"{r1['mean']:.2f} [{r1['ci95'][0]:.2f}, {r1['ci95'][1]:.2f}]" if r1 else "-"
        print(
            f"{name:<26} {wv['mean']:.2f} [{wv['ci95'][0]:.2f}, {wv['ci95'][1]:.2f}]"
            f"{'':<14} {r1_text:<22} {wv['cases']}"
        )
    for name, test in summary["tests"].items():
        print(
            f"{name}: only first {test['only_first']}, only second {test['only_second']}, "
            f"p = {test['p_value']:.4f}, Holm p = {test['p_holm']:.4f}"
        )
    print(f"\nSaved {folder / 'summary.json'}")


def sheet(options: argparse.Namespace) -> None:
    folder = Path(options.results)
    answers = read_jsonl(sorted(folder.glob("answering-*.jsonl")))
    rows, key = scoring_sheet(answers, load_manifest(MANIFEST))
    (folder / "scoring-sheet.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    (folder / "scoring-key.json").write_text(json.dumps(key, indent=2) + "\n")
    print(f"{len(rows)} answers. Score scoring-sheet.json without opening scoring-key.json.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stages = parser.add_subparsers(dest="stage", required=True)

    run_parser = stages.add_parser("run")
    run_parser.add_argument("--repos", required=True, help="Folder holding the six clones.")
    run_parser.add_argument("--runs", type=int, default=3)
    run_parser.add_argument("--offline", action="store_true", help="Practice, no Cohere calls.")
    run_parser.set_defaults(func=run)

    for name, func in (("analyze", analyze), ("sheet", sheet)):
        stage = stages.add_parser(name)
        stage.add_argument("--results", default=str(RESULTS))
        stage.set_defaults(func=func)

    options = parser.parse_args()
    options.func(options)


if __name__ == "__main__":
    sys.exit(main())
