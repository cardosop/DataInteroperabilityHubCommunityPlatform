# RB-ASSETS-001 — Asset Creation & Lifecycle Operations

**Date:** 2026-05-20
**Feature flag:** `asset_creation_enabled` (GA, default-on)
**Audit event:** `ASSET_CREATED`, `ASSET_ACTIVATED`, `ASSET_DELETED`, `ASSET_VERSION_CREATED`

## 1. Overview

Operational procedure for the asset lifecycle — creation, activation, versioning,
and deletion. Covers the asset creation saga (Phase 240), fail-closed compliance
gate (Phase 283.2.6), and asset auto-activation (284.C).

## 2. When This Runbook Fires

- **Prometheus alert `AssetCreationFailed`** — asset creation saga step fails.
- **Prometheus alert `AssetActivationStuck`** — asset in PENDING_ACTIVATION > 1h.
- **Support escalation** — user reports "my asset won't create" or "asset stuck".
- **Scheduled asset audit** — monthly review of orphaned/deactivated assets.

## 3. Scope

1. **Asset creation saga** — multi-step orchestration: metadata ingest → compliance
   scan → contract validation → activation. Each step has a compensation handler.
2. **Compliance gate (fail-closed)** — when `compliance_fail_closed_enabled=True`,
   non-compliant assets are rejected at creation time.
3. **Asset versioning** — immutable versions created on each update; rollback
   support via `POST /api/v1/assets/{id}/versions/{vid}/rollback/`.
4. **Asset deletion** — soft-delete with retention period; hard-delete after
   retention expiry. Orphaned assets cleaned up by `cleanup_orphan_assets` job.
5. **Auto-activation (284.C)** — when `asset_auto_activate_on_gate_pass=True`,
   assets auto-activate after successful compliance + contract validation.
6. **Dark mode** — asset detail pages render correctly in dark theme; verified
   via Chromatic visual regression on every PR.
7. **Accessibility (a11y)** — asset creation wizard and detail pages pass
   `@axe-core` audits at CI; violations block merge.

## 4. Investigation Procedure

### 4.1 — Confirm asset state

```sql
SELECT id, tenant_id, status, compliance_status, created_at, updated_at
FROM assets
WHERE id = '<asset-uuid>';
```

Asset status values: `DRAFT`, `PENDING_COMPLIANCE`, `PENDING_CONTRACT`,
`PENDING_ACTIVATION`, `ACTIVE`, `FAILED`, `DELETED`.

### 4.2 — Check saga step history

```
GET /api/v1/assets/{id}/saga-steps/
```

Each step has `status` (PENDING/IN_PROGRESS/COMPLETED/FAILED/COMPENSATED) and
`compensation_status`.

### 4.3 — Check compliance scan

```
GET /api/v1/compliance/runs/?asset_id={id}&ordering=-created_at
```

If the compliance run failed, investigate the scanner logs.

### 4.4 — Check contract validation

```sql
SELECT id, status, validation_errors
FROM contract_validations
WHERE asset_id = '<asset-uuid>'
ORDER BY created_at DESC LIMIT 1;
```

## 5. Remediation

### Asset stuck in PENDING_COMPLIANCE

1. Check compliance-service health: `kubectl get pods -n hub-staging -l app=compliance-service`
2. Check Redis queue depth: `rq info --url $REDIS_URL --queue job_critical`
3. If scanner backlog, scale workers: `kubectl scale deploy hub-worker-heavy --replicas=4`
4. Re-trigger scan: `POST /api/v1/compliance/runs/ {asset_id: "<id>"}`

### Asset activation failed

1. Check contract validation errors in the saga step details
2. Verify required business rules passed: `GET /api/v1/health/business-rules`
3. Manual activation via admin API: `POST /api/v1/admin/assets/{id}/activate/`

### Orphaned asset cleanup

```bash
python manage.py cleanup_orphan_drafts --dry-run
python manage.py cleanup_orphan_drafts --older-than 30d
```

## 6. Forensic Queries

```python
# python manage.py shell
from hub.apps.assets.models import Asset, AssetStatus
from django.utils import timezone
from datetime import timedelta

# Assets stuck in non-terminal state > 1h
stuck = Asset.objects.filter(
    status__in=[
        AssetStatus.PENDING_COMPLIANCE,
        AssetStatus.PENDING_CONTRACT,
        AssetStatus.PENDING_ACTIVATION,
    ],
    updated_at__lt=timezone.now() - timedelta(hours=1),
).count()
print(f"Stuck assets: {stuck}")

# Failed creations in last 24h
recent_failures = Asset.objects.filter(
    status=AssetStatus.FAILED,
    updated_at__gte=timezone.now() - timedelta(hours=24),
).count()
print(f"Failed in 24h: {recent_failures}")
```

## 7. Related

- **Spec**: `openspec/changes/preprod01/specs/asset-creation/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 240 (Asset Creation), 283.2.6 (Compliance Gate), 284.C (Auto-Activation)
- **Code**:
  - `hub/apps/assets/models.py` — `Asset`, `AssetVersion`
  - `hub/apps/assets/views.py` — `AssetViewSet`
  - `hub/apps/orchestration/workflows/asset_activation_saga.py` — asset creation saga steps
  - `hub/apps/compliance/models.py` — `ComplianceRun`
- **Alerts**: `monitoring/prometheus/alerts/asset-operations.yml`
- **Dashboard**: `monitoring/grafana/dashboards/assets-overview.json`
- **Cross-runbook**:
  - [`RB-COMP-001-compliance-fail-closed.md`](RB-COMP-001-compliance-fail-closed.md)
  - [`asset-creation.md`](asset-creation.md) — legacy asset creation runbook
  - [`asset-saga-mutation-testing.md`](asset-saga-mutation-testing.md)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
