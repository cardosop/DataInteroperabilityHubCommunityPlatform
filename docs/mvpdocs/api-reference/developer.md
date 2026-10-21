# Meshant Developer API

The Developer API provides tools for programmatic integration with the
Meshant platform. It manages API keys used for service-to-service
authentication, exposes per-key usage statistics, and surfaces current
rate-limit quotas so integrators can plan their request patterns.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/developer/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /developer/keys/ | List API keys for the current tenant |
| POST | /developer/keys/ | Create a new API key |
| GET | /developer/keys/{id}/ | Get API key metadata (key value is never re-shown) |
| PUT | /developer/keys/{id}/ | Update key name, scopes, or expiration |
| DELETE | /developer/keys/{id}/ | Revoke an API key |
| POST | /developer/keys/{id}/rotate/ | Rotate an API key and return the new value |
| GET | /developer/usage/ | Aggregated usage statistics for the current tenant |
| GET | /developer/usage/{key_id}/ | Usage statistics for a specific API key |
| GET | /developer/rate-limits/ | Current rate-limit quotas and remaining budget |
| GET | /developer/scopes/ | List available permission scopes for API keys |

## Request / Response Examples

### POST /developer/keys/

**Request body:**

```json
{
  "name": "ETL Pipeline Prod",
  "scopes": ["datasets:read", "datasets:write", "jobs:read"],
  "expires_at": "2027-04-09T00:00:00Z"
}
```

**Response 201:**

```json
{
  "id": "key_abc123",
  "name": "ETL Pipeline Prod",
  "prefix": "msh_abc1",
  "secret": "msh_abc123...full_key_shown_only_once",
  "scopes": ["datasets:read", "datasets:write", "jobs:read"],
  "expires_at": "2027-04-09T00:00:00Z",
  "created_at": "2026-04-09T15:00:00Z"
}
```

### GET /developer/rate-limits/

**Response 200:**

```json
{
  "plan": "professional",
  "limits": {
    "requests_per_minute": 600,
    "requests_per_day": 100000
  },
  "current": {
    "minute_remaining": 583,
    "day_remaining": 98450,
    "resets_at": "2026-04-09T15:01:00Z"
  }
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `since` (datetime) -- Start of usage reporting window (ISO 8601).
- `until` (datetime) -- End of usage reporting window (ISO 8601).
- `granularity` (string) -- Usage aggregation: `hourly`, `daily`, `monthly`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `DEVELOPER_SCOPE_INVALID` | One or more requested scopes do not exist |
| 404 | `DEVELOPER_KEY_NOT_FOUND` | API key ID does not exist |
| 409 | `DEVELOPER_KEY_EXPIRED` | Key has expired and cannot be used or rotated |
| 429 | `DEVELOPER_RATE_LIMITED` | Rate limit exceeded; retry after the reset time |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub developer`](../cli-reference/developer.md)
- SDK: [`DeveloperAPI`](../sdk-reference/python/developer.md)
