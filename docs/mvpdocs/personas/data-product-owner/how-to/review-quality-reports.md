# How to Review Data Quality and Compliance Reports

Every asset in Meshant can be scanned for data quality (DQ) and regulatory
compliance. This guide explains how to find, read, and act on those reports.

## Prerequisites

- An asset with at least one completed DQ or compliance run.
- The **data_product_owner** role (or read access to quality data).

## Step 1 -- Navigate to the Quality Dashboard

**UI:**

1. Go to **Assets > [Your Asset]**.
2. Click the **Quality** tab to see all DQ runs, ordered newest first.
3. Click the **Compliance** tab for compliance scan results.

**CLI:**

```bash
# List recent DQ runs
datahub dq list --asset-id <ASSET_ID> --limit 5

# List recent compliance runs
datahub compliance list --asset-id <ASSET_ID> --limit 5
```

## Step 2 -- Understand the DQ Report

Each DQ run produces a report with the following sections:

### Overall Score

A single number between 0.0 and 1.0 representing the aggregate quality of
the dataset. The threshold (e.g., 0.95) is defined in the asset's data
contract or the domain default.

### Per-Column Metrics

| Metric | Description |
|--------|-------------|
| Completeness | Percentage of non-null values in the column. |
| Uniqueness | Percentage of distinct values (relevant for key columns). |
| Pattern conformance | Percentage of values matching the expected regex or format. |
| Range validity | For numeric/date columns, percentage within the declared min/max. |

Columns that fall below their threshold are highlighted in red. Hover over
a column name to see the exact values and the threshold that was violated.

### Rule Violations

If the data contract includes custom rules (e.g., "amount must be positive"),
each violation is listed with the rule name, the number of offending rows,
and a sample of failing values.

## Step 3 -- Understand the Compliance Report

Compliance scans detect sensitive data categories:

| Category | Examples |
|----------|----------|
| PII_DIRECT_EMAIL | Email addresses |
| PII_DIRECT_PHONE | Phone numbers |
| PII_DIRECT_NAME | Full names |
| PII_QUASI_DOB | Dates of birth |
| FINANCIAL_ACCOUNT | Bank account or credit card numbers |

The report assigns a **risk level** to the asset:

- **Low** -- no sensitive categories detected.
- **Medium** -- quasi-identifiers found; review recommended.
- **High** -- direct PII detected; remediation required before publishing.

## Step 4 -- Take Action

Based on the report findings:

1. **Fix data issues** -- correct source data, re-ingest, and re-run DQ.
2. **Update the contract** -- if a threshold is too strict or too lenient,
   revise the contract and re-validate.
3. **Mask or redact PII** -- use Meshant's transformation module or handle
   upstream before re-ingesting.
4. **Approve and publish** -- once all checks are green, proceed with
   [publishing](publish-asset.md).

## CLI Quick Reference

```bash
# Get detailed DQ report as JSON
datahub dq report --run-id <RUN_ID> --format json

# Get compliance report
datahub compliance report --run-id <RUN_ID> --format json
```

## Next Steps

- [Publish Asset to Marketplace](publish-asset.md)
- [Manage Data Contracts](manage-contracts.md)
- [Data Quality Runs Concept](../../../concepts/dq-runs.md)
