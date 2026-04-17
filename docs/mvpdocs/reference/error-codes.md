# Error Codes

Every error response from the Meshant API returns a consistent JSON envelope
with an HTTP status code, a machine-readable error code, a human-readable
message, and optional structured details.

## Error Response Format

```json
{
  "error": {
    "code": "ASSET_NOT_FOUND",
    "message": "Asset with ID a-999 does not exist.",
    "http_status": 404,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-04-17T12:00:00Z",
    "details": {
      "asset_id": "a-999"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error.code` | `string` | Machine-readable error code (see tables below) |
| `error.message` | `string` | Human-readable description |
| `error.http_status` | `integer` | HTTP status code |
| `error.request_id` | `string` | UUID for support tickets |
| `error.timestamp` | `string` | ISO 8601 UTC timestamp |
| `error.details` | `object` | Optional context-specific fields |

## Standard HTTP Error Codes

| Status | Meaning | When It Occurs |
|--------|---------|----------------|
| `400` | Bad Request | Malformed JSON, missing required fields, invalid query parameters |
| `401` | Unauthorized | Missing or expired JWT token, invalid API key |
| `403` | Forbidden | Authenticated but insufficient permissions for the requested action |
| `404` | Not Found | Resource does not exist or is not accessible in the current tenant |
| `409` | Conflict | Resource already exists, version conflict, or state transition violation |
| `422` | Unprocessable Entity | Request is well-formed but fails business validation rules |
| `429` | Too Many Requests | Rate limit exceeded; check `Retry-After` header |
| `500` | Internal Server Error | Unexpected server failure; retry with exponential backoff |

## Domain-Specific Error Codes

These codes appear in the `code` field of the error response body alongside
the appropriate HTTP status code.

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ASSET_NOT_FOUND` | 404 | The requested asset does not exist in the current tenant |
| `CONTRACT_VALIDATION_FAILED` | 422 | The data contract failed schema or rule validation |
| `DQ_CHECK_FAILED` | 422 | One or more data quality checks did not pass |
| `COMPLIANCE_SCAN_FAILED` | 422 | The compliance scan encountered errors during execution |
| `MVP_FEATURE_GATED` | 403 | The requested feature is not available in the current MVP release |
| `QUOTA_EXCEEDED` | 429 | The tenant has exceeded its usage quota for this resource |
| `TENANT_NOT_FOUND` | 404 | The specified tenant does not exist or the user has no access |
| `WEBHOOK_DELIVERY_FAILED` | 422 | The webhook endpoint did not respond with a 2xx status |
| `AUTH_TOKEN_EXPIRED` | 401 | The JWT access token has expired; use the refresh endpoint |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests; see `X-RateLimit-Reset` header for retry time |

## SDK Exception Mapping

The Python SDK maps these codes to typed exceptions:

```python
from datahub_interoperability import (
    DataHubClient,
    NotFoundError,          # 404
    ValidationError,        # 422
    AuthenticationError,    # 401
    ForbiddenError,         # 403
    ConflictError,          # 409
    RateLimitError,         # 429
    MVPGatedFeatureError,   # MVP_FEATURE_GATED
    ServerError,            # 500
)

client = DataHubClient(api_key="msh_live_...")
try:
    asset = client.assets.get("a-999")
except NotFoundError as e:
    print(f"Code: {e.code}, Message: {e.message}")
except RateLimitError as e:
    print(f"Retry after {e.retry_after} seconds")
```

## Handling Errors in curl

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  https://meshant-internal.example.com/api/v1/assets/a-999/
```

A non-2xx response always includes the JSON error body described above.

## Best Practices

- Always check the `code` field for programmatic error handling, not the
  `message` field which may change between releases.
- Log the `request_id` value when reporting issues to Meshant support.
- On `429` responses, respect the `Retry-After` header before retrying.
- On `500` responses, retry with exponential backoff (initial delay 1s,
  max 3 retries).

## Related

- [Authentication](authentication.md) -- token lifecycle and 401 handling
- [Rate Limits](rate-limits.md) -- rate limit headers and backoff strategies
- [Conventions](conventions.md) -- general API conventions
