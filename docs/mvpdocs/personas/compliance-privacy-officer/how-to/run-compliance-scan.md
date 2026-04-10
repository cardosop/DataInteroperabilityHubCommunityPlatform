# How to Run a Compliance Scan

A compliance scan analyzes every column in a dataset to detect sensitive data
categories (PII, financial, health) and assigns a risk level. This guide
covers running scans manually, scheduling recurring scans, and interpreting
the results in detail.

## Prerequisites

- The **compliance_officer** role in Meshant RBAC.
- At least one asset in `active` or `draft` state with ingested data.

## Step 1 -- Trigger the Scan

### Via the UI

1. Go to **Assets > [Your Asset] > Compliance**.
2. Click **Run Compliance Scan**.
3. Optionally select a scan profile (e.g., "GDPR-EU", "HIPAA-US") to
   restrict detection to regulation-specific categories. The default
   profile scans for all known categories.
4. Click **Start**.

### Via the CLI

```bash
datahub compliance run --asset-id <ASSET_ID>
```

With a specific profile:

```bash
datahub compliance run --asset-id <ASSET_ID> --profile gdpr-eu
```

### Via the SDK

```python
from datahub_sdk import MeshantClient

client = MeshantClient()
run = client.compliance.run(asset_id="<ASSET_ID>", profile="gdpr-eu")
print(f"Run ID: {run.id}")
```

## Step 2 -- Monitor Progress

Scans run asynchronously. Monitor progress with:

```bash
datahub compliance status --run-id <RUN_ID>
```

Or block until completion:

```bash
datahub compliance run --asset-id <ASSET_ID> --wait --timeout 300
```

## Step 3 -- Review the Report

Once the scan completes, retrieve the full report:

```bash
datahub compliance report --run-id <RUN_ID> --format table
```

The report contains:

- **Overall risk level** -- low, medium, or high.
- **Per-column detections** -- each column lists the detected category,
  confidence score (0.0 to 1.0), and contributing risk weight.
- **Recommendations** -- suggested actions such as "mask column",
  "redact before publishing", or "add consent tracking".

### Reading Confidence Scores

| Range | Interpretation |
|-------|---------------|
| 0.90 -- 1.00 | High confidence -- almost certainly sensitive data |
| 0.70 -- 0.89 | Moderate confidence -- manual review recommended |
| Below 0.70 | Low confidence -- likely a false positive |

## Step 4 -- Schedule Recurring Scans

To ensure ongoing compliance, schedule scans to run automatically:

```bash
datahub compliance schedule \
  --asset-id <ASSET_ID> \
  --cron "0 2 * * *" \
  --profile gdpr-eu
```

This runs a GDPR scan every day at 02:00 UTC.

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| Scan returns no findings | Dataset contains only numeric IDs | Expected behavior; risk is Low |
| High false-positive rate | Column names mislead the detector | Add column-level annotations to clarify semantics |
| Scan times out | Very large dataset | Contact platform admin to increase worker resources |

## Next Steps

- [Export Audit Logs](export-audit-logs.md)
- [Configure GDPR Data Subject Rights](configure-gdpr-rights.md)
- [Compliance Runs Concept](../../../concepts/compliance-runs.md)
