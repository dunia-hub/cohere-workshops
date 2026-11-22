"""Load repository chunks from Git revisions and label their versions."""

import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from cohere_workshops.chunks import RepositoryChunk, chunk_document
from cohere_workshops.corpus import CorpusError
from cohere_workshops.documents import LANGUAGES, RepositoryDocument
from cohere_workshops.safety import detect_secret_types
from cohere_workshops.scanner import (
    IGNORED_DIRECTORIES,
    MAX_FILE_SIZE_BYTES,
    SENSITIVE_FILE_NAMES,
    SUPPORTED_EXTENSIONS,
    ExcludedFile,
)

CURRENT = "current"
SUPERSEDED = "superseded"
REMOVED = "removed"


@dataclass(frozen=True)
class RevisionSnapshot:
    """Safe, traceable chunks from one exact Git commit."""

    revision: str
    commit: str
    chunks: tuple[RepositoryChunk, ...]
    exclusions: tuple[ExcludedFile, ...]
    errors: tuple[CorpusError, ...]


@dataclass(frozen=True)
class VersionedChunk:
    """A repository chunk with the revision it came from and its status."""

    chunk: RepositoryChunk
    revision: str
    commit: str
    status: str


@dataclass(frozen=True)
class VersionedCorpus:
    """Current chunks plus older chunks that changed or were removed."""

    previous: RevisionSnapshot
    current: RevisionSnapshot
    chunks: tuple[VersionedChunk, ...]
    unchanged: tuple[RepositoryChunk, ...]

    @property
    def unchanged_count(self) -> int:
        """Previous chunks skipped because the current version is identical."""
        return len(self.unchanged)


def _git(repository: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Git is required to read repository revisions") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.decode("utf-8", "replace").strip()
        raise ValueError(message or "Git command failed") from error
    return completed.stdout


def resolve_commit(repository: Path, revision: str) -> str:
    """Resolve a tag, branch or commit to its full commit hash."""
    if not revision.strip() or revision.startswith("-"):
        raise ValueError(f"Invalid revision: {revision!r}")
    output = _git(repository, "rev-parse", "--verify", f"{revision}^{{commit}}")
    return output.decode("ascii").strip()


def _tree_entries(repository: Path, commit: str) -> list[tuple[str, str, int]]:
    """Return (path, blob id, size) for regular files in a commit."""
    output = _git(repository, "ls-tree", "-r", "-l", "-z", commit)
    entries = []

    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id, size = metadata.decode("ascii").split()
        # Skip submodules (commit) and symbolic links (120000).
        if object_type != "blob" or mode == "120000":
            continue
        entries.append((raw_path.decode("utf-8"), object_id, int(size)))

    return sorted(entries)


def load_revision(repository: Path, revision: str) -> RevisionSnapshot:
    """Chunk every supported file exactly as it existed at one revision."""
    repository = repository.resolve()
    commit = resolve_commit(repository, revision)
    chunks: list[RepositoryChunk] = []
    exclusions: list[ExcludedFile] = []
    errors: list[CorpusError] = []

    for path, object_id, size in _tree_entries(repository, commit):
        parsed = PurePosixPath(path)

        if any(part in IGNORED_DIRECTORIES for part in parsed.parts):
            continue
        if parsed.name.lower() in SENSITIVE_FILE_NAMES:
            exclusions.append(ExcludedFile(path, "sensitive_path"))
            continue
        if parsed.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if size > MAX_FILE_SIZE_BYTES:
            exclusions.append(ExcludedFile(path, "file_too_large"))
            continue

        raw = _git(repository, "cat-file", "blob", object_id)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(CorpusError(path, "load", "invalid_utf8"))
            continue

        if detect_secret_types(content):
            exclusions.append(ExcludedFile(path, "suspected_secret"))
            continue

        document = RepositoryDocument(
            path=path,
            language=LANGUAGES.get(parsed.suffix.lower(), "text"),
            content=content,
            content_hash=sha256(content.encode("utf-8")).hexdigest(),
        )
        try:
            chunks.extend(chunk_document(document))
        except SyntaxError:
            errors.append(CorpusError(path, "chunk", "invalid_python_syntax"))

    return RevisionSnapshot(
        revision=revision,
        commit=commit,
        chunks=tuple(chunks),
        exclusions=tuple(exclusions),
        errors=tuple(errors),
    )


def _version_key(chunk: RepositoryChunk) -> tuple[str, str, str, int]:
    """Identify the same code location across revisions."""
    return (chunk.path, chunk.kind, chunk.symbol or "", chunk.part_index)


def location_key(chunk: RepositoryChunk) -> tuple[str, str, str, int]:
    """The code location a chunk belongs to: path, kind, symbol and part index."""
    return _version_key(chunk)


def label_versions(
    previous: RevisionSnapshot,
    current: RevisionSnapshot,
) -> VersionedCorpus:
    """Keep current chunks plus previous chunks that changed or disappeared."""
    current_by_key = {_version_key(chunk): chunk for chunk in current.chunks}
    labelled = [
        VersionedChunk(chunk, current.revision, current.commit, CURRENT)
        for chunk in current.chunks
    ]
    unchanged: list[RepositoryChunk] = []

    for chunk in previous.chunks:
        match = current_by_key.get(_version_key(chunk))

        if match is None:
            status = REMOVED
        elif match.content_hash == chunk.content_hash:
            unchanged.append(chunk)
            continue
        else:
            status = SUPERSEDED

        labelled.append(
            VersionedChunk(chunk, previous.revision, previous.commit, status)
        )

    return VersionedCorpus(
        previous=previous,
        current=current,
        chunks=tuple(labelled),
        unchanged=tuple(unchanged),
    )


def build_versioned_corpus(
    repository: Path,
    previous_revision: str,
    current_revision: str,
) -> VersionedCorpus:
    """Load two revisions and label every indexed chunk by version."""
    previous = load_revision(repository, previous_revision)
    current = load_revision(repository, current_revision)
    return label_versions(previous, current)
