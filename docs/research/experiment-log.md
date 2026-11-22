# Experiment Log

## Purpose

This log records model experiments, benchmark runs, failures and material observations.

Development checks are clearly labelled and must not be presented as research results.

## Experiment index

| ID | Date | Type | Description | Status |
| --- | --- | --- | --- | --- |
| PRACTICE-001 | 21 September 2026 | API connection check | First Cohere Chat request from the Python prototype | Completed |
| exp-2026-10-12-gitignore-retrieval | 12 October 2026 | Exploratory retrieval | Retrieve files relevant to Git ignore support | Completed; development only |
| exp-2026-10-13-chunk-limits-prediction | 13 October 2026 | Exploratory prediction | Predict files affected by bounded chunking | Completed; development only |
| exp-2026-10-13-chunk-limits-ungrounded | 13 October 2026 | Exploratory prediction | Ungrounded Command baseline for bounded chunking | Completed; development only |
| exp-2026-11-18-demo-*-attempt1 | 18 November 2026 | Exploratory rerun | Embed, Rerank and agent on the practice repository | Failed at agent stage: trial key monthly limit; kept as record |
| exp-2026-11-18-demo-*-attempt2 | 18 November 2026 | Exploratory rerun | Same, on a production key | Failed at agent stage: Command A+ monthly cap; kept as record |
| exp-2026-11-22-demo-embed | 22 November 2026 | Exploratory retrieval | Embed across v1 and v2 of the practice repository | Completed; development only |
| exp-2026-11-22-demo-rerank | 22 November 2026 | Exploratory retrieval | Rerank in code and metadata formats, with Git filter | Completed; development only |
| exp-2026-11-22-demo-agent | 22 November 2026 | Exploratory agent | 4 questions at targets v1 and v2, Command A; scored in scoring.md | Completed; development only |
| exp-2026-11-22-demo-agent-nofilter | 22 November 2026 | Exploratory agent ablation | Same questions without the Git filter (configuration 7); scored in scoring.md | Completed; development only |

## Protocol changes

| Date | Change | Record |
| --- | --- | --- |
| 22 November 2026 | Study changed from change-impact prediction to version-aware retrieval. Runs before this date were made under the earlier protocol and are development evidence only. | D017 |

## Entry template

Copy this template for every new experiment:

```markdown
## EXPERIMENT-ID: Short title

### Classification

- Type:
- Research question:
- Status:

### Date and ownership

- Date:
- Researcher:
- Start time:
- End time:

### Application

- Application commit:
- Working tree clean:
- Python version:
- Cohere SDK version:
- Dependency snapshot:

### Dataset

- Dataset version:
- Repository:
- Repository commit:
- Pull request:
- Pre-change commit:
- Inclusion rationale:
- Exclusions:

### Configuration

- Endpoint:
- Model:
- Input type:
- Prompt version:
- Temperature:
- Seed:
- Retrieval configuration:
- Reranking configuration:
- Abstention threshold:

### Procedure

1.
2.
3.

### Output

- Raw output:
- Prediction file:
- Ground-truth file:
- Latency:
- API usage:
- Errors:
- Retries:

### Results

- Precision:
- Recall:
- Ranking metrics:
- Unsupported prediction rate:
- Abstention:
- Other observations:

### Interpretation

Describe what the result supports and what it does not support.

### Limitations

List threats, confounders and unresolved questions.

### Next action

State the specific follow-up experiment or engineering change.
```

---

## PRACTICE-001: First Cohere Chat request

### Classification

- Type: Development connection check
- Research question: Not applicable
- Status: Completed successfully
- Research result: No

### Date and ownership

- Date: 21 September 2026
- Researcher: Fatuma Yattani

### Application

- Project version: `0.1.0`
- Python version: `3.12.3`
- Cohere SDK version: `5.21.1`
- Module: `src/cohere_workshops/hello_cohere.py`

### Configuration

- Endpoint: Cohere Chat V2
- Client: `cohere.ClientV2`
- Model: `command-a-03-2025`
- Key type: Trial
- Temperature: `0`
- Maximum output tokens: `80`

### Prompt

```text
In one sentence, explain why grounding matters in an AI system that analyzes source code.
```

### Response

```text
Grounding matters in an AI system that analyzes source code because it ensures the model's understanding and reasoning are anchored to real-world programming concepts, syntax, and semantics, reducing hallucinations and improving accuracy in tasks like bug detection, code generation, and documentation.
```

### Result

The Cohere Python SDK, local environment loading and Trial API key worked correctly.

### Interpretation

This result verifies connectivity only.

It does not evaluate:

- Grounding quality
- Hallucination rate
- Repository understanding
- Retrieval quality
- Change-impact prediction
- Research hypotheses

### Next action

Complete and document the deterministic repository-analysis foundation before beginning Cohere Embed experiments.

---

## exp-2026-10-12-gitignore-retrieval: Git ignore retrieval

### Classification

- Type: Exploratory development run
- Research result: No
- Status: Completed

### Configuration

- Application commit: `a2aa09fe9b84f833af1c53d9a8bb0ad41e70d311`
- Query: `Respect .gitignore rules when scanning a repository`
- Embed model: `embed-v4.0`
- Rerank model: `rerank-v4.0-pro`
- Retrieval K: `10`
- Rerank K: `5`
- Key type: Trial

### Result

The highest-ranked evidence identified `src/cohere_workshops/scanner.py` and its scanner tests before Git ignore support was implemented.

### Interpretation

The run showed that semantic retrieval and reranking could locate the directly relevant implementation and test evidence for this development task.

It is not a final evaluation result because the query was used during feature development and no independent benchmark case was defined beforehand.

### Record

Full metadata and output are stored in `experiments/exploratory/exp-2026-10-12-gitignore-retrieval`.

---

## exp-2026-10-13-chunk-limits-prediction: Bounded chunking

### Classification

- Type: Exploratory development run
- Research result: No
- Status: Completed after three failed live attempts

### Query

```text
Split repository chunks that exceed safe model input limits while preserving complete source coverage and traceable line ranges
```

### Configuration

- Embed model: `embed-v4.0`
- Rerank model: `rerank-v4.0-pro`
- Prediction model: `command-a-plus-05-2026`
- Retrieval K: `10`
- Rerank K: `5`
- Key type: Trial

### Failures observed

1. A thinking content block appeared before the JSON text and broke response parsing.
2. The model returned a duplicate file path.
3. The model returned an unsupported symbol.

Each failure produced an engineering correction before the successful rerun. The parser now selects text content safely, duplicate paths are normalized, and unsupported symbols are rejected or removed through constrained generation and local validation.

### Ground truth

After implementation, the changed files were:

- `src/cohere_workshops/chunks.py`
- `src/cohere_workshops/embeddings.py`
- `tests/test_chunks.py`

### Results

The reranked unique file set contained:

- `src/cohere_workshops/chunks.py`
- `src/cohere_workshops/corpus.py`
- `src/cohere_workshops/embeddings.py`

Retrieval recall was `0.3333` at K=1 and `0.6667` at K=3 and K=5.

The final grounded prediction returned only `src/cohere_workshops/chunks.py`, producing prediction recall of `0.3333` at K=1, K=3 and K=5. It predicted `RepositoryChunk` and `chunk_document` with confidence `0.7` and recorded unresolved implementation questions.

### Interpretation

Retrieval found two of the three changed files, while the final prediction reduced coverage to one. This development case exposed a real recall loss between retrieval and generation and motivated retaining separate retrieval and prediction metrics.

The case cannot support a general claim about system quality. It was used to build and debug the feature, used this repository rather than an independent evaluation repository, and initially omitted the test file because synthetic secret fixtures triggered the safety filter. Those fixtures were later corrected without changing the recorded original result.

### Record

Full metadata and output are stored in `experiments/exploratory/exp-2026-10-13-chunk-limits-prediction`.
