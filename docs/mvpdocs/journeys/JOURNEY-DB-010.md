# JOURNEY-DB-010: Manage SQL Warehouses

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-DB-010

## Overview

A data engineer manages the tenant's Databricks SQL warehouses from the Hub. The warehouse list is MIRROR-FIRST — the Hub mirrors the workspace's compute API state (`STARTING`/`RUNNING`/`STOPPING`/`STOPPED`/`DELETING`, the serverless flag, the size tier, the auto-stop minutes) and never invents a state. Start/stop run under the D12 INTERACTIVE identity (OBO — fail-closed without a Databricks user binding) and refresh the mirror afterwards, so long-running lifecycle operations surface as non-blocking progress. Creation is gated by the `databricks.warehouse.create` chain BEFORE any network call (tier-gated sizes + the per-tenant warehouse quota). Live-query connections derive their `http_path` from the warehouse id at the linkage boundary, so the connection and the managed warehouse never drift.

## Journey Steps

1. **List warehouses** — GET `/api/v1/databricks/workspaces/{id}/sql-warehouses/` returns the paginated mirror rows (zero network — the READ leg serves the 3.2 mirror; the workspace registry gates the surface).
2. **Start and stop** — POST `.../sql-warehouses/{warehouse_id}/start/` (or `/stop/`) resolves the interactive identity and drives the production compute client; the mirror refreshes after the action and the row reports the compute API's new state (`STARTING`/`STOPPING`) — never an invented one. A warehouse already in the desired state is a no-op (zero mutation calls, no audit row).
3. **Create (gated)** — the `databricks.warehouse.create` chain runs the tenant-scoping → tier-gate → per-tenant quota → structural-validation steps before any compute call; a gated request fails with a classified code (`DATABRICKS_WAREHOUSE_TIER_FORBIDDEN` / `DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED` / `DATABRICKS_WAREHOUSE_INVALID_CONFIG`).
4. **Use the warehouse** — `WarehouseConnection.derive_from_sql_warehouse()` derives the connection's `http_path` from the mirror row's warehouse id (`/sql/1.0/warehouses/{id}`) — derived, never stored twice.

## Success Criteria

- State transitions are mirrored truthfully (delta-diff refresh; unknown reported states are skipped, never coerced).
- Cross-tenant warehouse access is impossible: RLS on the mirror rows + the per-(tenant, warehouse) connection pool with the borrow-time tenant re-check.
- Creating beyond the tier or the per-tenant cap fails with a classified chain code and ZERO network calls.
- Every performed lifecycle action emits its `DATABRICKS_WAREHOUSE_CREATED/STARTED/STOPPED/RESIZED/DELETED` audit row (no-ops emit nothing — the trail shows what actually happened).
- An action without a Databricks binding fails closed (`502 DATABRICKS_OBO_REFRESH_FAILED`, zero network) — never a service-credential fallback on interactive paths.

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Feature Availability](../concepts/feature-availability.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-011](JOURNEY-DB-011.md) (Run a Databricks Job), [JOURNEY-DB-015](JOURNEY-DB-015.md) (Set a Databricks Budget)
