# UC-AUTH-003: User Resets Password

**Persona:** All ([DC](../personas/data-consumer/index.md), [DPO](../personas/data-product-owner/index.md), [DE](../personas/data-engineer/index.md), [CPO](../personas/compliance-privacy-officer/index.md), [MPA](../personas/marketplace-platform-admin/index.md), [DEV](../personas/external-developer/index.md))
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_auth_reset_password`

## Description

A user who has forgotten their password initiates a self-service reset
flow. The platform sends a time-limited reset link to the user's
registered email. Clicking the link allows the user to set a new
password and immediately regain access.

## Preconditions

- The user has an existing, verified Meshant account.
- The email delivery service is operational.
- The user has access to the email inbox associated with their account.

## Steps

1. User clicks "Forgot password?" on the login page or calls
   `POST /api/v1/auth/forgot-password` with `{ email }`.
2. The API always returns `200 OK` regardless of whether the email
   exists (prevents user enumeration).
3. If the email matches a verified account, the platform generates a
   one-time reset token (valid for 30 minutes) and sends a reset link
   to the user's inbox.
4. User clicks the link in the email, which opens the reset-password
   page with the token pre-filled.
5. User enters a new password (must satisfy complexity rules) and
   submits the form, which calls
   `POST /api/v1/auth/reset-password` with `{ token, new_password }`.
6. The API validates the token (not expired, not already used), hashes
   the new password, updates the user record, and invalidates all
   existing refresh tokens for the account.
7. The API returns `200 OK` confirming the password has been changed.
8. User logs in with the new password (see [UC-AUTH-002](UC-AUTH-002.md)).

## Expected Outcome

- The user's password hash is updated in the database.
- All previously issued refresh tokens for this user are revoked,
  forcing re-authentication on other devices.
- An `AUDIT_PASSWORD_RESET` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- The one-time reset token is marked as consumed and cannot be reused.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Expired reset token | `410 Gone` with instruction to request a new link |
| Already-used token | `410 Gone` |
| Weak new password | `422 Unprocessable Entity` with validation details |
| Rate-limit on reset requests | `429 Too Many Requests` |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md)
- Journeys: [JOURNEY-AUTH-003 -- User Resets Password](../journeys/JOURNEY-AUTH-003.md)
- Personas: [Persona Overview](../personas/_persona-overview.md)
