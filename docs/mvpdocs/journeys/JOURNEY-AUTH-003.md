# JOURNEY-AUTH-003: User Resets Password

**Persona:** Any (registered user)
**Use Cases:** UC-AUTH-005

## Overview

A registered user who has forgotten their password initiates a
self-service reset flow, receives an email with a secure token link,
sets a new password, and confirms they can log in with the updated
credentials. The flow is designed to prevent enumeration attacks and
to comply with OWASP best practices.

## Journey Steps

1. **Click "Forgot Password"** — From the login page the user clicks
   the "Forgot your password?" link. The platform displays a form
   requesting the account email address.

2. **Enter email** — The user types their registered email and submits.
   Regardless of whether the email exists in the system, the platform
   shows an identical confirmation message: "If an account with that
   email exists, a reset link has been sent." This prevents account
   enumeration.

3. **Receive reset link** — If the email matches an active account the
   platform generates a cryptographically random token (256-bit,
   URL-safe base64), stores a SHA-256 hash of the token with a
   30-minute TTL, and sends a reset email. The email contains a
   one-time link to `meshant.com/auth/reset?token=<token>`.

4. **Set new password** — The user clicks the link. The platform
   validates the token hash and expiry. If valid the user sees a form
   to enter and confirm a new password. The new password must satisfy
   the same policy as registration (minimum 12 characters, complexity
   rules) and must not match the previous 5 passwords.

5. **Platform updates credentials** — The backend hashes the new
   password with bcrypt (cost factor 12), invalidates all existing
   refresh tokens for the account, and records a
   `auth.password_reset` [audit event](../concepts/audit-events.md).
   The used reset token is immediately revoked.

6. **Confirm login** — The user is redirected to the login page with a
   success banner. They log in with the new password and receive a
   fresh JWT session, confirming the reset is complete (see
   [JOURNEY-AUTH-002](JOURNEY-AUTH-002.md)).

## Success Criteria

- The reset token expires after 30 minutes or first use, whichever
  comes first.
- Previous refresh tokens are invalidated, forcing re-authentication
  on all devices.
- The new password is accepted only if it meets complexity rules and
  differs from the last 5 passwords.
- An `auth.password_reset` audit event is recorded.
- The user can log in with the new password immediately after reset.

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Product Owner Quickstart](../personas/data-product-owner/quickstart.md)
- Journeys: [JOURNEY-AUTH-002](JOURNEY-AUTH-002.md) (Login), [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md) (Register)
