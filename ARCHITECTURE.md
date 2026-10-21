
## Phase 275 — Warehouse Connectivity

The warehouse connectivity subsystem (`hub/apps/warehouses/`) provides live
query access to Snowflake, BigQuery, Databricks, and Athena. Architecture:

```
Client → Records API (DatasetViewSet.rows) → LIVE_QUERY? → WarehouseConnector
                                                         → file-backed dataset
Client → Delta Sharing (DatasetViewSet.share) → WAREHOUSE_SHARE_ACCESSED audit
Client → ScheduledExport → DltAdapter → dlt pipeline → warehouse table
```

Key components:
- `WarehouseConnection` model with KMS+Fernet credential encryption
- `WarehouseConnector` ABC with 4 concrete implementations
- `RuleChain` integration for validation pipelines
- Per-tenant feature flags (warehouse_connectivity_enabled + per-warehouse sub-flags)
