# Common Reference

This section documents cross-cutting conventions and mechanisms that apply
to all Meshant APIs, the CLI, and the Python SDK.

## Topics

| Page | Description |
|------|-------------|
| [Authentication](authentication.md) | JWT tokens, API keys, SSO, scopes, and multi-tenant context |
| [Error Codes](error-codes.md) | HTTP status codes, domain-specific error codes, and error response format |
| [Pagination](pagination.md) | Offset-based and cursor-based pagination, response envelope |
| [Rate Limits](rate-limits.md) | Rate limit headers, per-endpoint limits, backoff strategies |
| [Idempotency](idempotency.md) | Idempotency-Key header, safe retries, duplicate key behavior |
| [Webhooks](webhooks.md) | Event types, payload format, HMAC verification, retry policy |
| [Conventions](conventions.md) | REST conventions, URL structure, date formats, filtering, versioning |

## Quick Links

- [API Reference](../api-reference/index.md) -- REST endpoint documentation
- [SDK Reference](../sdk-reference/python/index.md) -- Python SDK classes
- [CLI Reference](../cli-reference/) -- command-line interface
