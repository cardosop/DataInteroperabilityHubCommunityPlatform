# ODPS $ref Cache Warming Strategy

**Version:** 1.0.0
**Last Updated:** 2026-01-02
**Task:** 9.8.4.3 - Implement Cache Warming Strategy

---

## Overview

This document describes the cache warming strategy for ODPS external $ref resolution. Cache warming pre-populates the Redis cache with frequently accessed external references to improve response times and reduce external API calls.

## Cache Warming Strategy

### Objectives

1. **Improve Response Times**: Pre-populate cache with frequently accessed refs to reduce cache misses
2. **Reduce External API Calls**: Minimize requests to external URLs by ensuring popular refs are cached
3. **Optimize Resource Usage**: Focus warming efforts on refs that provide the most value

### Frequently Accessed Refs Identification

Frequently accessed refs are identified using Redis sorted sets that track access counts per URL:

- **Access Tracking**: Each external ref URL access increments a counter in Redis sorted set
- **Key Format**: `odps_ref_access:all` (sorted set with URL hash as member, access count as score)
- **URL Mapping**: `odps_ref_access:url:{url_hash}` stores the actual URL for hash lookup
- **TTL**: Access tracking data expires after 24 hours (same as cache stats)

### Cache Warming Triggers

Cache warming is performed in three scenarios:

#### 1. Application Startup

- **Trigger**: When Django application starts (via AppConfig.ready())
- **Scope**: Top 100 most frequently accessed refs
- **Timing**: Asynchronous background task to avoid blocking startup
- **Configuration**: Controlled by `ODPS_CACHE_WARMING_ENABLED` setting (default: True)

#### 2. Scheduled Warming

- **Trigger**: Daily scheduled job (via Django management command or cron)
- **Scope**: Top 1000 most frequently accessed refs
- **Timing**: Runs once per day during low-traffic hours (configurable)
- **Configuration**: Controlled by `ODPS_CACHE_WARMING_SCHEDULED_ENABLED` setting (default: True)

#### 3. On-Demand Warming

- **Trigger**: When a ref is accessed but not in cache (cache miss)
- **Scope**: Single ref being accessed
- **Timing**: Immediate, synchronous (non-blocking)
- **Configuration**: Always enabled (part of normal ref resolution flow)

### Cache Warming Batch Size

- **Startup**: 100 refs (configurable via `ODPS_CACHE_WARMING_STARTUP_LIMIT`)
- **Scheduled**: 1000 refs (configurable via `ODPS_CACHE_WARMING_SCHEDULED_LIMIT`)
- **On-Demand**: 1 ref (immediate warming on cache miss)

### Cache Warming Process

1. **Identify Frequently Accessed Refs**:
   - Query Redis sorted set `odps_ref_access:all`
   - Sort by access count (score) descending
   - Take top N refs based on batch size

2. **Resolve and Cache Refs**:
   - For each ref URL:
     - Check if already cached (skip if cached)
     - Resolve ref using RefResolver.resolve_external()
     - Cache result automatically via RefResolver._set_cache()
     - Handle errors gracefully (log and continue)

3. **Progress Reporting**:
   - Log progress every 10 refs
   - Report success/failure counts
   - Track total time taken

### Error Handling

- **Individual Ref Failures**: Log warning and continue with next ref
- **Redis Unavailable**: Skip warming gracefully (cache will populate naturally)
- **Rate Limit Exceeded**: Respect rate limits, skip refs that would exceed limits
- **Invalid URLs**: Skip invalid URLs, log warning

### Configuration

Settings in `hub/settings.py`:

```python
# Cache warming configuration
ODPS_CACHE_WARMING_ENABLED = True  # Enable cache warming
ODPS_CACHE_WARMING_STARTUP_ENABLED = True  # Enable startup warming
ODPS_CACHE_WARMING_SCHEDULED_ENABLED = True  # Enable scheduled warming
ODPS_CACHE_WARMING_STARTUP_LIMIT = 100  # Number of refs to warm on startup
ODPS_CACHE_WARMING_SCHEDULED_LIMIT = 1000  # Number of refs to warm in scheduled job
ODPS_CACHE_WARMING_BATCH_SIZE = 10  # Process refs in batches of N
```

### Management Command

Cache warming can be triggered manually via management command:

```bash
# Warm top 100 refs (default)
python manage.py warm_odps_ref_cache

# Warm top N refs
python manage.py warm_odps_ref_cache --limit 500

# Warm refs matching URL pattern
python manage.py warm_odps_ref_cache --url-pattern "https://example.com/*"

# Dry-run mode (no actual warming)
python manage.py warm_odps_ref_cache --dry-run

# Warm for specific tenant
python manage.py warm_odps_ref_cache --tenant-id <uuid>
```

### Monitoring

Cache warming effectiveness is monitored via:

- **Metrics**: `odps_ref_cache_hit_rate` gauge (should increase after warming)
- **Logs**: Structured logging for warming operations
- **Redis Stats**: Access counts in `odps_ref_access:all` sorted set

### Performance Considerations

- **Startup Warming**: Runs asynchronously to avoid blocking application startup
- **Scheduled Warming**: Runs during low-traffic hours to minimize impact
- **On-Demand Warming**: Immediate but non-blocking (part of normal flow)
- **Batch Processing**: Processes refs in configurable batches to avoid overwhelming Redis/network

### Future Enhancements

- **Predictive Warming**: Use ML to predict which refs will be accessed
- **Tenant-Specific Warming**: Warm refs per tenant based on tenant access patterns
- **Time-Based Warming**: Warm refs based on time-of-day access patterns
- **Cost-Aware Warming**: Prioritize warming based on external API costs

---

## Implementation Details

### Access Tracking

Per-URL access tracking is implemented in `RefResolver._track_ref_access()`:

- Tracks access count per URL using Redis sorted set
- Stores URL mapping for hash-to-URL lookup
- Expires after 24 hours (same as cache stats)

### Cache Warming Functions

Located in `hub/apps/contracts/ref_warming.py`:

- `get_frequently_accessed_refs(limit: int, min_access_count: int = 1) -> List[str]`: Get top N frequently accessed ref URLs
- `warm_ref_cache(ref_urls: List[str], tenant_id: Optional[str] = None) -> Dict[str, Any]`: Warm cache for list of ref URLs
- `warm_cache_on_startup()`: Startup cache warming (called from AppConfig.ready())

### Management Command

Located in `hub/apps/contracts/management/commands/warm_odps_ref_cache.py`:

- Supports multiple warming modes (limit, URL pattern, tenant-specific)
- Dry-run mode for testing
- Progress reporting and error handling

---

## References

- [ODPS $ref Resolution Rate Limiting Design](contracts/docs/ODPS_RATE_LIMITING_DESIGN.md)
- [ODPS Cache Performance Dashboard](../../monitoring/grafana/dashboards/odps-cache-performance.json)

