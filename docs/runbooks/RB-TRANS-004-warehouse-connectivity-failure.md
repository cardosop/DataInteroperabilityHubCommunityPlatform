# RB-TRANS-004: Warehouse Connectivity Failure

**Owner:** Data Platform Team
**Severity:** Critical
**Runbook ID:** RB-TRANS-004

---

## 1. Overview

This runbook covers failures to connect to the customer's data warehouse during dbt transformation execution. Warehouse connectivity is required for: credential resolution, dbt command execution, INFORMATION_SCHEMA queries (validation), and output registration.

## 2. Symptoms

- `CredentialResolverError: Access denied for secret` when resolving credentials
- `VALIDATION_QUERY_FAILED` on the validate-output endpoint
- `DBT_EXECUTION_FAILED` with "Database Error" or "connection refused" in dbt logs
- `_GenericConnector.connect()` raises `ModuleNotFoundError` (driver not installed)
- Prefect flow times out waiting for warehouse response

## 3. Diagnosis

### 3.1 Check AWS Secrets Manager access
```bash
aws secretsmanager get-secret-value \
  --secret-id <warehouse_credential_ref> \
  --region us-east-1
```
If this returns `AccessDeniedException`, the Prefect worker IAM role lacks permission.

### 3.2 Check warehouse driver availability
```bash
# In the Prefect worker container
pip list | grep -E "snowflake|bigquery|databricks"
```

### 3.3 Test warehouse connection
For Snowflake:
```bash
python -c "
import snowflake.connector
conn = snowflake.connector.connect(
    account='...', user='...', password='...',
    warehouse='...', database='...', schema='...'
)
print('Connected')
conn.close()
"
```

### 3.4 Check network connectivity
```bash
# From the worker node
nc -zv <warehouse_host> <port>
# Snowflake: <account>.snowflakecomputing.com:443
# BigQuery: bigquery.googleapis.com:443
# Databricks: <workspace>.cloud.databricks.com:443
```

### 3.5 Check circuit breaker
```bash
# If circuit breaker is open, all warehouse calls are blocked
python hub/manage.py check_circuit_breaker --channel warehouse_snowflake_<tenant_id>
```

## 4. Impact

- All pipeline executions for the affected tenant/warehouse fail
- `TRANSFORMATION_FAILED` audit events are emitted for each attempt
- Tenant's `max_transformation_runs_per_month` quota is consumed by failed attempts
- Downstream data products are not refreshed

## 5. Resolution

### 5.1 AWS SM access denied
1. Verify the IAM role attached to the Prefect worker has:
   ```json
   {
     "Effect": "Allow",
     "Action": "secretsmanager:GetSecretValue",
     "Resource": "<warehouse_credential_ref>"
   }
   ```
2. Check if the secret was deleted or moved to a different region
3. Update the `warehouse_credential_ref` on the pipeline to the correct ARN

### 5.2 Driver not installed
```bash
# In the Prefect worker container
pip install snowflake-connector-python  # or google-cloud-bigquery / databricks-sql-connector
```

### 5.3 Network connectivity
1. Verify the worker node's security group allows outbound to the warehouse
2. Check VPC peering / PrivateLink configuration for private warehouse endpoints
3. Verify DNS resolution: `nslookup <warehouse_host>`

### 5.4 Credential rotation
If credentials were rotated:
1. Update the AWS SM secret with new credentials
2. The credential resolver fetches the latest version on every call (no caching)
3. Next pipeline execution will pick up new credentials automatically
4. No restart required

### 5.5 Circuit breaker
```bash
python hub/manage.py reset_circuit_breaker --channel warehouse_snowflake_<tenant_id>
```
Only reset after verifying the underlying issue is resolved.

## 6. Escalation

| Level | Contact | When |
|-------|---------|------|
| L1 | Data Platform on-call | Any warehouse connectivity failure |
| L2 | Cloud Infrastructure team | Network/VPC/PrivateLink issues |
| L3 | Warehouse DBA | Persistent warehouse errors (not network) |
| L4 | AWS IAM admin | Secrets Manager permission issues |
| L5 | Security team | Credential rotation / access denied pattern |

## 7. Prevention

- Set up warehouse connection health checks (periodic `SELECT 1` via circuit breaker health endpoint)
- Monitor `TRANSFORMATION_FAILED` rate per tenant
- Set up AWS CloudWatch alarms on `AccessDeniedException` for transformation secrets
- Rotate credentials with sufficient overlap (old + new both valid during transition)
- Keep warehouse driver packages pinned and tested in CI
- Document warehouse compatibility matrix in PRODUCT_GUIDE.md
