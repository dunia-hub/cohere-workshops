# Evaluation Plan

## Purpose

This document defines how the version-aware retrieval and answering configurations in the [research protocol](protocol.md) will be evaluated.

Last updated: 22 November 2026 (D017). The earlier plan evaluated change-impact prediction against merged pull-request diffs.

## Evaluation dataset

Each case must contain:

- a public Python repository;
- an older and a newer commit on the same line of history;
- a target, which is either commit;
- one code location that was superseded or removed between the two commits;
- a query or question written by the researcher about that location;
- the target-valid chunk and the wrong-version chunk for that location, derived from Git;
- for answering cases, an answer key with the facts true at each commit.

## Dataset construction

1. **Choose repositories.** Public Python repositories with a permissive licence, tagged releases and Python source in most changes. Repositories used during development are excluded.
2. **Choose commit pairs.** Use consecutive release tags as the older and newer commits. An index built from an older release is the realistic case this study models. Where a repository has too few releases, use commits at least 50 commits apart and record why.
3. **List candidate locations.** Run `cohere-candidates` on the commit pair. It builds the two-revision corpus and lists every symbol-level chunk labelled superseded or removed.
4. **Filter candidates.** `cohere-candidates` applies the automatic exclusion criteria below and records every exclusion with its reason.
5. **Sample.** `cohere-candidates` shuffles every included location with a recorded seed (default 2026) and marks the first 20 per commit pair as sampled, so large releases do not dominate.
6. **Review.** Read each sampled location at both commits with `cohere-review`. Some non-behavioural changes pass the automatic filters, for example renaming a typing alias, so record a decision and reason for every sampled location in its `review` field. A rejected location is replaced by the next included one in `sample_order`, never by choice; `cohere-review` does this automatically and records which location replaced it.
7. **Write queries.** For each location, read the code at both commits and the commit messages, then write one query describing the behaviour in plain words. The query must not contain the symbol name or the file path.
8. **Write answer keys.** For the answering subset, list the facts true at each commit, checked by reading the code at both commits and, where practical, by running it.
9. **Freeze.** Commit the manifest, queries and answer keys before any final run. Changes after that point are recorded as protocol changes.

### Target size

At least 5 repositories and 100 locations. Each location is evaluated at both targets, giving 200 paired retrieval cases. At 100 locations, a rate near 30% has a 95% confidence interval of about ±9 percentage points, which is enough to compare configurations that differ by more than that. Answering uses a subset of at least 40 locations (80 question and target cases), because every answering case needs a hand-written answer key.

## Inclusion criteria

A location may be included when:

- both commits can be checked out reproducibly;
- the location is a function, class or method in a non-test Python file;
- the code changed in behaviour, not only in formatting;
- the change can be described in a query without naming the symbol or path.

## Exclusion criteria

A location must be excluded when:

- the change is whitespace, formatting, comments or docstrings only;
- the change is to type annotations only;
- the file is generated, vendored or a test file;
- the file is documentation or example code (`docs/`, `docs_src/`, `examples/`);
- the change is a pure rename or move with no change in behaviour;
- the location is ambiguous: more than one chunk shares its path and symbol at either commit, for example `typing.overload` definitions;
- the location is a class or function whose change lies inside a changed nested symbol, which is a case of its own;
- the repository or file is excluded by the safety scanner;
- review finds the change is not behavioural;
- a fair query cannot be written without revealing the symbol or path.

Every exclusion and its reason must be recorded. `cohere-candidates` applies the first seven automatically; the last three are review decisions. Vendored code under a package-private name (such as `typer/_click`) is not detected by path, so repositories that vendor other projects are not used.

## Ground truth

Ground truth comes from Git history alone:

- **Target-valid chunk:** the chunk at the location whose content hash exists at the target commit.
- **Wrong-version chunk:** the chunk at the same location from the other commit.
- **Removed locations:** at the newer target, there is no target-valid chunk at the location; the correct outcome is that no chunk from that location ranks first and the agent does not describe the removed code as current.

For answering, the answer key is the ground truth. It is written by the researcher, not generated by a language model.

## Compared configurations

### Retrieval

1. **BM25 keyword retrieval** over the two-revision index. Not yet wired to versioned corpora.
2. **Cohere Embed.** `cohere-versions`.
3. **Cohere Embed and Rerank, code text.** `cohere-rerank --format code`.
4. **Cohere Embed and Rerank, code text with metadata.** `cohere-rerank --format metadata`. Adds revision, commit and commit date to the text Rerank reads.
5. **Embed, Rerank and the Git validity filter.** The ranking from configuration 3 with wrong-version chunks removed.

Configuration 5 checks validity against the target commit (`cohere-rerank --target`), so it works at both the older and the newer commit.

### Answering

6. **Command without retrieval.** The question and the repository name only. Not yet implemented for questions.
7. **Agent without the Git validity filter.** `cohere-agent --no-git-filter`. The same agent, search and models, with the top candidates passed to Command whether or not they are valid. Each piece of evidence is labelled with the revisions it exists in, and the prompts name the target, so Command has the information Git uses and must decide validity itself.
8. **Agent with the Git validity filter.** `cohere-agent`.

## Retrieval metrics

Computed per case from the ranked candidates.

### Primary

- **Wrong-version above valid:** the wrong-version chunk for the case's location ranks above its target-valid chunk. For removed locations at the newer target, any chunk from the removed location ranking first counts. This metric tests H1 to H3.

### Secondary

- **Valid@1:** the top result is target-valid.
- **Gold Recall@K** for K = 1, 3, 5 and 10: the target-valid chunk is in the top K.
- **Mean reciprocal rank** of the target-valid chunk.
- **Wrong-version share of the top K** for K = 3 and 5.
- **Score gap:** target-valid score minus wrong-version score for the location. Compared within a configuration only, because Embed and Rerank scores are on different scales.

For configuration 5, wrong-version share is zero by construction. Its cost is reported instead: how often the target-valid chunk was never retrieved, so the filter left nothing useful.

These metrics are implemented per location in `location_metrics.py`. `check_ranking` in `rerank_versions.py` is a coarser check that compares the best valid and best wrong-version chunk anywhere in the ranking; it is used for console output, not for reported results.

## Answering metrics

Each answer is scored against its answer key with one outcome:

- **Wrong-version:** states any fact true only at the other commit.
- **Declined:** the agent declined to answer.
- **Correct:** states every target fact and no wrong-version fact.
- **Incomplete:** states some target facts, none from the wrong version.

Outcomes are assigned in that order, so an answer that mixes versions is scored as wrong-version.

Reported per configuration:

- wrong-version fact rate (primary, tests H4);
- correct rate;
- decline rate, and unnecessary declines, where the target-valid chunk was among the candidates but the agent declined;
- citation validity: cited evidence is target-valid. This holds by construction for configuration 8, because the answer schema only allows validated evidence IDs. It is measured for configuration 7.

The automatic stale-name check (`stale_references`) is reported as a secondary signal only. It skips names that also exist in valid code, so it cannot catch a superseded function that kept its name.

### Scoring procedure

Answers are scored with the configuration hidden: answers are exported in random order with their configuration labels removed, scored, then joined back. Where a second scorer is available, a random 20% of answers is scored twice and agreement is reported.

## Repeated runs

Embed scores varied between runs in exploratory work (0.5622 and 0.5629 for the same query). Each retrieval configuration is therefore run 3 times, and results report the mean and range. Answering configurations run once at temperature 0, with a random 20% subset repeated 3 times to measure answer stability.

## Experimental procedure

For every case:

1. Check out both recorded commits and verify their tree hashes.
2. Build the two-revision corpus.
3. Submit the same query or question to every configuration, at both targets.
4. Record ranked candidates, validity decisions, answers and citations.
5. Compute metrics against the Git ground truth and the answer key.
6. Record latency and API usage.
7. Store errors and decline reasons.
8. Keep the raw output for later audit, including failed runs.

## Development and evaluation separation

Runs on the practice repository and on this repository are development runs (D016). Queries, prompts and thresholds are fixed before the final manifest is frozen, and no case used during development enters the final set.

## Statistical analysis

Report:

- number of repositories, commit pairs, locations and cases;
- every metric per configuration, overall and per repository;
- bootstrap 95% confidence intervals, resampling repositories and then cases, because cases from one repository are not independent;
- paired comparisons on the same cases: McNemar's test for binary outcomes, for configurations 2 vs 3 (H2), 3 vs 4 (H3), and 8 vs 7 and 8 vs 6 (H4);
- effect sizes as differences in rates with confidence intervals;
- Holm correction across the hypothesis tests;
- results at the older and newer target separately (secondary question 5).

Results must not rely on a single aggregate score.

## Error analysis

Wrong-version and incorrect outcomes are categorised as:

- near-identical versions (small change, similar wording);
- target-valid chunk not retrieved;
- Rerank preferred the wrong version;
- metadata changed the Rerank order for the worse;
- the agent's own search query drifted from the question;
- the answer mixed facts from both versions;
- unnecessary decline;
- rename or move counted as removal;
- answer key or ground-truth error.

## Known measurement limits

- A code location is its path, kind, symbol and part index. Moved or renamed code appears as one removed and one new location.
- Content hashes change on any edit, so formatting-only changes are removed during filtering, not by the hash.
- The automatic stale-name check is weak, as described above.

## Human evaluation

Workshop feedback may be used as a separate, secondary usability study only with voluntary consent.

Human ratings do not replace Git ground truth or answer keys in the technical evaluation.

## Reporting requirements

The final report must include:

- the dataset construction method and seed;
- inclusion and exclusion counts with reasons;
- model and API versions;
- prompts and configuration settings;
- results for every configuration, at both targets;
- confidence intervals;
- failure examples from each error category;
- limitations;
- API usage and latency;
- reproduction instructions.
