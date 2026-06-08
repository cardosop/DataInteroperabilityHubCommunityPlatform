# RB-COMP-008 — Processor Agreement Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
Processor agreements manage Article 28-compliant data processor contracts, linking processors to assets and tracking agreement expiry.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Processor register returns 403 | `compliance_processor_agreements_enabled=False` (DPO signoff) |
| Article 28 agreement template missing | Jurisdiction template not configured |
| Asset-processor link broken | Processor or asset deleted; cascading unlink |
| Agreement expiry notifications not sent | `PROCESSOR_AGREEMENT_EXPIRY_CHECK` sweep not running |

## 3. Investigation
1. Check flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Verify processor: `GET /api/v1/processor-agreements/processors/{id}/`
3. Check links: `GET /api/v1/processor-agreements/links/?processor_id={id}`
4. Sweep: query `JobType.PROCESSOR_AGREEMENT_EXPIRY_CHECK` jobs

## 4. Remediation
- **Flag off:** Obtain DPO signoff; enable flag
- **Missing template:** Add jurisdiction template in admin
- **Broken link:** Re-link processor to asset
- **Sweep:** Restart `PROCESSOR_AGREEMENT_EXPIRY_CHECK` cron (60/30/7-day notifications)

## 5. Recovery
1. Fix root cause
2. Re-create agreement if needed
3. Verify expiry notifications resume

## 6. Escalation
- **P3:** Single agreement template issue
- **P2:** All processor agreements for a tenant blocked
- **P1:** Processor register data loss — SEV1
- **Contact:** privacy-eng@meshant.com

## 7. Related
- `docs/runbooks/RB-FLAG-007-processor-agreements.md`
- `docs/runbooks/phase232-compliance-programme.md`
- `hub/apps/processor_agreements/views.py`
