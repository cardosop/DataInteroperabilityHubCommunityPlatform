# Warehouse Connectivity — Operational Runbook

**Phase 275.E** — Connection troubleshooting for warehouse connectivity.

## 1. Symptom
`POST /api/v1/warehouses/connections/{id}/test/` returns failure.

## 2. Impact
LIVE_QUERY assets cannot serve data. Warehouse-native DQ/Compliance scans fail.

## 3. Diagnosis
```bash
curl -X POST /api/v1/warehouses/connections/{id}/test/ -H "Authorization: Bearer $TOKEN"
```

## 4. Common Causes
| Cause | Fix |
|-------|-----|
| Credential expired | Rotate AWS Secrets Manager secret, update credential_ref |
| Network blocked | Verify NetworkPolicy allows egress 443 to warehouse host |
| Warehouse paused | Resume in provider console |

## 5. Recovery
1. Test connection via API. 2. Fix root cause. 3. Re-test.

## 6. Prevention
Monitor `warehouse_credential_age_days` metric. Set credential rotation alerts at 80 days.

## 7. Escalation
If multiple tenants affected, check warehouse provider status page.
