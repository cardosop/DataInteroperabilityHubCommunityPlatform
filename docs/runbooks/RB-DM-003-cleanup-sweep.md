# RB-DM-003: dlt State Table Cleanup Sweep

**Feature:** Data Movement (dlt)
**Severity:** Low (background housekeeping)
**Runbook owner:** Platform Engineering

## Overview

The dlt library creates internal state tables (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`) in the `dlt_ingestion` and `dlt_export` PostgreSQL schemas. When a `ScheduledIngestion` or `ScheduledExport` is deleted, these tables become orphaned. This sweep drops them after a 90-day grace period.

## Schedule

- **Frequency**: Weekly (Sunday 03:00 UTC)
- **Command**: `python hub/manage.py cleanup_dlt_state_tables --execute`

## Manual Execution

```bash
# Preview (dry-run)
python hub/manage.py cleanup_dlt_state_tables --dry-run

# Execute with default 90-day grace period
python hub/manage.py cleanup_dlt_state_tables --execute

# Custom grace period (180 days)
python hub/manage.py cleanup_dlt_state_tables --execute --min-age-days 180

# Single schema only
python hub/manage.py cleanup_dlt_state_tables --execute --schema dlt_ingestion
```

## What It Does

1. Queries `information_schema.tables` for tables matching `_dlt_*` in the dlt schemas
2. Checks each table against active `ScheduledIngestion` and `ScheduledExport` records
3. Drops tables whose pipeline no longer exists (CASCADE to remove dependencies)
4. Logs each dropped table via structlog

## Safety

- Tables belonging to ACTIVE, PAUSED, or ERROR pipelines are NEVER dropped
- The `--dry-run` flag shows exactly what would happen
- Only `_dlt_*` prefixed tables are targeted — data tables are never touched
- The 90-day default grace period prevents premature cleanup of recently deleted pipelines

## Monitoring

- Check the `dlt_state_table_dropped` structlog events in Grafana
- Alert if the sweep fails to run for > 8 days (missed weekly window)

## Rollback

Dropped tables cannot be recovered from the database. If a pipeline was deleted prematurely:
1. Recreate the pipeline in the Django admin
2. dlt will recreate its state tables on the next pipeline run
3. Incremental state will be lost (full re-ingestion on next run)
