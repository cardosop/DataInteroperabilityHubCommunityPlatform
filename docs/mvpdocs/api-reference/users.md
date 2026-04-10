# Meshant Users API

The Users API provides full user lifecycle management within a tenant.
Administrators can create, update, and deactivate user accounts, assign
roles and fine-grained permissions, and manage user profiles.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/users/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /users/ | List all users in the current tenant |
| POST | /users/ | Create a new user account |
| GET | /users/{id}/ | Get user details by ID |
| PUT | /users/{id}/ | Update user profile, status, or metadata |
| DELETE | /users/{id}/ | Deactivate a user account |
| GET | /users/{id}/roles/ | List roles assigned to a user |
| POST | /users/{id}/roles/ | Assign a role to a user |
| DELETE | /users/{id}/roles/{role_id}/ | Remove a role from a user |
| GET | /users/{id}/permissions/ | List effective permissions for a user |
| GET | /users/me/ | Get the currently authenticated user's profile |
| PUT | /users/me/ | Update the current user's own profile |

## Request / Response Examples

### POST /users/

**Request body:**

```json
{
  "email": "carol@example.com",
  "first_name": "Carol",
  "last_name": "Reyes",
  "role": "viewer"
}
```

**Response 201:**

```json
{
  "id": "usr_def456",
  "email": "carol@example.com",
  "first_name": "Carol",
  "last_name": "Reyes",
  "is_active": true,
  "roles": ["viewer"],
  "created_at": "2026-04-09T14:30:00Z"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `search` (string) -- Filter by name or email substring.
- `role` (string) -- Filter by role name (e.g., `admin`, `editor`, `viewer`).
- `is_active` (bool) -- Filter by active/deactivated status.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 403 | `USER_FORBIDDEN` | Caller lacks permission to manage users |
| 404 | `USER_NOT_FOUND` | User ID does not exist in this tenant |
| 409 | `USER_EMAIL_CONFLICT` | A user with this email already exists |
| 422 | `USER_ROLE_INVALID` | The specified role does not exist |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub users`](../cli-reference/users.md)
- SDK: [`UsersAPI`](../sdk-reference/python/users.md)
