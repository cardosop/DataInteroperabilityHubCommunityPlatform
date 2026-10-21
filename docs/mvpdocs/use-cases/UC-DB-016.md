# UC-DB-016: Provision Workspace from Account

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase P8 Test:** `hub/apps/databricks_admin/tests/test_account_journeys.py::TestJOURNEYDB016ProvisionWorkspaceFromAccount::test_admin_db_path`

## Description

For the optional hub-owned account plane, provision metastores and workspaces for tenants through the Databricks account API from a platform-scoped account link — flag-gated, signoff-required, and executed only via the admin DB connection with platform-admin RBAC.

## Preconditions

- Platform-admin role (account-plane endpoints have NO tenant RLS; the account row resolves through the forced admin alias).
- `databricks_workspace_provisioning_enabled=True` AND a COMPLETE DPO/Legal signoff recorded on the account row (by + at + evidence URL — all three fields).

## Steps

1. The account link exists (`DatabricksAccount` PLATFORM row, admin credential encrypted at rest) — linked at task 8.2; the `DATABRICKS_ACCOUNT_LINKED` audit event ships with task 8.5.
2. Admin creates a metastore via the account API (`POST .../accounts/{id}/metastores/`) — the `DATABRICKS_METASTORE_CREATED` audit event ships with task 8.5.
3. Admin provisions a workspace (`POST .../accounts/{id}/workspaces/`) and the registry row attaches to the tenant through the EXISTING host/region validation — the `DATABRICKS_WORKSPACE_PROVISIONED` audit event ships with task 8.5.
4. The cross-tenant estate summary (`GET /api/v1/databricks/estate-summary/`) aggregates workspace counts by state and budget figures across tenants.

## Expected Outcome

- The provisioned workspace lands in the tenant's registry and the estate summary reflects it (one derived admin-DB aggregate row).
- Registration-first remains the default; provisioning is the exception.
- Every account-level operation emits its own audit event (task 8.5 — the events register there).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Flag off | `403` with `DATABRICKS_WORKSPACE_PROVISIONING_DISABLED` |
| Signoff missing or incomplete | `403` with `DATABRICKS_PROVISIONING_SIGNOFF_MISSING` |
| Non-platform-admin caller | `403` with `PERMISSION_DENIED` |

## Related

- Concepts: [Tenants](../concepts/tenants.md), [Audit Events](../concepts/audit-events.md)
- Journeys: [JOURNEY-DB-016 -- Provision a Workspace from the Account](../journeys/JOURNEY-DB-016.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
