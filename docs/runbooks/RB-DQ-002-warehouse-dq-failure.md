# RB-DQ-002 — Warehouse-Native DQ Failure

**Owner:** data-platform@meshant.com | **Created:** 2026-05-19

## 1. Overview

Warehouse-native DQ executes data quality checks as SQL queries directly against a customer's warehouse (Snowflake, BigQuery, or Databricks) rather than downloading files and running pandas-based checks on the platform side. Failures in this pipeline can originate from credential expiry, warehouse connectivity loss, SQL compilation errors, query timeouts, or Prefect flow crashes.

The execution flow: `POST /api/v1/dq/runs/{id}/execute-warehouse/` → Prefect flow `run_warehouse_dq` → `WarehouseQueryRunner` → customer warehouse. If the Prefect flow's PATCH back to the hub fails after all retries (3 attempts, 5 s backoff), the stuck-run detector (`detect_stuck_dq_compliance_runs` CronJob, every 15 min) eventually marks the run `FAILED` with `error_code: STUCK_RUN_DETECTED`.

## 2. Symptoms

| Symptom | Likely Cause |
|---------|-------------|
| `WAREHOUSE_QUERY_TIMEOUT` error in DQ run | Query exceeded `query_timeout_seconds`; warehouse overloaded or table larger than expected |
| `WAREHOUSE_UNREACHABLE` error | Network partition, warehouse paused/stopped, firewall rule change |
| DQ run stuck in `RUNNING` >2× timeout | Prefect worker crash; hub PATCH retries exhausted; stuck-run detector will clean up |
| `DQ_WAREHOUSE_EXECUTED` audit event missing | Prefect flow never started; check Prefect deployment health |
| SQL compilation error in `details_json` | `DQWarehouseSQLCompiler` failed on a check definition; invalid SQL dialect for warehouse type |
| `credential_ref` resolution failure | AWS Secrets Manager secret rotated or deleted; IAM permission revoked |
| `READ_ONLY_VIOLATION` error | Warehouse user lacks write permissions; dq-service tried to create temp table/result set |
| `stuck_runs_detected_total{run_type="dq"}` metric increments | Stuck-run detector found orphaned RUNNING runs |

## 3. Investigation

### 3.1 Check the DQ run status and error details
```bash
# Via CLI
datahub dq get <run_id>

# Via API
curl -s /api/v1/dq/runs/<run_id>/ | jq '{status, engine, error_code, error_message, warehouse_config}'
```

### 3.2 Check Prefect flow run logs
```bash
prefect flow-run logs <flow_run_id>
```
Look for: `warehouse_dq_flow_failed`, `warehouse_dq_timeout`, `failed_to_patch_dq_run`.

### 3.3 Verify warehouse connectivity from the worker
```bash
# From the Prefect worker pod / node
python -c "
from hub.apps.transformation.credential_resolver import resolve_warehouse_credentials
profile = resolve_warehouse_credentials('<credential_ref>', profile_name='meshant_dq')
print(profile)
"
```

### 3.4 Check warehouse credential status
```bash
aws secretsmanager describe-secret --secret-id '<credential_ref>' --profile staging
aws secretsmanager get-secret-value --secret-id '<credential_ref>' --profile staging | jq '.SecretString | fromjson'
```
Verify the secret has not been rotated or deleted. Verify the IAM role used by the Prefect worker has `secretsmanager:GetSecretValue` on the ARN.

### 3.5 Check stuck-run detector status
```bash
# Last CronJob run
kubectl get jobs -l app.kubernetes.io/component=detect-stuck-dq-compliance-runs --sort-by=.status.startTime | tail -3

# Recent detections
kubectl logs -l app.kubernetes.io/component=detect-stuck-dq-compliance-runs --tail=50 | grep "stuck_dq_run_detected"
```

### 3.6 Prometheus queries
```promql
# DQ run failure rate by engine
sum(rate(dq_runs_total{status="FAILED"}[15m])) by (engine)

# Stuck DQ run detection rate
rate(stuck_runs_detected_total{run_type="dq"}[15m])

# Warehouse query timeout rate
rate(dq_runs_total{status="FAILED"}[15m]) * on(tenant_id) group_left(warehouse_type) dq_warehouse_config
```

## 4. Remediation

- **Credential expired/rotated:** Update the AWS SM secret value; the next run picks it up (credential resolved per-execution, no restart needed). Rotate with sufficient overlap to avoid in-flight execution windows.
- **Warehouse unreachable:** Verify the warehouse is running (Snowflake: `SHOW WAREHOUSES`; BigQuery: check job status; Databricks: cluster health). Check VPC peering / PrivateLink / firewall rules between the Prefect worker subnet and the warehouse endpoint.
- **Query timeout:** Increase `query_timeout_seconds` in the DQ run's `warehouse_config` (default 300 s). For persistent timeouts, profile the compiled SQL with `EXPLAIN` to identify missing indexes or full scans.
- **SQL compilation error:** Inspect `DQWarehouseSQLCompiler` (``hub/apps/dq/warehouse_sql_compiler.py``) to confirm the check definition is compatible with the target warehouse dialect. Each warehouse type has a dialect-specific compiler path.
- **READ_ONLY_VIOLATION:** The `WarehouseQueryRunner` enforces read-only execution (wraps all queries in read-only transactions). If the check definition includes `INSERT`/`UPDATE`/`DELETE`/`CREATE`, it will be rejected. Rewrite the check as a read-only `SELECT` with aggregate/window functions.
- **Stuck runs:** If the stuck-run detector hasn't fired yet, manually run: `python manage.py detect_stuck_dq_compliance_runs --direction=dq`. The command is idempotent — re-running on already-FAILED runs is a no-op.

## 5. Recovery

1. **Identify root cause** using the investigation steps above.
2. **Fix the underlying issue** (credential, network, SQL, timeout).
3. **Re-create the DQ run** if needed:
   ```bash
   datahub dq run --asset-id <id> --warehouse-type SNOWFLAKE --credential-ref <ref> --table-fqn <fqn>
   datahub dq execute-warehouse <new_run_id>
   ```
4. **Monitor the new run:**
   ```bash
   datahub dq watch <new_run_id> --timeout 600
   ```
5. **Verify** the `DQ_WAREHOUSE_EXECUTED` audit event was emitted and the run reached `SUCCEEDED`.

### Bulk re-run for stuck runs
If multiple runs were orphaned by a worker outage, the stuck-run detector marks them FAILED automatically. For each affected tenant, re-create and re-execute:
```bash
# List failed warehouse DQ runs for a tenant
python manage.py shell -c "
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
for r in DQRun.objects.filter(status=DQRunStatus.FAILED, engine=DQEngine.WAREHOUSE_SQL, error_code='STUCK_RUN_DETECTED').order_by('-created_at')[:20]:
    print(r.id, r.profile_key, r.error_message[:80] if r.error_message else '')
"
```

## 6. Escalation

| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single tenant, single warehouse DQ run failed | Tenant on-call (investigate tenant-side warehouse health) |
| P2 | Multiple tenants failing warehouse DQ with same warehouse type | data-platform@meshant.com (possible dialect adapter regression) |
| P2 | `stuck_runs_detected_total{run_type="dq"}` rate > 0 for >2 cycles (30 min) | data-platform@meshant.com (Prefect worker or CronJob down) |
| P1 | All warehouse DQ runs across all tenants failing | SEV1 — page data-platform on-call immediately |
| P1 | `credential_ref` secret deleted (data loss exposure) | SEV1 — page security@meshant.com + data-platform on-call |

## 7. Related

- `docs/runbooks/RB-DQ-003-warehouse-query-runner.md`
- `docs/runbooks/RB-TRANS-004-warehouse-connectivity-failure.md`
- `docs/runbooks/warehouse-connectivity.md`
- `docs/runbooks/warehouse-dr.md`
- `hub/apps/dq/warehouse_sql_compiler.py`
- `hub/data_movement/warehouse_query_runner.py`
- `services/prefect-integration/workflows/warehouse_dq_flow.py`
- `hub/apps/jobs/management/commands/detect_stuck_dq_compliance_runs.py`
- `hub/apps/transformation/credential_resolver.py`
- `helm/templates/cronjob/detect-stuck-dq-compliance-runs.yaml`
