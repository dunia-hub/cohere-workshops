"""List code locations that changed between two revisions, as evaluation candidates.

Implements steps 3 to 5 of the dataset construction in
docs/research/evaluation-plan.md, and prepares step 6: list superseded and
removed symbol-level chunks, apply the automatic filters, and sample with a
recorded seed.

Every candidate is kept in the output, included or not, so every exclusion and
its reason is recorded. Records contain paths, line ranges and hashes, never
source code.

The automatic filters are a first pass. Some changes that do not alter behaviour
still pass them (for example, renaming a typing alias), so the researcher reviews
each sampled candidate and records the decision in its "review" field. A rejected
candidate is replaced by the next included one in "sample_order".
"""

import ast
import difflib
import random
import textwrap
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cohere_workshops.git_ground_truth import is_test_path
from cohere_workshops.versions import (
    CURRENT,
    REMOVED,
    SUPERSEDED,
    VersionedChunk,
    VersionedCorpus,
    build_versioned_corpus,
    location_key,
)

SYMBOL_KINDS = ("function", "method", "class")
DEFAULT_SAMPLE = 20
DEFAULT_SEED = 2026

# Path parts and file name endings treated as generated or vendored code.
GENERATED_PARTS = frozenset(
    {"vendor", "vendored", "_vendor", "third_party", "thirdparty", "generated", "migrations"}
)
GENERATED_SUFFIXES = ("_pb2.py", "_pb2_grpc.py")

# Directories holding documentation and example code rather than library code.
DOCS_PARTS = frozenset({"docs", "doc", "docs_src", "examples", "example"})


@dataclass(frozen=True)
class Candidate:
    """One changed code location and what the filters decided about it."""

    item: VersionedChunk
    counterpart: VersionedChunk | None
    reason: str | None
    lines_changed: int
    normalized: bool
    sample_order: int | None = None
    sampled: bool = False

    @property
    def included(self) -> bool:
        return self.reason is None


@dataclass(frozen=True)
class CandidateList:
    """All candidates for one commit pair, with the settings that produced them."""

    corpus: VersionedCorpus
    candidates: tuple[Candidate, ...]
    seed: int
    sample_size: int


class _StripAnnotations(ast.NodeTransformer):
    """Remove type annotations, which do not change behaviour."""

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.returns = None
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.returns = None
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST | None:
        if node.value is None:
            return None
        return ast.Assign(targets=[node.target], value=node.value)


def normalized_form(
    content: str,
    *,
    rename_to: str | None = None,
    strip_annotations: bool = False,
) -> str | None:
    """Code structure without formatting, comments or docstrings.

    Returns None when the chunk does not parse on its own (for example, a chunk
    split into parts). With rename_to, the top-level definition's name is replaced,
    so a renamed but otherwise identical definition compares equal. With
    strip_annotations, type annotations are removed too.
    """
    try:
        tree = ast.parse(textwrap.dedent(content))
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]

    if strip_annotations:
        tree = _StripAnnotations().visit(tree)

    if rename_to is not None and tree.body:
        top = tree.body[0]
        if isinstance(top, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            top.name = rename_to

    return ast.dump(tree, include_attributes=False)


def is_generated_path(path: str) -> bool:
    """Vendored or generated code, by path convention."""
    parsed = PurePosixPath(path)
    return bool(GENERATED_PARTS & set(parsed.parts[:-1])) or parsed.name.endswith(
        GENERATED_SUFFIXES
    )


def is_docs_or_examples_path(path: str) -> bool:
    """Documentation or example code, by directory name."""
    return bool(DOCS_PARTS & set(PurePosixPath(path).parts[:-1]))


def _lines_changed(old: str, new: str) -> int:
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
    return sum(
        1
        for line in diff
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )


def _nested_in_changed(item: VersionedChunk, changed: set[tuple[str, str]]) -> bool:
    """A class or function whose change sits inside a changed nested symbol."""
    symbol = item.chunk.symbol or ""
    return any(
        path == item.chunk.path and other.startswith(symbol + ".")
        for path, other in changed
    )


def list_candidates(
    corpus: VersionedCorpus,
    *,
    sample_size: int = DEFAULT_SAMPLE,
    seed: int = DEFAULT_SEED,
) -> CandidateList:
    """Apply the evaluation-plan filters to every changed location, then sample."""
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1")

    current = {location_key(i.chunk): i for i in corpus.chunks if i.status == CURRENT}
    old_locations = {location_key(c) for c in corpus.previous.chunks}
    added = [
        i
        for i in current.values()
        if location_key(i.chunk) not in old_locations and i.chunk.kind in SYMBOL_KINDS
    ]
    added_forms = {
        form
        for i in added
        if (form := normalized_form(i.chunk.content, rename_to="_")) is not None
    }

    changed = [
        i
        for i in corpus.chunks
        if i.status in (SUPERSEDED, REMOVED) and i.chunk.kind in SYMBOL_KINDS
    ]
    changed_symbols = {(i.chunk.path, i.chunk.symbol or "") for i in changed}
    ambiguous = {
        key
        for snapshot in (corpus.previous, corpus.current)
        for key, count in Counter(location_key(c) for c in snapshot.chunks).items()
        if count > 1
    }

    candidates: list[Candidate] = []
    for item in sorted(changed, key=lambda i: location_key(i.chunk)):
        chunk = item.chunk
        counterpart = current.get(location_key(chunk)) if item.status == SUPERSEDED else None
        old_form = normalized_form(chunk.content)
        normalized = old_form is not None

        if chunk.language != "python":
            reason = "not_python"
        elif is_test_path(chunk.path):
            reason = "test_file"
        elif is_generated_path(chunk.path):
            reason = "generated_or_vendored"
        elif is_docs_or_examples_path(chunk.path):
            reason = "docs_or_examples"
        elif location_key(chunk) in ambiguous:
            reason = "ambiguous_location"
        elif _nested_in_changed(item, changed_symbols):
            reason = "contains_changed_symbol"
        elif counterpart is not None and normalized and (
            old_form == normalized_form(counterpart.chunk.content)
        ):
            reason = "formatting_or_docstring_only"
        elif counterpart is not None and normalized and (
            normalized_form(chunk.content, strip_annotations=True)
            == normalized_form(counterpart.chunk.content, strip_annotations=True)
        ):
            reason = "type_annotations_only"
        elif item.status == REMOVED and normalized and (
            normalized_form(chunk.content, rename_to="_") in added_forms
        ):
            reason = "renamed_or_moved"
        else:
            reason = None

        lines = _lines_changed(chunk.content, counterpart.chunk.content if counterpart else "")
        candidates.append(Candidate(item, counterpart, reason, lines, normalized))

    included = [c for c in candidates if c.included]
    # Shuffle every included candidate, not only the sample, so a candidate
    # rejected during manual review is replaced by the next one in this order.
    shuffled = random.Random(seed).sample(range(len(included)), len(included))
    order = {location_key(included[i].item.chunk): n for n, i in enumerate(shuffled, start=1)}
    candidates = [
        Candidate(
            c.item,
            c.counterpart,
            c.reason,
            c.lines_changed,
            c.normalized,
            order.get(location_key(c.item.chunk)) if c.included else None,
            c.included and order[location_key(c.item.chunk)] <= sample_size,
        )
        for c in candidates
    ]
    return CandidateList(corpus, tuple(candidates), seed, sample_size)


def build_candidate_list(
    repository: Path,
    old: str,
    new: str,
    *,
    sample_size: int = DEFAULT_SAMPLE,
    seed: int = DEFAULT_SEED,
) -> CandidateList:
    """Load two revisions and list their candidates.

    Parsing old source can raise SyntaxWarning (for example, for old escape
    sequences). The warnings say nothing about the change, so they are silenced.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        corpus = build_versioned_corpus(repository, old, new)
        return list_candidates(corpus, sample_size=sample_size, seed=seed)


def _chunk_record(item: VersionedChunk) -> dict[str, object]:
    chunk = item.chunk
    return {
        "revision": item.revision,
        "commit": item.commit,
        "lines": [chunk.start_line, chunk.end_line],
        "content_hash": chunk.content_hash,
    }


def candidate_record(candidate: Candidate) -> dict[str, object]:
    """JSON-ready record for one candidate. No source code."""
    chunk = candidate.item.chunk
    return {
        "path": chunk.path,
        "kind": chunk.kind,
        "symbol": chunk.symbol,
        "part_index": chunk.part_index,
        "part_count": chunk.part_count,
        "status": candidate.item.status,
        "old": _chunk_record(candidate.item),
        "new": _chunk_record(candidate.counterpart) if candidate.counterpart else None,
        "lines_changed": candidate.lines_changed,
        "normalized": candidate.normalized,
        "included": candidate.included,
        "exclusion_reason": candidate.reason,
        "sample_order": candidate.sample_order,
        "sampled": candidate.sampled,
        "review": {"decision": None, "reason": None} if candidate.included else None,
    }


def candidate_list_record(result: CandidateList, repository_url: str | None) -> dict[str, object]:
    """The whole list as one JSON document."""
    corpus = result.corpus
    reasons = Counter(c.reason for c in result.candidates if not c.included)
    return {
        "repository_url": repository_url,
        "old": {"revision": corpus.previous.revision, "commit": corpus.previous.commit},
        "new": {"revision": corpus.current.revision, "commit": corpus.current.commit},
        "seed": result.seed,
        "sample_size": result.sample_size,
        "counts": {
            "candidates": len(result.candidates),
            "included": sum(c.included for c in result.candidates),
            "sampled": sum(c.sampled for c in result.candidates),
            "excluded_by_reason": dict(sorted(reasons.items())),
        },
        "scanner_exclusions": {
            snapshot.revision: [
                {"path": e.path, "reason": e.reason} for e in snapshot.exclusions
            ]
            for snapshot in (corpus.previous, corpus.current)
        },
        "candidates": [candidate_record(c) for c in result.candidates],
    }