# RB-DATA-002 — Scheduled Export Failure

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
Scheduled export pushes Hub datasets to external destinations (S3, Snowflake, BigQuery, Databricks, Athena) via dlt pipelines on a recurring schedule.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Export run stuck in RUNNING >1h | Worker crash; destination unreachable; dlt schema evolution conflict |
| All exports for tenant failing | `credential_ref` invalid; billing quota exceeded |
| Export writes 0 rows | Source scope empty; dataset retired/archived |
| dlt schema mismatch error | Destination table schema diverged; `write_disposition` conflict |

## 3. Investigation
1. `python manage.py detect_stuck_runs --direction=export --timeout-hours=1`
2. Check destination connectivity: `DataMovementPipeline.run()` test with dry-run
3. Verify `destination_config` and `credential_ref`
4. Check dlt state: query `_dlt_loads` in `dlt_export` schema

## 4. Remediation
- **Schema conflict:** Force `write_disposition="replace"` for one run to realign
- **Credentials:** Rotate via `RB-DM-002` procedure
- **Quota:** Upgrade billing tier or reduce export scope
- **Stuck run:** `detect_stuck_runs --execute`

## 5. Recovery
1. Fix root cause
2. Re-enqueue export run
3. Verify destination has expected row count
4. Audit: `SCHEDULED_EXPORT_RUN_COMPLETED` event

## 5.5 Crash recovery (W3.5 heartbeat lease)

Export workers claim their runs with a `heartbeat_at` liveness lease
(the internal PATCH's `heartbeat_at` field). The stuck-run detector
recovers a run ONLY when its lease expired: RUNNING runs older than the
threshold with a stale or missing heartbeat (NULL `started_at` never
hides a run).

**Scheduling:**
- Kubernetes: `detect-stuck-export-runs` CronJob (helm,
  `helm/templates/cronjob/detect-stuck-export-runs.yaml`), every 15
  minutes.
- Compose deployments: run the sweep on a cron from the host, e.g.
  `*/15 * * * * cd <checkout> && docker compose exec -T api-service python manage.py detect_and_remediate_stuck_export_runs`

Manual invocation: `python manage.py detect_and_remediate_stuck_export_runs [--dry-run] [--threshold-hours N]`.

## 6. Escalation
- **P3:** Single export failure (destination-specific)
- **P2:** All exports for a tenant failing
- **P1:** dlt infrastructure down — all exports failing
- **Contact:** data-plane-eng@meshant.com

## 7. Related
- `docs/runbooks/RB-DM-001-dlt-pipeline-failure.md`
- `docs/runbooks/RB-DM-002-credential-ref-rotation.md`
- `docs/runbooks/warehouse-dr.md`
