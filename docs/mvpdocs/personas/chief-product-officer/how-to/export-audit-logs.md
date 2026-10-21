# How to Export Audit Logs

Meshant records an immutable audit trail for every action performed on
assets, contracts, marketplace listings, compliance scans, and GDPR
requests. This guide shows how to query, filter, and export those logs
for regulatory reviews, internal investigations, or SIEM integration.

## Prerequisites

- The **compliance_officer** role (grants cross-domain audit read access).
- Knowledge of the date range and event types you need.

## Step 1 -- Browse Audit Events in the UI

1. Navigate to **Audit** in the left sidebar.
2. The default view shows the most recent 50 events across all domains.
3. Use the filter bar to narrow results:
   - **Date range** -- start and end dates.
   - **Event type** -- e.g., `asset.created`, `compliance.scan.completed`,
     `gdpr.erasure.executed`.
   - **Actor** -- the user or service account that performed the action.
   - **Asset** -- scope to a specific asset ID.
   - **Domain** -- scope to a specific organizational domain.

Each event row shows: timestamp, actor, event type, target resource, and
a summary of what changed.

## Step 2 -- Export via the UI

1. After applying your filters, click **Export**.
2. Choose the format:
   - **CSV** -- human-readable, opens in Excel or Google Sheets.
   - **JSON** -- machine-readable, suitable for ingestion into Splunk,
     Elastic, or other SIEM platforms.
   - **PDF** -- formatted report with a cover page, suitable for sharing
     with legal counsel or regulators.
3. For small result sets (under 10,000 events), the download starts
   immediately. For larger exports, Meshant sends a download link to your
   email when the file is ready.

## Step 3 -- Export via the CLI

```bash
# Export last 7 days as CSV
datahub audit export \
  --from 2026-04-02 \
  --to 2026-04-09 \
  --format csv \
  --output audit_week.csv

# Export compliance-related events only
datahub audit export \
  --from 2026-01-01 \
  --to 2026-04-09 \
  --event-type "compliance.*" \
  --format json \
  --output compliance_events.json

# Export events for a specific asset
datahub audit export \
  --asset-id <ASSET_ID> \
  --from 2026-04-01 \
  --to 2026-04-09 \
  --format csv \
  --output asset_audit.csv
```

## Step 4 -- Export via the SDK

```python
from datahub_interoperability import DataHubClient

client = DataHubClient()

events = client.audit.list(
    from_date="2026-04-01",
    to_date="2026-04-09",
    event_type="compliance.*",
    page_size=100,
)

for event in events:
    print(f"{event.timestamp} | {event.actor} | {event.event_type} | {event.target}")
```

For large exports, use the async export method:

```python
export = client.audit.export(
    from_date="2026-01-01",
    to_date="2026-04-09",
    format="json",
)
export.download("audit_q1.json")
```

## Audit Event Schema

Each audit event contains:

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique event identifier |
| timestamp | ISO 8601 | When the event occurred |
| actor | string | User or service account ID |
| event_type | string | Dot-notated event type (e.g., `asset.published`) |
| target_type | string | Resource type (asset, contract, listing) |
| target_id | string | Resource identifier |
| domain | string | Organizational domain |
| details | object | Event-specific payload (before/after values) |

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| Export returns empty file | Filters too restrictive | Broaden the date range or remove event type filter |
| "Permission denied" | Missing compliance_officer role | Request the role from your tenant administrator |
| Email export never arrives | Email delivery issue | Check spam folder; verify email in account settings |

## Next Steps

- [Run a Compliance Scan](run-compliance-scan.md)
- [Configure GDPR Data Subject Rights](configure-gdpr-rights.md)
- [Audit Events Concept](../../../concepts/audit-events.md)
