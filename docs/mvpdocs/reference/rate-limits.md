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

## Rate Limit Model

Rate limits are enforced at three levels — **tenant**, **user**, and
**API key** — using a sliding window algorithm backed by Redis. Each
request is evaluated against three time windows:

| Window | Duration | Purpose |
|--------|----------|---------|
| BURST | 10 seconds | Prevents short spikes |
| SUSTAINED | 60 seconds | Per-minute rate control |
| DAILY | 24 hours | Long-term fair usage |

### Endpoint Categories

Limits are configured per endpoint category. Default platform limits apply
unless overridden by tenant configuration:

| Category | Description |
|----------|-------------|
| AUTH | Login, token refresh, password reset |
| ASSET | Asset CRUD operations |
| CONTRACT | Contract CRUD, validation, linting |
| SEARCH | Full-text search and autocomplete |
| FILE_UPLOAD | File upload initiation and chunks |
| FILE_DOWNLOAD | File downloads |
| DQ_RUN | Data quality run triggers |
| COMPLIANCE_RUN | Compliance scan triggers |
| CONTRACT_VALIDATION | Contract validation and linting |
| CATALOG_READ | Catalog browsing and listing |
| SPARQL_QUERY | SPARQL endpoint queries |
| GENERAL | All other endpoints |

### Tenant-Configurable Limits

Platform administrators can configure per-tenant rate limits via
`TenantConfig.rate_limits`. Tenant limits cannot exceed platform maximums.
When no tenant-specific configuration exists, platform defaults apply.

## 429 Response Handling

When you exceed the rate limit, the API returns:

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
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
