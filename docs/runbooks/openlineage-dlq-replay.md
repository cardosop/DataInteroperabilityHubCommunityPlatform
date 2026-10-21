# OpenLineage DLQ replay runbook

**Phase:** 228 F4 (228.F4.25)
**Owner:** Data Platform Eng
**Severity:** P2 (DLQ growing) / P1 (≥1000 pending rows)
**Last reviewed:** 2026-04-30

## When this runbook fires

The OpenLineage adapter dead-letters events that exhausted the
retry budget (5 attempts, exp backoff `1s/2s/4s/8s/16s`). Symptoms:

1. Grafana panel "DLQ pending" climbs above 0 and stays there.
2. Alert `LineageEdgeBackfillDrift` (or a future OpenLineage-specific
   alert) fires.
3. Customer reports "events not appearing in Marquez".

## TL;DR — replay

```bash
# Inspect what's pending — read-only, fast.
python /app/hub/manage.py replay_openlineage_dlq --dry-run --max=100

# Replay up to 100 rows. Bumps replay_attempts; rows that
# permanently fail after 10 attempts are flagged.
python /app/hub/manage.py replay_openlineage_dlq --max=500
```

The command outputs a structured JSON report:

```json
{
  "phase": "228.F4.12",
  "dry_run": false,
  "max_rows": 500,
  "processed": 12,
  "replayed_ok": 8,
  "replayed_dead": 4,
  "permanently_failed_now": 0
}
```

## Investigating individual DLQ rows

Open one row in `python manage.py shell`:

```python
from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter

row = OpenLineageDeadLetter.objects.first()
print("event_id:", row.event_id)
print("failure_reason:", row.failure_reason)
print("attempts:", row.attempts, "/", "replay_attempts:", row.replay_attempts)
print("permanently_failed:", row.permanently_failed)
# Decrypt the payload (NEVER log the result):
event = row.event_payload
print("eventType:", event["eventType"], "runId:", event["run"]["runId"])
```

## Common DLQ causes

| `failure_reason` | Diagnosis | Action |
|---|---|---|
| `http_400` | Marquez rejected the schema | Check `failure_detail` for the validation error. Likely Marquez-version skew. Upgrade Marquez per `marquez-upgrade.md`. |
| `http_401` / `http_403` | Auth misconfig | Verify Marquez admin key in AWS Secrets Manager (`meshant/staging/openlineage/marquez_admin`). |
| `http_404` | Wrong target URL | Check `OPENLINEAGE_URL` env var matches the deployed Marquez. |
| `http_5xx` repeated | Marquez instability | See `marquez-outage.md`. |
| `network_error` | Hub ↔ Marquez network | Verify VPC peering / NetworkPolicy / mTLS cert. |

## When replay does not converge

Rows with `replay_attempts >= 10` are flagged `permanently_failed=True`. The replay sweep skips them automatically. Manual investigation:

```python
perm = OpenLineageDeadLetter.objects.filter(permanently_failed=True)
for row in perm[:10]:
    print(row.id, row.event_id, row.failure_reason, row.failure_detail[:200])
```

If the underlying receiver issue is fixed, manually un-flag the rows + re-run the sweep:

```python
# DANGEROUS — only after confirming the root cause is fixed.
OpenLineageDeadLetter.objects.filter(permanently_failed=True).update(
    permanently_failed=False, replay_attempts=0,
)
```

Then run `replay_openlineage_dlq --max=10000` to drain.

## Escalation

| State | Severity | Action |
|---|---|---|
| <100 pending rows, replay running | P3 | Continue. |
| 100–1000 pending, growing | P2 | Investigate the failure_reason cohort; page during business hours. |
| >1000 pending OR >100 permanently_failed | P1 | Page on-call immediately. Likely Marquez outage — see `marquez-outage.md`. |

## Related

- [REQ-LIN-F4-002 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md)
- [Marquez outage runbook](marquez-outage.md)
- [OpenLineage integration doc](../integrations/openlineage.md)
- Source: [`hub/apps/integrations/openlineage/tasks.py`](../../hub/apps/integrations/openlineage/tasks.py)
