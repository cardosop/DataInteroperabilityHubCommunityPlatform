# dlt Migration Guide

**Phase:** 285.6 | **Date:** 2026-05-18
**Target:** Replace custom ingestion/export code with dlt (data load tool)

## Overview

dlt (data load tool) becomes the single bidirectional data movement engine for
Meshant. This migration replaces 2,141 lines of custom code (5 files) with dlt's
built-in primitives for incremental loading, schema management, retry, and monitoring.

## Architecture

```
                    ┌─────────────────────┐
  Source (S3/GCS/    │  DataMovementPipeline │  ┌──────────────────┐
  Snowflake/HTTP) ──▶│    (dlt wrapper)       │──▶│ Destination (S3/ │
                    │  hub/data_movement/    │  │  Snowflake/BQ/   │
                    └─────────────────────┘  │  FTP)             │
                                             └──────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  dlt state tables   │
                    │  (dlt_ingestion /   │
                    │   dlt_export schema)│
                    └────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `hub/data_movement/dlt_pipeline.py` | DataMovementPipeline wrapper |
| `hub/data_movement/dlt_credentials.py` | Credential resolution (AWS SM / Prefect / toml) |
| `hub/data_movement/dlt_resources.py` | @dlt.resource definitions for ingestion |
| `hub/data_movement/dlt_incremental.py` | Incremental loading via dlt cursor state |
| `hub/data_movement/dlt_retry.py` | Failed load retry with exponential backoff |
| `hub/data_movement/dlt_metrics.py` | Prometheus metrics export from dlt LoadInfo |

## Migration Steps

### For Tenants
1. `data_movement_enabled` flag is GA and default-ON for new tenants
2. Existing tenants: flag is ON (default). Set `credential_ref` on ScheduledIngestion/ScheduledExport
3. Old inline credentials continue to work during migration window
4. After migration: old `source_config`/`destination_config` inline creds can be removed

### For Developers
1. Add `credential_ref` to new ScheduledIngestion/ScheduledExport records
2. dlt pipeline auto-resolves credentials from the ref (AWS SM ARN, Prefect block, or toml key)
3. Dual-path validation: serializers accept both `credential_ref` and inline config creds
4. Delete old `credential_manager.py` after all tenants migrated (>95% credential_ref coverage)

## Rollback
1. Set `data_movement_enabled=False` on tenant → legacy worker path reactivates
2. `source_config_backup` preserves original inline credentials
3. dlt `_dlt_*` state tables preserved — no data loss

## Related
- `docs/runbooks/RB-DM-001-dlt-pipeline-failure.md`
- `docs/runbooks/RB-DM-002-credential-ref-rotation.md`
- `docs/BaaS.md`, `docs/ML.md`, `docs/virtualization.md` — other new feature docs
