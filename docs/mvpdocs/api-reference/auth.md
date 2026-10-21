# Meshant Authentication API

The Authentication API handles user login, logout, JWT token lifecycle,
email verification, and password reset flows. These endpoints are the
entry point for every authenticated session on the platform.

## Authentication

Most endpoints in this group are **public** (no token required).
Endpoints that mutate the current session (logout, refresh) require
a valid JWT bearer token in the `Authorization` header.
See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/auth/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/login/ | Authenticate with email and password, receive JWT pair |
| POST | /auth/logout/ | Revoke the current refresh token |
| POST | /auth/token/refresh/ | Exchange a refresh token for a new access token |
| POST | /auth/token/verify/ | Verify that an access token is still valid |
| POST | /auth/register/ | Create a new user account (when self-registration is enabled) |
| POST | /auth/verify-email/ | Confirm email address using the token from the verification email |
| POST | /auth/password/reset/ | Request a password-reset email |
| POST | /auth/password/reset/confirm/ | Set a new password using the reset token |
| POST | /auth/password/change/ | Change password for the currently authenticated user |
| GET  | /auth/me/ | Return profile and permissions for the current user |

## Request / Response Examples

### POST /auth/login/

**Request body:**

```json
{
  "email": "alice@example.com",
  "password": "s3cureP@ss"
}
```

**Response 200:**

```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": "usr_abc123",
    "email": "alice@example.com",
    "tenant_id": "tnt_xyz"
  }
}
```

### POST /auth/token/refresh/

**Request body:**

```json
{
  "refresh": "eyJ..."
}
```

**Response 200:**

```json
{
  "access": "eyJ..."
}
```

## Common Parameters

- `next` (string) -- Redirect URL after email verification (query param on verify-email).

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 401 | `AUTH_INVALID_CREDENTIALS` | Email or password is incorrect |
| 401 | `AUTH_TOKEN_EXPIRED` | Access or refresh token has expired |
| 403 | `AUTH_EMAIL_NOT_VERIFIED` | Login blocked until email is confirmed |
| 429 | `AUTH_RATE_LIMITED` | Too many login attempts; retry after cooldown |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub auth`](../cli-reference/auth.md)
- SDK: [`AuthAPI`](../sdk-reference/python/auth.md)
