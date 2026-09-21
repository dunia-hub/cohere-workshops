"""Discover source files inside a repository."""

from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

SUPPORTED_EXTENSIONS = {
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".sol",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}


def discover_source_files(repository: Path) -> list[Path]:
    """Return supported repository files in deterministic order."""
    repository = repository.resolve()

    if not repository.is_dir():
        raise ValueError(f"Repository does not exist: {repository}")

    files = [
        path
        for path in repository.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(repository).parts)
    ]

    return sorted(files)