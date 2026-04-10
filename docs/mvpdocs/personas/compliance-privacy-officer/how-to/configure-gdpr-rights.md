# How to Configure GDPR Data Subject Rights

Under GDPR, data subjects have the right to access, rectify, erase, and
port their personal data. Meshant provides built-in workflows to process
these requests across all assets in your catalog. This guide explains how
to configure and execute each right.

## Prerequisites

- The **compliance_officer** role in Meshant RBAC.
- At least one asset that contains personal data (PII detected by a
  compliance scan).
- Familiarity with your organization's data subject request (DSR) process.

## Overview of Supported Rights

| Right | GDPR Article | Meshant Workflow |
|-------|-------------|-----------------|
| Right to Access | Art. 15 | Search and export all data related to a subject |
| Right to Rectification | Art. 16 | Update incorrect records across assets |
| Right to Erasure | Art. 17 | Delete or anonymize a subject's data |
| Right to Portability | Art. 20 | Export data in a machine-readable format |

## Step 1 -- Enable GDPR Workflows

GDPR rights workflows must be enabled at the tenant level by a platform
administrator. Once enabled, the **GDPR** section appears in the left
sidebar for compliance officers.

Verify that workflows are active:

```bash
datahub gdpr status
```

Expected output:

```
GDPR workflows: enabled
Configured rights: access, rectification, erasure, portability
Notification email: dpo@example.com
```

## Step 2 -- Process a Right-to-Access Request

When a data subject requests access to their data:

### Via the UI

1. Go to **GDPR > New Request**.
2. Select **Right to Access**.
3. Enter the subject identifier (e.g., email address, user ID).
4. Click **Search**. Meshant searches all assets where the identifier
   column matches and presents a list of matching assets and row counts.
5. Click **Generate Export**. The system creates a ZIP archive containing
   the subject's data from each matching asset, formatted as CSV.
6. Download the archive and provide it to the data subject through your
   organization's secure channel.

### Via the CLI

```bash
datahub gdpr access \
  --identifier-column email \
  --identifier-value "subject@example.com" \
  --output subject_data.zip
```

### Via the SDK

```python
from datahub_sdk import MeshantClient

client = MeshantClient()
export = client.gdpr.access(
    identifier_column="email",
    identifier_value="subject@example.com",
)
export.download("subject_data.zip")
```

## Step 3 -- Process a Right-to-Erasure Request

When a data subject requests deletion of their data:

1. Go to **GDPR > New Request** and select **Right to Erasure**.
2. Enter the subject identifier.
3. Meshant shows all matching assets. Review the list and confirm which
   assets should be processed (some may have legal retention obligations).
4. Choose the erasure method:
   - **Delete** -- remove matching rows entirely.
   - **Anonymize** -- replace PII columns with anonymized values while
     preserving non-identifying data for analytics.
5. Click **Execute Erasure**.
6. The system processes each asset, records the action in the audit log,
   and sends a confirmation to the notification email.

**CLI:**

```bash
datahub gdpr erase \
  --identifier-column email \
  --identifier-value "subject@example.com" \
  --method anonymize \
  --confirm
```

The `--confirm` flag skips the interactive confirmation prompt (use in
automated pipelines only).

## Step 4 -- Process a Right-to-Portability Request

Similar to access, but the output is in a structured, machine-readable
format (JSON or Parquet) for transfer to another data controller.

```bash
datahub gdpr portability \
  --identifier-column email \
  --identifier-value "subject@example.com" \
  --format json \
  --output portable_data.json
```

## Step 5 -- Track and Report on Requests

All GDPR requests are logged with timestamps, actors, and outcomes:

```bash
datahub gdpr list --from 2026-01-01 --to 2026-04-09 --format table
```

This produces a table with: request ID, type, subject identifier (hashed),
status, requested date, and completed date. Use this for regulatory
reporting.

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| "GDPR workflows not enabled" | Tenant config missing | Ask platform admin to enable |
| No matching assets found | Identifier column name mismatch | Verify column naming across assets |
| Erasure blocked | Asset has a legal hold | Remove the hold or document the exemption |

## Next Steps

- [Run a Compliance Scan](run-compliance-scan.md)
- [Export Audit Logs](export-audit-logs.md)
- [GDPR Rights Concept](../../../concepts/gdpr-rights.md)
