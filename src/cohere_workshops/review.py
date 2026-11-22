"""Record manual review decisions on a candidate list from cohere-candidates.

Implements step 6 of the dataset construction in docs/research/evaluation-plan.md.
The researcher decides; this module only finds the code, records the decision and,
when a location is rejected, samples the next included location in seeded order.
"""

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from cohere_workshops.chunks import RepositoryChunk
from cohere_workshops.versions import load_revision

ACCEPT = "accept"
REJECT = "reject"
REJECT_REASONS = ("not_behavioural", "not_library_code", "no_fair_query")


def load_list(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_list(path: Path, record: dict) -> None:
    """Write atomically, so an interrupted review never leaves a broken file."""
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        file.write(json.dumps(record, indent=2) + "\n")
    os.replace(temporary, path)


def pending(record: dict) -> list[dict]:
    """Sampled candidates without a decision, in sample order."""
    return sorted(
        (
            c
            for c in record["candidates"]
            if c["sampled"] and c["review"] and c["review"]["decision"] is None
        ),
        key=lambda c: c["sample_order"],
    )


def next_replacement(record: dict) -> dict | None:
    """The first included candidate in sample order that is not yet sampled."""
    unsampled = [c for c in record["candidates"] if c["included"] and not c["sampled"]]
    return min(unsampled, key=lambda c: c["sample_order"], default=None)


def decide(record: dict, candidate: dict, decision: str, reason: str) -> dict | None:
    """Record a decision. A rejection samples the next candidate, which is returned."""
    if candidate not in record["candidates"] or not candidate["sampled"]:
        raise ValueError("only sampled candidates can be reviewed")
    if candidate["review"]["decision"] is not None:
        raise ValueError("candidate already has a decision")
    if not reason.strip():
        raise ValueError("a reason is required")

    if decision == ACCEPT:
        candidate["review"] = {"decision": ACCEPT, "reason": reason.strip()}
        return None

    if decision != REJECT:
        raise ValueError(f"decision must be {ACCEPT!r} or {REJECT!r}")
    code = reason.split(":", 1)[0].strip()
    if code not in REJECT_REASONS:
        raise ValueError(f"reject reason must start with one of {REJECT_REASONS}")

    replacement = next_replacement(record)
    candidate["review"] = {
        "decision": REJECT,
        "reason": reason.strip(),
        "replaced_by_order": replacement["sample_order"] if replacement else None,
    }
    if replacement is not None:
        replacement["sampled"] = True
    return replacement


def summary(record: dict) -> dict[str, int]:
    reviews = [c["review"] for c in record["candidates"] if c["sampled"] and c["review"]]
    return {
        "sampled": len(reviews),
        "accepted": sum(r["decision"] == ACCEPT for r in reviews),
        "rejected": sum(r["decision"] == REJECT for r in reviews),
        "pending": sum(r["decision"] is None for r in reviews),
        "unsampled_left": sum(
            c["included"] and not c["sampled"] for c in record["candidates"]
        ),
    }


class CodeLookup:
    """Finds a candidate's exact code at a commit by its content hash."""

    def __init__(
        self,
        repository: Path,
        loader: Callable[[Path, str], object] = load_revision,
    ) -> None:
        self.repository = repository
        self.loader = loader
        self._chunks: dict[str, dict[tuple[str, str], RepositoryChunk]] = {}

    def chunk(self, side: dict, path: str) -> RepositoryChunk:
        commit = side["commit"]
        if commit not in self._chunks:
            snapshot = self.loader(self.repository, commit)
            if snapshot.commit != commit:
                raise ValueError(f"{commit[:7]} resolved to {snapshot.commit[:7]}")
            self._chunks[commit] = {(c.path, c.content_hash): c for c in snapshot.chunks}
        found = self._chunks[commit].get((path, side["content_hash"]))
        if found is None:
            raise ValueError(
                f"{path} with hash {side['content_hash'][:12]} not found at {commit[:7]}. "
                "Is this the right repository?"
            )
        return found
