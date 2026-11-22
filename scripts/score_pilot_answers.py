"""Record blind scores for the pilot answers, then unblind and compare configurations.

Usage:
    python scripts/score_pilot_answers.py record   # writes the scores into scoring-sheet.json
    python scripts/score_pilot_answers.py unblind  # joins with scoring-key.json and summarises

Scores were assigned from scoring-sheet.json alone, before the key was opened, using
the rule in docs/research/evaluation-plan.md: wrong_version, then declined, then
correct (every target fact), otherwise incomplete. Pre-scored by an AI assistant
and confirmed by the author.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from cohere_workshops.pilot import mcnemar_exact

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "pilot"
OUTCOMES = ("correct", "incomplete", "wrong_version", "declined")

SCORES = {
    "correct": [3, 9, 15, 20, 22, 24, 25, 27, 29, 30, 31, 36, 37, 39, 42, 44, 45],
    "wrong_version": [10, 12, 26, 40, 41, 46],
    "declined": [5, 18, 28],
}
NOTES = {
    10: "recommends ceil(week_start=7), which only exists in the newer release",
    12: "says PAGER arguments are passed on, which is newer-release behaviour",
    23: "answer key error: 'deprecated label is appended' is true in both releases; not counted",
    26: "says NaN gives a validation error, which is newer-release behaviour",
    40: "says an empty data_key falls back to the field name, which is older-release behaviour",
    41: "says an empty data_key falls back to the field name, which is older-release behaviour",
    46: "says NaN gives a validation error (newer-release behaviour) plus unrelated allow_nan details",
}


def record(sheet_path: Path) -> None:
    rows = json.loads(sheet_path.read_text(encoding="utf-8"))
    assigned = {n: outcome for outcome, numbers in SCORES.items() for n in numbers}
    for row in rows:
        row["outcome"] = assigned.get(row["answer_number"], "incomplete")
        if row["answer_number"] in NOTES:
            row["note"] = NOTES[row["answer_number"]]
    sheet_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(dict(Counter(r["outcome"] for r in rows)))


def unblind(folder: Path) -> dict:
    rows = json.loads((folder / "scoring-sheet.json").read_text(encoding="utf-8"))
    if any(r["outcome"] not in OUTCOMES for r in rows):
        raise SystemExit("Every answer needs an outcome before unblinding.")
    key = json.loads((folder / "scoring-key.json").read_text(encoding="utf-8"))

    joined = []
    for row in rows:
        case_id, target, config = key[str(row["answer_number"])].rsplit("-", 2)
        joined.append({**row, "case_id": case_id, "target": target, "config": config})

    summary: dict = {"by_config": {}, "by_config_and_target": {}}
    for config in ("filter", "nofilter"):
        group = [r for r in joined if r["config"] == config]
        counts = Counter(r["outcome"] for r in group)
        summary["by_config"][config] = {o: counts.get(o, 0) for o in OUTCOMES} | {"answers": len(group)}
        for target in ("old", "new"):
            sub = Counter(r["outcome"] for r in group if r["target"] == target)
            summary["by_config_and_target"][f"{config}@{target}"] = {o: sub.get(o, 0) for o in OUTCOMES}

    pairs = sorted({(r["case_id"], r["target"]) for r in joined})
    outcome = {(r["case_id"], r["target"], r["config"]): r["outcome"] for r in joined}
    wrong_off = [outcome[(c, t, "nofilter")] == "wrong_version" for c, t in pairs]
    wrong_on = [outcome[(c, t, "filter")] == "wrong_version" for c, t in pairs]
    summary["h4_wrong_version_nofilter_vs_filter"] = mcnemar_exact(wrong_off, wrong_on) | {
        "pairs": len(pairs)
    }
    declined_off = [outcome[(c, t, "nofilter")] == "declined" for c, t in pairs]
    declined_on = [outcome[(c, t, "filter")] == "declined" for c, t in pairs]
    summary["declines_nofilter_vs_filter"] = mcnemar_exact(declined_off, declined_on) | {
        "pairs": len(pairs)
    }
    summary["wrong_version_answers"] = [
        {k: r[k] for k in ("answer_number", "case_id", "target", "config", "note")}
        for r in joined
        if r["outcome"] == "wrong_version"
    ]

    (folder / "answer-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    folder = Path(sys.argv[2]) if len(sys.argv) > 2 else RESULTS
    if stage == "record":
        record(folder / "scoring-sheet.json")
    elif stage == "unblind":
        unblind(folder)
    else:
        raise SystemExit("Usage: score_pilot_answers.py record|unblind [results folder]")
