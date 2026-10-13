# UC-DB-010: Manage SQL Warehouse Lifecycle

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P3 Test:** `hub/apps/databricks_admin/tests/test_warehouse_journeys.py::TestJOURNEYDB010ManageSQLWarehouses::test_lifecycle_state_transitions`

## Description

Manage the tenant's Databricks SQL warehouses from the Hub: list the mirrored fleet (the 3.2 mirror — zero network on the READ leg), start and stop through the interactive identity with the mirror refreshing after each action (never an invented state), gate creation through the `databricks.warehouse.create` chain before any network call, and wire live-query connections through the derived `http_path` (`/sql/1.0/warehouses/{id}` — the path is derived at the linkage boundary, never stored twice).

## Preconditions

- A registered `ACTIVE` workspace and the tenant's `databricks_control_plane_enabled` flag.
- For start/stop: a `DatabricksUserBinding` for the acting user (the D12 INTERACTIVE identity) — without one the action fails closed.
- For creation: the requested size within the tenant's plan tier and headroom under the per-tenant `max_databricks_warehouses` quota.

## Steps

1. User GETs `/api/v1/databricks/workspaces/{id}/sql-warehouses/` — the paginated mirror rows (state/serverless/size/auto-stop), tenant- and workspace-scoped.
2. User POSTs `.../sql-warehouses/{warehouse_id}/start/` or `/stop/` — the view resolves the interactive identity (OBO), drives the production compute client, and refreshes the mirror afterwards; the row reports the compute API's new state. A warehouse already in the desired state is a no-op.
3. The `databricks.warehouse.create` chain gates creation (tier allowlist → per-tenant quota → structural validation) BEFORE any compute call.
4. `WarehouseConnection.derive_from_sql_warehouse()` links the connection to the warehouse with the derived `http_path`.

## Expected Outcome

- Every performed lifecycle action emits its `DATABRICKS_WAREHOUSE_CREATED/STARTED/STOPPED/RESIZED/DELETED` audit row (no-ops emit nothing).
- The connection pool reuses per-(tenant, warehouse) connections without cross-tenant leakage (borrow-time tenant re-check; a tenant's exhaustion never affects another tenant).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Size above plan tier / unknown tier | Chain FAIL `DATABRICKS_WAREHOUSE_TIER_FORBIDDEN` (zero network) |
| Per-tenant warehouse quota exhausted | Chain FAIL `DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED` (zero network) |
| Malformed create request | Chain FAIL `DATABRICKS_WAREHOUSE_INVALID_CONFIG` (zero network) |
| START on a DELETING warehouse / unknown reported state | `409` `DATABRICKS_WAREHOUSE_STATE_ERROR` (zero mutation calls) |
| No Databricks user binding on an action | `502` `DATABRICKS_OBO_REFRESH_FAILED` (fail-closed, zero network) |
| Workspace rejection | `502` `DATABRICKS_AUTH_FAILED` (masked — never the token or the raw error) |
| Throttle exhausted | `429` (`databricks_sql_warehouses` 30/minute, tenant-scoped) |
| Connection pool exhausted | `DATABRICKS_WAREHOUSE_POOL_EXHAUSTED` (the tenant's own bound; other tenants unaffected) |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Feature Availability](../concepts/feature-availability.md)
- Journeys: [JOURNEY-DB-010 -- Manage SQL Warehouses](../journeys/JOURNEY-DB-010.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
