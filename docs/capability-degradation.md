# Capability Degradation Guide

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26

---

## Overview

This guide documents how Meshant degrades gracefully when external dependencies are unavailable. Each dependency has a circuit breaker pattern to prevent cascading failures.

## Dependency Impact Matrix

| Dependency          | Impact When Down                                              | Degraded Mode                        | Recovery         |
|---------------------|---------------------------------------------------------------|--------------------------------------|------------------|
| PostgreSQL          | Full outage — all reads/writes fail                           | 503 Service Unavailable              | Auto-reconnect   |
| Redis (cache)       | Cache misses; increased DB load; slower responses             | Bypass cache, serve from DB          | Auto-reconnect   |
| Redis (queue)       | Async jobs not processed; webhooks delayed                    | Queue backpressure; retry on recover | Auto-reconnect   |
| MinIO / S3          | File upload/download fails                                    | Return 503 for file operations only  | Auto-reconnect   |
| Fuseki              | Semantic/SPARQL queries fail                                  | Return 503 for semantic endpoints    | Auto-reconnect   |
| Compliance Service  | Compliance scans cannot run                                   | Return 503 for compliance endpoints  | Health check poll |
| Prefect             | Scheduled ingestion/DQ runs not orchestrated                  | Manual trigger via API still works   | Health check poll |

## Circuit Breaker Implementation

Each external integration uses a circuit breaker pattern:

1. **Closed** (normal): Requests flow through normally
2. **Open** (tripped): After N consecutive failures, requests are short-circuited with a fallback response
3. **Half-Open** (probe): After cooldown, a single request is allowed through to test recovery

### Configuration

Circuit breaker thresholds are configured per-dependency in `hub/settings.py`:

```python
CIRCUIT_BREAKER_DEFAULTS = {
    "failure_threshold": 5,
    "recovery_timeout": 30,  # seconds
    "expected_exception": ConnectionError,
}
```

## PostgreSQL

- **Detection**: Connection pool exhaustion or query timeout
- **Impact**: Complete service outage
- **Mitigation**: PgBouncer connection pooling, read replica failover
- **Recovery**: Automatic reconnection via Django's `CONN_HEALTH_CHECKS`

## Redis

- **Detection**: `ConnectionError` or `TimeoutError` on cache/queue operations
- **Impact**: Degraded performance (cache miss), delayed async processing (queue)
- **Mitigation**: Cache operations wrapped in try/except with graceful fallback
- **Recovery**: Automatic reconnection; queue jobs retried on recovery

## MinIO / S3

- **Detection**: `ClientError` or connection timeout on storage operations
- **Impact**: File operations fail; core CRUD unaffected
- **Mitigation**: Return 503 only for file-related endpoints
- **Recovery**: Automatic on storage availability

## Fuseki

- **Detection**: HTTP timeout or connection refused on SPARQL endpoint
- **Impact**: Semantic search and ontology features unavailable
- **Mitigation**: Return 503 for semantic endpoints; other features unaffected
- **Recovery**: Health check polling with exponential backoff

## Compliance Service

- **Detection**: gRPC or HTTP health check failure
- **Impact**: Compliance scans cannot run; existing results still readable
- **Mitigation**: Queue compliance requests; process on recovery
- **Recovery**: Health check poll every 30 seconds

## Prefect

- **Detection**: API health endpoint failure
- **Impact**: Scheduled workflows don't execute; manual triggers still work
- **Mitigation**: Workflows queued in database; executed on recovery
- **Recovery**: Prefect server health check polling
