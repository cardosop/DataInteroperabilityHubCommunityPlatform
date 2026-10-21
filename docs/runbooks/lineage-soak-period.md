# Lineage 7-day staging soak — runbook

**Phase:** 228 Foundations (228.0.DoD.8)
**Owner:** Data Platform Eng + SRE on-call
**Severity ladder:** OK / WARN (info-only) / CRITICAL (P1, gate fails)
**Last reviewed:** 2026-04-30

## Purpose

Phase 228 DoD.8 requires "no P1 incidents during 7-day staging soak". This runbook defines:

1. **Pre-soak checklist** — what must be true before the soak clock starts.
2. **Daily observation procedure** — what the operator runs every day to confirm the gate is still green.
3. **P1 escalation** — what triggers a P1 + the recovery procedure.
4. **Gate sign-off** — what closes the soak and unblocks the next wave.

Engineering automation: the daily check is a single command — `python manage.py lineage_soak_status` — that emits a structured JSON report and exits non-zero on CRITICAL. The cron / CI workflow branches on the return code.

## Pre-soak checklist (T-0)

Run BEFORE setting `soak_start_date`. Each item must be `[x]` for the soak clock to start.

- [ ] Migration `0025_lineage_edges` applied on staging RDS:
  ```bash
  python /app/hub/manage.py showmigrations contracts | grep 0025
  # expect: [X] 0025_lineage_edges
  ```
- [ ] Backfill executed cleanly on staging (DoD.3):
  ```bash
  bash /app/scripts/staging/run-lineage-backfill.sh
  # expect: "OK: backfill ran cleanly + drift ≤ 0.001."
  ```
  Archive the artefact directory `audit-reports/lineage-backfill/<date>/` to the soak-tracking issue.
- [ ] Capability flags responding correctly:
  ```bash
  curl -s https://stagingmeshant-internal.example.com/api/v1/capabilities/ | jq '.capabilities'
  # expect five lineage.* keys, each true on staging (per REQ-LIN-006 default)
  ```
- [ ] Five Prometheus alert rules loaded:
  ```bash
  curl -s http://prometheus:9090/api/v1/rules | jq '.data.groups[] | select(.name=="lineage_alerts") | .rules | length'
  # expect: 5
  ```
- [ ] Grafana dashboard panel-count check:
  ```bash
  curl -s http://grafana:3000/api/dashboards/uid/hub-lineage-overview-228 | jq '.dashboard.panels | length'
  # expect: 6
  ```
- [ ] On-call rotation acknowledged in `#data-platform-oncall`. The five lineage alerts route to that channel via the existing alertmanager config; on-call has the runbook URLs in their incident-response cheat sheet.

When every item is `[x]`, set `soak_start_date = today` in the soak-tracking issue and start the daily observation.

## Daily observation (T+0 through T+7)

### One-shot status check

The canonical command:

```bash
python /app/hub/manage.py lineage_soak_status --days=7
```

Output is a JSON report on stdout. Example:

```json
{
  "phase": "228.0.DoD.8",
  "status": "OK",
  "tenant_id": null,
  "window_days": 7,
  "window_start": "2026-04-23T12:00:00+00:00",
  "window_end": "2026-04-30T12:00:00+00:00",
  "rules": [
    {"rule": "drift", "severity": "critical", "count": 0, "status": "OK", "description": "..."},
    {"rule": "edge_writes", "severity": "warning", "count": 12345, "threshold": 100000, "status": "OK", "description": "..."},
    {"rule": "auto_revert", "severity": "warning", "count": 0, "status": "OK", "description": "..."}
  ],
  "checked_at": "2026-04-30T12:00:00.123456+00:00"
}
```

Status interpretation:

| Top-level `status` | Exit code | Operator action |
|---|---|---|
| `OK` | 0 | Continue soak. Append the report to the soak-tracking issue. |
| `WARN` | 0 | Continue soak. Investigate the WARN rule's `count` against the per-rule `description` to confirm it's expected. |
| `CRITICAL` | non-zero | **P1 escalation** — see below. The soak clock pauses; the gate fails. |

### Daily cron wiring (recommended)

```cron
# /etc/cron.d/lineage-soak
0 9 * * * meshant /app/hub/manage.py lineage_soak_status --days=7 \
    | tee /var/log/meshant/lineage-soak-$(date +\%F).json \
    || curl -X POST -H "Content-type: application/json" \
        --data '{"text":"Lineage soak P1: see /var/log/meshant/lineage-soak-$(date +%F).json"}' \
        $SLACK_WEBHOOK_DATA_PLATFORM_ONCALL
```

The `||` clause fires the Slack alert only when the command exits non-zero (i.e., CRITICAL); the daily green log is silent.

## P1 escalation

CRITICAL status fires when:

- **Rule `drift`** sees ≥1 `LINEAGE_EDGE_DRIFT_DETECTED` audit event in the window. This means the relational `LineageEdge` index diverged from the JSONB source of truth.

### P1 recovery procedure

1. **Acknowledge** the alert in `#data-platform-oncall` within 15 minutes.
2. **Identify the affected scope:**
   ```bash
   python /app/hub/manage.py lineage_soak_status --days=7 \
       | jq '.rules[] | select(.rule=="drift")'
   ```
3. **Re-run the drift-correction backfill:**
   ```bash
   bash /app/scripts/staging/run-lineage-backfill.sh
   ```
4. **Verify recovery:**
   ```bash
   python /app/hub/manage.py lineage_soak_status --days=7
   # expect: "status": "OK"
   ```
5. **Restart the soak clock** — DoD.8 requires a *consecutive* 7-day soak. A P1 mid-soak resets `soak_start_date` to the day after recovery. Document the reset in the soak-tracking issue.

### When recovery doesn't converge

If step 4 still reports `CRITICAL` after a clean backfill run:

- The diff algorithm in `_sync_contract_edges` may have a defect — escalate to engineering as a P0.
- The signal handler may be silently raising — check structured logs for `lineage_sync_handler_failed`.
- Cross-reference the [sync-drift runbook](lineage-edge-sync-drift.md) for the four common drift causes.

## WARN-level signals (information-only; do NOT page)

- **Rule `edge_writes`** above the 100k-event threshold means a runaway contract-rewrite job is producing a lot of mutations. Investigate the responsible job, but the soak gate does NOT fail.
- **Rule `auto_revert`** with count > 0 means a Phase 227 W5 sweep ran during the Phase 228 soak. Verify it's an authorised cycle (the W5 runbook documents authorised windows). Not a soak failure on its own.

## Gate sign-off (T+7)

After 7 consecutive days of `OK` (or `WARN`-only) status:

- [ ] Final `lineage_soak_status --days=7` reports `OK` or `WARN`.
- [ ] No P1 reset occurred during the window (confirmed via `git log` of the soak-tracking issue).
- [ ] The five Prometheus alert rules are still firing-evaluation-clean (`rate(prometheus_rule_evaluation_failures_total{rulegroup="lineage_alerts"}[7d]) == 0`).
- [ ] Sign off DoD.8 in `tasks.md` with the soak window dates + the seven daily report timestamps in the closeout.

## Related

- [DoD.3 backfill wrapper](../../scripts/staging/run-lineage-backfill.sh)
- [Sync-drift runbook](lineage-edge-sync-drift.md)
- [Backfill failure runbook](lineage-edge-backfill-failure.md)
- [DR runbook](lineage-dr.md)
- [REQ-LIN-007 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md#requirement-lineage-observability-primitives-req-lin-007)
- Source: [`hub/apps/contracts/management/commands/lineage_soak_status.py`](../../hub/apps/contracts/management/commands/lineage_soak_status.py)
