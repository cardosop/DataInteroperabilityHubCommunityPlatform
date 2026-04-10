# UC-AUTH-002: User Logs In

**Persona:** All ([DC](../personas/data-consumer/index.md), [DPO](../personas/data-product-owner/index.md), [DE](../personas/data-engineer/index.md), [CPO](../personas/compliance-privacy-officer/index.md), [MPA](../personas/marketplace-platform-admin/index.md), [DEV](../personas/external-developer/index.md))
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_auth_login`

## Description

An existing, verified user authenticates with Meshant using either
email-and-password credentials or an SSO provider. On success the API
issues a short-lived JWT access token and a long-lived refresh token,
establishing the authenticated session used by all subsequent API calls.

## Preconditions

- The user has a verified Meshant account (see [UC-AUTH-001](UC-AUTH-001.md)).
- For SSO logins, the tenant has a configured SAML or OIDC identity
  provider (see [UC-AUTH-006](UC-AUTH-006.md)).
- The authentication service is healthy and reachable.

## Steps

1. User navigates to the login page or calls `POST /api/v1/auth/login`
   with `{ email, password }`.
2. **Password flow:** The API validates credentials against the stored
   bcrypt hash. On match, proceed to step 5.
3. **SSO flow (alternative):** User clicks "Sign in with SSO". The front
   end redirects to the IdP authorization URL. After IdP authentication,
   the callback delivers an authorization code.
4. Meshant exchanges the authorization code for IdP tokens, maps the
   IdP identity to a local user record, and proceeds to step 5.
5. The API generates a JWT access token (15-minute TTL) and a refresh
   token (7-day TTL). Both are returned in the response body (and
   optionally as HTTP-only cookies).
6. The client stores the tokens and includes the access token in the
   `Authorization: Bearer` header of subsequent requests.
7. When the access token expires, the client calls
   `POST /api/v1/auth/refresh` with the refresh token to obtain a new
   access token without re-entering credentials.

## Expected Outcome

- The user receives a valid JWT containing `sub`, `tenant_id`, `roles`,
  and `exp` claims.
- The refresh token is persisted server-side and is rotatable.
- An `AUDIT_USER_LOGIN` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- Failed login attempts increment a per-user counter; after five
  consecutive failures the account is temporarily locked for 15 minutes.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Wrong password | `401 Unauthorized` (generic message to avoid enumeration) |
| Unverified email | `403 Forbidden` with `EMAIL_NOT_VERIFIED` code |
| Account locked | `423 Locked` with retry-after header |
| Invalid refresh token | `401 Unauthorized` -- user must re-login |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md), [Tenants](../../concepts/tenants.md)
- Journeys: [JOURNEY-AUTH-002 -- User Logs In](../journeys/JOURNEY-AUTH-002.md)
- Personas: [Persona Overview](../personas/_persona-overview.md)
