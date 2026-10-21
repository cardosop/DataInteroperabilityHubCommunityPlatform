# UC-AUTH-001: User Registers

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_auth_register`

## Description

A first-time visitor creates a Meshant account by completing the
registration form, verifying their email address, and logging in for the
first time. Upon successful registration the platform provisions a
personal workspace within the visitor's assigned tenant and issues an
initial JWT access token.

## Preconditions

- The visitor has a valid, unique email address not yet registered on Meshant.
- The Meshant registration endpoint (`/api/v1/auth/register`) is reachable.
- Email delivery service (SES / SMTP relay) is operational for the
  verification link.

## Steps

1. Visitor navigates to the Meshant sign-up page or calls
   `POST /api/v1/auth/register` with `{ email, password, full_name }`.
2. The API validates the payload (email format, password complexity,
   uniqueness) and returns `201 Created` with a pending-verification
   status.
3. Meshant sends a verification email containing a one-time token link.
4. Visitor clicks the verification link, which calls
   `POST /api/v1/auth/verify-email` with the token.
5. The API marks the account as **verified** and returns a confirmation.
6. Visitor logs in with `POST /api/v1/auth/login` using the credentials
   supplied during registration.
7. The API issues a JWT access token and a refresh token. The user lands
   on their personal dashboard.

## Expected Outcome

- A new `User` record exists with `status = ACTIVE` and
  `email_verified = true`.
- The user is assigned default RBAC roles (`USER`, `DATA_CONSUMER`)
  within the tenant.
- A JWT access token (short-lived) and refresh token (long-lived) are
  returned.
- An `AUDIT_USER_REGISTERED` event is written to the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Duplicate email | `409 Conflict` with `USER_ALREADY_EXISTS` code |
| Weak password | `422 Unprocessable Entity` with validation details |
| Expired verification token | `410 Gone` -- user must request a new link |
| Rate-limit exceeded | `429 Too Many Requests` |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md), [Tenants](../../concepts/tenants.md)
- Journeys: [JOURNEY-AUTH-001 -- First-Time Visitor Registers](../journeys/JOURNEY-AUTH-001.md)
- Personas: [Data Consumer](../personas/data-consumer/index.md)
