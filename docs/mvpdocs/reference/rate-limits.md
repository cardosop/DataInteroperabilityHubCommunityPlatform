# Rate Limits

Meshant enforces rate limits to ensure fair usage and platform stability.
Rate limits are applied per tenant and per API key.

## Rate Limit Headers

Every API response includes rate limit headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Unix timestamp (seconds) when the window resets |

### Example Response Headers

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 742
X-RateLimit-Reset: 1744207200
```

## Per-Endpoint Limits

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Read endpoints (`GET`) | 1000 requests | 1 minute |
| Write endpoints (`POST`, `PUT`, `PATCH`) | 200 requests | 1 minute |
| Search and autocomplete | 100 requests | 1 minute |
| File upload | 50 requests | 1 minute |
| Auth login / refresh | 20 requests | 1 minute |
| Bulk operations | 10 requests | 1 minute |

## Tenant Quotas

In addition to per-minute rate limits, tenants have monthly quotas based
on their subscription plan:

| Plan | Monthly API Calls | Storage | Concurrent Jobs |
|------|-------------------|---------|-----------------|
| Free | 10,000 | 1 GB | 2 |
| Pro | 500,000 | 50 GB | 10 |
| Enterprise | Unlimited | Unlimited | 50 |

When a tenant exceeds its monthly quota, the API returns `429` with the
`QUOTA_EXCEEDED` error code.

## 429 Response Handling

When you exceed the rate limit, the API returns:

```json
{
  "code": "RATE_LIMITED",
  "message": "Rate limit exceeded. Retry after 2026-04-09T14:35:00Z.",
  "details": {
    "limit": 1000,
    "remaining": 0,
    "reset_at": "2026-04-09T14:35:00Z"
  }
}
```

The response also includes a `Retry-After` header with the number of
seconds to wait:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1744207200
```

## Backoff Strategies

### Exponential Backoff

The recommended retry strategy for rate-limited requests:

```python
import time
from datahub_interoperability import DataHubClient, RateLimitError

client = DataHubClient(api_key="msh_live_...")

def fetch_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            delay = min(2 ** attempt, e.retry_after or 60)
            time.sleep(delay)

assets = fetch_with_retry(lambda: client.assets.list())
```

### curl Example

```bash
response=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  https://meshant-internal.example.com/api/v1/assets/)

http_code=$(echo "$response" | tail -1)
if [ "$http_code" = "429" ]; then
  retry_after=$(curl -sI -H "Authorization: Bearer $TOKEN" \
    https://meshant-internal.example.com/api/v1/assets/ | grep -i retry-after | awk '{print $2}')
  sleep "$retry_after"
fi
```

## Best Practices

- Monitor `X-RateLimit-Remaining` and slow down before hitting zero.
- Use API keys with appropriate scopes to avoid sharing rate limit
  budgets across unrelated integrations.
- For bulk operations, use dedicated bulk endpoints instead of looping
  over individual calls.
- Cache responses where possible to reduce unnecessary API calls.

## Related

- [Error Codes](error-codes.md) -- RATE_LIMITED and QUOTA_EXCEEDED codes
- [Authentication](authentication.md) -- per-key rate limits
- [Pagination](pagination.md) -- efficient data retrieval patterns
