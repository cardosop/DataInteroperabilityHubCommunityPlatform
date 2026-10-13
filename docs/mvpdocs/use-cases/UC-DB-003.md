# UC-DB-003: Databricks SSO Login

**Persona:** Any (authenticated users)
**MVP Tier:** :white_check_mark:
**Phase P0b Test:** `hub/apps/databricks_admin/tests/test_sso_obo_journeys.py::TestJOURNEYDB003DatabricksSignIn::test_token_exchange_creates_binding`

## Description

Sign in to the Hub with a Databricks identity via the OAuth U2M authorization-code flow with PKCE. The Hub stores a per-(user, workspace) token binding so subsequent operations execute On-Behalf-Of the user.

## Preconditions

- The tenant has `databricks_sso_enabled=True` and at least one active workspace (AWS/Azure; GCP excluded).
- The customer's "App connection" is registered in the Databricks account console with the Hub's redirect URI.

## Steps

1. User clicks "Continue with Databricks" and picks the workspace (chooser when multiple).
2. Browser redirects to `GET {host}/oidc/v1/authorize` with PKCE `code_challenge` and a random `state`.
3. User consents to the scopes (`sql all-apis offline_access`).
4. The Hub validates `state` and exchanges the code at `POST {host}/oidc/v1/token`.
5. First login creates the Hub-user ↔ Databricks-principal binding; the Hub session is issued.

## Expected Outcome

- A token binding exists per (user, workspace); refresh token stored encrypted.
- `DATABRICKS_SSO_LOGIN_SUCCESS` audit event is written.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| State mismatch | `400` with `DATABRICKS_SSO_STATE_MISMATCH` |
| GCP workspace | `400` with `DATABRICKS_SSO_UNAVAILABLE` |
| Missing `offline_access` scope | No refresh token persisted; login still completes without OBO persistence |
| Token exchange rejected | `502` with masked reason + `DATABRICKS_SSO_LOGIN_FAILED` |

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Tenants](../concepts/tenants.md)
- Journeys: [JOURNEY-DB-003 -- Sign In with Databricks](../journeys/JOURNEY-DB-003.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md)
