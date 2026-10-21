# RB-COMP-001: Warehouse-Native Compliance Scan Failure

## 1. Symptom
A Compliance run with `scan_mode=WAREHOUSE_SQL` fails with status `FAILED`. The asset's `allowed_to_store` may default to `False` (fail-closed).

## 2. Impact
Compliance PII/retention/classification checks against the customer's warehouse table did not complete. The intake gate will block asset creation/publishing. Existing assets are unaffected but cannot be re-scanned until the issue is resolved.

## 3. Diagnosis
```bash
# Find recent warehouse compliance failures
python hub/manage.py shell -c "
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
runs = ComplianceRun.objects.filter(scan_mode='WAREHOUSE_SQL', status=ComplianceRunStatus.FAILED).order_by('-created_at')[:10]
for r in runs:
    err = r.error_message or 'unknown'
    print(f'{r.id} | {r.created_at} | {err[:100]}')
"

# Verify warehouse connectivity (same as RB-DQ-001)
```

## 4. Common Causes
Same as RB-DQ-001 plus:

| Cause | Error Code | Fix |
|-------|-----------|-----|
| Regex dialect mismatch | `WAREHOUSE_UNSUPPORTED_DIALECT` | PII pattern regex function not supported on this warehouse type. Check `ComplianceWarehouseSQLCompiler` dialect support. |
| Table schema mismatch | `WAREHOUSE_TABLE_NOT_FOUND` | Expected PII columns (`email`, `phone`, `ssn`, etc.) not found in table. Verify column naming against compliance scan expectations. |

## 5. Recovery
1. Fix the underlying cause (same as RB-DQ-001).
2. Re-trigger the compliance scan via `POST /api/v1/compliance/warehouse-scan/`.
3. If `fail_closed` blocked intake, the asset will need to be re-created or the compliance run re-executed.

## 6. Prevention
- Same as RB-DQ-001 plus:
- Document expected PII column naming conventions for each scan type.
- Monitor `compliance_warehouse_pii_matches` for anomaly spikes (potential false positives from regex pattern changes).

## 7. Escalation
- If PII detection regex patterns produce false positives, escalate to the compliance engineering team for pattern tuning.
- If warehouse-specific SQL dialect issues arise (new warehouse type), escalate to the data platform team for SQL compiler extension.
