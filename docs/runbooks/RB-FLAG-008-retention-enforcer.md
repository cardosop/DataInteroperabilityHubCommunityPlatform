# RB-FLAG-008 — Retention Enforcer Feature Flag

**Flag:** `compliance_retention_enforcer_enabled`
**Stage:** GA (opt-in — `default_new=False`, requires DPO signoff)
**Owner:** privacy-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Scope

Gates the Phase 232.7 automated retention enforcement engine: tombstone sweep, hard-delete sweep, DSAR hold interaction, and legal-hold override. Default OFF for new tenants (opt-in with DPO signoff) — retention automation has permanent data destruction implications and requires explicit DPO approval.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Retention sweep not running | Flag disabled; sweep scheduler paused | Flag state; `retention_sweep_scheduler_state`; cron health |
| Data not tombstoned at retention deadline | Sweep window misconfigured; DSAR hold active | `retention_policy` config; active DSAR holds on affected data |
| Hard-delete executed prematurely | Retention policy misconfigured; legal-hold bypassed | `retention_sweep_audit_log`; legal-hold registry; rollback capability |
| DSAR response missing data | Retention sweep deleted data during active DSAR | DSAR hold check in sweep logic; `dsar_active_holds` metric |
| Sweep causing performance degradation | Large batch; no throttling; DB I/O spike | `retention_sweep_duration_seconds`; DB CPU/IO metrics; batch size config |
| Legal hold not preventing deletion | Hold registration race condition; hold expiry misconfigured | Legal hold registry; `legal_hold_active_total`; sweep exclusion list |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/retention.json`
- **Primary:** `retention_sweep_duration_seconds{phase}` (tombstone, hard-delete)
- **Volume:** `retention_sweep_rows_processed_total{action}` (tombstoned, deleted, skipped)
- **Holds:** `legal_hold_active_total`, `dsar_hold_active_total`
- **Errors:** `retention_sweep_errors_total{error_code}`
- **Audit:** `RETENTION_SWEEP_COMPLETED`, `RETENTION_TOMBSTONE_CREATED`, `RETENTION_HARD_DELETE_EXECUTED`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Confirm DPO signoff: `requires_dpo_signoff=True` → signoff record exists
3. Check sweep schedule: confirm cron is active and last sweep completed successfully
4. Verify hold interaction: create test DSAR hold → confirm sweep excludes held data
5. Verify legal hold: register test legal hold → confirm sweep excludes held data
6. Batch size: confirm `RETENTION_SWEEP_BATCH_SIZE` is appropriate for tenant data volume
7. Recovery: confirm tombstoned data is recoverable within grace period; hard-deletes are permanent
8. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=compliance_retention_enforcer_enabled`

## Escalation

- **P3** — Sweep schedule missed one window (catch-up on next cycle)
- **P2** — Sweep causing DB performance degradation (>70% CPU for >5min)
- **P1** — Premature hard-delete executed (SEV1 — immediate rollback + data recovery)
- **P0** — Legal hold bypassed by sweep (SEV0 — regulatory notification required)

## Related

- `docs/runbooks/file-retention.md` — File retention procedures
- `docs/compliance/retention-schedule.md` — Retention schedule policy
- `docs/mvpdocs/concepts/governance.md` — Governance concepts

## Maintenance

- **Owner:** Privacy Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
