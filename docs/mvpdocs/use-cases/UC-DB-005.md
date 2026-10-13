# UC-DB-005: Browse Unity Catalog

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P1 Test:** `hub/apps/databricks_admin/tests/test_uc_catalog_journeys.py::TestJOURNEYDB005BrowseUCCatalog::test_browse_endpoints_paginated`

## Description

Browse the mirrored Unity Catalog of a registered workspace — catalogs, schemas, tables, views, volumes, and registered models — with search, filters, and pagination, served from RLS-scoped mirror models kept fresh by the UC metadata sync job.

## Preconditions

- A registered `ACTIVE` workspace.
- The `DATABRICKS_UC_METADATA_SYNC` job has completed at least once.

## Steps

1. User calls `GET /api/v1/databricks/workspaces/{id}/uc/catalogs/` (paginated `{count, results}`).
2. User drills into schemas and tables (`/uc/catalogs/{catalog_id}/schemas/`, `/uc/schemas/{schema_id}/tables/` — the mirror row IDs, reconciled with the shipped 1.3 routes).
3. User opens a table detail (`/uc/tables/{table_id}/`) with columns, metadata, and the LIVE `effective_permissions` answer (OBO-backed).
4. The mirror freshness marker reflects `synced_at` against the sync schedule.

## Expected Outcome

- Mirror rows are tenant-scoped via the workspace (RLS).
- Sync failures emit `DATABRICKS_UC_METADATA_SYNC_FAILED` and surface a stale-mirror marker.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Cross-tenant workspace access | `404` (tenant-scoped lookups — the shipped 1.3 contract, reconciled) |
| Unknown catalog/table | `404` (DRF NotFound, the standard envelope) |
| Throttle exhausted | `429` (`databricks_uc_browse` 30/minute scope) |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Search](../concepts/search.md)
- Journeys: [JOURNEY-DB-005 -- Browse the Unity Catalog](../journeys/JOURNEY-DB-005.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
