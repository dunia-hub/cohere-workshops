"""Command-line interface for the read-only, version aware code agent."""

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from cohere_workshops.agent import agent_record, run_agent
from cohere_workshops.agent_tools import CodeSearchTool, TargetValidator
from cohere_workshops.embeddings import EMBED_MODEL
from cohere_workshops.prediction import COMMAND_MODEL
from cohere_workshops.rerank_cli import OfflineClient, commit_dates, create_client
from cohere_workshops.reranking import RERANK_MODEL
from cohere_workshops.version_search import append_records
from cohere_workshops.versions import build_versioned_corpus, load_revision

DEMO_QUESTION = "How is the transfer fee calculated?"


class OfflineAgentClient(OfflineClient):
    """Practice mode: fake Command that searches once and quotes the evidence."""

    def chat(self, **kwargs: object) -> object:
        messages = kwargs["messages"]
        assert isinstance(messages, list)

        if "response_format" in kwargs:
            schema = kwargs["response_format"]["schema"]
            ids = schema["properties"]["evidence_ids"]["items"]["enum"]
            payload = {
                "answer": "Practice mode: no real answer. See the cited evidence.",
                "declined": False,
                "decline_reason": "",
                "evidence_ids": ids[:1],
            }
            text = SimpleNamespace(text=json.dumps(payload))
            return SimpleNamespace(message=SimpleNamespace(content=[text]))

        searched = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
        if not searched:
            question = messages[-1]["content"]
            call = SimpleNamespace(
                id="offline-1",
                function=SimpleNamespace(
                    name="search_code", arguments=json.dumps({"query": question})
                ),
            )
            return SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[call], tool_plan="Practice mode: search once.", content=[]
                )
            )
        return SimpleNamespace(
            message=SimpleNamespace(tool_calls=None, content=[SimpleNamespace(text="Done.")])
        )


def build_parser() -> argparse.ArgumentParser:
    """Create the agent command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Ask a question about a repository at a target commit. Cohere Command "
            "calls a read-only search tool; Git decides which code is valid."
        )
    )
    parser.add_argument("repository", help="Local Git repository.")
    parser.add_argument("--old", required=True, help="Older revision to search, e.g. v1.")
    parser.add_argument("--new", required=True, help="Newer revision to search, e.g. v2.")
    parser.add_argument(
        "--target",
        help="Commit the answer must be valid at. Defaults to --new.",
    )
    parser.add_argument("--question", default=DEMO_QUESTION)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--keep", type=int, default=4, help="Most evidence sent per search.")
    parser.add_argument("--max-tool-calls", type=int, default=3)
    parser.add_argument(
        "--command-model",
        default=COMMAND_MODEL,
        help=f"Cohere Command model for tool planning and answers. Default: {COMMAND_MODEL}.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Practice without an API key. Not real answers.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/agent-runs.jsonl"),
        help="JSON Lines file that traces are appended to.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> None:
    """Run the agent once, print the trace and save it."""
    options = build_parser().parse_args(arguments)
    repository = Path(options.repository)
    target = options.target or options.new

    client = OfflineAgentClient() if options.offline else create_client(False)
    models = (
        {"embed": "offline", "rerank": "offline", "command": "offline"}
        if options.offline
        else {"embed": EMBED_MODEL, "rerank": RERANK_MODEL, "command": options.command_model}
    )

    corpus = build_versioned_corpus(repository, options.old, options.new)
    validator = TargetValidator(load_revision(repository, target))
    date = commit_dates(repository, [validator.commit])[validator.commit]
    print(f"Question: {options.question}")
    print(f"Target: {validator.revision} ({validator.commit[:7]}, {date})")

    tool = CodeSearchTool(
        client, corpus, validator, candidates=options.candidates, keep=options.keep
    )
    result = run_agent(
        client,
        tool,
        options.question,
        model=options.command_model,
        max_tool_calls=options.max_tool_calls,
    )

    for plan in result.tool_plans:
        print(f"\nCommand's plan: {plan}")
    if result.forced_search:
        print("\nCommand did not call the tool, so the app searched anyway.")

    for number, call in enumerate(tool.calls, start=1):
        print(f'\nSearch {number}: "{call.query}"')
        print(f"{'Rank':<5} {'Score':<7} {'Git check':<10} {'Found in':<9} Location")
        for d in call.decisions[:6]:
            check = "valid" if d.valid else "REJECTED"
            location = f"{d.item.chunk.path}::{d.item.chunk.symbol}"
            print(f"{d.rank:<5} {d.rerank_score:<7.4f} {check:<10} {d.item.revision:<9} {location}")

    print()
    if result.declined:
        print(f"Declined: {result.decline_reason}")
    else:
        print(f"Answer: {result.answer}")
        for ref in result.references:
            print(
                f"  - {ref['path']}::{ref['symbol']} lines {ref['lines']}"
                f" @ {str(ref['valid_at_commit'])[:7]}"
            )
    print(f"Stale references in answer: {', '.join(result.stale) or 'none'}")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    append_records(options.output, [agent_record(result, tool, run_id=run_id, models=models)])
    print(f"\nSaved trace to {options.output}")


if __name__ == "__main__":
    main()
