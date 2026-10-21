# RB-WAREHOUSES-001 — Warehouse Connection Failure

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Warehouse connections manage customer data warehouse credentials and connectivity. Failures include unreachable endpoints, expired credentials, schema drift detection errors, and read-only violations.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `WAREHOUSE_UNREACHABLE` | Endpoint down, network partition, firewall block |
| Credential validation fails | AWS SM secret rotated or deleted |
| Schema drift unreconciled | Source schema changed; drift detector flagged |
| Connection test timeout | DNS resolution slow; warehouse overloaded |

## 3. Investigation
1. Test connectivity: `python manage.py shell -c "from hub.data_movement.warehouse_query_runner import ..."`
2. Verify credentials: `aws secretsmanager get-secret-value --secret-id <ref>`
3. Check drift status: `GET /api/v1/warehouses/connections/{id}/drift/`
4. Review warehouse alert metrics in Prometheus

## 4. Remediation
- **Unreachable:** Verify VPC peering, PrivateLink, firewall rules
- **Credentials:** Update AWS SM secret; next execution picks up
- **Schema drift:** Re-sync schema; update downstream pipeline configs
- **Timeout:** Increase connection timeout; verify warehouse capacity

## 5. Recovery
1. Fix connectivity or credential issue
2. Re-test connection via API or management command
3. Verify schema drift reconciled
4. Confirm downstream pipelines functional

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single warehouse connection degraded | Tenant admin |
| P2 | All connections for a warehouse type failing | data-plane-eng@meshant.com |
| P1 | Credential secret deleted | SEV1 — security + data-platform on-call |

## 7. Related
- `hub/data_movement/warehouse_query_runner.py`
- `hub/apps/warehouses/models.py`
- `docs/runbooks/warehouse-connectivity.md`
- `docs/runbooks/RB-DQ-002-warehouse-dq-failure.md`
