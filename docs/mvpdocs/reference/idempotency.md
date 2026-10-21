# Idempotency

Meshant supports idempotent requests for safe retries on `POST` and `PUT`
operations. This prevents duplicate resource creation when network errors
cause a client to retry a request that the server already processed.

## Idempotency-Key Header

Include the `Idempotency-Key` header with a unique value (typically a UUID v4)
on any `POST` or `PUT` request that creates or mutates a resource.

```bash
curl -X POST https://meshant-internal.example.com/api/v1/assets/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"name": "customer_events", "dataset_id": "d-123"}'
```

### SDK Usage

```python
from datahub_interoperability import DataHubClient
import uuid

client = DataHubClient(api_key="msh_live_...")
asset = client.assets.create(
    name="customer_events",
    dataset_id="d-123",
    idempotency_key=str(uuid.uuid4())
)
```

## How It Works

1. The client sends a request with an `Idempotency-Key` header.
2. The server checks whether a response has already been stored for that key.
3. If the key is new, the server processes the request normally and caches
   the response.
4. If the key has been seen before, the server returns the cached response
   without re-executing the operation.

### Request Flow

```
Client                          Server
  |                               |
  |-- POST /assets/ (key=abc) --> |
  |                               |-- process request
  |                               |-- store response for key=abc
  | <-- 201 Created ------------- |
  |                               |
  |-- POST /assets/ (key=abc) --> |  (retry after timeout)
  |                               |-- key=abc found in cache
  | <-- 201 Created (cached) ---- |
```

## Behavior on Duplicate Keys

| Scenario | Behavior |
|----------|----------|
| Same key, same body | Returns the cached response (same status code and body) |
| Same key, different body | Returns `409 Conflict` with code `IDEMPOTENCY_KEY_REUSED` |
| No key provided | Request is processed normally without idempotency guarantees |

## Key Expiry

Idempotency keys are stored for **24 hours** after the initial request.
After expiry, the same key can be reused for a new request without conflict.

## Safe Methods

`GET`, `DELETE`, and `HEAD` requests are inherently idempotent and do not
require the `Idempotency-Key` header. Sending the header on these methods
is harmless but has no effect.

## Best Practices

- Always generate a new UUID v4 for each logical operation.
- Store the idempotency key on the client side before sending the request,
  so you can retry with the same key if the response is lost.
- Do not reuse keys across different operations or endpoints.
- Set a reasonable retry limit (3 attempts) with exponential backoff.

## Error Responses

If the key is reused with a different request body:

```json
{
  "code": "IDEMPOTENCY_KEY_REUSED",
  "message": "Idempotency key 550e8400-... was already used with a different request body.",
  "details": {
    "original_request_at": "2026-04-09T10:30:00Z"
  }
}
```

## Related

- [Error Codes](error-codes.md) -- error response format
- [Conventions](conventions.md) -- HTTP method semantics
- [Rate Limits](rate-limits.md) -- retries and rate limiting interaction
