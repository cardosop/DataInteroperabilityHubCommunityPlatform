# JOURNEY-DB-003: Sign In with Databricks

**Persona:** Any (authenticated users)
**Use Cases:** UC-DB-003

## Overview

Users sign in to the Hub with their Databricks identity using the OAuth user-to-machine (U2M) authorization-code flow with PKCE. After sign-in the Hub holds a per-(user, workspace) token binding so that user-initiated Databricks operations execute On-Behalf-Of the user — Unity Catalog enforces the user's grants natively and Databricks audit logs attribute the real user.

## Journey Steps

1. **Click "Continue with Databricks"** — The login page offers the Databricks identity option. GCP workspaces are excluded (U2M unsupported) and show `DATABRICKS_SSO_UNAVAILABLE`.
2. **Redirect to the workspace** — The browser is sent to `GET {host}/oidc/v1/authorize` with `response_type=code`, a PKCE `code_challenge` (S256), and a random `state`. If the tenant has multiple workspaces, a chooser is shown first.
3. **Consent** — The workspace consent screen explains the requested scopes (`sql`, `all-apis`, `offline_access`) and what the Hub does on the user's behalf; tokens are stored encrypted and revocable.
4. **Callback and token exchange** — The Hub validates the returned `state` (mismatch → HTTP 400 `DATABRICKS_SSO_STATE_MISMATCH`) and exchanges the code for access + refresh tokens. A Hub-user ↔ Databricks-principal binding is created on first login.
5. **Use the session** — The Hub issues its own session; interactive Databricks operations carry the user's bearer token. Expired access tokens refresh once via the stored refresh token (repeated failure → `DATABRICKS_OBO_REFRESH_FAILED`).
6. **Log out** — Hub logout revokes the Databricks refresh tokens for every bound workspace and deletes local token material (`DATABRICKS_OBO_TOKEN_REVOKED`).

## Success Criteria

- A `state` mismatch is rejected and no tokens are stored.
- Missing `offline_access` scope means no refresh token is persisted.
- Tokens bound to workspace W1 are never sent to workspace W2.
- `DATABRICKS_SSO_LOGIN_SUCCESS` / `DATABRICKS_SSO_LOGIN_FAILED` are emitted for every attempt.

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Tenants](../concepts/tenants.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-004](JOURNEY-DB-004.md) (Session Refresh and Expiry Handling)
