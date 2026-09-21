# Reproducibility Guide

## Purpose

This guide defines how to recreate the prototype environment and produce traceable research results.

## System requirements

- Git
- Python 3.11 or newer
- A Cohere API key for live model experiments
- A Unix-compatible shell for the documented commands

The current development environment uses Python 3.12.

## Clone the repository

```bash
git clone <repository-url>
cd cohere-workshops
```

Replace `<repository-url>` with the public GitHub repository URL.

## Create the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Confirm the installation:

```bash
python -c "from importlib.metadata import version; import cohere_workshops; print('Cohere SDK:', version('cohere')); print('Project:', cohere_workshops.__version__)"
```

## Configure Cohere

Create a private environment file:

```bash
cp .env.example .env
```

Add the API key:

```env
COHERE_API_KEY=your_private_key
```

Never commit `.env`.

The API-key type used for an experiment must be recorded without recording the key itself.

Example:

```text
key_type: trial
```

## Verify the project

Run:

```bash
ruff check src tests
pytest
```

The checks must pass before an experiment is recorded.

Tests must not make live Cohere requests.

## Run the structural mapper

Map the current repository:

```bash
cohere-workshops .
```

Map another local repository:

```bash
cohere-workshops /path/to/repository
```

The result is written as JSON to standard output.

Save a result when required:

```bash
cohere-workshops /path/to/repository > repository-map.json
```

Generated experiment outputs should not be committed until an output-directory policy has been defined.

## Run the Cohere connection check

```bash
python -m cohere_workshops.hello_cohere
```

This command makes a live Cohere request. It is not part of the automated tests.

## Required experiment metadata

Every experiment must record:

```text
experiment_id:
date:
researcher:
application_commit:
repository_url:
repository_commit:
pull_request:
pre_change_commit:
change_request_source:
cohere_sdk_version:
model:
model_parameters:
retrieval_configuration:
reranking_configuration:
prompt_version:
random_seed:
start_time:
end_time:
latency:
api_usage:
output_path:
ground_truth_path:
notes:
```

Fields that do not apply must be marked `not_applicable` rather than silently omitted.

## Version control requirements

Before running a recorded experiment:

1. Commit the implementation.
2. Push the commit.
3. Confirm the working tree is clean.
4. Record the application commit hash.
5. Record the target repository commit hash.

Commands:

```bash
git status
git rev-parse HEAD
```

## Dependency recording

The project declares supported dependency ranges in `pyproject.toml`.

For every formal experiment, also capture exact installed versions:

```bash
python -m pip freeze
```

The exact output should be stored with the experiment record.

A lock-file strategy must be selected before the final benchmark is run.

## Input integrity

Every processed document receives a SHA-256 content hash.

Experiment outputs must retain enough information to connect:

- Repository commit
- File path
- Document content hash
- Chunk identifier
- Model request
- Prediction
- Ground truth

If an input hash changes, the earlier result must not be treated as a result for the new content.

## Randomness

Where an API or local process supports a random seed:

- Set the seed explicitly.
- Record it in the experiment metadata.
- Repeat the experiment when model nondeterminism may affect conclusions.

Temperature and other sampling parameters must be recorded.

## API usage

For every live Cohere experiment, record:

- Endpoint
- Model
- Input type
- Number of documents
- Input size
- Output size
- Latency
- Reported token usage where available
- Error or retry count

Never record the API key.

## Failure recording

Failed experiments must not be silently deleted.

Record:

- Experiment identifier
- Failure stage
- Error category
- Relevant non-secret error message
- Retry count
- Whether partial output was produced
- Resolution or exclusion decision

## Reproducing a published result

A published result should provide:

1. Application commit
2. Dataset manifest
3. Repository and pull-request identifiers
4. Pre-change commit identifiers
5. Configuration
6. Prompt version
7. Exact dependency versions
8. Evaluation script
9. Raw predictions where permitted
10. Aggregated metrics
11. Known exclusions
12. Instructions for rerunning the experiment

## Current reproducibility gaps

The project does not yet have:

- A dependency lock file
- A formal dataset manifest
- Experiment-run directories
- Versioned prompts
- Stored API-usage records
- Automated benchmark commands
- Continuous-integration configuration

These must be addressed before the final evaluation.