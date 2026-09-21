# Research Protocol

## Working title

**Predict Before You Patch: Evidence-Grounded Change Impact Analysis for Open-Source Repositories**

## Status

Draft protocol  
Last updated: 21 September 2026

## Background

Developers often receive an issue or feature request before knowing which files, functions, tests and dependencies will need modification. Language models can suggest possible changes, but their recommendations may be incomplete, unsupported or confidently incorrect.

This research investigates whether deterministic repository analysis combined with Cohere Embed, Rerank and Command can produce more accurate and auditable change-impact predictions.

## Primary research question

Can an evidence-grounded AI system predict which parts of a Python repository will be affected by a proposed code change more accurately than keyword search, embedding retrieval or a language model without repository grounding?

## Secondary research questions

1. Does structural repository information improve file-level prediction accuracy?
2. Does Cohere Rerank improve the ordering of relevant files retrieved with Cohere Embed?
3. Can repository evidence reduce unsupported change recommendations?
4. Can calibrated abstention reduce incorrect predictions when repository evidence is insufficient?
5. What quality, latency and API-usage trade-offs arise between the evaluated approaches?

## Hypotheses

### H1

Structural and semantic retrieval will achieve higher file-level recall than keyword retrieval alone.

### H2

Cohere Rerank will improve the ranking of files that were actually modified in the corresponding pull request.

### H3

Requiring repository evidence for each prediction will reduce unsupported file and symbol recommendations.

### H4

An abstention mechanism will reduce false-positive predictions on ambiguous or incomplete change requests.

## Unit of analysis

One experiment unit consists of:

- A repository snapshot before a merged pull request
- The issue or change request associated with that pull request
- The files and tests actually changed by the pull request
- Predictions produced from the pre-change repository

The merged pull-request diff provides the primary ground truth.

## Planned system configurations

1. Keyword retrieval
2. Cohere Embed retrieval
3. Cohere Embed with Cohere Rerank
4. Structural and semantic retrieval
5. Evidence-grounded prediction with abstention

Each configuration will receive the same change request and pre-change repository snapshot.

## Scope

The initial study will focus on:

- Publicly available open-source repositories
- Python repositories
- Merged pull requests with identifiable pre-change commits
- Text-based source, configuration, test and documentation files
- File-level and symbol-level change-impact prediction

## Out of scope

The initial study will not evaluate:

- Automatic code modification
- Pull-request generation
- Private repositories
- Security vulnerability detection
- Developer productivity claims beyond the measured tasks
- Fully autonomous software maintenance
- Non-Python structural parsing

## Prototype role

The current repository contains the reference prototype used to develop and evaluate the research system.

It currently supports:

- Repository file discovery
- Deterministic document loading
- SHA-256 content hashing
- Python AST analysis
- Symbol and import extraction
- Structural repository mapping
- JSON command-line output
- A basic Cohere Chat request

Semantic retrieval, reranking, prediction and evaluation remain under development.

## Workshop relationship

The prototype will be developed and tested before Workshops 2–4 are designed.

Workshop attendance is separate from research participation. Attendees may participate in every workshop without contributing research data. Any participant study data will require separate voluntary consent.

The primary technical evaluation will use public repository history and will not depend on workshop participation.

## Reproducibility

Every experiment must record:

- Repository URL
- Repository commit
- Pull-request identifier
- Model names
- Prompt or query
- Retrieval configuration
- Random seed where applicable
- Date and time
- Latency
- API usage
- Predictions
- Ground truth
- Evaluation results
- Relevant code version

## Protocol changes

Material changes to the research questions, hypotheses, dataset or evaluation method must be recorded before running the affected experiments.

Changes must be documented in the experiment log and committed to Git.