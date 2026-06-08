# RB-DQ-001 — Data Quality Operations

**Date:** 2026-05-20
**Feature flag:** `data_quality_enabled` (GA, default-on), `data_quality_advanced_enabled` (GA, default-on)
**Audit event:** `DQ_RUN_STARTED`, `DQ_RUN_COMPLETED`, `DQ_RUN_FAILED`, `DQ_ANOMALY_DETECTED`

## 1. Overview

Operational procedure for data quality (DQ) run lifecycle — scheduled DQ scans,
anomaly detection, warehouse-native DQ, and DQ run failure investigation.
Covers both the standard DQ engine and the warehouse-native DQ path (285.10).

## 2. When This Runbook Fires

- **Prometheus alert `HighDQRunFailureRate`** — DQ run failure rate > 2/sec.
- **Prometheus alert `DQAnomalySpike`** — anomaly detection rate spike.
- **Scheduled DQ run failure** — cron-triggered DQ scan returns FAILED.
- **Support escalation** — user reports "my data quality score dropped" or
  "DQ run has been running for hours".

## 3. Scope

1. **Standard DQ engine** — rule-based validation: null checks, range checks,
   uniqueness, referential integrity, custom SQL rules.
2. **Warehouse-native DQ (285.10)** — pushdown DQ to warehouse (Snowflake,
   BigQuery, Redshift) via `warehouse_dq_enabled` flag. Uses warehouse compute;
   avoids pulling data through the hub.
3. **Anomaly detection** — statistical anomaly detection on DQ metrics
   (Z-score, IQR, moving average). Configurable sensitivity per metric.
4. **Advanced quality endpoints** — trends, scorecards, root-cause analysis
   (Phase 240.3.B). Throttled per-endpoint.
5. **DQ run scheduling** — cron-based or event-triggered (on asset
   activation, on scheduled ingestion completion).

## 4. Investigation Procedure

### 4.1 — Check DQ run status

```sql
SELECT id, asset_id, tenant_id, status, rule_framework,
       rules_total, rules_passed, rules_failed, rules_error,
       started_at, completed_at, error_message
FROM dq_runs
WHERE id = '<run-uuid>';
```

### 4.2 — Check rule-level failures

```
GET /api/v1/dq/runs/{id}/rule-results/?status__in=FAILED,ERROR&limit=50
```

### 4.3 — Check warehouse DQ path

```sql
-- For warehouse-native DQ runs
SELECT id, asset_id, warehouse_type, query_id, bytes_scanned,
       execution_time_ms, pushdown_successful
FROM dq_warehouse_runs
WHERE dq_run_id = '<run-uuid>';
```

### 4.4 — Check anomaly detection

```
GET /api/v1/dq/anomalies/?asset_id={id}&since=7d
```

Look for: false positive anomalies, anomaly threshold misconfiguration.

## 5. Remediation

### DQ run failed — rule error

1. Check the specific rule that errored: `GET /api/v1/dq/runs/{id}/rule-results/`
2. Common causes: invalid SQL in custom rule, schema change breaking rule,
   warehouse connection timeout
3. Fix the rule definition or update the schema reference
4. Re-trigger: `POST /api/v1/dq/runs/ {asset_id: "<id>"}`

### DQ run timeout (warehouse-native)

1. Check warehouse query execution time: `dq_warehouse_runs.execution_time_ms`
2. If > 5 min, the warehouse query may need optimization or the scan scope
   may be too large
3. Reduce scan scope or increase timeout in `settings.DQ_WAREHOUSE_TIMEOUT`
4. For Snowflake: check `QUERY_HISTORY` for the query ID

### Anomaly detection false positive

1. Review the anomaly details: metric value, threshold, detection method
2. Adjust sensitivity: `PATCH /api/v1/dq/metrics/{id}/ {anomaly_threshold: X}`
3. If systemic: review the detection baseline period

## 6. Forensic Queries

```python
# python manage.py shell
from hub.apps.dq.models import DqRun, DqRunStatus
from django.utils import timezone
from datetime import timedelta

# DQ run failure rate in last 24h
total = DqRun.objects.filter(
    started_at__gte=timezone.now() - timedelta(hours=24),
).count()
failed = DqRun.objects.filter(
    started_at__gte=timezone.now() - timedelta(hours=24),
    status=DqRunStatus.FAILED,
).count()
print(f"DQ failure rate (24h): {failed}/{total} = {failed/max(total,1)*100:.1f}%")

# Warehouse DQ path usage
from hub.apps.dq.models import DqWarehouseRun
wh_runs = DqWarehouseRun.objects.filter(
    created_at__gte=timezone.now() - timedelta(days=7),
).count()
print(f"Warehouse DQ runs (7d): {wh_runs}")
```

## 7. Related

- **Spec**: `openspec/changes/preprod01/specs/data-quality/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 240.3 (DQ), 285.10 (Warehouse DQ)
- **Code**:
  - `hub/apps/dq/models.py` — `DqRun`, `DqRuleResult`, `DqWarehouseRun`
  - `hub/apps/dq/views.py` — `DqRunViewSet`, `DqQualityViewSet`
  - `hub/apps/dq/tasks.py` — async DQ execution
- **Alerts**: `monitoring/prometheus/alerts/dq.yml`
- **Dashboard**: `monitoring/grafana/dashboards/data-quality.json`
- **Cross-runbook**:
  - [`RB-DQ-002-warehouse-dq-failure.md`](RB-DQ-002-warehouse-dq-failure.md)
  - [`RB-DQ-003-warehouse-query-runner.md`](RB-DQ-003-warehouse-query-runner.md)
  - [`RB-WAREHOUSES-001-connection-failure.md`](RB-WAREHOUSES-001-connection-failure.md)

## Maintenance

- **Owner**: Data Platform Team
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
