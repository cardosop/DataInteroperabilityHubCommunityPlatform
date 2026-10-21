# RB-GDPR-001 — Data Export / Erasure Request Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
GDPR subsystem handles DataExportJob (right of access, Art. 15) and ErasureRequest (right to erasure, Art. 17). Failures occur when data cannot be located, exports time out, or erasure cascades fail.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `DataExportJob` stuck in PENDING | Worker not processing export queue |
| Export file empty or incomplete | Data subject has no records in tenant |
| `ErasureRequest` partially completed | Cascade delete blocked by FK constraints |
| Statutory deadline approaching | SLA clock running; job not processing |

## 3. Investigation
1. Check job status: `GET /api/v1/gdpr/export-jobs/{id}/`
2. Verify data subject exists in tenant records
3. Check RQ worker queue depth
4. Review SLA clock: days remaining until statutory deadline

## 4. Remediation
- **Export stuck:** Restart RQ worker; check queue depth
- **Empty export:** Verify data subject identifier; check cross-tenant records
- **Erasure cascade:** Manually resolve FK constraints; retry erasure
- **SLA risk:** Escalate immediately per P1 process

## 5. Recovery
1. Fix blocking issue
2. Re-run export or erasure job
3. Verify completion and audit event emitted
4. Confirm SLA compliance

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single export delayed | privacy-eng@meshant.com |
| P2 | Erasure cascade blocked | privacy-eng + data-platform |
| P1 | Statutory deadline < 48h | SEV1 — DPO + legal + privacy-eng |

## 7. Related
- `hub/apps/gdpr/models.py`
- `hub/apps/gdpr/migrations/0004_enable_rls_gdpr.py`
- `docs/runbooks/phase232-dsar.md`
