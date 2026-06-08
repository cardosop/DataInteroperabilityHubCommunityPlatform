# RB-COMP-010 — Warehouse-Native Compliance Scan Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-19

## 1. Overview

Warehouse-native compliance scans execute PII-detection and regulatory-compliance SQL queries directly against a customer's warehouse via `WarehouseQueryRunner`, without downloading or staging file contents in Meshant. The scan identifies columns containing PII (email, SSN, credit card, phone, etc.), evaluates policy compliance via the hub's policy engine, and emits `COMPLIANCE_WAREHOUSE_SCANNED` audit events. Failures fall into three categories: scan execution failure (warehouse unreachable, query timeout), PII detection timeout (query runs too long for large tables), and retention query errors (warehouse-side constraints block inspection).

The execution flow: `POST /api/v1/compliance/runs/{id}/scan-warehouse/` → Prefect flow `run_warehouse_compliance` → `WarehouseQueryRunner` → customer warehouse → policy evaluation callback to hub. Stuck runs (RUNNING or QUEUED for >2× timeout) are cleaned up by `detect_stuck_dq_compliance_runs` (every 15 min) and marked `FAILED` with `error_code: STUCK_RUN_DETECTED`.

## 2. Symptoms

| Symptom | Likely Cause |
|---------|-------------|
| `WAREHOUSE_UNREACHABLE` in compliance run | Warehouse paused, network partition, or credential expired |
| `WAREHOUSE_COMPLIANCE_SCAN_FAILED` audit event | Scan SQL execution failed; check Prefect flow logs for the specific error |
| Compliance run stuck in `RUNNING` >2× timeout | Prefect worker crash; hub PATCH retries exhausted; stuck-run detector will clean up |
| Compliance run stuck in `QUEUED` >60 min | Compliance service accepted the job but never transitioned to RUNNING; service crash or queue loss |
| PII detection returns 0 columns on known-PII table | `table_fqn` incorrect; warehouse dialect causing column-name mismatch; sampling threshold too low |
| Policy evaluation returns unexpected `allowed_to_store=false` | `compliance_fail_closed_enabled` flag ON; warehouse scan detected PII above tenant's risk threshold |
| `retention query error` in run metadata | Warehouse-side constraints (row-level security, column masking, time-travel limitations) block the inspection query |
| `stuck_runs_detected_total{run_type="compliance"}` or `{run_type="compliance_queued"}` increments | Stuck-run detector found orphaned RUNNING or stale QUEUED runs |
| `COMPLIANCE_RUN_STUCK_DETECTED` audit event | Stuck-run detector marked a compliance run FAILED |
| `WAREHOUSE_QUERY_TIMEOUT` error | `query_timeout_seconds` exceeded; table larger than expected or warehouse under-provisioned |

## 3. Investigation

### 3.1 Check the compliance run status
```bash
# Via CLI
datahub compliance get <run_id>

# Via API
curl -s /api/v1/compliance/runs/<run_id>/ | jq '{status, scan_mode, risk_level, allowed_to_store, error_code, error_message, warehouse_config}'
```

### 3.2 Check Prefect flow run logs
```bash
prefect flow-run logs <flow_run_id>
```
Look for: `warehouse_compliance_flow_failed`, `compliance_scan_failed`, `failed_to_patch_compliance_run`. The flow emits structured log lines with the `compliance_run_id` for correlation.

### 3.3 Verify the scan findings
```bash
curl -s /api/v1/compliance/runs/<run_id>/results/ | jq '{
  overall_status,
  risk_level,
  allowed_to_store,
  score_breakdown,
  violations: [.violations[]? | {column, pii_type, severity}],
  regulations_checked: .risk_assessment.regulations_checked
}'
```

### 3.4 Verify policy evaluation
The compliance flow calls back to the hub for policy evaluation after scans complete. Check:
```bash
# Hub-side policy evaluation logs
kubectl logs -l app.kubernetes.io/component=api --tail=200 | grep "evaluate_compliance_policy\|compliance_run_id=$run_id"
```

### 3.5 Check warehouse query runner (shared with DQ)
Follow the investigation steps in `RB-DQ-003-warehouse-query-runner.md` §3 for driver availability, credential resolution, and connectivity testing.

### 3.6 Check for stale QUEUED runs
```bash
python manage.py detect_stuck_dq_compliance_runs --direction=compliance --dry-run
```
This dry-run reports QUEUED runs older than `--stale-queued-minutes` (default 60 min) without modifying them.

### 3.7 Prometheus queries
```promql
# Compliance run failure rate by scan mode
sum(rate(compliance_runs_total{status="FAILED"}[15m])) by (scan_mode)

# Stuck compliance run detection rate
rate(stuck_runs_detected_total{run_type=~"compliance.*"}[15m])

# Policy evaluation: fail-closed gate activations
rate(compliance_intake_gate_events_total{event="ACTIVATION_GATE_BLOCK"}[1h])
```

## 4. Remediation

### 4.1 Scan execution failure
- **Warehouse unreachable:** Same remediation as `RB-DQ-003` §4.2 — verify warehouse is running, check network path, test connectivity from worker pod.
- **Credential expired:** Update the AWS SM secret. Credentials are resolved per-execution; no restart needed.
- **Query timeout:** Increase `query_timeout_seconds` in the compliance run's `warehouse_config` (default 300 s). For persistent timeouts on large tables, consider adding a sampling step or partitioning the scan by date range.

### 4.2 PII detection timeout
Large tables (>10 M rows) can cause PII-detection queries to exceed the default 300 s timeout.
1. Increase `query_timeout_seconds` in the `warehouse_config` (max 3600 s / 1 h).
2. If the table has a date-partition column, add a `WHERE` clause to the scan SQL to limit the scan window.
3. For persistent timeout on multi-billion-row tables, consider a warehouse-side pre-aggregation step (materialized view, summary table) and scan the summary instead.

### 4.3 Retention query error
Some warehouses apply row-level security or column masking that interferes with compliance inspection queries.
1. Verify the warehouse credential has `UNMASKED` or equivalent read privilege on the target table.
2. For Snowflake: the role must have `SELECT` on the table WITHOUT a masking policy applied, or the masking policy must include an exemption for the compliance service account.
3. For BigQuery: the service account must have `bigquery.tables.getData` at the table level; column-level security policies must exempt the service account.
4. If column masking cannot be bypassed, document the known limitation — those columns will show as `UNKNOWN` in the scan results.

### 4.4 Stuck QUEUED runs
If compliance runs are accumulating in QUEUED:
1. Check the compliance service health: `kubectl get pods -l app.kubernetes.io/component=compliance-service`.
2. Check the RQ queue depth: `datahub jobs queue-depth`.
3. Restart the compliance service if it's crashed: `kubectl rollout restart deployment/<release>-compliance-service`.
4. Manually fail stale QUEUED runs:
   ```bash
   python manage.py detect_stuck_dq_compliance_runs --direction=compliance
   ```

### 4.5 Policy evaluation returning unexpected results
If `allowed_to_store=false` when the operator expects `true`:
1. Check the tenant's `compliance_fail_closed_enabled` flag — when ON, any PII detection above the risk threshold blocks storage.
2. Review the scan findings: `GET /api/v1/compliance/runs/<id>/results/` → `violations`.
3. The fail-closed gate uses `RiskLevel.exceeds(level, threshold)`. If the tenant's threshold is `LOW`, even a single `MEDIUM`-severity finding will block.
4. If the block is a false positive (e.g., a test column named `email` that doesn't contain real PII), add a column exclusion in the scan profile.

## 5. Recovery

1. **Identify** the failure category using §3 investigation.
2. **Apply** the relevant §4 remediation.
3. **Re-create and re-execute** if the original run cannot be retried:
   ```bash
   datahub compliance run \
     --asset-id <id> \
     --scan-mode WAREHOUSE_SQL \
     --warehouse-type SNOWFLAKE \
     --credential-ref <ref> \
     --table-fqn <fqn> \
     --regulations GDPR,HIPAA
   datahub compliance scan-warehouse <new_run_id>
   ```
4. **Monitor** the new run:
   ```bash
   datahub compliance get <run_id>
   ```
5. **Verify** the run reaches `SUCCEEDED`, the `COMPLIANCE_WAREHOUSE_SCANNED` audit event is emitted, and the policy evaluation returns the expected `allowed_to_store` value.

### Recovering after a stuck-run detector sweep
After a worker outage, the stuck-run detector automatically marks orphaned runs FAILED. To re-run affected compliance scans:
```bash
python manage.py shell -c "
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, ScanMode
for r in ComplianceRun.objects.filter(
    status=ComplianceRunStatus.FAILED,
    scan_mode=ScanMode.WAREHOUSE_SQL,
    error_code='STUCK_RUN_DETECTED'
).order_by('-created_at')[:20]:
    print(f'{r.id}  {r.created_at}  tenant={r.tenant_id}')
"
```

## 6. Escalation

| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single tenant's warehouse compliance scan failed (credential/table issue) | Tenant admin + privacy-eng@meshant.com |
| P2 | `stuck_runs_detected_total{run_type="compliance_queued"}` rate > 0 for >2 cycles | privacy-eng@meshant.com (compliance service queue health) |
| P2 | Multiple tenants failing with same warehouse type (dialect regression) | data-platform@meshant.com |
| P1 | `allowed_to_store=false` for a tenant where DPO has explicitly approved storage | privacy-eng@meshant.com + DPO (false-positive blocking storage; regulatory risk) |
| P1 | Compliance scan result data loss (audit events missing, findings not persisted) | SEV1 — page privacy-eng + data-platform on-call |
| P1 | `compliance_fail_closed_enabled` flag accidentally toggled OFF in production | SEV1 — page security@meshant.com (compliance gate bypassed; regulatory exposure) |

## 7. Related

- `docs/runbooks/RB-DQ-002-warehouse-dq-failure.md`
- `docs/runbooks/RB-DQ-003-warehouse-query-runner.md`
- `docs/runbooks/RB-COMP-001-compliance-fail-closed.md`
- `docs/runbooks/compliance-intake-gate.md`
- `docs/runbooks/RB-TRANS-004-warehouse-connectivity-failure.md`
- `docs/runbooks/warehouse-connectivity.md`
- `hub/apps/compliance/views.py` (``scan-warehouse`` action, ``execute_warehouse_compliance_run``)
- `hub/apps/compliance/feature_flags.py` (``check_warehouse_compliance_enabled``)
- `hub/apps/compliance/services.py` (``run_warehouse_compliance``)
- `hub/data_movement/warehouse_query_runner.py`
- `services/prefect-integration/workflows/warehouse_compliance_flow.py`
- `hub/apps/jobs/management/commands/detect_stuck_dq_compliance_runs.py`
- `helm/templates/cronjob/detect-stuck-dq-compliance-runs.yaml`
