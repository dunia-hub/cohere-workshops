from hashlib import sha256
from pathlib import Path

from cohere_workshops.documents import load_document


def test_loads_repository_document_with_stable_metadata(
    tmp_path: Path,
) -> None:
    content = "def greet() -> str:\n    return 'hello'\n"
    source_file = tmp_path / "app.py"
    source_file.write_text(content, encoding="utf-8")

    document = load_document(source_file, tmp_path)

    assert document.path == "app.py"
    assert document.language == "python"
    assert document.content == content
    assert document.content_hash == sha256(
        content.encode("utf-8")
    ).hexdigest()