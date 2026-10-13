# UC-DB-004: On-Behalf-Of Query Execution

**Persona:** [Data Engineer](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase P0b Test:** `hub/apps/databricks_admin/tests/test_sso_obo_journeys.py::TestJOURNEYDB004SessionRefreshExpiry::test_401_refresh_retry_once`

## Description

Execute user-initiated Databricks operations with the user's own U2M access token, so Unity Catalog enforces the user's grants natively and workspace audit logs attribute the real user. Expired tokens refresh once and retry.

## Preconditions

- The user has an active OBO token binding for the target workspace.
- The tenant has `databricks_obo_enabled=True`.

## Steps

1. User runs a live query or browses the catalog; the Hub attaches the user's access token as the request bearer.
2. On HTTP 401 the Hub refreshes the token once via the stored refresh token and retries.
3. UC evaluates the query against the user's grants; the result is returned.
4. On repeated refresh failure the operation fails closed with `DATABRICKS_OBO_REFRESH_FAILED`.

## Expected Outcome

- Databricks-side audit shows the user's principal, not a service credential.
- A table the user lacks SELECT on returns a UC permission error attributed to the user.
- Exactly one refresh + one retry occurs per 401.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| No bound token for the workspace | `502` with `DATABRICKS_OBO_REFRESH_FAILED` (fail closed, no service fallback — the catalogue row in `docs/api/error-codes.md` is the canonical status; reconciled when task 1.3 shipped the first live surface for this code) |
| Refresh rejected after rotation | `502` with `DATABRICKS_OBO_REFRESH_FAILED` + re-login prompt |
| Cross-workspace token reuse attempt | Refused — token never sent to a non-bound workspace |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Governance](../concepts/governance.md)
- Journeys: [JOURNEY-DB-004 -- Session Refresh and Expiry Handling](../journeys/JOURNEY-DB-004.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
