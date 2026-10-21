# UC-DB-007: Request UC DDL Change

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P2 Test:** `hub/apps/databricks_admin/tests/test_uc_change_journeys.py::TestJOURNEYDB007RequestDdlChange::test_request_ddl_change_success`

## Description

Request a Unity Catalog DDL change on a registered workspace — CREATE for the supported securables (catalogs/schemas/tables/views/volumes/external-locations/storage-credentials/models; materialized views and streaming tables via the SQL fallback), DROP for the destructive family (flag-gated). The request carries a truthful DDL preview (the exact REST method/path/body or the SQL statement) derived locally from the 2.3 executor's dispatch table.

## Preconditions

- A registered `ACTIVE` workspace and the `databricks_control_plane_enabled` flag.
- For destructive requests: the tenant's `databricks_uc_destructive_ddl_enabled` flag (the 2.4 denylist).

## Steps

1. User POSTs `/api/v1/databricks/workspaces/{id}/uc/changes/` with `change_type`, `securable_type`, and the payload-shaped `definition` (identifiers + options).
2. The 2.4 guards run at the boundary: the denylist refuses destructive DDL on a flag-off tenant (`403 DATABRICKS_DDL_DENYLISTED`), the identifier regex rejects malformed identifiers (`400 DATABRICKS_DDL_INVALID_IDENTIFIER`) — zero network.
3. A `DRAFT` request is created with the truthful preview (`kind: rest` with method/path/body, or `kind: sql` with the statement; unknown vocabulary marks `kind: unsupported`).

## Expected Outcome

- The draft request is tenant-scoped and lists under the workspace registry (paginated).
- The requester submits it (`/submit/` → `PENDING_APPROVAL`); the step approvers are notified in-app and a `databricks.uc_change.submitted` webhook fires.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Flag-off destructive request | `403` `DATABRICKS_DDL_DENYLISTED` (zero network) |
| Malformed identifier / missing fields | `400` `DATABRICKS_DDL_INVALID_IDENTIFIER` / clean 400 |
| Cross-tenant workspace | `404` (tenant-scoped lookups) |
| Throttle exhausted | `429` (`databricks_uc_changes` 30/minute scope) |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-007 -- Request a UC DDL Change](../journeys/JOURNEY-DB-007.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
