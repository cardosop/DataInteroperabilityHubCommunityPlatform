# Data Engineer -- 5-Minute Quickstart

This guide gets you from zero to a validated contract and a live asset using
only the CLI and Python SDK. No UI required.

## Prerequisites

- Python 3.10 or later.
- A Meshant account with the **data_engineer** role.
- An API token (generate one from **Settings > API Tokens** or ask your
  tenant admin).

## Step 1 -- Install and Configure the CLI

```bash
pip install datahub
```

Point the CLI at your Meshant instance:

```bash
datahub config set --api-url https://meshant-internal.example.com --token <YOUR_TOKEN>
```

Verify the connection:

```bash
datahub health check
```

Expected output:

```
Status: healthy
API version: 1.x.x
```

## Step 2 -- Write a Data Contract

Create a file called `contract.yaml`:

```yaml
apiVersion: meshant/v1
kind: DataContract
metadata:
  name: clickstream-events
  domain: product-analytics
  version: "1.0.0"
  owner: de-team@example.com
spec:
  schema:
    fields:
      - name: event_id
        type: string
        nullable: false
        unique: true
      - name: user_id
        type: string
        nullable: false
      - name: event_type
        type: string
        nullable: false
        allowed_values: [page_view, click, scroll, form_submit]
      - name: occurred_at
        type: timestamp
        nullable: false
  quality:
    completeness_threshold: 0.99
    uniqueness_columns: [event_id]
  sla:
    freshness: "1h"
    availability: "99.9%"
```

## Step 3 -- Validate the Contract

```bash
datahub contract validate contract.yaml
```

On success:

```
contract.yaml: valid (4 fields, 1 uniqueness rule, 1 SLA)
```

On failure the CLI prints each issue with a line number so you can fix it
in place.

## Step 4 -- Create an Asset via the API

Use the Python SDK to create the asset and attach the contract in one script:

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(
    base_url="https://meshant-internal.example.com",
    token="<YOUR_TOKEN>",
)

# Create the asset
asset = client.assets.create(
    name="clickstream-events",
    domain="product-analytics",
    flow="contract-first",
)
print(f"Asset created: {asset.id}")

# Attach the contract
client.contracts.attach(
    asset_id=asset.id,
    file_path="contract.yaml",
)
print("Contract attached.")

# Trigger a DQ dry-run (no data yet, validates the contract rules)
run = client.dq.run(asset_id=asset.id, dry_run=True)
print(f"DQ dry-run started: {run.id}")
```

**CLI equivalent:**

```bash
ASSET_ID=$(datahub asset create \
  --name clickstream-events \
  --domain product-analytics \
  --flow contract-first \
  --output id)

datahub contract attach --asset-id "$ASSET_ID" --file contract.yaml

datahub dq run --asset-id "$ASSET_ID" --dry-run
```

## Step 5 -- Verify

Check that the asset exists and the contract is attached:

```bash
datahub asset get --asset-id "$ASSET_ID"
datahub contract get --asset-id "$ASSET_ID"
```

## What You Just Did

- Installed and configured the Meshant CLI.
- Authored a data contract as a YAML file.
- Validated the contract locally.
- Created an asset via the SDK and attached the contract programmatically.
- Triggered a DQ dry-run to confirm the rules are well-formed.

## Next Steps

- [Automate Contract Validation in CI/CD](how-to/automate-contract-validation.md)
- [Trigger DQ Checks via the API](how-to/trigger-dq-checks-via-api.md)
- [Use Semantic Queries (SPARQL / JSON-LD)](how-to/use-semantic-queries.md)
- [Full Reference (API / CLI / SDK)](reference.md)
