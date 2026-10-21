# RB-VIRT-001 — Virtualization Query Failure

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Data virtualization allows querying external data sources (PostgreSQL, MySQL, S3) through the Meshant query engine without ingestion. Failures occur when virtual datasets cannot connect to source systems, queries time out, or schema drift breaks compatibility.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Query returns `SERVICE_UNAVAILABLE` | Source database unreachable |
| `QueryExecution` stuck in RUNNING | Query timeout at source; Prefect worker not picking up |
| Schema mismatch error | Source schema changed; virtual dataset definition stale |
| Credential error | Encrypted source credentials expired or rotated |
| `virtualization_enabled=False` → 403 | Feature flag off for tenant |

## 3. Investigation
1. Check query execution: `GET /api/v1/virtualization/queries/{id}/`
2. Test source connectivity from worker pod
3. Verify credentials via AWS SM: `aws secretsmanager get-secret-value`
4. Check flag: `Tenant.virtualization_enabled`

## 4. Remediation
- **Source unreachable:** Verify network path, credentials, source DB health
- **Query timeout:** Increase `query_timeout_seconds` in virtual dataset config
- **Schema drift:** Re-sync virtual dataset schema from source
- **Credentials:** Rotate and update encrypted source config

## 5. Recovery
1. Fix root cause
2. Re-run query via `POST /api/v1/virtualization/datasets/{id}/query/`
3. Verify results return successfully

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single virtual dataset query failing | Tenant admin |
| P2 | All virtualization queries failing | data-plane-eng@meshant.com |
| P1 | Source credential leak suspected | security@meshant.com |

## 7. Related
- `hub/apps/virtualization/models.py`
- `hub/apps/virtualization/views.py`
- `docs/runbooks/warehouse-connectivity.md`
