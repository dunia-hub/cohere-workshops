# Engineering Decision Log

This document records technical decisions that materially affect the prototype or research.

## Decision format

Each decision records:

- Identifier
- Date
- Status
- Context
- Decision
- Rationale
- Consequences

---

## D001: Build the reference prototype before Workshops 2–4

**Date:** 21 September 2026
**Status:** Accepted

### Context

The workshop series is intended to produce a useful application and support a research paper. Designing the workshops before testing the complete technical workflow could produce disconnected or unverified material.

### Decision

Build and evaluate a reference prototype first. Use the tested implementation to design Workshops 2–4 later.

### Rationale

This ensures that workshop content is based on working code, real limitations and measured results.

### Consequences

- Prototype development is not workshop delivery.
- Workshop materials remain separate from experimental code.
- Features may be rejected or revised before becoming workshop content.

---

## D002: Use Python 3.11 or newer

**Date:** 21 September 2026
**Status:** Accepted

### Context

The project needs a language suitable for repository analysis, Cohere integration, experiments and data analysis.

### Decision

Use Python 3.11 or newer for the reference implementation.

### Rationale

Python provides:

- The standard-library AST parser
- A supported Cohere SDK
- Mature testing and research tooling
- Clear examples for workshop participants
- Strong data-analysis support

### Consequences

The first structural parser will target Python repositories.

---

## D003: Separate deterministic evidence from model reasoning

**Date:** 21 September 2026
**Status:** Accepted

### Context

Language models may invent files, symbols or dependencies when repository evidence is incomplete.

### Decision

File discovery, hashing, parsing, symbol extraction, diff ground truth and metric calculation must remain deterministic.

Cohere models may assist with semantic retrieval, reranking and structured reasoning.

### Rationale

This creates an auditable boundary between repository facts and model-generated conclusions.

### Consequences

Every model prediction must point to evidence produced by the deterministic layer.

---

## D004: Begin with public Python repositories

**Date:** 21 September 2026
**Status:** Accepted

### Context

Supporting multiple programming languages would increase parser complexity and weaken the initial evaluation.

### Decision

Limit the first study to public Python repositories.

### Rationale

A narrower scope enables reliable AST analysis, reproducible experiments and clearer conclusions.

### Consequences

Non-Python files may be indexed as text, but structural symbol extraction initially applies only to Python.

---

## D005: Use Python AST for structural extraction

**Date:** 21 September 2026
**Status:** Accepted

### Context

The prototype needs reliable functions, classes, imports and source locations.

### Decision

Use Python’s standard-library `ast` module for the first structural analyzer.

### Rationale

AST analysis is deterministic, local, testable and does not require model inference.

### Consequences

Malformed Python files must be handled explicitly in a future error-handling step.

---

## D006: Hash every loaded document

**Date:** 21 September 2026
**Status:** Accepted

### Context

Research outputs must be connected to the exact source content used in an experiment.

### Decision

Generate a SHA-256 hash for each loaded document.

### Rationale

Hashes allow the system to identify content changes, support caching and verify experimental inputs.

### Consequences

Embedding records, predictions and experiment logs should retain the relevant content hashes.

---

## D007: Start with a command-line interface

**Date:** 21 September 2026
**Status:** Accepted

### Context

A graphical interface would add work unrelated to the initial research questions.

### Decision

Expose the prototype through a command-line interface before building a browser interface.

### Rationale

A CLI is easier to test, automate and reproduce.

### Consequences

The initial system outputs JSON. A user interface remains optional and out of scope until the research pipeline works.

---

## D008: Tests must not spend Cohere credits

**Date:** 21 September 2026
**Status:** Accepted

### Context

Automated tests may run frequently in local development and continuous integration.

### Decision

All automated tests must use deterministic fixtures or mocked Cohere responses.

### Rationale

This keeps tests fast, repeatable and independent of API availability or account balance.

### Consequences

Live API checks must be clearly separated from the automated test suite.

---

## D009: Use Cohere ClientV2

**Date:** 21 September 2026
**Status:** Accepted

### Context

The project uses the Cohere Python SDK for model requests.

### Decision

Use `cohere.ClientV2` for new integration code.

### Rationale

The V2 client supports Chat, Embed and the structured workflows planned for the prototype.

### Consequences

SDK requests and tests should follow the V2 response structures.

---

## D010: Keep workshop participation separate from research consent

**Date:** 21 September 2026
**Status:** Accepted

### Context

Dunia Hub workshops are educational activities. Attendance must not require participation in research.

### Decision

Workshop registration, attendance and support will remain independent from voluntary research consent.

### Rationale

Participants should be able to learn without contributing their data to the study.

### Consequences

Research consent, identifiers, storage and withdrawal procedures require separate documentation and implementation.

---

## D011: Exclude unsafe repository content before model processing

**Date:** 13 October 2026
**Status:** Accepted

### Context

Repository scans may encounter credentials, sensitive files, generated dependencies, ignored files, oversized inputs or undecodable content.

### Decision

Apply Git ignore rules, sensitive-path checks, a 1,000,000-byte file limit and high-confidence secret detection before external model processing. Record exclusions and processing errors.

### Rationale

Repository analysis must fail safely and preserve an auditable account of omitted evidence.

### Consequences

Excluded content cannot be retrieved or cited. Tests construct fake secret patterns at runtime so the test suite remains indexable.

---

## D012: Use deterministic traceable chunks with a size limit

**Date:** 13 October 2026
**Status:** Accepted

### Context

Complete files and symbols can exceed safe model input sizes, while evaluation requires every model input to remain traceable to source.

### Decision

Create stable file-level and symbol-level chunks capped at 12,000 characters. Preserve source paths, line ranges, hashes, identifiers and part metadata while maintaining full source coverage.

### Rationale

Bounded chunks support reliable API calls without losing provenance or silently dropping source text.

### Consequences

Long content may produce multiple chunks. Retrieval and prediction must retain chunk identifiers and source hashes.

---

## D013: Use verified Cohere models for distinct pipeline stages

**Date:** 13 October 2026
**Status:** Accepted

### Context

Retrieval, reranking and change-impact reasoning require different model capabilities.

### Decision

Use `embed-v4.0` for document and query embeddings, `rerank-v4.0-pro` for candidate reranking and `command-a-plus-05-2026` for structured prediction.

### Rationale

Separating the stages makes each contribution measurable and supports the planned ablation study.

### Consequences

Every experiment must record model names and configurations. Live calls spend Cohere credits; automated tests use fake clients.

---

## D014: Constrain and validate every model prediction locally

**Date:** 13 October 2026
**Status:** Accepted

### Context

Early live runs produced thinking blocks, duplicate paths and unsupported symbols.

### Decision

Use JSON Schema to constrain generated predictions, then validate paths, symbols, evidence identifiers, test paths and confidence values locally. Normalize duplicate file predictions and reject unsupported output.

### Rationale

Structured generation alone does not guarantee that a prediction is supported by repository evidence.

### Consequences

Only locally validated predictions are returned. Insufficient evidence produces an explicit abstention.

---

## D015: Evaluate structural import expansion as a separate configuration

**Date:** 13 October 2026
**Status:** Accepted

### Context

Semantic retrieval may find the directly described file while missing locally related modules and tests.

### Decision

Resolve deterministic local Python import relationships and optionally add a bounded set of one-hop related files before Cohere Rerank.

### Rationale

Keeping structural expansion optional allows its contribution to be measured independently.

### Consequences

Structural candidates must exist in the scanned repository, retain provenance and never replace the original semantic candidates.

---

## D016: Separate exploratory development cases from final evaluation

**Date:** 13 October 2026
**Status:** Accepted

### Context

Queries used to design chunking, validation or retrieval logic would leak development knowledge into a final benchmark.

### Decision

Store development runs under `experiments/exploratory` and exclude them from the final evaluation dataset.

### Rationale

Development and evaluation separation reduces overfitting and supports credible reporting.

### Consequences

Exploratory results may document failures and guide implementation, but they cannot be reported as final benchmark evidence.

---

## D017: Refocus the study on version-aware retrieval

**Date:** 22 November 2026
**Status:** Accepted

### Context

The protocol, evaluation plan and architecture were written for change-impact prediction: given a change request, predict which files a merged pull request modified. During Workshops 2–4 the prototype gained version-aware components (`versions.py`, `version_search.py`, `rerank_versions.py`, `agent_tools.py`, `agent.py`). Exploratory runs with them showed a narrower problem: retrieval over two revisions often ranks superseded or removed code above current code. The README already presents the project as *Right Code, Wrong Version*, so the README and the research documents describe different studies.

### Decision

The study is *Right Code, Wrong Version: Evaluating Temporal Robustness in Repository Level Code Retrieval*. Its question is whether retrieval, and an agent grounded in retrieval, can tell code that is valid at a target commit from other versions of the same code. Change-impact prediction is no longer a research question of this study.

### Rationale

- The exploratory evidence points to the version-aware question.
- Validity at a commit can be derived deterministically from Git, which follows D003 and D014: models rank and answer, Git decides what is valid.
- One question keeps the dataset, ground truth and metrics consistent.

### Consequences

- `protocol.md`, `evaluation-plan.md` and `architecture.md` are rewritten for the version-aware study.
- Change-impact components (BM25, `cohere-search`, grounded and ungrounded prediction, pull-request manifests) stay in the codebase as foundation and possible baselines. Their results are not reported as findings of this study.
- Ground truth changes from merged pull-request diffs to Git-derived chunk validity at a target commit, plus answer keys committed before any run.
- The October exploratory records and the November demo reruns remain development evidence under D016 and are excluded from the final evaluation.
- Earlier experiments ran under the previous protocol. This change is recorded before any final evaluation run, as the protocol requires.
