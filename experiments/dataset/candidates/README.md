# Dataset candidates

Candidate code locations for the final evaluation, produced by `cohere-candidates`
(see the [evaluation plan](../../../docs/research/evaluation-plan.md), dataset
construction steps 3 to 6). Each file lists every symbol-level location that was
superseded or removed between two releases, the automatic exclusions with their
reasons, and a seeded sample order. Files hold paths, line ranges and hashes, never
source code.

## Sources

| Repository | Licence | Release pair | Changed | Included | Sampled |
| --- | --- | --- | --- | --- | --- |
| [pallets/click](https://github.com/pallets/click) | BSD-3-Clause | 8.4.2 → 8.5.1 | 296 | 47 | 20 |
| [encode/httpx](https://github.com/encode/httpx) | BSD-3-Clause | 0.27.2 → 0.28.1 | 165 | 69 | 20 |
| [Textualize/rich](https://github.com/Textualize/rich) | MIT | v14.2.0 → v14.3.4 | 133 | 49 | 20 |
| [arrow-py/arrow](https://github.com/arrow-py/arrow) | Apache-2.0 | 1.3.0 → 1.4.0 | 163 | 24 | 20 |
| [python-attrs/attrs](https://github.com/python-attrs/attrs) | MIT | 25.3.0 → 25.4.0 | 120 | 18 | 18 |
| [python-attrs/attrs](https://github.com/python-attrs/attrs) | MIT | 25.4.0 → 26.1.0 | 46 | 12 | 12 |
| [marshmallow-code/marshmallow](https://github.com/marshmallow-code/marshmallow) | MIT | 4.1.2 → 4.2.4 | 49 | 15 | 15 |
| [marshmallow-code/marshmallow](https://github.com/marshmallow-code/marshmallow) | MIT | 4.3.1 → 4.4.0 | 60 | 7 | 7 |
| **Total** | | | | **241** | **132** |

Commits for every tag are recorded in each file. Seed: 2026 for all pairs. The lists
were produced independently on two machines with identical results.

## How the repositories were chosen

Nine public Python repositories were surveyed over 27 release pairs. The six above
cover different kinds of code (command-line parsing, HTTP, terminal rendering,
dates and times, class generation, serialisation and validation), all have
permissive licences, and all had releases in 2025 or 2026. attrs and marshmallow
use two release pairs each, because one pair alone gives fewer than 20 candidates.

Left out:

- **fastapi/typer** vendors a copy of click under `typer/_click`, which the path
  filters do not detect, so its cases would duplicate click's.
- **pallets/itsdangerous** was used to design the filters and is a development
  repository (D016).
- **python-humanize/humanize** and **pallets/jinja** are reserves.

All six are widely used, so Command has likely seen both versions in training.
This matters most for configuration 6 (Command without retrieval) and is reported
as a limitation.

## Reproduce

```bash
git clone https://github.com/pallets/click ~/eval-repos/click
cohere-candidates ~/eval-repos/click --old 8.4.2 --new 8.5.1 \
  --repository-url https://github.com/pallets/click \
  --output experiments/dataset/candidates/click-8.4.2-8.5.1.json
```

The same pattern applies to every row above. `cohere-candidates` refuses to
overwrite an existing file.

## Review

For each sampled location, read the code at both commits and fill in its `review`
field:

```json
"review": {"decision": "accept", "reason": "fee rule changed from flat to tiered"}
"review": {"decision": "reject", "reason": "not_behavioural: typing alias renamed"}
```

Reject reasons:

- `not_behavioural`: the automatic filters missed a change that does not alter behaviour
- `not_library_code`: build scripts, benchmarks, tooling
- `no_fair_query`: the change cannot be described without naming the symbol or path

Two sampled locations are already known to be `not_library_code`:
`tools/make_terminal_widths.py::make_widths_table` (rich, order 4) and
`performance/benchmark.py::main` (marshmallow 4.3.1 → 4.4.0, order 1).

For each rejection, take the next included location in `sample_order` that is not
yet sampled, set its `sampled` to true, and review it. Never pick a replacement by
choice.
