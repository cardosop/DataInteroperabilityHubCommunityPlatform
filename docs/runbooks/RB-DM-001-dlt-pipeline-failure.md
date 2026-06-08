# RB-DM-001 — dlt Pipeline Failure Investigation

**Feature:** Data Movement (dlt), `data_movement_enabled` GA
**Owner:** data-plane-eng@meshant.com
**Created:** 2026-05-18 (Phase 285.6.6)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Pipeline stuck in RUNNING >24h | Worker crashed; dlt state corrupted; Prefect worker down | `detect_stuck_runs --timeout-hours=24`; worker pod status |
| dlt load fails with schema mismatch | Source schema changed; dlt schema evolution blocked | `_dlt_loads` table; schema version in `_dlt_versions` |
| Pipeline returns 0 rows | Source empty; credential expired; incremental cursor wrong | Source config; `credential_ref` resolution; dlt state cursor |
| `_dlt_*` tables accumulating | Cleanup sweep not running; pipelines deleted without table drop | `dlt_tables_total` gauge; last sweep timestamp |
| Credential resolution fails | SM ARN expired/invalid; Prefect block deleted; IAM permission missing | `resolve_credentials()` log; AWS SM console; IAM policy |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/data-movement.json`
- **Primary:** `dlt_pipeline_load_duration_seconds{pipeline}`
- **Failed:** `dlt_pipeline_failed_loads_total{pipeline}`
- **Health:** `dlt_pipeline_health_status{pipeline}` (0=healthy, 1=degraded, 2=unhealthy)
- **Tables:** `dlt_tables_total` gauge

## Investigation Checklist

1. Identify stuck pipeline: `python manage.py detect_stuck_runs --direction=both`
2. Check dlt state: `_dlt_loads` + `_dlt_versions` tables in `dlt_ingestion`/`dlt_export` schema
3. Resolve credentials: `resolve_credentials(credential_ref)` → verify secret accessible
4. Check worker logs: `kubectl logs -l app=hub-worker -n hub-staging | grep dlt`
5. Retry failed: `DataMovementPipeline.retry_failed(pipeline_name, resources)`

## Escalation

- **P3:** Single pipeline failure (credential or schema-specific)
- **P2:** All pipelines for a tenant failing (credential/configuration)
- **P1:** dlt infrastructure down (worker pods down; PostgreSQL unreachable)

## Rollback

1. Toggle `data_movement_enabled=False` on tenant → legacy path reactivates
2. Credential migration reversible: `source_config_backup` restored from pre-migration state
3. Pipeline state preserved in `_dlt_*` tables — no data loss on rollback

## Related

- `hub/data_movement/dlt_pipeline.py` — DataMovementPipeline
- `hub/data_movement/dlt_retry.py` — retry_failed()
- `hub/data_movement/dlt_metrics.py` — health_status()
- `docs/dlt-MIGRATION.md` — developer guide

## Maintenance

- **Owner:** Data Plane Engineering
- **Last reviewed:** 2026-05-18
- **Next review:** 2026-08-18
