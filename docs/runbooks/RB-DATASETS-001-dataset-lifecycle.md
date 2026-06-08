# RB-DATASETS-001 — Dataset Lifecycle & Refresh Operations

**Date:** 2026-05-20
**Feature flag:** `datasets_enabled` (GA, default-on)
**Audit event:** `DATASET_CREATED`, `DATASET_REFRESHED`, `DATASET_VERSION_CREATED`, `DATASET_DELETED`

## 1. Overview

Operational procedure for dataset lifecycle — creation, file ingestion, refresh,
versioning, and deletion. Covers the scheduled refresh pipeline (Phase 260),
file-based refresh (Phase 260.4), and dataset version conflict resolution.

## 2. When This Runbook Fires

- **Prometheus alert `DatasetRefreshFailed`** — scheduled or manual refresh fails.
- **Prometheus alert `DatasetVersionConflict`** — concurrent version creation conflict.
- **Support escalation** — user reports "my dataset is empty" or "refresh didn't update".
- **Scheduled data retention enforcement** — monthly job verifies datasets comply
  with retention policies.

## 3. Scope

1. **Dataset creation** — metadata + initial file ingest. Schema inference from
   file headers (CSV, Parquet, JSON).
2. **Refresh lifecycle** — scheduled ingestions, file-based refreshes, manual
   `POST /api/v1/datasets/{id}/refresh/`. Each refresh creates a new
   `DatasetVersion`.
3. **Version management** — immutable versions; diff between versions via
   `GET /api/v1/versioning/diff/datasets/{id}/{v1}/{v2}/`.
4. **File storage** — files stored in S3-compatible object storage; presigned
   URLs for upload/download. Virus scanning on upload (Phase 260.4).
5. **Retention enforcement** — `enforce_data_retention` job archives/deletes
   datasets past their retention period.
6. **API documentation** — full OpenAPI 3.1 spec at `docs/api/openapi.yaml`;
   endpoints documented with `@extend_schema` decorators on all ViewSets.

## 4. Investigation Procedure

### 4.1 — Check dataset state

```sql
SELECT id, tenant_id, name, status, file_count, storage_bytes,
       last_refreshed_at, retention_days, created_at
FROM datasets
WHERE id = '<dataset-uuid>';
```

### 4.2 — Check refresh history

```
GET /api/v1/datasets/{id}/versions/?ordering=-created_at&limit=10
```

Look for: recent `FAILED` versions, refresh duration spikes, storage growth.

### 4.3 — Check file storage health

```bash
# Verify S3 bucket access
aws s3 ls s3://meshant-staging-datasets/{tenant_id}/{dataset_id}/ --profile staging

# Check file count vs database
python manage.py shell -c "
from hub.apps.datasets.models import Dataset
d = Dataset.objects.get(id='<uuid>')
print(f'DB files: {d.file_count}, Storage: {d.storage_bytes} bytes')
"
```

### 4.4 — Check retention enforcement

```sql
-- Datasets past retention that haven't been archived
SELECT id, tenant_id, name, retention_days,
       EXTRACT(DAY FROM (NOW() - created_at)) AS age_days
FROM datasets
WHERE retention_days IS NOT NULL
  AND EXTRACT(DAY FROM (NOW() - created_at)) > retention_days
  AND status != 'ARCHIVED';
```

## 5. Remediation

### Refresh failed — file source error

1. Check the refresh run logs: `GET /api/v1/datasets/{id}/versions/` → find the
   failed version → check `error_details`
2. Common causes: file deleted from source, schema mismatch, encoding change
3. Re-trigger refresh with dry-run first

### Refresh failed — storage capacity

1. Check tenant storage quota: `GET /api/v1/admin/tenants/{id}/limits/`
2. Increase quota if needed or ask tenant to archive old datasets
3. Re-trigger after quota adjustment

### Version conflict

1. Two concurrent refreshes created conflicting versions
2. The latest version timestamp wins — older conflicting version is marked
   `CONFLICT`
3. Manual resolution: roll back to the pre-conflict version and re-trigger

## 6. Forensic Queries

```python
# python manage.py shell
from hub.apps.datasets.models import Dataset, DatasetStatus
from django.utils import timezone
from datetime import timedelta

# Failed refreshes in last 24h
failed = Dataset.objects.filter(
    last_refresh_status='FAILED',
    last_refreshed_at__gte=timezone.now() - timedelta(hours=24),
).count()

# Datasets approaching retention expiry (within 7 days)
from django.db.models import F
expiring = Dataset.objects.raw("""
    SELECT id, name, retention_days,
           EXTRACT(DAY FROM (NOW() - created_at)) AS age
    FROM datasets
    WHERE retention_days IS NOT NULL
      AND retention_days - EXTRACT(DAY FROM (NOW() - created_at)) BETWEEN 0 AND 7
""")
```

## 7. Related

- **Spec**: `openspec/changes/preprod01/specs/datasets-files/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 260 (Datasets & Files)
- **Code**:
  - `hub/apps/datasets/models.py` — `Dataset`
  - `hub/apps/datasets/views.py` — `DatasetViewSet`
  - `hub/apps/datasets/refresh.py` — dataset refresh operations
- **Alerts**: `monitoring/prometheus/alerts/datasets-files.yml`
- **Dashboard**: `monitoring/grafana/dashboards/datasets-files.json`
- **API docs**: `docs/api/openapi.yaml` § Datasets
- **Cross-runbook**:
  - [`RB-DATA-003-dataset-version-conflict.md`](RB-DATA-003-dataset-version-conflict.md)
  - [`RB-DATA-004-file-storage-failure.md`](RB-DATA-004-file-storage-failure.md)
  - [`RB-FILES-001-file-upload-failure.md`](RB-FILES-001-file-upload-failure.md)

## Maintenance

- **Owner**: Data Platform Team
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
