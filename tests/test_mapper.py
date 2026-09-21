from pathlib import Path

from cohere_workshops.mapper import map_repository
from cohere_workshops.structure import CodeSymbol


def test_builds_repository_map_from_supported_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# Example", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import json\n\ndef run() -> None:\n    pass\n",
        encoding="utf-8",
    )

    result = map_repository(tmp_path)

    assert result.root == tmp_path.name
    assert [file.path for file in result.files] == [
        "README.md",
        "app.py",
    ]

    python_file = result.files[1]
    assert python_file.imports == ("json",)
    assert python_file.symbols == (
        CodeSymbol(name="run", kind="function", line=3),
    )

    markdown_file = result.files[0]
    assert markdown_file.symbols == ()
    assert markdown_file.imports == ()