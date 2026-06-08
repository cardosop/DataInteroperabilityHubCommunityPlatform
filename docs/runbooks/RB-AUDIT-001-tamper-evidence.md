# RB-AUDIT-001 — Audit Trail & Tamper Evidence

**Date:** 2026-05-20
**Feature flag:** N/A (platform-level infrastructure)
**Audit event:** `AUDIT_EVENT_CREATED`, `MERKLE_ROOT_PUBLISHED`, `TAMPER_EVIDENCE_VERIFIED`, `TAMPER_EVIDENCE_FAILED`

## 1. Overview

Operational procedure for the audit trail subsystem — event ingestion,
tamper-evidence chain (Merkle tree), retention policies, and forensic
verification. Covers the Phase 274.16 audit hardening and Phase
234.5 retention policy enforcement.

## 2. When This Runbook Fires

- **Prometheus alert `AuditWriteFailure`** — audit events failing to persist.
- **Prometheus alert `TamperEvidenceFailed`** — Merkle root verification fails.
- **Scheduled audit retention job** — monthly enforcement of retention windows.
- **Compliance audit request** — external auditor requests evidence pack.
- **Security incident** — forensic investigation requires audit trail replay.

## 3. Scope

1. **Audit event ingestion** — all mutation endpoints emit audit events via
   `create_audit_event()`. Events are written to the `audit_events` table
   with tenant-scoped RLS.
2. **Tamper-evidence chain** — Merkle tree over audit events. Each hour's
   events are hashed into a Merkle root, published to an append-only log
   and optionally anchored to a public blockchain (Phase 274.16).
3. **Retention policies** — configurable per event category:
   - `business_rules`: 30 days
   - `compliance`: 7 years
   - `security`: 7 years
   - `billing`: 7 years
   - `general`: 90 days
   Retention enforced by `enforce_audit_retention` cron job.
4. **Forensic verification** — `verify_tamper_evidence` management command
   rebuilds Merkle tree from raw events and compares against published roots.

## 4. Investigation Procedure

### 4.1 — Check audit event throughput

```
GET /api/v1/admin/audit/stats/?since=1h
```

Returns: total events, events by action, events by tenant, write latency p95.

### 4.2 — Verify tamper-evidence chain

```bash
python manage.py verify_tamper_evidence --since 24h
```

Output: `VERIFIED` (all roots match), `MISMATCH` (tampering detected for
specific hours), `MISSING` (no root published for an hour).

### 4.3 — Check retention enforcement

```bash
python manage.py enforce_audit_retention --dry-run
```

Shows events that would be deleted without executing.

### 4.4 — Tamper evidence failure investigation

If `verify_tamper_evidence` returns MISMATCH:

```sql
-- Find affected events
SELECT id, event_type, tenant_id, timestamp, merkle_leaf_hash
FROM audit_events
WHERE merkle_root_id = '<affected-root-id>'
ORDER BY timestamp;
```

Cross-reference with application logs and access logs for the affected hour.

## 5. Remediation

### Audit write failure

1. Check database connectivity: `kubectl logs -n hub-staging deployment/api-service`
2. Check disk space on PostgreSQL: audit table can grow large
3. If `audit_events` table is full: run retention enforcement immediately
4. Circuit breaker: audit write failures are non-blocking (events log to
   stdout as fallback)

### Tamper evidence mismatch

1. **DO NOT** modify any audit data — preserve forensic state
2. Isolate the affected node: `kubectl cordon <node>`
3. Take a filesystem snapshot of the PostgreSQL data volume
4. File a security incident per `postmortem-template.md`
5. Engage security team for forensic analysis

### Retention enforcement stuck

1. Check cron job status: `kubectl get cronjob audit-retention-enforcement`
2. Check job logs for the last run
3. If table is very large, increase batch size:
   `python manage.py enforce_audit_retention --batch-size 10000`

## 6. Forensic Queries

```python
# python manage.py shell
from hub.apps.audit.models import AuditEvent
from django.utils import timezone
from datetime import timedelta

# Events by category in last 24h
from django.db.models import Count
by_cat = AuditEvent.objects.filter(
    timestamp__gte=timezone.now() - timedelta(hours=24),
).values("audit_retention_category").annotate(count=Count("id"))
for row in by_cat:
    print(f"{row['audit_retention_category']}: {row['count']}")

# Recent tamper evidence verification results
from hub.apps.audit.models import TamperEvidenceVerification
recent = TamperEvidenceVerification.objects.order_by("-verified_at")[:5]
for v in recent:
    print(f"{v.verified_at}: hour={v.merkle_hour} status={v.status}")
```

## 7. Related

- **Spec**: `openspec/changes/preprod01/specs/audit/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 274.16 (Audit Hardening), 234.5 (Retention)
- **Code**:
  - `hub/apps/audit/models.py` — `AuditEvent`, `MerkleRoot`, `TamperEvidenceVerification`
  - `hub/apps/audit/utils.py` — `create_audit_event`
  - `hub/apps/audit/management/commands/enforce_audit_retention.py`
  - `hub/apps/audit/management/commands/verify_tamper_evidence.py`
- **Alerts**: `monitoring/prometheus/alerts.yml` — `ComplianceAuditLogWriteFailure`
- **Dashboard**: `monitoring/grafana/dashboards/audit-health.json`
- **Cross-runbook**:
  - [`audit-tamper-evidence.md`](audit-tamper-evidence.md) — detailed tamper investigation
  - [`postmortem-template.md`](postmortem-template.md)
  - [`RB-SEC-002-cve-remediation.md`](RB-SEC-002-cve-remediation.md)

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
