"""Create reproducible documents from repository files."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

LANGUAGES = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".sol": "solidity",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(frozen=True)
class RepositoryDocument:
    """A source file prepared for structural and semantic analysis."""

    path: str
    language: str
    content: str
    content_hash: str


def load_document(path: Path, repository: Path) -> RepositoryDocument:
    """Load one repository file with stable metadata."""
    repository = repository.resolve()
    path = path.resolve()
    relative_path = path.relative_to(repository)
    content = path.read_text(encoding="utf-8")

    return RepositoryDocument(
        path=relative_path.as_posix(),
        language=LANGUAGES.get(path.suffix.lower(), "text"),
        content=content,
        content_hash=sha256(content.encode("utf-8")).hexdigest(),
    )