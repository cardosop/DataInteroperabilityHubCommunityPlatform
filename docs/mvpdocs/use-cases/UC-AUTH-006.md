# UC-AUTH-006: SSO Login

**Persona:** [Data Engineer (DE)](../personas/data-engineer/index.md) / [External Developer (DEV)](../personas/external-developer/index.md)
**MVP Tier:** :large_orange_circle: (NET-NEW)
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_sso_login`

## Description

A user authenticates with Meshant via their organization's SAML 2.0 or
OIDC identity provider instead of using a local email-and-password
credential. The platform redirects to the external IdP, receives an
assertion or authorization code on callback, maps the external identity
to a Meshant user record, and issues a JWT session -- all without the
user managing a separate Meshant password.

## Preconditions

- The tenant administrator has configured an SSO connection
  (`SAML` or `OIDC`) in the tenant identity settings, providing the
  IdP metadata URL or discovery endpoint.
- The user has an active account with the configured IdP.
- The Meshant callback URL is registered as an allowed redirect URI in
  the IdP configuration.

## Steps

1. User navigates to the Meshant login page and clicks
   "Sign in with SSO" (or their organization name).
2. The front end calls `GET /api/v1/auth/sso/authorize?tenant_slug={slug}`
   to retrieve the IdP authorization URL.
3. The browser redirects to the IdP login page. The user authenticates
   with their corporate credentials (and MFA if required by the IdP).
4. The IdP posts a SAML assertion or redirects with an OIDC
   authorization code to the Meshant callback endpoint
   (`POST /api/v1/auth/sso/callback`).
5. **SAML flow:** Meshant validates the XML signature, extracts
   `NameID` and attribute statements.
   **OIDC flow:** Meshant exchanges the authorization code for
   `id_token` and `access_token`, validates the JWT signature against
   the IdP JWKS.
6. The API maps the external identity (`email` or `sub` claim) to an
   existing Meshant user. If no user exists and JIT provisioning is
   enabled, a new user record is created automatically.
7. Meshant issues its own JWT access token and refresh token (same
   format as [UC-AUTH-002](UC-AUTH-002.md)).
8. The user is redirected to the dashboard with an active session.

## Expected Outcome

- The user is authenticated without entering a Meshant-specific
  password.
- A valid JWT is issued containing the correct `tenant_id` and roles.
- If JIT provisioning fired, a new `User` record exists with
  `auth_provider = SSO` and an `AUDIT_USER_PROVISIONED_JIT` event is
  logged.
- An `AUDIT_USER_LOGIN_SSO` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| IdP returns error | `502 Bad Gateway` with IdP error detail |
| Signature validation fails | `401 Unauthorized` |
| No matching user and JIT disabled | `403 Forbidden` with `SSO_USER_NOT_FOUND` |
| Tenant SSO not configured | `404 Not Found` |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md), [Tenants](../../concepts/tenants.md)
- Journeys: [JOURNEY-AUTH-002 -- User Logs In](../journeys/JOURNEY-AUTH-002.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md), [External Developer](../personas/external-developer/index.md)
