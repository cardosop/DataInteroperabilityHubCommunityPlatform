# JOURNEY-DB-004: Session Refresh and Expiry Handling

**Persona:** Any (authenticated users)
**Use Cases:** UC-DB-004

## Overview

A signed-in user keeps a long-lived Hub session while their Databricks OBO tokens refresh silently in the background. When the Databricks-configured absolute session lifetime approaches, the UI warns and prompts re-authentication — without invalidating the Hub session itself.

## Journey Steps

1. **Work with an active session** — The user runs live queries and browses the catalog; each interactive Databricks operation carries the user's access token.
2. **Silent refresh** — At half the access-token TTL the Hub refreshes the token using the stored refresh token (single-use rotation when the workspace supports it) and caches the new access token in Redis with TTL ≤ expiry.
3. **Transparent retry** — If an in-flight call returns 401, the Hub refreshes once and retries; repeated failure surfaces `DATABRICKS_OBO_REFRESH_FAILED` and fails closed (never falling back to a service credential on interactive paths).
4. **Expiry countdown** — Near the workspace's `absolute_session_lifetime`, the UI shows a non-blocking countdown and stops refresh attempts.
5. **Re-authenticate** — The user signs in again (JOURNEY-DB-003), which rebinds the (user, workspace) token pair. The Hub session is unaffected by the Databricks binding expiry.

## Success Criteria

- A single 401 triggers exactly one refresh + one retry.
- Cross-workspace token reuse never happens.
- Binding expiry never logs the user out of the Hub session.
- `DATABRICKS_OBO_TOKEN_REFRESHED` / `DATABRICKS_OBO_TOKEN_REVOKED` events fire on refresh and revocation.

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-003](JOURNEY-DB-003.md) (Sign In with Databricks)
