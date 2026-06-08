# RB-COMP-007 — DPIA Assessment Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
DPIA (Data Protection Impact Assessment) wizard manages the lifecycle of privacy impact assessments with DPO review workflow and periodic re-review sweeps.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| DPIA creation returns 403 | `compliance_dpia_enabled=False` (requires DPO signoff) |
| DPO review workflow stuck | Delegation chain broken; reviewer unavailable |
| Periodic re-review not triggering | `DPIA_REVIEW_DUE` sweep not running |
| DPIA export PDF corrupted | Rendering engine error; missing template |

## 3. Investigation
1. Check flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check DPO review: `ApprovalDelegation` state for DPIA reviews
3. Sweep status: query `JobType.DPIA_REVIEW_DUE` jobs
4. PDF export: check template rendering logs

## 4. Remediation
- **Flag off:** Obtain DPO signoff; enable `compliance_dpia_enabled`
- **Stuck review:** Reassign reviewer; update `ApprovalDelegation`
- **Sweep:** Restart DPIA_REVIEW_DUE cron
- **PDF:** Regenerate with correct template

## 5. Recovery
1. Fix root cause
2. Retry failed operation
3. Verify DPIA transitions to expected state

## 6. Escalation
- **P3:** Single DPIA stuck in review
- **P2:** All DPIAs for a tenant blocked
- **P1:** DPIA data loss — SEV1
- **Contact:** privacy-eng@meshant.com

## 7. Related
- `docs/runbooks/RB-COMP-005-dpia.md`
- `docs/runbooks/phase232-dpia.md`
- `hub/apps/dpia/views.py`
