# Compliance & Privacy Officer -- 5-Minute Quickstart

This guide walks you through running your first compliance scan on an
existing asset, reviewing the results, and exporting the audit log. You
will use the Meshant web UI for each step, with CLI alternatives noted
for automation-minded teams.

## Prerequisites

- A Meshant account with the **compliance_officer** role.
- At least one asset already ingested (ask a Data Product Owner or Data
  Engineer to create one if your catalog is empty).

## Step 1 -- Log In and Open the Compliance Dashboard

1. Navigate to your Meshant instance (e.g., `https://meshant-internal.example.com`).
2. Sign in with your organizational credentials.
3. In the left sidebar, click **Compliance**. The dashboard shows an
   overview of your organization's compliance posture:
   - Total assets scanned vs. unscanned.
   - Distribution by risk level (low / medium / high).
   - Recent scan activity.

## Step 2 -- Select an Asset and Run a Compliance Scan

1. Click **Assets** in the sidebar to browse the catalog.
2. Select the asset you want to scan (e.g., "customer-contacts").
3. Navigate to the **Compliance** tab on the asset detail page.
4. Click **Run Compliance Scan**.
5. Meshant analyzes every column for sensitive data categories and assigns
   a risk level. Typical scan times range from a few seconds to a minute
   depending on dataset size.

**CLI alternative:**

```bash
datahub compliance run --asset-id <ASSET_ID>
datahub compliance status --run-id <RUN_ID>
```

## Step 3 -- Review the Results

Once the scan completes, the Compliance tab displays:

### Risk Level Badge

A colored badge at the top of the page:

- **Green (Low)** -- no sensitive data detected.
- **Yellow (Medium)** -- quasi-identifiers found (e.g., ZIP codes, dates
  of birth). Review recommended.
- **Red (High)** -- direct PII detected (e.g., emails, phone numbers,
  names). Remediation required before the asset can be published.

### Per-Column Findings

A table listing each column with:

| Column | Category Detected | Confidence | Risk |
|--------|-------------------|-----------|------|
| email | PII_DIRECT_EMAIL | 0.98 | High |
| full_name | PII_DIRECT_NAME | 0.95 | High |
| zip_code | PII_QUASI_ZIP | 0.87 | Medium |
| order_total | (none) | -- | Low |

Click any row to see sample values that triggered the detection (samples
are redacted to the first and last characters for safety).

## Step 4 -- Export the Audit Log

Every scan, every action, and every status change is recorded in the
immutable audit log.

1. Navigate to **Audit** in the left sidebar (or **Compliance > Audit
   Log** on the asset page for asset-scoped events).
2. Set the date range and filter by event type (e.g., `compliance.scan`,
   `asset.published`, `gdpr.erasure`).
3. Click **Export** and choose the format:
   - **CSV** -- for spreadsheet review.
   - **JSON** -- for programmatic ingestion into SIEM or GRC tools.
4. The file downloads immediately for small result sets or is sent to your
   email for larger exports.

**CLI alternative:**

```bash
datahub audit export \
  --from 2026-04-01 \
  --to 2026-04-09 \
  --format csv \
  --output audit_report.csv
```

## What You Just Did

- Reviewed the compliance posture dashboard.
- Ran a compliance scan on a specific asset.
- Interpreted per-column PII detections and risk levels.
- Exported an audit log for regulatory review.

## Next Steps

- [How to Run a Compliance Scan (detailed)](how-to/run-compliance-scan.md)
- [How to Export Audit Logs](how-to/export-audit-logs.md)
- [How to Configure GDPR Data Subject Rights](how-to/configure-gdpr-rights.md)
- [Full Reference (API / CLI / SDK)](reference.md)
