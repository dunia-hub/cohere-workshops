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