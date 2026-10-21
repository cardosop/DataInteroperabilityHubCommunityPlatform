# UC-DB-002: Rotate Databricks Credential

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase P0 Test:** `hub/apps/databricks_admin/tests/test_workspace_journeys.py::TestJOURNEYDB002TestConnectionRotateCredentials::test_rotate_pat_rewrites_ciphertext_and_audits`

## Description

Rotate a workspace credential (PAT or OAuth M2M secret) on schedule or after a suspected leak. Rotation replaces the token on the Databricks side and rewrites the encrypted config in the Hub without exposing the plaintext.

## Preconditions

- A registered workspace with at least one `DatabricksCredential`.
- The caller is a `TENANT_ADMIN` of the owning tenant.

## Steps

1. Admin calls `POST /api/v1/databricks/workspaces/{id}/credentials/{cid}/rotate/`.
2. For PAT mode, the Hub creates a replacement via the Databricks token-management API and deletes the old PAT.
3. The Hub rewrites the encrypted `config` ciphertext in place.
4. Admin re-runs the connection test to confirm the workspace is `ACTIVE`.

## Expected Outcome

- The old PAT no longer exists on the Databricks side.
- The new credential exists only as ciphertext in the Hub.
- A `DATABRICKS_CREDENTIAL_ROTATED` audit event is written with redacted details.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Workspace unreachable during rotation | `502` with `DATABRICKS_AUTH_FAILED` (masked) |
| Credential not found | `404` |
| Non-admin caller | `403` with `PERMISSION_DENIED` |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Audit Events](../concepts/audit-events.md)
- Journeys: [JOURNEY-DB-002 -- Test Workspace Connection and Rotate Credentials](../journeys/JOURNEY-DB-002.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
