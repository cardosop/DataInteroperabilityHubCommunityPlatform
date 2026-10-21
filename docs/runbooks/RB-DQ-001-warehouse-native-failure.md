# RB-DQ-001: Warehouse-Native DQ Execution Failure

## 1. Symptom
A DQ run with `engine=WAREHOUSE_SQL` fails with status `FAILED` and overall_status `UNKNOWN`.

## 2. Impact
DQ checks against the customer's warehouse table did not complete. The asset may be in an unverified state. The intake gate may block further processing if `compliance_fail_closed_enabled=True`.

## 3. Diagnosis
```bash
# Find recent warehouse DQ failures
python hub/manage.py shell -c "
from hub.apps.dq.models import DQRun, DQRunStatus
runs = DQRun.objects.filter(engine='WAREHOUSE_SQL', status=DQRunStatus.FAILED).order_by('-created_at')[:10]
for r in runs:
    err = (r.details_json or {}).get('error', 'unknown')
    print(f'{r.id} | {r.created_at} | {err[:100]}')
"

# Check warehouse connectivity
python hub/manage.py shell -c "
from hub.apps.warehouses.connectors.snowflake import SnowflakeConnector
# Verify credentials resolve and connection succeeds
"
```

## 4. Common Causes
| Cause | Error Code | Fix |
|-------|-----------|-----|
| Warehouse credential expired | `WAREHOUSE_CREDENTIAL_EXPIRED` | Rotate AWS Secrets Manager secret. Update `credential_ref`. |
| Warehouse unreachable | `WAREHOUSE_CONNECTION_FAILED` | Verify network/firewall allows outbound from Prefect worker to warehouse. |
| Query timeout | `WAREHOUSE_QUERY_TIMEOUT` | Increase timeout in `warehouse_config.query_timeout_seconds`. Check if table has grown significantly. |
| Table not found | `WAREHOUSE_TABLE_NOT_FOUND` | Verify `table_fqn` in `warehouse_config`. Table may have been dropped or renamed. |
| Permission denied | `WAREHOUSE_PERMISSION_DENIED` | Warehouse user lacks SELECT on the target table. Grant SELECT permission. |

## 5. Recovery
1. Identify the failing run from the DQ run list in the admin UI or via the query above.
2. Fix the underlying cause (credential rotation, network, permissions).
3. Re-trigger the DQ run via `POST /api/v1/dq/warehouse-run/` with the same parameters.
4. Verify the new run completes with status `SUCCEEDED`.

## 6. Prevention
- Set up AWS Secrets Manager credential rotation alerts (90-day expiry).
- Monitor `dq_warehouse_execution_duration_seconds` metric for trending upward (table growth).
- Run periodic connectivity tests via `POST /api/v1/warehouses/connections/{id}/test/`.

## 7. Escalation
- If credential resolution fails for multiple tenants simultaneously, escalate to AWS IAM/Secrets Manager team.
- If all warehouse DQ runs fail, check Prefect worker health and warehouse network connectivity.
