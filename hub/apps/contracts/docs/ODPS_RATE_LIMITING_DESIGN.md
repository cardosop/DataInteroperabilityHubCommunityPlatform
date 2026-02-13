# ODPS $ref Resolution Rate Limiting Design

## Overview

ODPS $ref resolution uses a **separate rate limiting system** from the platform's general API rate limiting. This document explains the rationale, implementation, and usage.

## Rationale for Separate Rate Limiting

### Why Not Use Platform Rate Limiting?

1. **Different Use Case**: ODPS $ref resolution involves:
   - External HTTP requests to remote servers
   - Caching of external resources (1-hour TTL)
   - Potential for abuse (fetching large external schemas repeatedly)
   - Different failure modes (network timeouts, DNS failures)

2. **Specialized Limits**: ODPS ref resolution requires lower limits than general API endpoints:
   - **Per-tenant**: 100 requests per hour (vs 600 requests per minute for general API)
   - **Per-user**: 50 requests per hour (vs 300 requests per minute for general API)
   - **Global**: 1000 requests per hour (platform-wide protection)

3. **Different Error Handling**: ODPS rate limiting uses `ODPSRefResolutionError` with:
   - Specialized retry-after calculation
   - Context-specific error messages
   - Integration with ODPS security logging

4. **Separate Metrics**: ODPS rate limiting tracks `odps_rate_limit_violations_total` separately from platform rate limiting metrics, allowing independent monitoring and alerting.

## Implementation

### Module: `hub.apps.contracts.odps_rate_limiting`

**Location**: `hub/apps/contracts/odps_rate_limiting.py`

**Key Functions**:
- `check_rate_limit(tenant_id, user_id, redis_client)` - Check if request is within limits
- `generate_rate_limit_key(tenant_id, user_id, level)` - Generate Redis keys
- `get_rate_limit_info(tenant_id, user_id, redis_client)` - Get current usage without incrementing

**Algorithm**: Sliding window with Redis sorted sets (same as platform rate limiting for consistency)

**Time Window**: 1 hour (3600 seconds)

**Rate Limits**:
- Global: 1000 requests/hour
- Per-tenant: 100 requests/hour
- Per-user: 50 requests/hour

### Usage in Ref-Resolver

**Location**: `hub/apps/contracts/ref_resolver.py`

**When Applied**: Before resolving external $refs (HTTP URLs)

**Example**:
```python
from hub.apps.contracts.odps_rate_limiting import check_rate_limit

# Before resolving external $ref
is_allowed, error = check_rate_limit(
    tenant_id=str(tenant.id),
    user_id=str(user.id) if user else None
)

if not is_allowed:
    raise error  # ODPSRefResolutionError with retry-after
```

## Integration with Platform Rate Limiting

### Two-Layer Protection

1. **Platform Middleware**: Applies general API rate limits to all `/api/v1/` endpoints (including ODPS endpoints)
2. **ODPS Rate Limiting**: Applies specialized limits specifically to external $ref resolution

**Result**: ODPS $ref resolution is protected by both:
- General API rate limits (via middleware)
- Specialized ODPS ref resolution limits (via in-code check)

This provides defense-in-depth: even if platform limits are high, ODPS-specific limits prevent abuse of external resource fetching.

## Monitoring and Alerting

### Metrics

- `odps_rate_limit_violations_total`: Counter of rate limit violations by level (global, tenant, user)
- Tracked separately from platform rate limiting metrics

### Alerts

- `ODPSExcessiveRateLimitViolations`: Alert when ODPS rate limit violations exceed threshold
- See `monitoring/prometheus/alerts/` for alert configuration

## Future Considerations

### Potential Unification

If platform rate limiting evolves to support:
- Custom rate limit categories per endpoint
- Different time windows per category
- Specialized error handling per category

Then ODPS rate limiting could potentially be unified with platform rate limiting. However, the current separation provides:
- Clear separation of concerns
- Independent monitoring
- Specialized error handling
- Easier maintenance

**Recommendation**: Keep ODPS rate limiting separate unless platform rate limiting gains sufficient flexibility to handle ODPS-specific requirements without complexity.

## Configuration

### Environment Variables

ODPS rate limiting uses the same Redis connection as platform rate limiting (`REDIS_URL`). No separate configuration is required.

### Rate Limit Constants

Defined in `hub/apps/contracts/odps_rate_limiting.py`:
- `RATE_LIMIT_PER_TENANT = 100` (requests per hour)
- `RATE_LIMIT_PER_USER = 50` (requests per hour)
- `RATE_LIMIT_GLOBAL = 1000` (requests per hour)
- `RATE_LIMIT_WINDOW = 3600` (1 hour in seconds)

These can be adjusted based on operational requirements.
