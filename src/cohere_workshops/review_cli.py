"""Command-line review of a candidate list, one sampled location at a time."""

import argparse
import difflib
from collections.abc import Callable, Sequence
from pathlib import Path

from cohere_workshops.review import (
    ACCEPT,
    REJECT,
    REJECT_REASONS,
    CodeLookup,
    decide,
    load_list,
    pending,
    save_list,
    summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review the sampled locations in a cohere-candidates list. Shows the old "
            "and new code, records your decision in the file after every answer, and "
            "samples the next location in seeded order when you reject one."
        )
    )
    parser.add_argument("candidates", type=Path, help="Candidate list JSON file.")
    parser.add_argument("--repo", type=Path, help="Local clone of the listed repository.")
    parser.add_argument(
        "--summary", action="store_true", help="Print progress and exit, without reviewing."
    )
    return parser


def show(candidate: dict, lookup: CodeLookup, record: dict) -> None:
    old = lookup.chunk(candidate["old"], candidate["path"])
    old_tag, new_tag = record["old"]["revision"], record["new"]["revision"]
    print("\n" + "=" * 78)
    print(
        f"Order {candidate['sample_order']} | {candidate['status']} | "
        f"{candidate['path']}::{candidate['symbol']} | {candidate['lines_changed']} lines"
    )
    print("=" * 78)

    if candidate["new"] is None:
        print(f"Removed in {new_tag}. Code at {old_tag}, lines {old.start_line}-{old.end_line}:\n")
        print(old.content)
        return

    new = lookup.chunk(candidate["new"], candidate["path"])
    diff = difflib.unified_diff(
        old.content.splitlines(),
        new.content.splitlines(),
        fromfile=f"{old_tag} lines {old.start_line}-{old.end_line}",
        tofile=f"{new_tag} lines {new.start_line}-{new.end_line}",
        lineterm="",
    )
    print("\n".join(diff))


def ask(prompt: str, read: Callable[[str], str]) -> str:
    return read(prompt).strip()


def review(path: Path, repo: Path, read: Callable[[str], str] = input) -> None:
    record = load_list(path)
    lookup = CodeLookup(repo)
    skipped: set[int] = set()

    while True:
        queue = [c for c in pending(record) if c["sample_order"] not in skipped]
        if not queue:
            break
        candidate = queue[0]
        show(candidate, lookup, record)

        choice = ask("\n[a] accept  [r] reject  [s] skip  [q] quit > ", read).lower()
        if choice == "q":
            break
        if choice == "s":
            skipped.add(candidate["sample_order"])
            continue
        if choice == "a":
            reason = ask("What changed in behaviour? > ", read)
            if not reason:
                print("A reason is required. Not recorded.")
                continue
            decide(record, candidate, ACCEPT, reason)
        elif choice == "r":
            menu = "  ".join(f"[{n}] {r}" for n, r in enumerate(REJECT_REASONS, start=1))
            pick = ask(f"Reason: {menu} > ", read)
            if pick not in {str(n) for n in range(1, len(REJECT_REASONS) + 1)}:
                print("Not recorded.")
                continue
            note = ask("Note (optional) > ", read)
            code = REJECT_REASONS[int(pick) - 1]
            replacement = decide(record, candidate, REJECT, f"{code}: {note}" if note else code)
            if replacement:
                print(
                    f"Sampled replacement: order {replacement['sample_order']}, "
                    f"{replacement['path']}::{replacement['symbol']}"
                )
            else:
                print("No included candidates left to sample in this list.")
        else:
            print("Type a, r, s or q.")
            continue
        save_list(path, record)

    print_summary(record)


def print_summary(record: dict) -> None:
    counts = summary(record)
    print(
        f"\n{record['old']['revision']} -> {record['new']['revision']}: "
        f"{counts['accepted']} accepted, {counts['rejected']} rejected, "
        f"{counts['pending']} pending, {counts['unsampled_left']} spare"
    )


def main(arguments: Sequence[str] | None = None) -> None:
    options = build_parser().parse_args(arguments)
    if options.summary:
        print_summary(load_list(options.candidates))
        return
    if options.repo is None:
        raise SystemExit("--repo is required to review. Use --summary to only see progress.")
    review(options.candidates, options.repo)


if __name__ == "__main__":
    main()
