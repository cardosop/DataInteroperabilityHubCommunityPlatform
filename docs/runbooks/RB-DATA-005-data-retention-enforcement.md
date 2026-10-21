# RB-DATA-005 — Data Retention Enforcement Failure

**Owner:** privacy-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
The retention enforcer (`compliance_retention_enforcer_enabled`) runs automated sweeps to tombstone and hard-delete data past its retention deadline, respecting DSAR holds and legal holds.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Sweep not running | `compliance_retention_enforcer_enabled=False`; cron paused |
| Data not tombstoned at deadline | DSAR hold active; legal hold blocking |
| Hard-delete executed prematurely | Retention policy misconfigured; grace period bypassed |
| Sweep causing DB performance issues | Large batch size; no throttling |

## 3. Investigation
1. Check flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check sweep schedule: cron job status; last `RETENTION_SWEEP_COMPLETED` event
3. Check active holds: `legal_hold_active` + `dsar_hold_active` metrics
4. Query: `SELECT count(*) FROM assets WHERE retention_date < now() AND status != 'tombstoned'`

## 4. Remediation
- **Flag off:** Enable `compliance_retention_enforcer_enabled`
- **DSAR hold blocking:** Verify hold is still active; release if resolved
- **Premature delete:** Immediately stop sweep; restore from backup
- **Performance:** Reduce `RETENTION_SWEEP_BATCH_SIZE`; add delay between batches

## 5. Recovery
1. Stop active sweep if causing issues
2. Fix configuration
3. Resume sweep; monitor `retention_sweep_duration_seconds`

## 6. Escalation
- **P3:** Sweep missed one window
- **P2:** Sweep causing >70% DB CPU for >5min
- **P1:** Premature hard-delete — SEV1, immediate rollback + data recovery
- **Contact:** privacy-eng@meshant.com

## 7. Related
- `docs/runbooks/RB-FLAG-008-retention-enforcer.md`
- `docs/runbooks/file-retention.md`
- `docs/runbooks/RB-COMP-009-compliance-retention-enforcer-failure.md`
