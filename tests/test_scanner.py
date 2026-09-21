from pathlib import Path

from cohere_workshops.scanner import discover_source_files


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
        path.relative_to(tmp_path)
        for path in discover_source_files(tmp_path)
    ]

    assert discovered == [
        Path("README.md"),
        Path("app.py"),
    ]