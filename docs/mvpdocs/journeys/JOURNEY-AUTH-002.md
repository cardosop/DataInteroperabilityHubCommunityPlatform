# JOURNEY-AUTH-002: User Logs In

**Persona:** Any (registered user)
**Use Cases:** UC-AUTH-003, UC-AUTH-004

## Overview

A registered Meshant user authenticates via email/password or SSO,
receives a JWT session, and lands on their tenant dashboard. This
journey covers both credential-based and federated login paths
including token lifecycle management.

## Journey Steps

1. **Navigate to login** — The user visits the login page either by
   clicking "Sign In" from the public homepage or by being redirected
   after an expired session. The page displays email/password fields and
   SSO provider buttons (Google, GitHub).

2. **Enter credentials or initiate SSO** — For email/password login
   the user enters their verified email and password. For SSO the user
   clicks the provider button and completes the OAuth 2.0 / OIDC
   authorization flow in the provider's consent screen.

3. **Platform authenticates** — The backend validates credentials
   against the stored bcrypt hash (email/password) or verifies the
   OIDC `id_token` (SSO). Failed attempts increment a per-account
   counter; after 5 consecutive failures the account is locked for
   15 minutes. All attempts are logged as
   [audit events](../concepts/audit-events.md).

4. **Receive JWT** — On success the platform issues a signed JWT
   access token (15-minute expiry, RS256) containing the user's
   `user_id`, `tenant_id`, and role claims. A refresh token (7-day
   expiry, opaque) is also issued and stored in an HttpOnly cookie.

5. **Land on dashboard** — The frontend stores the access token in
   memory (never localStorage) and redirects to the tenant dashboard.
   The dashboard fetches the user's recent [assets](../concepts/assets.md),
   pending [DQ runs](../concepts/dq-runs.md), and notification count.

6. **Token refresh cycle** — While the session is active the frontend
   silently refreshes the access token before expiry using the refresh
   token endpoint. If the refresh token itself expires the user is
   redirected to the login page.

## Success Criteria

- The user is authenticated and holds a valid JWT with correct claims.
- An `auth.login` audit event is recorded with method (`password` or
  `sso:{provider}`).
- The dashboard loads within 2 seconds of authentication.
- Failed login attempts surface a generic "invalid credentials" message
  (no information leakage about which field was wrong).
- Token refresh works transparently without user interaction.

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Audit Events](../concepts/audit-events.md), [Tenants](../concepts/tenants.md)
- How-To: [Data Product Owner Quickstart](../personas/data-product-owner/quickstart.md)
- Journeys: [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md) (Register), [JOURNEY-AUTH-003](JOURNEY-AUTH-003.md) (Reset Password)
