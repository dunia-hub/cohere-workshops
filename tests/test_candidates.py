import json
import subprocess
from pathlib import Path

import pytest

from cohere_workshops import candidates_cli
from cohere_workshops.candidates import (
    build_candidate_list,
    candidate_list_record,
    normalized_form,
)
from cohere_workshops.demo_repo import create_demo_repository

OLD_LIB = '''"""Library."""
import typing as t


def behaviour(x):
    return x + 1


def docstring_only(x):
    """Old docstring."""
    return x


def annotations_only(x: int) -> int:
    return x


def old_name(x):
    return x * 3


def gone(x):
    return x - 1


class Box:
    def size(self):
        return 1


@t.overload
def pick(x: int) -> int: ...
@t.overload
def pick(x: str) -> str: ...
def pick(x):
    return x
'''

NEW_LIB = '''"""Library."""
import typing as t


def behaviour(x):
    return x + 2


def docstring_only(x):
    """New docstring, same code."""
    return x


def annotations_only(x: int | None) -> int | None:
    return x


def new_name(x):
    return x * 3


class Box:
    def size(self):
        return 2


@t.overload
def pick(x: int) -> int: ...
@t.overload
def pick(x: bytes) -> bytes: ...
def pick(x):
    return x
'''


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def commit(repo: Path, files: dict[str, str], tag: str) -> None:
    for path, content in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", tag)
    git(repo, "tag", tag)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    test_old = "def test_one():\n    assert 1\n"
    test_new = "def test_one():\n    assert 2\n"
    vendored_old = "def helper():\n    return 1\n"
    vendored_new = "def helper():\n    return 2\n"
    commit(
        repo,
        {"lib.py": OLD_LIB, "tests/test_lib.py": test_old, "vendor/dep.py": vendored_old},
        "v1",
    )
    commit(
        repo,
        {"lib.py": NEW_LIB, "tests/test_lib.py": test_new, "vendor/dep.py": vendored_new},
        "v2",
    )
    return repo


def reasons(result) -> dict[str, str | None]:
    return {c.item.chunk.symbol: c.reason for c in result.candidates}


def test_filters_follow_the_evaluation_plan(repo: Path) -> None:
    result = build_candidate_list(repo, "v1", "v2")
    found = reasons(result)

    assert found["behaviour"] is None
    assert found["Box.size"] is None
    assert found["gone"] is None
    assert found["docstring_only"] == "formatting_or_docstring_only"
    assert found["annotations_only"] == "type_annotations_only"
    assert found["old_name"] == "renamed_or_moved"
    assert found["Box"] == "contains_changed_symbol"
    assert found["pick"] == "ambiguous_location"
    assert found["test_one"] == "test_file"
    assert found["helper"] == "generated_or_vendored"


def test_sampling_is_reproducible_and_orders_every_included_candidate(repo: Path) -> None:
    first = build_candidate_list(repo, "v1", "v2", sample_size=2, seed=7)
    again = build_candidate_list(repo, "v1", "v2", sample_size=2, seed=7)

    def orders(result):
        return {c.item.chunk.symbol: (c.sample_order, c.sampled) for c in result.candidates}

    assert orders(first) == orders(again)
    included = [c for c in first.candidates if c.included]
    assert sorted(c.sample_order for c in included) == list(range(1, len(included) + 1))
    assert sum(c.sampled for c in first.candidates) == 2
    assert all(c.sampled == (c.sample_order <= 2) for c in included)
    assert all(c.sample_order is None for c in first.candidates if not c.included)


def test_record_counts_exclusions_and_holds_no_source(repo: Path) -> None:
    record = candidate_list_record(build_candidate_list(repo, "v1", "v2"), "https://x")

    assert record["repository_url"] == "https://x"
    assert record["counts"]["candidates"] == len(record["candidates"])
    assert record["counts"]["excluded_by_reason"]["test_file"] == 1
    assert "return x + 1" not in json.dumps(record)
    included = [c for c in record["candidates"] if c["included"]]
    assert all(c["review"] == {"decision": None, "reason": None} for c in included)
    removed = next(c for c in record["candidates"] if c["symbol"] == "gone")
    assert removed["new"] is None and removed["status"] == "removed"


def test_demo_repository_has_three_candidates(tmp_path: Path) -> None:
    demo = create_demo_repository(tmp_path / "demo_repo")

    result = build_candidate_list(demo, "v1", "v2")

    assert {c.item.chunk.symbol for c in result.candidates if c.included} == {
        "calculate_transfer_fee",
        "send_payment",
        "validate_phone_number",
    }


def test_normalized_form_ignores_formatting_and_docstrings() -> None:
    a = 'def f(x):\n    """Doc."""\n    return x  # note\n'
    b = "def f( x ):\n    return x\n"
    c = "def f(x: int) -> int:\n    return x\n"

    assert normalized_form(a) == normalized_form(b)
    assert normalized_form(b) != normalized_form(c)
    assert normalized_form(b, strip_annotations=True) == normalized_form(c, strip_annotations=True)
    assert normalized_form("    return x\n  broken(") is None


def test_cli_writes_the_list_and_refuses_to_overwrite(
    repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "out" / "candidates.json"
    arguments = [str(repo), "--old", "v1", "--new", "v2", "--sample", "2", "--output", str(output)]

    candidates_cli.main(arguments)

    printed = capsys.readouterr().out
    record = json.loads(output.read_text())
    assert "excluded, type_annotations_only: 1" in printed
    assert record["sample_size"] == 2
    with pytest.raises(SystemExit, match="already exists"):
        candidates_cli.main(arguments)


def test_rejects_bad_sample_size(repo: Path) -> None:
    with pytest.raises(ValueError, match="sample_size"):
        build_candidate_list(repo, "v1", "v2", sample_size=0)
