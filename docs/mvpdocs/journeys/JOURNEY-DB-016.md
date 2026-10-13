# JOURNEY-DB-016: Provision a Workspace from the Account

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-DB-016

## Overview

For the optional hub-owned account plane, a platform admin provisions workspaces and metastores for tenants through the Databricks account API from a platform-scoped account link. Registration-first stays the default operating model: provisioning is flag-gated and requires a recorded DPO/Legal signoff because it creates external infrastructure.

## Journey Steps

1. **The account link exists** — The platform admin works with the `DatabricksAccount` PLATFORM row (admin-DB access, no tenant RLS, the encrypted account-level admin credential) — linked at task 8.2; the `DATABRICKS_ACCOUNT_LINKED` audit event ships with task 8.5.
2. **Create a metastore** — The admin provisions a metastore via the account API (`POST /api/v1/databricks/accounts/{id}/metastores/`) — the `DATABRICKS_METASTORE_CREATED` audit event ships with task 8.5.
3. **Provision a workspace** — With `databricks_workspace_provisioning_enabled` and a COMPLETE signoff record (by + at + evidence URL) on the account row, the admin creates a workspace (`POST /api/v1/databricks/accounts/{id}/workspaces/`) and the registry row attaches to the tenant through the EXISTING host/region validation — the `DATABRICKS_WORKSPACE_PROVISIONED` audit event ships with task 8.5.
4. **Review the estate** — The cross-tenant estate summary (`GET /api/v1/databricks/estate-summary/`, task 8.4) aggregates workspace counts by state and budget figures across tenants for the platform admins.

## Success Criteria

- Account-plane operations run only through the admin DB connection (BYPASSRLS) with platform-admin RBAC — the account row resolves through the forced admin alias and the estate summary is an admin-alias aggregate.
- Provisioning is refused with 403 (`DATABRICKS_WORKSPACE_PROVISIONING_DISABLED` / `DATABRICKS_PROVISIONING_SIGNOFF_MISSING`) and ZERO network calls without the flag or without the complete signoff record.
- Every account-level operation emits its own audit event (task 8.5 — the three events register there; the 8.6 journey pin drives the landed 8.2–8.4 spine).

## Related

- Concepts: [Tenants](../concepts/tenants.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-001](JOURNEY-DB-001.md) (Register a Databricks Workspace)
