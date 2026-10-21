# RB-COMP-009 — Retention Enforcer Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
The automated retention enforcer executes tombstone and hard-delete sweeps with DSAR and legal-hold interaction. Failures can result in regulatory non-compliance for overdue data retention.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Enforcer returns 403 on trigger | `compliance_retention_enforcer_enabled=False` |
| Sweep missed scheduled window | Cron job paused; worker queue backlog |
| Legal hold bypassed | Hold registration race condition; hold expiry misconfigured |
| Hard-delete executed on held data | DSAR hold not checked before delete; `_check_holds()` bug |

## 3. Investigation
1. Flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Sweep history: `RETENTION_ENFORCEMENT_SWEEP` jobs in `GET /api/v1/jobs/`
3. Holds: query `legal_hold_active` + `dsar_hold_active` metrics
4. Audit: `RETENTION_HARD_DELETE_EXECUTED` events for unexpected deletions

## 4. Remediation
- **Flag off:** Enable `compliance_retention_enforcer_enabled` (requires DPO signoff)
- **Sweep missed:** Manually trigger `RETENTION_ENFORCEMENT_SWEEP` job
- **Hold bypass:** Fix `_check_holds()` logic; re-register hold
- **Premature delete:** Stop sweep immediately; restore from backup; SEV1

## 5. Recovery
1. Stop active sweep
2. Restore prematurely deleted data from backup (tombstone → restore; hard-delete → backup)
3. Fix hold check logic
4. Resume sweep with monitoring

## 6. Escalation
- **P3:** Sweep missed one window
- **P2:** Hold bypassed for single asset
- **P1:** Hard-delete on held data — regulatory notification required
- **P0:** Legal hold bypassed — SEV0, immediate regulator notification
- **Contact:** privacy-eng@meshant.com, legal@meshant.com

## 7. Related
- `docs/runbooks/RB-FLAG-008-retention-enforcer.md`
- `docs/runbooks/RB-DATA-005-data-retention-enforcement.md`
- `docs/runbooks/file-retention.md`
