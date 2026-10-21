# JOURNEY-DB-001: Register a Databricks Workspace

**Persona:** [Data Engineer](../personas/data-engineer/), [Marketplace Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-DB-001

## Overview

A data engineer (or platform admin) onboards the tenant's customer-BYO Databricks workspace into the Hub so the control plane can manage its Unity Catalog objects, compute, jobs, and budgets. Registration is the foundation of every other Databricks capability and is gated by the tenant flag `databricks_control_plane_enabled`.

## Journey Steps

1. **Open Databricks management** — The user navigates to the Databricks workspace management page, which shows registered workspaces and a "Register workspace" call-to-action. If the tenant flag is off, the page surfaces `DATABRICKS_CONTROL_PLANE_DISABLED`.
2. **Enter workspace details** — The user provides a name, the workspace host (restricted to the `*.cloud.databricks.com` family), cloud, and region. The Hub validates the host against SSRF and residency rules at save time and re-resolves DNS at dispatch time.
3. **Save the workspace** — The Hub creates a tenant-scoped `DatabricksWorkspace` in `REGISTERED` state and writes a `DATABRICKS_WORKSPACE_REGISTERED` [audit event](../concepts/audit-events.md) with no credential material.
4. **Attach credentials** — The user adds a `DatabricksCredential` (PAT or OAuth M2M client credentials), stored encrypted at rest.
5. **Test the connection** — The Hub probes the workspace (e.g. `GET /api/2.0/workspace/list`). Success moves the workspace to `ACTIVE`; failure returns a masked reason (never the credential value) and a `DATABRICKS_WORKSPACE_TEST_FAILED` event.

## Success Criteria

- The workspace row is tenant-scoped and invisible to other tenants (RLS).
- A private-IP or metadata-IP host is rejected with HTTP 400 `SSRF_PROTECTION_TRIGGERED` and no row persisted.
- A connection test against revoked credentials returns HTTP 502 `DATABRICKS_AUTH_FAILED` with a masked message.
- Deleting a workspace with dependent objects returns HTTP 409 `DATABRICKS_WORKSPACE_HAS_DEPENDENTS`.

## Related

- Concepts: [Tenants](../concepts/tenants.md), [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-002](JOURNEY-DB-002.md) (Test Workspace Connection and Rotate Credentials), [JOURNEY-DB-003](JOURNEY-DB-003.md) (Sign In with Databricks)
