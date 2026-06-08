# How to Create and Validate Data Contracts

Data contracts define the expected schema, quality rules, and SLAs for a data
product. This guide covers writing a contract in YAML, validating it, and
attaching it to an asset.

## Prerequisites

- Familiarity with the Meshant contract YAML schema.
- The **data_product_owner** role for the target domain.
- The Meshant CLI installed (for local validation).

## Step 1 -- Write the Contract YAML

Create a file named `contract.yaml` (or any `.yaml` / `.yml` extension).
A minimal contract looks like this:

```yaml
apiVersion: meshant/v1
kind: DataContract
metadata:
  name: quarterly-revenue
  domain: finance
  version: "1.0.0"
  owner: dpo@example.com
spec:
  schema:
    fields:
      - name: transaction_id
        type: string
        nullable: false
        unique: true
      - name: amount
        type: decimal
        nullable: false
      - name: currency
        type: string
        nullable: false
        allowed_values: [USD, EUR, GBP]
      - name: recorded_at
        type: timestamp
        nullable: false
  quality:
    completeness_threshold: 0.98
    uniqueness_columns: [transaction_id]
  sla:
    freshness: "24h"
    availability: "99.5%"
```

Key sections:

- **metadata** -- name, domain, version, and owner identity.
- **spec.schema** -- column-level definitions including type, nullability,
  uniqueness, and allowed values.
- **spec.quality** -- minimum quality thresholds that DQ runs enforce.
- **spec.sla** -- freshness and availability guarantees.

## Step 2 -- Validate the Contract Locally

Use the CLI to validate syntax and semantics before pushing to the server:

```bash
datahub contract validate contract.yaml
```

The command exits with code 0 on success. On failure it prints each
violation with a line number and description:

```
ERROR line 14: field "amount" — type "decimal" requires precision and scale
```

Fix any reported issues and re-validate.

## Step 3 -- Attach the Contract to an Asset

**UI:**

1. Navigate to **Assets > [Your Asset] > Contract**.
2. Click **Upload Contract** and select your YAML file.
3. Meshant validates the contract server-side and shows a diff if a
   previous version exists.
4. Click **Confirm** to attach.

**CLI:**

```bash
datahub contract attach \
  --asset-id <ASSET_ID> \
  --file contract.yaml
```

**SDK:**

```python
from datahub_interoperability import DataHubClient

client = DataHubClient()
client.contracts.attach(asset_id="<ASSET_ID>", file_path="contract.yaml")
```

## Step 4 -- Version and Update

When the schema evolves, bump the `version` field in `metadata` and re-attach.
Meshant keeps a full version history. Previous versions remain accessible for
auditing.

```bash
datahub contract history --asset-id <ASSET_ID>
```

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| "Schema mismatch" on attach | Contract fields do not match the asset's inferred schema | Align the contract with the actual data columns |
| Validation timeout | Very large contract with many fields | Split into multiple contracts per logical group |

## Next Steps

- [Publish Asset to Marketplace](publish-asset.md)
- [Review Quality Reports](review-quality-reports.md)
- [Contracts Concept](../../../concepts/contracts.md)
