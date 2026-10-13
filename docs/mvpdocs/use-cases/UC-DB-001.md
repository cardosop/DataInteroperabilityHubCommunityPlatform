# UC-DB-001: Register Databricks Workspace

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P0 Test:** `hub/apps/databricks_admin/tests/test_workspace_journeys.py::TestJOURNEYDB001RegisterWorkspace::test_register_workspace_success`

## Description

Register a customer-BYO Databricks workspace so the Hub control plane can manage its Unity Catalog objects, compute, jobs, and budgets. The workspace is tenant-scoped with SSRF/residency-validated host and encrypted credentials.

## Preconditions

- The tenant has `databricks_control_plane_enabled=True`.
- The caller is a `TENANT_ADMIN`.
- The workspace host is within the `*.cloud.databricks.com` family.

## Steps

1. Admin calls `POST /api/v1/databricks/workspaces/` with `{ name, host, cloud, region }`.
2. The Hub validates the host (SSRF + residency) and persists a `DatabricksWorkspace` in `REGISTERED` state.
3. Admin attaches a credential via `POST /api/v1/databricks/workspaces/{id}/credentials/` (PAT or OAuth M2M, encrypted).
4. Admin calls `POST /api/v1/databricks/workspaces/{id}/test/` to probe connectivity; success moves the workspace to `ACTIVE`.

## Expected Outcome

- A tenant-scoped `databricks_workspaces` row exists with `status=ACTIVE`.
- `DATABRICKS_WORKSPACE_REGISTERED` and `DATABRICKS_WORKSPACE_TEST_PASSED` audit events are written with no credential material.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Flag disabled | `403` with `DATABRICKS_CONTROL_PLANE_DISABLED` |
| Host resolves to private IP | `400` with `SSRF_PROTECTION_TRIGGERED` |
| Revoked credential on test | `502` with `DATABRICKS_AUTH_FAILED` (masked) |
| Delete with dependents | `409` with `DATABRICKS_WORKSPACE_HAS_DEPENDENTS` |

## Related

- Concepts: [Tenants](../concepts/tenants.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-001 -- Register a Databricks Workspace](../journeys/JOURNEY-DB-001.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
