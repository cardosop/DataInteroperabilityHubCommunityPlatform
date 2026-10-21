# RB-DQ-003 — Warehouse Query Runner Failure

**Owner:** data-platform@meshant.com | **Created:** 2026-05-19

## 1. Overview

The `WarehouseQueryRunner` (`hub/data_movement/warehouse_query_runner.py`) is the shared execution layer for both warehouse-native DQ and warehouse-native compliance. It resolves warehouse credentials, establishes a read-only connection via the appropriate Python driver (snowflake-connector-python, google-cloud-bigquery, databricks-sql-connector), executes compiled SQL checks, and returns structured results. This runbook covers failures specific to the query-runner layer — connectivity issues, dialect mismatches, and the read-only enforcement guard — that are NOT caused by the higher-level DQ or compliance workflow logic.

## 2. Symptoms

| Symptom | Likely Cause |
|---------|-------------|
| `WAREHOUSE_UNREACHABLE` in both DQ and compliance runs | Warehouse endpoint DNS resolution failure, network partition, or driver installation missing |
| Connection timeout after ~30 s | Firewall blocking outbound port; VPC peering misconfigured; PrivateLink endpoint not accepted |
| `snowflake.connector.errors.ProgrammingError` | Invalid warehouse/database/schema in `table_fqn`; role lacks USAGE privilege |
| `google.api_core.exceptions.Forbidden` (BigQuery) | Service account lacks `bigquery.jobs.create` or `bigquery.tables.getData` |
| `databricks.sql.exc.ServerOperationError` | Cluster stopped; HTTP path changed; personal access token expired |
| Query returns 0 rows when data is expected | `table_fqn` resolves to wrong catalog/schema; case-sensitivity mismatch (Snowflake uppercases unquoted identifiers) |
| `READ_ONLY_VIOLATION` error | Compiled SQL contains write operations; the read-only guard rejected the query before execution |
| Dialect-specific SQL compilation failure | Check definition uses syntax unsupported by the target warehouse (e.g., BigQuery `QUALIFY` on Snowflake, Snowflake `FLATTEN` on Databricks) |
| `ModuleNotFoundError: No module named 'snowflake'` / `'google.cloud'` / `'databricks'` | Warehouse driver not installed in the Prefect worker image |

## 3. Investigation

### 3.1 Verify driver availability
```bash
# From the Prefect worker pod
python -c "
try:
    import snowflake.connector; print('Snowflake: OK')
except ImportError: print('Snowflake: MISSING')
try:
    from google.cloud import bigquery; print('BigQuery: OK')
except ImportError: print('BigQuery: MISSING')
try:
    from databricks import sql; print('Databricks: OK')
except ImportError: print('Databricks: MISSING')
"
```

### 3.2 Test credential resolution
```bash
python -c "
from hub.apps.transformation.credential_resolver import resolve_warehouse_credentials
import json
try:
    profile = resolve_warehouse_credentials('<credential_ref>', profile_name='meshant_dq')
    # Mask secrets before printing
    safe = json.loads(json.dumps(profile))
    if 'password' in safe: safe['password'] = '***'
    print(json.dumps(safe, indent=2))
except Exception as e:
    print(f'FAILED: {e}')
"
```

### 3.3 Test direct warehouse connectivity
```python
# Snowflake
import snowflake.connector
conn = snowflake.connector.connect(
    account='<account>',
    user='<user>',
    password='<password>',
    warehouse='<warehouse>',
    database='<database>',
    schema='<schema>',
)
cur = conn.cursor()
cur.execute("SELECT 1 AS connectivity_test")
print(cur.fetchone())
conn.close()
```

### 3.4 Verify the compiled SQL dialect
```bash
# The compiled SQL is logged in the Prefect flow run
prefect flow-run logs <flow_run_id> | grep -A5 "compiled_sql"
```
Cross-reference the compiled SQL against the warehouse-specific dialect documentation. Each warehouse type has a dedicated compiler in `DQWarehouseSQLCompiler` that should produce dialect-correct SQL. If the emitted SQL doesn't parse, check the compiler mapping for the warehouse type.

### 3.5 Check the read-only guard
```bash
grep -n "READ_ONLY_VIOLATION\|_enforce_read_only\|read.only" hub/data_movement/warehouse_query_runner.py
```
The guard inspects the SQL text before execution. It blocks statements containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `MERGE`, `GRANT`, `REVOKE` (case-insensitive). If a legitimate read-only query is being blocked, verify the SQL doesn't contain these keywords in comments or string literals (the guard uses simple keyword matching, not a full SQL parser).

### 3.6 Prometheus queries
```promql
# Warehouse query error rate by warehouse type
sum(rate(dq_runs_total{status="FAILED"}[15m])) by (engine)

# Cross-reference with stuck-run detection
stuck_runs_detected_total{run_type="dq"}
```

## 4. Remediation

### 4.1 Missing driver
Add the driver to the Prefect worker image:
```dockerfile
# In the worker Dockerfile
RUN pip install snowflake-connector-python google-cloud-bigquery databricks-sql-connector
```
Rebuild, push, and redeploy the worker image. Verify with the driver availability check in §3.1.

### 4.2 Warehouse connectivity failure
1. Confirm the warehouse is running (not paused, stopped, or in maintenance).
2. Verify network path: the Prefect worker pod must be able to reach the warehouse endpoint on the driver-specific port:
   - Snowflake: TCP 443 to `<account>.snowflakecomputing.com`
   - BigQuery: TCP 443 to `bigquery.googleapis.com`
   - Databricks: TCP 443 to `<workspace>.cloud.databricks.com`
3. Test from the worker pod: `nc -zv <host> 443` or `curl -v https://<host>`.
4. If using AWS PrivateLink / VPC peering, verify the endpoint is `available` and the route table entries are correct.

### 4.3 Credential mismatch
1. Verify the AWS SM secret value matches the warehouse credentials.
2. For Snowflake: confirm `account`, `user`, `password`, `warehouse`, `database`, `schema` keys.
3. For BigQuery: confirm the secret contains a valid service-account JSON key with `bigquery.jobs.create` and `bigquery.tables.getData` permissions.
4. For Databricks: confirm `server_hostname`, `http_path`, `access_token` keys.

### 4.4 Dialect-specific SQL
If a check definition compiles to SQL that fails on the target warehouse:
1. Identify the check that failed from the DQ run's `checks_json`.
2. Review the compiled SQL in the Prefect flow logs.
3. Either fix the check definition to use dialect-compatible syntax, or mark the check as warehouse-incompatible in the profile definition.
4. Each warehouse type has known dialect constraints:
   - **Snowflake**: identifiers are uppercased unless quoted; use `IDENTIFIER()` for dynamic references.
   - **BigQuery**: backticks for identifiers; `STRUCT`/`ARRAY` types need special handling; `LIMIT` clause required for `QUALIFY`.
   - **Databricks**: Spark SQL dialect; `FLOAT` is `DOUBLE`; `VARCHAR` without length spec; limited DDL in SQL warehouses.

### 4.5 Read-only guard false positive
If a legitimate query is blocked:
```python
# Temporary override (emergency only — requires code change):
# In warehouse_query_runner.py, add the specific SQL pattern to the allowlist
# NEVER disable the guard globally — it exists to prevent accidental writes
# to customer warehouses.
```
For production, fix the SQL to avoid the blocked keywords (e.g., rename a column alias `delete_flag` to `removal_flag` if the parser is matching `DELETE` in a comment).

## 5. Recovery

1. **Diagnose** using §3 investigation steps.
2. **Apply** the relevant §4 remediation.
3. **Re-run** the failed DQ or compliance execution:
   ```bash
   # DQ
   datahub dq execute-warehouse <run_id>
   # Compliance
   datahub compliance scan-warehouse <run_id>
   ```
4. **Monitor** with `datahub dq watch <run_id> --timeout 600` or the equivalent compliance command.
5. **Verify** the run reaches `SUCCEEDED` and the appropriate audit event is emitted.

### Recovering multiple runs after a driver installation fix
```bash
# List all WAREHOUSE_SQL runs that failed with WAREHOUSE_UNREACHABLE
python manage.py shell -c "
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, ScanMode

# DQ
for r in DQRun.objects.filter(status=DQRunStatus.FAILED, engine=DQEngine.WAREHOUSE_SQL).order_by('-created_at')[:20]:
    err = (r.details_json or {}).get('error', '')
    if 'UNREACHABLE' in str(err) or 'ModuleNotFoundError' in str(err):
        print(f'DQ  {r.id}  {r.created_at}  {err[:80]}')

# Compliance
for r in ComplianceRun.objects.filter(status=ComplianceRunStatus.FAILED, scan_mode=ScanMode.WAREHOUSE_SQL).order_by('-created_at')[:20]:
    err = (r.metadata_json or {}).get('error', '')
    if 'UNREACHABLE' in str(err) or 'ModuleNotFoundError' in str(err):
        print(f'CMP {r.id}  {r.created_at}  {err[:80]}')
"
```

## 6. Escalation

| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single warehouse type driver missing in worker image | data-platform@meshant.com (Dockerfile update + rebuild) |
| P3 | Single tenant's credential_ref secret misconfigured | Tenant admin (secret owned by tenant) |
| P2 | Warehouse host unreachable from worker subnet | Infrastructure on-call (VPC / PrivateLink / firewall) |
| P2 | Dialect regression in `DQWarehouseSQLCompiler` for a specific warehouse type | data-platform@meshant.com (compiler regression) |
| P1 | All warehouse types failing for all tenants | SEV1 — page data-platform on-call (likely worker-image regression or network outage) |
| P1 | Read-only guard disabled or bypassed in production | SEV1 — page security@meshant.com immediately (customer data at risk) |

## 7. Related

- `docs/runbooks/RB-DQ-002-warehouse-dq-failure.md`
- `docs/runbooks/RB-COMP-010-warehouse-compliance-failure.md`
- `docs/runbooks/RB-TRANS-004-warehouse-connectivity-failure.md`
- `docs/runbooks/warehouse-connectivity.md`
- `docs/runbooks/warehouse-dr.md`
- `hub/data_movement/warehouse_query_runner.py`
- `hub/apps/dq/warehouse_sql_compiler.py`
- `hub/apps/transformation/credential_resolver.py`
- `services/prefect-integration/workflows/warehouse_dq_flow.py`
- `services/prefect-integration/workflows/warehouse_compliance_flow.py`
- `helm/templates/cronjob/detect-stuck-dq-compliance-runs.yaml`
