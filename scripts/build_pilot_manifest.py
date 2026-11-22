"""Build the pilot case manifest from reviewed candidate lists.

Every accepted location in the six pilot lists becomes one case. Queries describe
the behaviour in plain words without naming the symbol or file (evaluation plan,
step 7). Answering cases are the first two accepted locations per repository in
sample order; their answer keys were checked against the code at both releases
(step 8). Queries and answer keys were drafted with an AI assistant and checked
by the author.

Usage:
    python scripts/build_pilot_manifest.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "experiments" / "dataset" / "candidates"
OUTPUT = ROOT / "experiments" / "dataset" / "pilot" / "cases.json"

LISTS = {
    "arrow": "arrow-1.3.0-1.4.0.json",
    "attrs": "attrs-25.4.0-26.1.0.json",
    "click": "click-8.4.2-8.5.1.json",
    "httpx": "httpx-0.27.2-0.28.1.json",
    "marshmallow": "marshmallow-4.3.1-4.4.0.json",
    "rich": "rich-v14.2.0-v14.3.4.json",
}

# (repository, sample_order) -> query
QUERIES = {
    ("arrow", 1): "How do you get the last moment of the week containing a date, with weeks starting on Sunday?",
    ("arrow", 2): "Which time zone is attached to the current local time when no time zone is given?",
    ("arrow", 3): "When the current time is created through the module-level helper without a time zone, which tzinfo is used?",
    ("arrow", 4): "How are relative times such as 'in 2 weeks' written in Thai?",
    ("arrow", 5): "How is a time zone name such as 'Europe/Paris' turned into a tzinfo object?",
    ("arrow", 6): "Which time zone is assigned when converting a naive Python datetime without specifying one?",
    ("arrow", 8): "When is the week start day validated while computing the start and end of a period?",
    ("attrs", 1): "Can a frozen class use a no-op on-setattr hook on one of its fields?",
    ("attrs", 2): "How are pickled attribute definitions from an older version restored?",
    ("attrs", 4): "What happens to the evolve function's name and docstring when classes get a __replace__ method?",
    ("attrs", 5): "What happens to the checks on field values when the context manager that turns them off is nested?",
    ("attrs", 6): "How does an attribute record whether its init alias was generated automatically?",
    ("attrs", 7): "Which parameters control how a field's init alias is stored when a field definition object is created?",
    ("attrs", 8): "Can the error raised when assigning to an immutable instance be pickled, and what is its message?",
    ("attrs", 9): "How do you get the attribute definitions of an instance instead of its class?",
    ("attrs", 10): "Do field transformers see default init aliases on the attributes they receive?",
    ("attrs", 11): "When an attribute definition is copied with a new name, what happens to its init alias?",
    ("click", 1): "How are arguments in the PAGER environment variable handled when paging through a temporary file?",
    ("click", 2): "How is the short help text built for a deprecated command?",
    ("click", 6): "When output is paged through less, how is it decided whether to keep colours?",
    ("click", 7): "Which sections appear on a command's help page, and in what order?",
    ("click", 8): "Is the test runner helper that runs code inside a temporary working directory deprecated?",
    ("click", 9): "What happens when an invalid colour value is passed to styled terminal output?",
    ("click", 10): "Which environment variable name is shown in an option's help when its envvar is an empty string?",
    ("httpx", 3): "How does the client measure elapsed time for async responses?",
    ("httpx", 4): "How is the elapsed duration computed when an async response is closed?",
    ("httpx", 5): "Which code location does the warning about passing cookies to an individual call point to?",
    ("httpx", 6): "How is the default SSL context configured for verified connections?",
    ("httpx", 7): "Which characters are percent-escaped in a URL path?",
    ("httpx", 10): "What happens when decoding a zstd-encoded response with an empty body?",
    ("httpx", 11): "Which proxy URL schemes are accepted?",
    ("marshmallow", 2): "What happens when a duration field receives NaN?",
    ("marshmallow", 6): "When a field extracts a single value from a nested schema, which key is used if that field's data_key is an empty string?",
    ("marshmallow", 7): "How are dotted and integer keys looked up when reading a value from an object?",
    ("rich", 3): "How are ids generated for hyperlinks in styles?",
    ("rich", 5): "When rich is set as the default exception handler, which options for showing local variables does it pass on?",
    ("rich", 6): "How is a string containing emoji sequences cropped to fit a given display width?",
    ("rich", 7): "Is the style given when writing output applied to line breaks?",
    ("rich", 8): "What happens to strings with line breaking turned off when overflow is set to ignore?",
    ("rich", 10): "How is the hyperlink id set when a style's link is changed?",
    ("rich", 11): "Is markup rendered in the error message shown when an interactive question gets an invalid answer?",
}

# (repository, sample_order) -> facts true only at the old and only at the new release.
ANSWER_KEYS = {
    ("arrow", 1): {
        "old": ["ceil does not accept week_start", "use span('week', week_start=7) and take its end"],
        "new": ["ceil accepts week_start", "ceil('week', week_start=7)"],
    },
    ("arrow", 2): {
        "old": ["dateutil tzlocal()"],
        "new": ["fixed-offset local time zone from datetime.now().astimezone()", "standard library timezone, not dateutil"],
    },
    ("attrs", 1): {
        "old": ["raises ValueError", "Frozen classes can't use on_setattr"],
        "new": ["allowed when on_setattr is setters.NO_OP", "other on_setattr hooks still raise ValueError"],
    },
    ("attrs", 2): {
        "old": ["state is set directly from the pickled tuple", "no alias_is_default field"],
        "new": ["older pickles are missing alias_is_default", "alias_is_default is inferred from the alias"],
    },
    ("click", 1): {
        "old": ["only the pager command is run with the file name", "PAGER arguments are dropped"],
        "new": ["PAGER arguments are passed before the temporary file name"],
    },
    ("click", 2): {
        "old": ["help text is passed through gettext translation before the deprecated label"],
        "new": ["help text is not passed through gettext translation", "deprecated label is appended"],
    },
    ("httpx", 3): {
        "old": ["event loop clock", "trio.current_time() under trio", "asyncio loop time otherwise"],
        "new": ["time.perf_counter", "same clock for sync and async"],
    },
    ("httpx", 4): {
        "old": ["event loop clock", "trio.current_time() under trio", "asyncio loop time otherwise"],
        "new": ["time.perf_counter", "same clock for sync and async"],
    },
    ("marshmallow", 2): {
        "old": ["NaN raises an uncaught ValueError", "only OverflowError is turned into a validation error"],
        "new": ["NaN raises the field's invalid validation error"],
    },
    ("marshmallow", 6): {
        "old": ["empty string falls back to the field name"],
        "new": ["empty string is used as the key", "falls back to the field name only when data_key is None"],
    },
    ("rich", 3): {
        "old": ["random number from randint(0, 999999)"],
        "new": ["sequential ids from a counter"],
    },
    ("rich", 5): {
        "old": ["locals_max_depth is not passed on", "locals_overflow is not passed on"],
        "new": ["locals_max_depth is passed on", "locals_overflow is passed on"],
    },
}


def main() -> None:
    cases = []
    for repository, filename in LISTS.items():
        record = json.loads((CANDIDATES / filename).read_text(encoding="utf-8"))
        accepted = sorted(
            (
                c
                for c in record["candidates"]
                if c["review"] and c["review"]["decision"] == "accept"
            ),
            key=lambda c: c["sample_order"],
        )
        for candidate in accepted:
            key = (repository, candidate["sample_order"])
            if key not in QUERIES:
                raise SystemExit(f"No query for accepted location {key}")
            query = QUERIES[key]
            if candidate["symbol"].rsplit(".", 1)[-1].lower() in query.lower():
                raise SystemExit(f"Query names the symbol: {key}")
            file_stem = candidate["path"].rsplit("/", 1)[-1].removesuffix(".py").lower()
            words = query.lower().replace("?", " ").replace(",", " ").split()
            if file_stem in words:
                raise SystemExit(f"Query names the file: {key}")
            cases.append(
                {
                    "case_id": f"{repository}-{candidate['sample_order']}",
                    "repository": repository,
                    "repository_url": record["repository_url"],
                    "candidate_list": f"experiments/dataset/candidates/{filename}",
                    "old": record["old"],
                    "new": record["new"],
                    "location": {
                        "path": candidate["path"],
                        "kind": candidate["kind"],
                        "symbol": candidate["symbol"],
                        "part_index": candidate["part_index"],
                    },
                    "status": candidate["status"],
                    "review_reason": candidate["review"]["reason"],
                    "query": query,
                    "answer_key": ANSWER_KEYS.get(key),
                }
            )

    unused = set(QUERIES) - {(c["repository"], int(c["case_id"].rsplit("-", 1)[1])) for c in cases}
    if unused:
        raise SystemExit(f"Queries for locations that were not accepted: {sorted(unused)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "study": "Right Code, Wrong Version: pilot",
        "cases": cases,
        "counts": {
            "cases": len(cases),
            "answering_cases": sum(c["answer_key"] is not None for c in cases),
        },
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases, {manifest['counts']['answering_cases']} with answer keys -> {OUTPUT}")


if __name__ == "__main__":
    main()
