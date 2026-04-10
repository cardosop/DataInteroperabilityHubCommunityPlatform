# How to Automate Contract Validation in CI/CD

Catching contract errors before they reach production is the single highest
leverage automation for a Data Engineer. This guide shows how to integrate
Meshant contract validation into GitHub Actions, GitLab CI, and generic
CI pipelines.

## Prerequisites

- Contracts stored as YAML files in your Git repository (e.g., under
  `contracts/`).
- A CI service account token with the **data_engineer** role.
- The `datahub-cli` package available in your CI environment.

## Option A -- GitHub Actions

Add the following step to your workflow (e.g., `.github/workflows/ci.yml`):

```yaml
jobs:
  validate-contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Meshant CLI
        run: pip install datahub-cli

      - name: Configure CLI
        env:
          MESHANT_API_URL: ${{ secrets.MESHANT_API_URL }}
          MESHANT_TOKEN: ${{ secrets.MESHANT_TOKEN }}
        run: |
          datahub config set \
            --api-url "$MESHANT_API_URL" \
            --token "$MESHANT_TOKEN"

      - name: Validate all contracts
        run: datahub contract validate contracts/**/*.yaml --strict
```

The `--strict` flag treats warnings as errors, so the pipeline fails on
any schema ambiguity.

## Option B -- GitLab CI

```yaml
validate-contracts:
  image: python:3.12-slim
  stage: test
  script:
    - pip install datahub-cli
    - datahub config set --api-url "$MESHANT_API_URL" --token "$MESHANT_TOKEN"
    - datahub contract validate contracts/**/*.yaml --strict
  only:
    changes:
      - contracts/**/*.yaml
```

The `only.changes` filter ensures the job runs only when contract files are
modified, keeping pipeline times short.

## Option C -- Generic Pipeline (Shell)

For Jenkins, CircleCI, or any system that runs shell commands:

```bash
#!/usr/bin/env bash
set -euo pipefail

pip install datahub-cli
datahub config set --api-url "$MESHANT_API_URL" --token "$MESHANT_TOKEN"

# Validate every YAML file under contracts/
find contracts -name '*.yaml' -o -name '*.yml' | while read -r f; do
  echo "Validating $f ..."
  datahub contract validate "$f" --strict
done
```

## Handling Failures

When validation fails, the CLI exits with a non-zero code and prints each
issue:

```
ERROR contracts/clickstream.yaml:18 — field "user_id" type "uuid" is not
  a recognized Meshant type. Did you mean "string"?
WARNING contracts/clickstream.yaml:25 — SLA freshness "0.5h" is below the
  recommended minimum of "1h".
```

In `--strict` mode, both errors and warnings cause a non-zero exit.

## Python SDK Alternative

If your pipeline is Python-native, use the SDK directly:

```python
from datahub_sdk import MeshantClient
from pathlib import Path

client = MeshantClient()
errors = []

for contract_path in Path("contracts").glob("**/*.yaml"):
    result = client.contracts.validate(file_path=str(contract_path))
    if not result.valid:
        errors.extend(result.issues)

if errors:
    for e in errors:
        print(f"{e.file}:{e.line} — {e.message}")
    raise SystemExit(1)
```

## Next Steps

- [Trigger DQ Checks via the API](trigger-dq-checks-via-api.md)
- [Use Semantic Queries](use-semantic-queries.md)
- [Contracts Concept](../../../concepts/contracts.md)
