"""Command-line interface for listing evaluation candidates between two revisions."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from cohere_workshops.candidates import (
    DEFAULT_SAMPLE,
    DEFAULT_SEED,
    build_candidate_list,
    candidate_list_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "List code locations that were superseded or removed between two "
            "revisions, apply the evaluation-plan filters and sample with a seed. "
            "No Cohere calls."
        )
    )
    parser.add_argument("repository", help="Local Git repository.")
    parser.add_argument("--old", required=True, help="Older revision, e.g. a release tag.")
    parser.add_argument("--new", required=True, help="Newer revision, e.g. the next release tag.")
    parser.add_argument(
        "--sample",
        type=int,
        default=DEFAULT_SAMPLE,
        help=f"Locations to sample from the included candidates. Default: {DEFAULT_SAMPLE}.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for sampling, recorded in the output. Default: {DEFAULT_SEED}.",
    )
    parser.add_argument("--repository-url", help="Public URL of the repository, recorded.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSON file to write. Refuses to overwrite an existing file.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> None:
    options = build_parser().parse_args(arguments)
    if options.output.exists():
        raise SystemExit(f"{options.output} already exists. Choose a new file name.")

    result = build_candidate_list(
        Path(options.repository),
        options.old,
        options.new,
        sample_size=options.sample,
        seed=options.seed,
    )
    record = candidate_list_record(result, options.repository_url)
    counts = record["counts"]

    print(
        f"{record['old']['revision']} ({record['old']['commit'][:7]}) -> "
        f"{record['new']['revision']} ({record['new']['commit'][:7]})"
    )
    print(
        f"Changed symbol locations: {counts['candidates']} | "
        f"included: {counts['included']} | sampled: {counts['sampled']} (seed {options.seed})"
    )
    for reason, count in counts["excluded_by_reason"].items():
        print(f"  excluded, {reason}: {count}")

    sampled = [c for c in record["candidates"] if c["sampled"]]
    if sampled:
        print(f"\n{'Order':<6} {'Status':<11} {'Lines':<6} Location")
        for c in sorted(sampled, key=lambda c: c["sample_order"]):
            print(
                f"{c['sample_order']:<6} {c['status']:<11} {c['lines_changed']:<6} "
                f"{c['path']}::{c['symbol']}"
            )
        print("\nReview each sampled candidate and record the decision in its 'review' field.")

    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved to {options.output}")


if __name__ == "__main__":
    main()
