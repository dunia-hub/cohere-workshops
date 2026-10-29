"""Discover source files inside a repository."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_SIZE_BYTES = 1_000_000

SENSITIVE_FILE_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "service-account.json",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
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


@dataclass(frozen=True)
class ExcludedFile:
    """A file excluded from analysis with an auditable reason."""

    path: str
    reason: str


@dataclass(frozen=True)
class ScanResult:
    """Supported files and recorded safety exclusions."""

    files: tuple[Path, ...]
    exclusions: tuple[ExcludedFile, ...]


def _git_ignored_paths(
    repository: Path,
    paths: Sequence[Path],
) -> set[str]:
    """Return paths ignored by Git, including nested ignore rules."""
    if not paths:
        return set()

    try:
        repository_check = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "rev-parse",
                "--is-inside-work-tree",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Git is required to evaluate ignore rules") from error

    if repository_check.returncode != 0:
        return set()

    relative_paths = [path.relative_to(repository).as_posix() for path in paths]
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "check-ignore",
            "--no-index",
            "--stdin",
            "-z",
        ],
        input="\0".join(relative_paths) + "\0",
        capture_output=True,
        check=False,
        text=True,
    )

    if completed.returncode not in {0, 1}:
        raise RuntimeError("Git failed to evaluate repository ignore rules")

    return {path for path in completed.stdout.split("\0") if path}


def scan_repository(repository: Path) -> ScanResult:
    """Scan a repository and record safety-related exclusions."""
    repository = repository.resolve()

    if not repository.is_dir():
        raise ValueError(f"Repository does not exist: {repository}")

    candidates: list[Path] = []
    exclusions: list[ExcludedFile] = []

    for path in repository.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(repository)

        if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
            if not any(part in {".git", ".venv"} for part in relative_path.parts):
                exclusions.append(
                    ExcludedFile(relative_path.as_posix(), "ignored_directory")
                )
            continue

        if path.name.lower() in SENSITIVE_FILE_NAMES:
            exclusions.append(ExcludedFile(relative_path.as_posix(), "sensitive_path"))
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            exclusions.append(ExcludedFile(relative_path.as_posix(), "file_too_large"))
            continue

        candidates.append(path)

    ignored_paths = _git_ignored_paths(repository, candidates)
    files: list[Path] = []

    for path in candidates:
        relative_path = path.relative_to(repository).as_posix()

        if relative_path in ignored_paths:
            exclusions.append(ExcludedFile(relative_path, "git_ignored"))
        else:
            files.append(path)

    return ScanResult(
        files=tuple(
            sorted(files, key=lambda path: path.relative_to(repository).as_posix())
        ),
        exclusions=tuple(sorted(exclusions, key=lambda item: item.path)),
    )


def discover_source_files(repository: Path) -> list[Path]:
    """Return supported repository files in deterministic order."""
    return list(scan_repository(repository).files)
