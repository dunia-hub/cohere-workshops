"""Command-line interface for reranking code across Git versions."""

import argparse
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from cohere_workshops.agent_tools import TargetValidator
from cohere_workshops.embeddings import EMBED_MODEL
from cohere_workshops.rerank_versions import (
    FORMATS,
    RankedCandidate,
    check_ranking,
    rerank_hits,
    retrieval_order,
    serialize_rerank_result,
    temporal_filter,
)
from cohere_workshops.reranking import RERANK_MODEL
from cohere_workshops.version_cli import DEMO_QUERIES, OFFLINE_MODEL, OfflineEmbedClient
from cohere_workshops.version_search import LEVELS, append_records, search_versions
from cohere_workshops.versions import (
    VersionedChunk,
    build_versioned_corpus,
    load_revision,
)

OFFLINE_RERANK_MODEL = "offline-word-overlap"


class OfflineClient(OfflineEmbedClient):
    """Practice mode: word counting for Embed and Rerank. Not real results."""

    def rerank(self, **kwargs: object) -> object:
        query_words = set(re.findall(r"[a-z0-9]+", str(kwargs["query"]).lower()))
        documents = kwargs["documents"]
        assert isinstance(documents, list)
        scored = []

        for index, text in enumerate(documents):
            words = set(re.findall(r"[a-z0-9]+", text.lower()))
            score = len(query_words & words) / max(len(query_words), 1)
            scored.append(SimpleNamespace(index=index, relevance_score=score))

        scored.sort(key=lambda r: (-r.relevance_score, r.index))
        return SimpleNamespace(results=scored)


def build_parser() -> argparse.ArgumentParser:
    """Create the rerank command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve code from two Git revisions with Cohere Embed, reorder it "
            "with Cohere Rerank and check the order against Git."
        )
    )
    parser.add_argument("repository", help="Local Git repository.")
    parser.add_argument("--old", required=True, help="Older revision, e.g. v1.")
    parser.add_argument("--new", required=True, help="Current revision, e.g. v2.")
    parser.add_argument(
        "--target",
        help="Commit the code must be valid at. Defaults to --new.",
    )
    parser.add_argument(
        "--query",
        action="append",
        help="Question to search for. Repeat for several. Defaults to demo questions.",
    )
    parser.add_argument(
        "--format",
        choices=(*FORMATS, "both"),
        default="code",
        help="What Rerank reads: code only, code plus Git metadata, or both.",
    )
    parser.add_argument("--candidates", type=int, default=10, help="How many Embed results to rerank.")
    parser.add_argument("--k", type=int, default=3, help="How many top results to check.")
    parser.add_argument("--level", choices=LEVELS, default="symbol")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Practice without an API key. Not semantic search.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/rerank-runs.jsonl"),
        help="JSON Lines file that results are appended to.",
    )
    return parser


def create_client(offline: bool) -> object:
    if offline:
        return OfflineClient()

    import cohere

    load_dotenv()
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is missing from .env")
    return cohere.ClientV2(api_key=api_key, log_warning_experimental_features=False)


def commit_dates(repository: Path, commits: Sequence[str]) -> dict[str, str]:
    """Read each commit's date from Git."""
    dates = {}
    for commit in commits:
        completed = subprocess.run(
            ["git", "-C", str(repository), "log", "-1", "--format=%cs", commit],
            capture_output=True,
            text=True,
            check=True,
        )
        dates[commit] = completed.stdout.strip()
    return dates


def _location(candidate: RankedCandidate) -> str:
    chunk = candidate.item.chunk
    return f"{chunk.path}::{chunk.symbol or '<file>'}"


def print_ranking(
    title: str,
    ranking: Sequence[RankedCandidate],
    rows: int,
    is_valid: Callable[[VersionedChunk], bool],
) -> None:
    print(f"\n{title}")
    print(f"{'Rank':<5} {'Score':<7} {'Was':<4} {'Version':<11} {'Valid':<6} Location")
    for c in ranking[:rows]:
        valid = "yes" if is_valid(c.item) else "NO"
        print(
            f"{c.rank:<5} {c.score:<7.4f} {c.retrieval_rank:<4} "
            f"{c.item.status:<11} {valid:<6} {_location(c)}"
        )


def _yes(value: bool) -> str:
    return "YES" if value else "no"


def main(arguments: Sequence[str] | None = None) -> None:
    """Retrieve, rerank, check against Git, filter and record."""
    options = build_parser().parse_args(arguments)
    if options.candidates < 1 or options.k < 1:
        raise ValueError("--candidates and --k must be at least 1")

    queries = tuple(options.query or DEMO_QUERIES)
    styles = FORMATS if options.format == "both" else (options.format,)
    embed_model = OFFLINE_MODEL if options.offline else EMBED_MODEL
    rerank_model = OFFLINE_RERANK_MODEL if options.offline else RERANK_MODEL
    client = create_client(options.offline)
    repository = Path(options.repository)

    corpus = build_versioned_corpus(repository, options.old, options.new)
    dates = commit_dates(repository, (corpus.previous.commit, corpus.current.commit))
    print(
        f"{corpus.previous.revision} ({dates[corpus.previous.commit]}) -> "
        f"{corpus.current.revision} ({dates[corpus.current.commit]})"
    )
    validator = TargetValidator(load_revision(repository, options.target or options.new))

    def is_valid(item: VersionedChunk) -> bool:
        return validator.is_valid(item.chunk)

    print(f"Target: {validator.revision} ({validator.commit[:7]})")

    results = search_versions(
        client,
        corpus,
        queries,
        level=options.level,
        top_k=options.candidates,
    )
    if not results:
        print("No chunks to search at this level.")
        return

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    records = []
    rows = max(options.k, 5)

    for result in results:
        print(f"\n=== Query: {result.query}")
        before = retrieval_order(result.hits)
        print_ranking("Embed order (before Rerank)", before, rows, is_valid)
        before_check = check_ranking(before, k=options.k, is_valid=is_valid)

        for style in styles:
            after = rerank_hits(
                client,
                result.query,
                result.hits,
                style=style,
                commit_dates=dates,
                model=RERANK_MODEL,
            )
            after_check = check_ranking(after, k=options.k, is_valid=is_valid)
            filtered = temporal_filter(after, is_valid)

            print_ranking(f"Rerank order (format: {style})", after, rows, is_valid)
            print(
                "Wrong-version code above valid code: "
                f"Embed {_yes(before_check.stale_above_current)}"
                f" -> Rerank {_yes(after_check.stale_above_current)}"
            )
            print(
                f"Valid code in top {options.k}: {_yes(after_check.current_in_top_k)}"
                f" | Wrong-version share of top {options.k}: {after_check.stale_rate_at_k:.0%}"
            )
            if filtered:
                print(f"After the Git filter, top result: {_location(filtered[0])}")
            else:
                print("After the Git filter, nothing valid is left.")

            records.append(
                serialize_rerank_result(
                    run_id=run_id,
                    query=result.query,
                    style=style,
                    k=options.k,
                    embed_model=embed_model,
                    rerank_model=rerank_model,
                    previous=(corpus.previous.revision, corpus.previous.commit),
                    current=(corpus.current.revision, corpus.current.commit),
                    retrieval=before,
                    reranked=after,
                    target=(validator.revision, validator.commit),
                    is_valid=is_valid,
                )
            )

    append_records(options.output, records)
    print(f"\nSaved {len(records)} records to {options.output}")


if __name__ == "__main__":
    main()
