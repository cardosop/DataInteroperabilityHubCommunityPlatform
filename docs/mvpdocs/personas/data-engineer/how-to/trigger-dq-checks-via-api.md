# How to Trigger Data Quality Checks via the API

This guide shows how to programmatically trigger DQ checks, poll for
completion, and interpret results -- useful for embedding quality gates
in Airflow DAGs, dbt post-hooks, or custom orchestrators.

## Prerequisites

- An existing asset with data ingested.
- An API token with the **data_engineer** role.
- Python 3.10+ (for SDK examples) or `curl` / the CLI.

## Step 1 -- Trigger a DQ Run

**REST API:**

```bash
curl -X POST https://meshant-internal.example.com/api/v1/dq/runs \
  -H "Authorization: Bearer $MESHANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "<ASSET_ID>"}'
```

Response (HTTP 201):

```json
{
  "id": "run_abc123",
  "asset_id": "<ASSET_ID>",
  "status": "pending",
  "created_at": "2026-04-09T10:00:00Z"
}
```

**CLI:**

```bash
datahub dq run --asset-id <ASSET_ID>
```

**Python SDK:**

```python
from datahub_sdk import MeshantClient

client = MeshantClient()
run = client.dq.run(asset_id="<ASSET_ID>")
print(f"Run ID: {run.id}, Status: {run.status}")
```

## Step 2 -- Wait for Completion

DQ runs are asynchronous. Poll the status endpoint until the run reaches
a terminal state (`passed`, `failed`, or `error`).

**SDK (polling helper):**

```python
import time

run = client.dq.run(asset_id="<ASSET_ID>")

while run.status in ("pending", "running"):
    time.sleep(5)
    run = client.dq.get_run(run.id)

print(f"Final status: {run.status}")
print(f"Overall score: {run.overall_score}")
```

**CLI (blocking mode):**

```bash
datahub dq run --asset-id <ASSET_ID> --wait --timeout 300
```

The `--wait` flag blocks until the run finishes or the timeout (in seconds)
is reached.

## Step 3 -- Retrieve and Parse the Report

**REST API:**

```bash
curl https://meshant-internal.example.com/api/v1/dq/runs/run_abc123/report \
  -H "Authorization: Bearer $MESHANT_TOKEN"
```

**SDK:**

```python
report = client.dq.get_report(run_id=run.id)

for column in report.columns:
    status = "PASS" if column.passed else "FAIL"
    print(f"  {column.name}: completeness={column.completeness:.2%} [{status}]")
```

## Step 4 -- Use as a Pipeline Gate

Example: fail an Airflow task if DQ does not pass.

```python
from airflow.exceptions import AirflowFailException
from datahub_sdk import MeshantClient

def dq_gate(asset_id: str):
    client = MeshantClient()
    run = client.dq.run(asset_id=asset_id)

    while run.status in ("pending", "running"):
        import time; time.sleep(10)
        run = client.dq.get_run(run.id)

    if run.status != "passed":
        raise AirflowFailException(
            f"DQ check failed for asset {asset_id}: score {run.overall_score}"
        )
```

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| Run stuck in `pending` | Worker pool saturated | Check `datahub jobs list --status pending` and retry later |
| `404 Asset not found` | Wrong asset ID or missing permissions | Verify with `datahub asset get --asset-id <ID>` |
| Score is 0.0 | Asset has no data rows | Ingest data before running DQ |

## Next Steps

- [Automate Contract Validation in CI/CD](automate-contract-validation.md)
- [Use Semantic Queries](use-semantic-queries.md)
- [Data Quality Runs Concept](../../../concepts/dq-runs.md)
