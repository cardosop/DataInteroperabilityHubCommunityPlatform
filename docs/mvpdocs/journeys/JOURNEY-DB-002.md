# JOURNEY-DB-002: Test Workspace Connection and Rotate Credentials

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-DB-002

## Overview

A platform admin validates that a registered Databricks workspace is reachable with its stored credentials and rotates those credentials on a schedule or after a suspected leak. Rotation rewrites the encrypted ciphertext in place and deletes the old token on the Databricks side.

## Journey Steps

1. **Open workspace detail** — The admin opens the registered workspace and views its status (`REGISTERED`, `CONNECTING`, `ACTIVE`, `ERROR`, `DISABLED`) and the credential list.
2. **Run a connection test** — The Hub probes the workspace. A healthy workspace returns latency metadata and a `DATABRICKS_WORKSPACE_TEST_PASSED` event; a revoked credential returns HTTP 502 `DATABRICKS_AUTH_FAILED` with a masked message and a `DATABRICKS_WORKSPACE_TEST_FAILED` event.
3. **Rotate a PAT** — The admin triggers rotation. For PAT mode the Hub creates a replacement token via the Databricks token-management API, deletes the old token, and rewrites the encrypted config.
4. **Verify rotation** — The admin re-runs the connection test. The workspace returns to `ACTIVE` and a `DATABRICKS_CREDENTIAL_ROTATED` [audit event](../concepts/audit-events.md) is written without token material.

## Success Criteria

- Test failures never echo credential values in the response or audit payload.
- After rotation, the old PAT is deleted on the Databricks side and the new PAT exists only as ciphertext in the Hub.
- Every rotation emits `DATABRICKS_CREDENTIAL_ROTATED` with redacted details.

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-001](JOURNEY-DB-001.md) (Register a Databricks Workspace)
