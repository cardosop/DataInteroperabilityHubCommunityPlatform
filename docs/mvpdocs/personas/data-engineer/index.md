# Data Engineer (DE)

> Also known as: Analytics Engineer, Platform Engineer, Data Pipeline Engineer

## Who You Are

You are a technically proficient engineer who builds and maintains data
pipelines, automates quality checks, and integrates Meshant into your
organization's broader data stack. You prefer working in the terminal or
writing Python scripts over clicking through a UI. Contracts-as-code,
CI/CD-driven validation, and programmatic asset management are your bread
and butter.

Typical job titles that map to this persona:

- Data Engineer / Senior Data Engineer
- Analytics Engineer
- Platform Engineer (Data)
- DataOps Engineer

## What You Care About

| Priority | Description |
|----------|-------------|
| Automation | Every repeatable task should be scriptable via API, CLI, or SDK. |
| Contracts as code | Schema definitions, quality rules, and SLAs live in version control alongside pipeline code. |
| Pipeline integration | DQ and compliance checks run as steps in Airflow, dbt, or CI/CD pipelines. |
| Observability | Job statuses, run durations, and failure reasons are accessible programmatically. |
| Semantic metadata | SPARQL and JSON-LD enable rich, machine-readable metadata queries. |

## Your MVP Capabilities

Within the Meshant MVP you can:

1. **Manage contracts as code** -- write YAML contracts, validate them
   locally with the CLI, and push them through CI before attaching to assets.

2. **Automate asset intake via API and SDK** -- create assets, upload files,
   trigger schema inference, and attach contracts without touching the UI.

3. **Integrate DQ and compliance checks into pipelines** -- call the DQ and
   compliance endpoints from Airflow operators, dbt post-hooks, or GitHub
   Actions steps.

4. **Query semantic metadata** -- use the SPARQL endpoint or JSON-LD
   expansion to resolve lineage, domain relationships, and cross-asset
   dependencies.

5. **Monitor and manage jobs** -- poll or webhook-subscribe to ingestion,
   DQ, compliance, and transformation job events.

6. **Orchestrate transformations** -- define and trigger transformation
   jobs that reshape data before publishing.

## Key Journeys

End-to-end walkthroughs for your most common workflows:

- [Automate Contract Validation in CI](../../journeys/JOURNEY-DE-001.md)
- [Create and Ingest Assets via API](../../journeys/JOURNEY-DE-003.md)
- [Integrate DQ Checks into a Data Pipeline](../../journeys/JOURNEY-DE-004.md)

## Typical Day

1. Pull the latest contract YAML changes from the feature branch and run
   `datahub contract validate` locally.
2. Push the branch -- CI runs contract validation and DQ dry-runs
   automatically.
3. Merge triggers an API call that creates or updates the asset and
   attaches the new contract version.
4. Monitor the ingestion job via `datahub jobs list --status running`.
5. If a DQ check fails, inspect the report programmatically, fix the
   pipeline, and re-trigger.
6. Query the SPARQL endpoint to verify lineage is correctly captured after
   the new asset is live.

## Related Concepts

- [Contracts](../../concepts/contracts.md) -- schema + SLA + quality rules
- [Datasets](../../concepts/datasets.md) -- raw and processed data objects
- [Jobs](../../concepts/jobs.md) -- async task execution model
- [Semantic Resources](../../concepts/semantic-resources.md) -- JSON-LD and SPARQL metadata

## Permissions and Roles

The DE persona maps to the **data_engineer** role in Meshant RBAC. This
role grants:

- Full CRUD on assets and contracts within assigned domains.
- Execute permissions for DQ, compliance, and transformation jobs.
- Read access to job logs and run history.
- Read access to the semantic query endpoint.

For cross-domain automation, request the **platform_engineer** role from
your tenant administrator.

## Environment Setup

```bash
# Install the CLI
pip install datahub-cli

# Configure endpoint and credentials
datahub config set --api-url https://meshant-internal.example.com --token <YOUR_TOKEN>

# Verify connectivity
datahub health check
```

For the Python SDK:

```python
from datahub_sdk import MeshantClient

client = MeshantClient(
    base_url="https://meshant-internal.example.com",
    token="<YOUR_TOKEN>",
)
print(client.health.check())
```

## Get Started

- [5-Minute Quickstart](quickstart.md) -- validate a contract and create an asset from the terminal
- [How-To Guides](how-to/) -- automation recipes for CI, DQ, and semantic queries
- [API / CLI / SDK Reference](reference.md) -- full parameter details for every endpoint and command
