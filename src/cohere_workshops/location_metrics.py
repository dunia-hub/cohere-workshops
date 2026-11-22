"""Per-location ranking metrics for version-aware retrieval.

Implements the retrieval metrics in docs/research/evaluation-plan.md. One case is
one code location that changed between two revisions, scored against a target
commit. Git decides validity; these functions only count ranks.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from cohere_workshops.rerank_versions import RankedCandidate
from cohere_workshops.versions import RevisionSnapshot, VersionedChunk, location_key

Location = tuple[str, str, str, int]
DEFAULT_KS = (1, 3, 5, 10)


@dataclass(frozen=True)
class LocationScore:
    """How one ranking treated one code location at one target."""

    location: Location
    exists_at_target: bool
    valid_rank: int | None
    wrong_rank: int | None
    wrong_version_above_valid: bool
    valid_at_1: bool
    recall_at: dict[int, bool]
    reciprocal_rank: float
    wrong_share_at: dict[int, float]
    score_gap: float | None


def locations_at(snapshot: RevisionSnapshot) -> set[Location]:
    """Every code location that exists at one revision."""
    return {location_key(chunk) for chunk in snapshot.chunks}


def score_location(
    ranking: Sequence[RankedCandidate],
    location: Location,
    *,
    is_valid: Callable[[VersionedChunk], bool],
    exists_at_target: bool,
    ks: Sequence[int] = DEFAULT_KS,
) -> LocationScore:
    """Score one ranking for one location.

    Primary metric, wrong_version_above_valid:
    - if the location exists at the target, a wrong-version chunk from the location
      ranks above the target-valid chunk, or the target-valid chunk was not
      retrieved while a wrong-version one was;
    - if the location was removed at the target, a chunk from the location ranks first.
    """
    if not ranking:
        raise ValueError("ranking must not be empty")
    if any(k < 1 for k in ks):
        raise ValueError("every k must be at least 1")

    here = [c for c in ranking if location_key(c.item.chunk) == location]
    valid = [c for c in here if is_valid(c.item)]
    wrong = [c for c in here if not is_valid(c.item)]
    best_valid = min(valid, key=lambda c: c.rank) if valid else None
    best_wrong = min(wrong, key=lambda c: c.rank) if wrong else None
    valid_rank = best_valid.rank if best_valid else None
    wrong_rank = best_wrong.rank if best_wrong else None

    if exists_at_target:
        above = wrong_rank is not None and (valid_rank is None or wrong_rank < valid_rank)
    else:
        above = wrong_rank == 1

    return LocationScore(
        location=location,
        exists_at_target=exists_at_target,
        valid_rank=valid_rank,
        wrong_rank=wrong_rank,
        wrong_version_above_valid=above,
        valid_at_1=is_valid(ranking[0].item),
        recall_at={k: valid_rank is not None and valid_rank <= k for k in ks},
        reciprocal_rank=1 / valid_rank if valid_rank else 0.0,
        wrong_share_at={
            k: sum(not is_valid(c.item) for c in ranking[:k]) / len(ranking[:k]) for k in ks
        },
        score_gap=(
            best_valid.score - best_wrong.score if best_valid and best_wrong else None
        ),
    )


def summarize(scores: Iterable[LocationScore]) -> dict[str, object]:
    """Rates across cases.

    Recall and reciprocal rank need a target-valid chunk, so they are averaged
    over cases whose location exists at the target only.
    """
    scores = list(scores)
    if not scores:
        raise ValueError("no scores to summarize")

    present = [s for s in scores if s.exists_at_target]
    ks = sorted(scores[0].recall_at)

    def rate(values: list[bool]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "cases": len(scores),
        "cases_with_valid_chunk": len(present),
        "wrong_version_above_valid": rate([s.wrong_version_above_valid for s in scores]),
        "valid_at_1": rate([s.valid_at_1 for s in scores]),
        "recall_at": {k: rate([s.recall_at[k] for s in present]) for k in ks},
        "mean_reciprocal_rank": (
            sum(s.reciprocal_rank for s in present) / len(present) if present else None
        ),
        "wrong_share_at": {
            k: sum(s.wrong_share_at[k] for s in scores) / len(scores) for k in ks
        },
    }


def score_record(score: LocationScore) -> dict[str, object]:
    """JSON-ready version of one score."""
    path, kind, symbol, part = score.location
    return {
        "location": {"path": path, "kind": kind, "symbol": symbol, "part_index": part},
        "exists_at_target": score.exists_at_target,
        "valid_rank": score.valid_rank,
        "wrong_rank": score.wrong_rank,
        "wrong_version_above_valid": score.wrong_version_above_valid,
        "valid_at_1": score.valid_at_1,
        "recall_at": {str(k): v for k, v in score.recall_at.items()},
        "reciprocal_rank": round(score.reciprocal_rank, 6),
        "wrong_share_at": {str(k): round(v, 6) for k, v in score.wrong_share_at.items()},
        "score_gap": None if score.score_gap is None else round(score.score_gap, 6),
    }
