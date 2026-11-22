"""Pilot study runner and analysis.

Retrieval (configurations 2 to 5) runs every case at both releases. Answering
(configurations 7 and 8) runs the cases that have answer keys. Each repository's
two-release index is embedded once; query embedding and Rerank repeat per run.
See docs/research/evaluation-plan.md.
"""

import json
import math
import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from cohere_workshops.agent import agent_record, run_agent
from cohere_workshops.agent_tools import CodeSearchTool, TargetValidator
from cohere_workshops.embeddings import embed_chunks, embed_query
from cohere_workshops.location_metrics import locations_at, score_location, score_record
from cohere_workshops.rerank_cli import commit_dates
from cohere_workshops.rerank_versions import (
    rerank_hits,
    retrieval_order,
    temporal_filter,
)
from cohere_workshops.retrieval import retrieve_chunks
from cohere_workshops.version_search import VersionHit, select_level
from cohere_workshops.versions import VersionedChunk, build_versioned_corpus

RETRIEVAL_CONFIGS = ("embed", "rerank_code", "rerank_metadata", "git_filter")
TARGETS = ("old", "new")
CANDIDATES = 10
KS = (1, 3, 5, 10)
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 2026


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cases_by_repository(manifest: dict) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in manifest["cases"]:
        groups[case["repository"]].append(case)
    return dict(groups)


def _location(case: dict) -> tuple[str, str, str, int]:
    loc = case["location"]
    return (loc["path"], loc["kind"], loc["symbol"], loc["part_index"])


def _top(ranking: Sequence, is_valid: Callable[[VersionedChunk], bool]) -> list[dict]:
    return [
        {
            "rank": c.rank,
            "score": round(c.score, 6),
            "path": c.item.chunk.path,
            "symbol": c.item.chunk.symbol,
            "revision": c.item.revision,
            "valid_at_target": is_valid(c.item),
        }
        for c in ranking[:5]
    ]


class RepositoryIndex:
    """One repository's two-release index, embedded once."""

    def __init__(self, client: object, repository: Path, cases: list[dict]) -> None:
        first = cases[0]
        old, new = first["old"], first["new"]
        if any(c["old"] != old or c["new"] != new for c in cases):
            raise ValueError("all cases for one repository must share the release pair")

        self.corpus = build_versioned_corpus(repository, old["revision"], new["revision"])
        for side, snapshot in (("old", self.corpus.previous), ("new", self.corpus.current)):
            expected = first[side]["commit"]
            if snapshot.commit != expected:
                raise ValueError(
                    f"{repository}: {first[side]['revision']} is {snapshot.commit[:7]}, "
                    f"manifest says {expected[:7]}"
                )

        self.client = client
        self.items = select_level(self.corpus.chunks, "symbol")
        self.by_id = {item.chunk.chunk_id: item for item in self.items}
        self.embedded = embed_chunks(client, [item.chunk for item in self.items])
        self.validators = {
            "old": TargetValidator(self.corpus.previous),
            "new": TargetValidator(self.corpus.current),
        }
        self.locations = {
            "old": locations_at(self.corpus.previous),
            "new": locations_at(self.corpus.current),
        }
        self.dates = commit_dates(repository, (self.corpus.previous.commit, self.corpus.current.commit))

    def rule(self, target: str) -> Callable[[VersionedChunk], bool]:
        validator = self.validators[target]
        return lambda item: validator.is_valid(item.chunk)

    def retrieve(self, query: str) -> list[VersionHit]:
        vector = embed_query(self.client, query)
        retrieved = retrieve_chunks(vector, self.embedded, top_k=CANDIDATES)
        return [
            VersionHit(rank, r.score, self.by_id[r.embedded_chunk.chunk.chunk_id])
            for rank, r in enumerate(retrieved, start=1)
        ]


def retrieval_records(index: RepositoryIndex, case: dict, run: int) -> list[dict]:
    """Rank once per configuration, then score at both targets."""
    hits = index.retrieve(case["query"])
    rankings = {
        "embed": retrieval_order(hits),
        "rerank_code": rerank_hits(index.client, case["query"], hits, style="code"),
        "rerank_metadata": rerank_hits(
            index.client, case["query"], hits, style="metadata", commit_dates=index.dates
        ),
    }
    location = _location(case)
    records = []
    for target in TARGETS:
        is_valid = index.rule(target)
        per_config = dict(rankings)
        per_config["git_filter"] = temporal_filter(rankings["rerank_code"], is_valid)
        for config in RETRIEVAL_CONFIGS:
            ranking = per_config[config]
            base = {
                "case_id": case["case_id"],
                "repository": case["repository"],
                "run": run,
                "target": target,
                "config": config,
                "exists_at_target": location in index.locations[target],
            }
            if not ranking:
                records.append({**base, "empty": True})
                continue
            score = score_location(
                ranking,
                location,
                is_valid=is_valid,
                exists_at_target=base["exists_at_target"],
                ks=KS,
            )
            records.append({**base, "empty": False, **score_record(score), "top": _top(ranking, is_valid)})
    return records


def answering_records(index: RepositoryIndex, case: dict, *, command_model: str) -> list[dict]:
    """Configurations 8 (Git filter on) and 7 (off) at both targets."""
    client = index.client
    records = []
    for target in TARGETS:
        for git_filter in (True, False):
            tool = CodeSearchTool(
                client,
                index.corpus,
                index.validators[target],
                git_filter=git_filter,
                embedded=index.embedded,
            )
            result = run_agent(client, tool, case["query"], model=command_model)
            record = agent_record(
                result,
                tool,
                run_id=f"{case['case_id']}-{target}-{'filter' if git_filter else 'nofilter'}",
                models={"command": command_model},
            )
            records.append({"case_id": case["case_id"], "repository": case["repository"], **record})
    return records


# ---------------------------------------------------------------- analysis


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def case_values(records: Sequence[dict], metric: Callable[[dict], float | None]) -> dict:
    """Average a metric over runs, per (config, target, repository, case)."""
    grouped: dict[tuple, list[float]] = defaultdict(list)
    for r in records:
        value = metric(r)
        if value is not None:
            grouped[(r["config"], r["target"], r["repository"], r["case_id"])].append(value)
    return {key: _mean(values) for key, values in grouped.items()}


def clustered_bootstrap(per_case: dict[str, dict[str, float]], seed: int = BOOTSTRAP_SEED) -> tuple:
    """95% interval: resample repositories, then cases within each."""
    repositories = sorted(per_case)
    if not repositories:
        return (None, None)
    rng = random.Random(seed)
    means = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        for repository in rng.choices(repositories, k=len(repositories)):
            values = list(per_case[repository].values())
            sample.extend(rng.choices(values, k=len(values)))
        means.append(sum(sample) / len(sample))
    means.sort()
    return (means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1])


def mcnemar_exact(first: Sequence[bool], second: Sequence[bool]) -> dict:
    """Exact two-sided McNemar test on paired binary outcomes."""
    b = sum(x and not y for x, y in zip(first, second, strict=True))
    c = sum(y and not x for x, y in zip(first, second, strict=True))
    n = b + c
    if n == 0:
        return {"only_first": 0, "only_second": 0, "p_value": 1.0}
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return {"only_first": b, "only_second": c, "p_value": min(1.0, 2 * tail)}


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    adjusted, running = {}, 0.0
    for i, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - i) * p))
        adjusted[name] = running
    return adjusted


METRICS: dict[str, Callable[[dict], float | None]] = {
    "wrong_version_above_valid": lambda r: None if r["empty"] else float(r["wrong_version_above_valid"]),
    "valid_at_1": lambda r: None if r["empty"] else float(r["valid_at_1"]),
    "recall_at_1": lambda r: (
        None if not r["exists_at_target"] else (0.0 if r["empty"] else float(r["recall_at"]["1"]))
    ),
    "recall_at_5": lambda r: (
        None if not r["exists_at_target"] else (0.0 if r["empty"] else float(r["recall_at"]["5"]))
    ),
    "mrr": lambda r: (
        None if not r["exists_at_target"] else (0.0 if r["empty"] else r["reciprocal_rank"])
    ),
}


def summarize_retrieval(records: Sequence[dict]) -> dict:
    summary: dict = {"configs": {}, "tests": {}}
    for name, metric in METRICS.items():
        values = case_values(records, metric)
        for (config, target), group in _by_config_target(values).items():
            per_repo: dict[str, dict[str, float]] = defaultdict(dict)
            for (_, _, repository, case_id), value in group.items():
                per_repo[repository][case_id] = value
            all_values = [v for repo in per_repo.values() for v in repo.values()]
            low, high = clustered_bootstrap(per_repo)
            entry = summary["configs"].setdefault(f"{config}@{target}", {})
            entry[name] = {
                "mean": _round(_mean(all_values)),
                "ci95": [_round(low), _round(high)],
                "cases": len(all_values),
            }

    above = case_values(records, METRICS["wrong_version_above_valid"])
    pairs = {
        "H2 embed vs rerank_code": ("embed", "rerank_code"),
        "H3 rerank_code vs rerank_metadata": ("rerank_code", "rerank_metadata"),
    }
    raw = {}
    for name, (a, b) in pairs.items():
        keys = sorted(
            (t, r, c) for (cfg, t, r, c) in above if cfg == a and (b, t, r, c) in above
        )
        first = [above[(a, *k)] >= 0.5 for k in keys]
        second = [above[(b, *k)] >= 0.5 for k in keys]
        result = mcnemar_exact(first, second)
        result["pairs"] = len(keys)
        summary["tests"][name] = result
        raw[name] = result["p_value"]
    for name, p in holm(raw).items():
        summary["tests"][name]["p_holm"] = _round(p)
    return summary


def _by_config_target(values: dict) -> dict:
    grouped: dict[tuple, dict] = defaultdict(dict)
    for key, value in values.items():
        grouped[(key[0], key[1])][key] = value
    return grouped


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def scoring_sheet(
    answers: Sequence[dict], manifest: dict, seed: int = BOOTSTRAP_SEED
) -> tuple[list[dict], dict[int, str]]:
    """Answers in random order with the configuration hidden, for blind scoring.

    Returns the sheet and, separately, the key from answer number to run id.
    """
    keys = {c["case_id"]: c for c in manifest["cases"]}
    rows = []
    for record in answers:
        case = keys[record["case_id"]]
        target = "old" if record["target"]["commit"] == case["old"]["commit"] else "new"
        other = "new" if target == "old" else "old"
        rows.append(
            {
                "_run_id": record["run_id"],
                "question": case["query"],
                "target_release": case[target]["revision"],
                "facts_at_target": case["answer_key"][target],
                "facts_only_at_other_release": case["answer_key"][other],
                "answer": record["answer"] if not record["declined"] else "",
                "declined": record["declined"],
                "outcome": None,
            }
        )
    random.Random(seed).shuffle(rows)
    key = {}
    for number, row in enumerate(rows, start=1):
        key[number] = row.pop("_run_id")
        row["answer_number"] = number
    return rows, key
