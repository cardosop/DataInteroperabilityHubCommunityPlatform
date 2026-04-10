# Meshant Tenants API

The Tenants API manages multi-tenant workspaces on the Meshant platform.
Each tenant is an isolated namespace that owns datasets, contracts, and
users. Use this API to create tenants, invite members, and switch the
active tenant context.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/tenants/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /tenants/ | List tenants the current user belongs to |
| POST | /tenants/ | Create a new tenant |
| GET | /tenants/{id}/ | Get tenant details by ID |
| PUT | /tenants/{id}/ | Update tenant name, settings, or metadata |
| DELETE | /tenants/{id}/ | Delete a tenant (owner only) |
| GET | /tenants/{id}/members/ | List members of a tenant |
| POST | /tenants/{id}/members/ | Invite a user to the tenant |
| PUT | /tenants/{id}/members/{user_id}/ | Update a member's role |
| DELETE | /tenants/{id}/members/{user_id}/ | Remove a member from the tenant |
| POST | /tenants/switch/ | Switch the active tenant context for the session |

## Request / Response Examples

### POST /tenants/

**Request body:**

```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "professional"
}
```

**Response 201:**

```json
{
  "id": "tnt_xyz",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "professional",
  "created_at": "2026-04-09T12:00:00Z",
  "owner_id": "usr_abc123"
}
```

### POST /tenants/{id}/members/

**Request body:**

```json
{
  "email": "bob@example.com",
  "role": "editor"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `search` (string) -- Filter tenants by name substring.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 403 | `TENANT_FORBIDDEN` | User does not have permission on this tenant |
| 404 | `TENANT_NOT_FOUND` | Tenant ID does not exist |
| 409 | `TENANT_SLUG_CONFLICT` | Slug is already taken |
| 422 | `TENANT_PLAN_INVALID` | Requested plan is not available |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub tenants`](../cli-reference/tenants.md)
- SDK: [`TenantsAPI`](../sdk-reference/python/tenants.md)
