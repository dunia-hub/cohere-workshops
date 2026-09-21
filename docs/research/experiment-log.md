# Experiment Log

## Purpose

This log records model experiments, benchmark runs, failures and material observations.

Development checks are clearly labelled and must not be presented as research results.

## Experiment index

| ID | Date | Type | Description | Status |
| --- | --- | --- | --- | --- |
| PRACTICE-001 | 21 September 2026 | API connection check | First Cohere Chat request from the Python prototype | Completed |

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