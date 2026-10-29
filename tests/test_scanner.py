import subprocess
from pathlib import Path

from cohere_workshops.scanner import (
    MAX_FILE_SIZE_BYTES,
    discover_source_files,
    scan_repository,
)


def test_discovers_supported_files_and_ignores_generated_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Example", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Ignore me", encoding="utf-8")

    virtual_environment = tmp_path / ".venv"
    virtual_environment.mkdir()
    (virtual_environment / "ignored.py").write_text("", encoding="utf-8")

    discovered = [
        path.relative_to(tmp_path) for path in discover_source_files(tmp_path)
    ]

    assert discovered == [
        Path("README.md"),
        Path("app.py"),
    ]


def test_ignores_files_larger_than_limit(tmp_path: Path) -> None:
    oversized_file = tmp_path / "oversized.py"
    oversized_file.write_bytes(b"x" * (MAX_FILE_SIZE_BYTES + 1))

    assert discover_source_files(tmp_path) == []


def test_ignores_sensitive_file_names(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text('{"safe": true}', encoding="utf-8")
    (tmp_path / "credentials.json").write_text(
        '{"api_key": "secret"}',
        encoding="utf-8",
    )

    discovered = [
        path.relative_to(tmp_path) for path in discover_source_files(tmp_path)
    ]

    assert discovered == [Path("config.json")]


def test_records_safety_exclusions(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (tmp_path / "large.py").write_bytes(b"x" * 1_000_001)
    (tmp_path / "app.py").write_text("pass", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [path.name for path in result.files] == ["app.py"]
    assert [(excluded.path, excluded.reason) for excluded in result.exclusions] == [
        (".env", "sensitive_path"),
        ("large.py", "file_too_large"),
    ]


def test_respects_git_ignore_rules(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(tmp_path), "init", "-q"],
        check=True,
    )
    (tmp_path / ".gitignore").write_text(
        "ignored.py\nartifacts/\n",
        encoding="utf-8",
    )
    (tmp_path / "kept.py").write_text("pass", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("pass", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "generated.py").write_text("pass", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [path.name for path in result.files] == ["kept.py"]
    assert [(excluded.path, excluded.reason) for excluded in result.exclusions] == [
        ("artifacts/generated.py", "git_ignored"),
        ("ignored.py", "git_ignored"),
    ]


def test_records_ignored_directory_exclusions(tmp_path: Path) -> None:
    build_dir = tmp_path / "pkg" / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "core.py").write_text("pass", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert (
        "pkg/build/core.py",
        "ignored_directory",
    ) in [(excluded.path, excluded.reason) for excluded in result.exclusions]
