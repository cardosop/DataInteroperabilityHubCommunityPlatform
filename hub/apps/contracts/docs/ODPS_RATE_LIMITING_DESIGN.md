# ODPS $ref Resolution Rate Limiting Design

**Version:** 1.0.0
**Last Updated:** 2025-01-15
**Task:** 0.0.4.3 - Design Redis-based rate limiting

---

## Overview

This document describes the Redis-based rate limiting design for ODPS $ref resolution. Rate limiting prevents abuse and ensures fair resource usage across tenants and users when resolving external and local $ref references in ODPS documents.

## Architecture

### Rate Limiting Levels

Rate limiting is enforced at three hierarchical levels:

1. **Global Level**: 1000 requests per hour (across all tenants)
2. **Tenant Level**: 100 requests per hour (per tenant)
3. **User Level**: 50 requests per hour (per user within a tenant)

All three limits must pass for a request to be allowed. If any limit is exceeded, the request is rejected.

### Algorithm

Uses **sliding window algorithm** with Redis sorted sets for accurate rate limiting:

- **Prevents boundary bursts**: Unlike fixed window, sliding window prevents bursts at window boundaries
- **Accurate counting**: Uses Redis sorted sets to track individual request timestamps
- **Automatic cleanup**: Expired entries are removed automatically
- **TTL management**: Keys expire after window duration + 1 hour for cleanup

## Redis Key Format

### Key Structure

```
odps_ref_rate_limit:{level}:{identifiers}:{hour}
```

Where:
- `{level}`: One of `tenant`, `user`, or `global`
- `{identifiers}`: Level-specific identifiers
- `{hour}`: Current hour as Unix timestamp (rounded down to hour)

### Key Examples

**Per-Tenant:**
```
odps_ref_rate_limit:tenant:{tenant_id}:{hour}
```

Example:
```
odps_ref_rate_limit:tenant:550e8400-e29b-41d4-a716-446655440000:1704067200
```

**Per-User:**
```
odps_ref_rate_limit:user:{tenant_id}:{user_id}:{hour}
```

Example:
```
odps_ref_rate_limit:user:550e8400-e29b-41d4-a716-446655440000:660e8400-e29b-41d4-a716-446655440001:1704067200
```

**Global:**
```
odps_ref_rate_limit:global:{hour}
```

Example:
```
odps_ref_rate_limit:global:1704067200
```

### Hour Calculation

The `{hour}` component is calculated as:
```python
current_time = int(time.time())
current_hour = (current_time // 3600) * 3600
```

This creates 1-hour windows that reset at the top of each hour (e.g., 12:00:00, 13:00:00, 14:00:00).

## Rate Limits

### Default Limits

| Level | Limit | Window |
|-------|-------|--------|
| Global | 1000 requests | 1 hour |
| Tenant | 100 requests | 1 hour |
| User | 50 requests | 1 hour |

### Configuration

Rate limits are defined as constants in `odps_rate_limiting.py`:

```python
RATE_LIMIT_PER_TENANT = 100  # requests per hour
RATE_LIMIT_PER_USER = 50     # requests per hour
RATE_LIMIT_GLOBAL = 1000     # requests per hour
RATE_LIMIT_WINDOW = 3600     # 1 hour in seconds
```

Future enhancement: Make limits configurable via environment variables or configuration file.

## TTL Strategy

### Key Expiration

Redis keys use TTL (Time To Live) for automatic cleanup:

- **TTL Duration**: `RATE_LIMIT_WINDOW + 3600` seconds (2 hours total)
  - 1 hour for the active window
  - 1 hour buffer for cleanup after window expires

### Rationale

1. **Active Window**: Keys remain active during the 1-hour window
2. **Cleanup Buffer**: Additional 1 hour ensures keys are cleaned up even if requests stop
3. **Memory Efficiency**: Prevents accumulation of expired keys in Redis

### Implementation

```python
# Set TTL when adding request
redis_client.expire(key, RATE_LIMIT_WINDOW + 3600)
```

## Error Response Format

### ODPSRefResolutionError Exception

When rate limit is exceeded, an `ODPSRefResolutionError` exception is raised with:

- **message**: Human-readable error message
- **retry_after**: Unix timestamp when rate limit resets
- **error_code**: `RATE_LIMIT_EXCEEDED`
- **tenant_id**: Tenant ID (if applicable)
- **user_id**: User ID (if applicable)

### Error Dictionary Format

```python
{
    "error": "RATE_LIMIT_EXCEEDED",
    "message": "Tenant ODPS $ref resolution rate limit exceeded: 101/100 requests per hour",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "660e8400-e29b-41d4-a716-446655440001",  # if applicable
    "retry_after": 3600,  # seconds until retry
    "retry_after_timestamp": 1704070800  # Unix timestamp
}
```

### HTTP Response Headers

When rate limit is exceeded, include `Retry-After` header:

```
Retry-After: 3600
```

The `Retry-After` value is calculated as:
```python
current_time = int(time.time())
retry_seconds = max(0, retry_after - current_time)
```

## Implementation Details

### Sliding Window Algorithm

1. **Remove Expired Entries**: Remove entries older than window duration
   ```python
   window_start = current_time - RATE_LIMIT_WINDOW
   redis_client.zremrangebyscore(key, 0, window_start)
   ```

2. **Count Current Requests**: Count entries in sorted set
   ```python
   current_count = redis_client.zcard(key)
   ```

3. **Check Limit**: Compare count to limit
   ```python
   if current_count >= limit:
       return False, current_count, reset_time
   ```

4. **Add Request**: Add current request timestamp
   ```python
   request_id = f"{current_time}:{time.time_ns()}"
   redis_client.zadd(key, {request_id: current_time})
   ```

5. **Set TTL**: Set expiration for cleanup
   ```python
   redis_client.expire(key, RATE_LIMIT_WINDOW + 3600)
   ```

### Fail-Open Strategy

If Redis is unavailable or errors occur:
- **Allow requests**: Fail open to prevent service disruption
- **Log errors**: Log all errors for monitoring
- **Monitor**: Alert on Redis connection failures

This ensures that Redis failures don't break ODPS $ref resolution.

## Usage Example

### Basic Usage

```python
from hub.apps.contracts.odps_rate_limiting import check_rate_limit, ODPSRefResolutionError

# Check rate limit before resolving $ref
is_allowed, error = check_rate_limit(
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    user_id="660e8400-e29b-41d4-a716-446655440001"
)

if not is_allowed:
    # Rate limit exceeded
    raise error  # ODPSRefResolutionError with retry_after

# Proceed with $ref resolution
resolve_ref(ref_url)
```

### Error Handling

```python
try:
    is_allowed, error = check_rate_limit(tenant_id=tenant_id, user_id=user_id)
    if not is_allowed:
        # Return error response with Retry-After header
        return JsonResponse(
            error.to_dict(),
            status=429,  # Too Many Requests
            headers={"Retry-After": error.get_retry_after_header()}
        )
except ODPSRefResolutionError as e:
    # Handle other ODPS ref resolution errors
    return JsonResponse(e.to_dict(), status=400)
```

### Getting Rate Limit Info

```python
from hub.apps.contracts.odps_rate_limiting import get_rate_limit_info

# Get current usage without incrementing counters
info = get_rate_limit_info(tenant_id=tenant_id, user_id=user_id)

print(f"Global: {info['global']['count']}/{info['global']['limit']}")
print(f"Tenant: {info['tenant']['count']}/{info['tenant']['limit']}")
print(f"User: {info['user']['count']}/{info['user']['limit']}")
```

## Monitoring and Observability

### Metrics

Recommended Prometheus metrics:

- `odps_ref_rate_limit_checks_total`: Total rate limit checks
- `odps_ref_rate_limit_exceeded_total`: Total rate limit violations
- `odps_ref_rate_limit_redis_errors_total`: Redis connection errors
- `odps_ref_rate_limit_current_usage`: Current usage per level (gauge)

### Logging

Structured logging with:
- `odps_ref_rate_limit_exceeded`: Rate limit exceeded events
- `rate_limit_redis_error`: Redis connection/operation errors
- `rate_limit_check_error`: Rate limit check errors

### Alerts

Recommended alerts:
- High rate of rate limit violations (>10% of requests)
- Redis connection failures
- Unusual patterns in rate limit usage

## Testing

### Unit Tests

See `hub/apps/contracts/tests/test_odps_rate_limiting.py` for comprehensive unit tests covering:
- Redis key format generation
- Rate limit checking logic
- Error handling
- TTL management
- Fail-open behavior

### Integration Tests

Integration tests verify:
- Real Redis interactions
- Sliding window accuracy
- Multi-level rate limiting
- Error response format

## Future Enhancements

1. **Configurable Limits**: Make limits configurable via environment variables or config file
2. **Per-Tenant Overrides**: Allow per-tenant rate limit customization
3. **Dynamic Limits**: Adjust limits based on system load
4. **Rate Limit Exemptions**: Support exempting certain tenants/users
5. **Metrics Dashboard**: Create Grafana dashboard for rate limit monitoring

## References

- Redis Sorted Sets: https://redis.io/docs/data-types/sorted-sets/
- Sliding Window Rate Limiting: https://en.wikipedia.org/wiki/Sliding_window_protocol
- HTTP 429 Status Code: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
- Retry-After Header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After

