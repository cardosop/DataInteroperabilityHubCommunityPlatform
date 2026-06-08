# Scheduled ingestion stuck

## Diagnostics

1. Inspect Prefect / RQ job rows for ingestion runs with `RUNNING` > SLA.
2. Tail worker logs referencing `scheduled_ingestion_asset_key_retired_total`.
3. Replay failed files after clearing DLQ duplicates.

## Mitigation

Scale worker-heavy replicas; validate MinIO latency.

## Maintenance

- **Owner**: Data Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
