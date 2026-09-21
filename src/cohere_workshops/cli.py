"""Command-line interface for the repository mapper."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from cohere_workshops.mapper import map_repository


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Build a structural map of a source-code repository."
    )
    parser.add_argument(
        "repository",
        nargs="?",
        default=".",
        help="Repository directory to map. Defaults to the current directory.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> None:
    """Map a repository and print the result as JSON."""
    options = build_parser().parse_args(arguments)
    result = map_repository(Path(options.repository))
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()