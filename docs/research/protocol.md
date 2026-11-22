# Research Protocol

## Working title

**Right Code, Wrong Version: Evaluating Temporal Robustness in Repository Level Code Retrieval**

## Status

Draft protocol, revised for the version-aware study (D017)  
Last updated: 22 November 2026

The first version of this protocol (21 September 2026) described a change-impact study, *Predict Before You Patch*. D017 replaced it with the study described here.

## Background

AI coding tools answer questions about a repository by retrieving code and passing it to a language model. A repository's history holds many versions of the same function, and an index can end up containing more than one of them: an index that was not refreshed, an index built across branches or releases, or vendored copies of older code. When that happens, retrieval can return code that was correct once but is not correct at the commit the developer is working on.

Old and new versions of a function are usually close in wording, so similarity-based retrieval has little signal to tell them apart. A model that answers from the wrong version can give a confident, well-cited answer that is wrong for the code in front of the developer.

This study measures how often Cohere Embed and Cohere Rerank prefer the wrong version, whether showing Rerank revision metadata helps, and whether a deterministic Git validity check, combined with a read-only Cohere Command agent, keeps answers to code that is valid at the target commit.

## Primary research question

When a repository index contains code from two revisions, can retrieval, and an agent grounded in retrieval, return and use only code that is valid at a chosen target commit?

## Secondary research questions

1. How often does Cohere Embed rank a wrong-version chunk above the target-valid chunk for the same code location?
2. Does Cohere Rerank reduce that rate?
3. Does adding revision and commit-date metadata to the text Rerank reads reduce that rate?
4. Does a Git validity filter change the answer correctness, wrong-version fact rate and decline rate of a Command agent, compared with the same agent without the filter and with Command answering without retrieval?
5. Do the results hold when the target is the older revision rather than the newer one?
6. What latency and API usage does each configuration add?

## Hypotheses

### H1

Embed-only retrieval will rank a wrong-version chunk above the target-valid chunk for the same location at a rate above zero, with a 95% confidence interval that excludes zero.

### H2

Cohere Rerank will lower the wrong-version-above-valid rate compared with Embed alone, but will not reduce it to zero.

### H3

Adding revision and commit-date metadata to the Rerank input will not lower the wrong-version-above-valid rate compared with Rerank on code text alone.

### H4

The agent with the Git validity filter will state fewer wrong-version facts than the same agent without the filter and than Command without retrieval, without a higher rate of unnecessary declines.

## Definitions

- **Code location:** a chunk's path, kind, symbol and part index (`versions.py`, `_version_key`).
- **Target-valid chunk:** a chunk whose location and content hash both exist at the target commit (`agent_tools.py`, `TargetValidator`).
- **Wrong-version chunk:** a chunk from the other revision whose location changed (superseded) or no longer exists (removed) at the target. When the target is the newer revision, wrong-version chunks are stale code.
- **Unchanged chunk:** a chunk identical in both revisions. It is indexed once.

Validity is decided by Git history alone. Models never decide which code is valid.

## Unit of analysis

One case consists of:

- a public repository and two commits on the same line of history, older and newer;
- a target commit, which is either of the two;
- a query or question written by the researcher;
- the target-valid chunk or chunks that answer it, and their wrong-version counterparts, derived from Git;
- for answering cases, an answer key listing the facts true at the target and the facts true only at the other revision, committed before any run.

Every query is evaluated at both targets, giving paired cases.

## Planned system configurations

Retrieval configurations:

1. BM25 keyword retrieval over the two-revision index
2. Cohere Embed
3. Cohere Embed and Rerank, code text only
4. Cohere Embed and Rerank, code text with revision and commit-date metadata
5. Cohere Embed, Rerank and the Git validity filter (proposed retrieval)

Answering configurations:

6. Cohere Command without retrieval
7. Read-only agent without the Git validity filter (ablation)
8. Read-only agent with the Git validity filter (proposed system)

Every configuration receives the same cases, models, candidate counts and settings.

## Models

- Embed: `embed-v4.0`
- Rerank: `rerank-v4.0-pro`
- Command: `command-a-03-2025` as the primary model; `command-a-plus-05-2026` as a second model if its rate limit allows

The model used is recorded in every run.

## Scope

The study covers:

- public Python repositories;
- text files supported by the repository scanner;
- commit pairs where at least one indexed symbol was superseded or removed;
- indexes built from exactly two revisions;
- symbol-level chunks (functions, classes and methods);
- read-only retrieval and answering.

## Out of scope

The study does not evaluate:

- indexes with more than two revisions;
- change-impact prediction (see D017);
- automatic code modification or pull-request generation;
- private repositories;
- non-Python structural parsing;
- security vulnerability detection;
- developer productivity.

## Prototype role

The repository contains the reference prototype used for the study.

Implemented:

- loading any Git revision through the safety exclusions (`versions.py`);
- labelling chunks as current, superseded or removed;
- Embed retrieval across two revisions (`cohere-versions`);
- Rerank in code and metadata formats, with a Git filter (`cohere-rerank`);
- the read-only agent, validated against any target commit (`cohere-agent`);
- the agent without the Git filter, as an ablation (`cohere-agent --no-git-filter`);
- Rerank and the Git filter checked against any target commit (`cohere-rerank --target`);
- the per-location retrieval metrics (`location_metrics.py`);
- listing, filtering and sampling dataset candidates (`cohere-candidates`);
- JSON Lines records for every run;
- a rerun script for recorded exploratory runs (`scripts/rerun_demo_experiments.py`).

Not yet implemented:

- BM25 over the two-revision index (configuration 1);
- Command without retrieval for questions (configuration 6);
- a manifest format for commit-pair cases, queries and answer keys at scale;
- an aggregate runner;
- embedding caching, a dependency lock file and continuous integration.

## Development and evaluation separation

The practice repository (`cohere-demo-repo`), this repository, and any repository used while writing queries, prompts or thresholds are development repositories. Their runs are exploratory and are excluded from the final evaluation (D016).

Final evaluation repositories and cases are fixed in a committed manifest before any final run.

## Workshop relationship

Workshops 2–4 were built on this prototype and taught its retrieval, reranking and agent stages.

Workshop attendance is separate from research participation. Attendees may take part in every workshop without contributing research data. Any participant study data requires separate voluntary consent.

The technical evaluation uses public repository history and does not depend on workshop participation.

## Reproducibility

Every experiment must record:

- repository URL, both commits, the target, and tree hashes;
- application commit and whether the working tree was clean;
- model names, Cohere SDK version and Python version;
- query or question, and the answer key identifier;
- configuration settings;
- date and time;
- latency;
- API usage;
- ranked outputs, validity decisions and answers;
- evaluation results.

## Protocol changes

Material changes to the research questions, hypotheses, dataset or evaluation method must be recorded before running the affected experiments.

Changes must be documented in the decision log and the experiment log and committed to Git. The change from change-impact prediction to version-aware retrieval is recorded as D017.
