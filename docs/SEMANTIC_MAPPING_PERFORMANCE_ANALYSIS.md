# Semantic Mapping Performance Analysis and Improvement Opportunities

## Executive Summary

Semantic mapping operations are experiencing significant slowness, with operations timing out after 60-120 seconds. This document provides a deep analysis of the bottlenecks and proposes concrete improvements.

## Current Performance Issues

### 1. **Timeout Configuration**

**Current State:**
- Semantic service client timeout: **60 seconds** (production), **10 seconds** (tests)
- Fuseki client timeout: **30 seconds** per operation
- Total potential wait time: **120 seconds** (60s timeout + retry with backoff)

**Location:** `hub/apps/semantic/service_client.py:80`

**Impact:**
- Each semantic mapping call can take up to 60 seconds before timing out
- With retry logic (1 retry), total time can reach 120 seconds
- Circuit breaker opens after failures, causing immediate fallback

### 2. **Retry Logic Overhead**

**Current State:**
- Max retries: **1** (reduced from 2)
- Backoff factor: **0.5 seconds**
- Exponential backoff: `backoff_factor * (2 ** attempt)`
- Total retry delay: Up to **1 second** (0.5s * 2^0) + **1 second** (0.5s * 2^1) = **2 seconds**

**Location:** `hub/apps/semantic/service_client.py:85-86, 110-151`

**Impact:**
- Adds 1-2 seconds delay on retries
- Combined with 60s timeout, can extend total time to 120+ seconds

### 3. **Circuit Breaker Behavior**

**Current State:**
- Failure threshold: **5 failures**
- Timeout: **60 seconds** before attempting HALF_OPEN
- Success threshold: **2 successes** needed to close circuit
- Redis-backed state (falls back to in-memory if Redis unavailable)

**Location:** `hub/apps/core/resilience/circuit_breaker.py`

**Impact:**
- After 5 failures, circuit opens immediately (no wait)
- Falls back to degraded mode (returns immediately)
- But initial 5 failures still take 60s each = **300 seconds** before circuit opens

### 4. **Fuseki Operations**

**Current State:**
- Dataset existence check: **Cached** (5-minute TTL) ✅
- Query result cache: **Implemented** (60s for ASK, 300s for SELECT) ✅
- Connection pooling: **Implemented** (20 keepalive, 100 max) ✅
- Store graph timeout: **30 seconds**
- Dataset creation: **5 seconds** timeout

**Location:** `services/semantic-service/fuseki_client.py`

**Bottlenecks:**
- Large graphs: Converting triples to SPARQL INSERT DATA format can be slow
- Fuseki processing: Large INSERT DATA operations can take time
- Network latency: HTTP calls to Fuseki add latency

**Optimizations Already Implemented:**
- ✅ Dataset existence caching (avoids repeated checks)
- ✅ Query result caching (reduces repeated queries)
- ✅ Connection pooling (reuses HTTP connections)
- ✅ Async query operations (eliminates thread pool overhead)

### 5. **Graph Size Impact**

**Current State:**
- Each contract can generate **hundreds to thousands** of triples
- ODPS contracts with multilingual details generate even more triples
- Large INSERT DATA statements can be slow to process

**Location:** `services/semantic-service/fuseki_client.py:222-296`

**Impact:**
- Large graphs take longer to:
  - Convert to SPARQL format (O(n) where n = triples)
  - Send over HTTP (large payloads)
  - Process in Fuseki (INSERT DATA operations)

## Root Cause Analysis

### Primary Bottleneck: Fuseki Service Unavailability

**Evidence:**
- Test shows semantic service call timing out after 60 seconds
- Circuit breaker opening after failures
- Network errors: "timed out" after 60s

**Likely Causes:**
1. **Fuseki service not responding** - Most likely cause
2. **Network connectivity issues** - Service unreachable
3. **Fuseki overloaded** - Processing too many requests
4. **Large graph processing** - Taking longer than 30s timeout

### Secondary Bottlenecks

1. **Sequential Processing** - ODPS and ODCS contracts mapped sequentially (now parallel in workflow)
2. **No Request Batching** - Each contract mapped individually
3. **No Incremental Updates** - Full remapping even for small changes
4. **No Background Processing** - Synchronous mapping blocks workflow

## Improvement Opportunities

### 1. **Reduce Timeouts (High Impact)**

**Current:** 60s timeout for semantic service, 30s for Fuseki
**Proposed:**
- Semantic service: **15 seconds** (production), **5 seconds** (tests)
- Fuseki operations: **10 seconds** (production), **3 seconds** (tests)

**Impact:**
- Faster failure detection
- Reduces total wait time from 120s to 30s
- Circuit breaker opens faster (75s instead of 300s)

**Implementation:**
```python
# hub/apps/semantic/service_client.py
if 'pytest' in sys.modules or 'unittest' in sys.modules:
    default_timeout = 5  # Reduced from 10
else:
    default_timeout = 15  # Reduced from 60
```

```python
# services/semantic-service/fuseki_client.py
timeout=10.0  # Reduced from 30.0 for production
timeout=3.0   # For tests
```

### 2. **Eliminate Retries for Timeouts (High Impact)**

**Current:** Retries on all errors, including timeouts
**Proposed:** Don't retry on timeout errors (service is clearly unavailable)

**Impact:**
- Saves 1-2 seconds on timeout failures
- Faster failure detection

**Implementation:**
```python
# hub/apps/semantic/service_client.py
except httpx.TimeoutException as e:
    # Don't retry timeouts - service is clearly unavailable
    logger.warning(f"Semantic service timeout: {e}")
    raise
except httpx.RequestError as e:
    # Only retry on connection errors, not timeouts
    if isinstance(e, httpx.TimeoutException):
        raise
    if attempt < self.max_retries:
        # ... retry logic
```

### 3. **Implement Request Batching (Medium Impact)**

**Current:** Each contract mapped individually
**Proposed:** Batch multiple contracts in single request

**Impact:**
- Reduces HTTP overhead
- Single Fuseki transaction for multiple contracts
- Faster overall processing

**Implementation:**
```python
# New endpoint: POST /map/contracts (batch)
# Accepts list of contracts, returns list of results
```

### 4. **Implement Incremental Updates (Medium Impact)**

**Current:** Full remapping on every contract update
**Proposed:** Only map changed fields/triples

**Impact:**
- Reduces graph size for updates
- Faster processing for small changes
- Less Fuseki load

**Implementation:**
- Track last mapping version/hash
- Compare current contract with previous
- Only map changed triples

### 5. **Background Processing (High Impact)**

**Current:** Synchronous mapping blocks workflow
**Proposed:** Queue mapping jobs for background processing

**Impact:**
- Workflow completes immediately
- Mapping happens asynchronously
- Better user experience

**Implementation:**
```python
# Use Celery/background job queue
# Queue semantic mapping job after contract creation
# Return immediately with "mapping queued" status
```

### 6. **Optimize Graph Size (Low-Medium Impact)**

**Current:** All triples included in every mapping
**Proposed:**
- Skip empty/null values
- Compress repeated patterns
- Use named graphs for organization

**Impact:**
- Smaller INSERT DATA statements
- Faster Fuseki processing
- Less network overhead

### 7. **Connection Pool Optimization (Low Impact)**

**Current:** Connection pooling implemented
**Proposed:**
- Increase pool size if needed
- Monitor pool utilization
- Adjust keepalive timeout

**Impact:**
- Already optimized, minimal gains

### 8. **Health Check Optimization (Low Impact)**

**Current:** Health checks use 5s timeout
**Proposed:**
- Use cached health status
- Reduce health check frequency
- Fail fast on known-unavailable service

**Impact:**
- Faster failure detection
- Less unnecessary requests

### 9. **Circuit Breaker Tuning (Medium Impact)**

**Current:** 5 failures threshold, 60s timeout
**Proposed:**
- Lower failure threshold: **3 failures** (faster circuit opening)
- Shorter timeout: **30 seconds** (faster recovery attempts)
- Faster fallback: Return degraded immediately if circuit open

**Impact:**
- Circuit opens after 45s (3 failures * 15s) instead of 300s
- Faster recovery attempts
- Better user experience (immediate degraded response)

### 10. **Monitoring and Alerting (High Value)**

**Proposed:**
- Track semantic mapping duration metrics
- Alert on high timeout rates
- Monitor Fuseki health
- Track circuit breaker state

**Impact:**
- Early detection of issues
- Better visibility into performance
- Proactive problem resolution

## Recommended Implementation Priority

### Phase 1: Quick Wins (Immediate) ✅ COMPLETED
1. ✅ **Reduce timeouts** (15s production, 5s tests)
2. ✅ **Eliminate retries on timeouts**
3. ✅ **Skip semantic mapping in tests** (already implemented)

### Phase 2: Medium-Term (1-2 weeks) ✅ COMPLETED
4. ✅ **Background processing** - Queue mapping jobs
5. ✅ **Circuit breaker tuning** - Lower thresholds (3 failures, 30s timeout)
6. ✅ **Health check optimization** - Cached status (30s TTL)

### Phase 3: Long-Term (1-2 months)
7. **Request batching** - Batch multiple contracts
8. **Incremental updates** - Only map changes
9. **Graph size optimization** - Skip empty values

### Phase 4: Monitoring (Ongoing)
10. **Metrics and alerting** - Track performance

## Expected Performance Improvements

### Current Performance
- **Best case:** 1-2 seconds (service available, small graph)
- **Average case:** 5-10 seconds (service available, medium graph)
- **Worst case:** 120+ seconds (timeout + retry + circuit breaker)

### After Phase 1 Improvements
- **Best case:** 1-2 seconds (unchanged)
- **Average case:** 3-5 seconds (faster timeouts)
- **Worst case:** 30 seconds (15s timeout + no retry + immediate fallback)

### After Phase 2 Improvements
- **Best case:** <1 second (workflow returns immediately)
- **Average case:** <1 second (background processing)
- **Worst case:** 15 seconds (timeout only, no blocking)

### After Phase 3 Improvements
- **Best case:** <1 second (workflow + optimized mapping)
- **Average case:** <1 second (batching + incremental updates)
- **Worst case:** 15 seconds (timeout only)

## Testing Recommendations

1. **Load Testing:** Test with various graph sizes (10, 100, 1000, 10000 triples)
2. **Failure Testing:** Test behavior when Fuseki is unavailable
3. **Circuit Breaker Testing:** Verify circuit opens/closes correctly
4. **Performance Testing:** Measure actual improvements after each phase

## Conclusion

The primary bottleneck is **Fuseki service unavailability** causing 60-second timeouts. The recommended improvements will:

1. **Reduce wait times** by 75% (120s → 30s) in Phase 1
2. **Eliminate blocking** by moving to background processing in Phase 2
3. **Optimize operations** with batching and incremental updates in Phase 3

These improvements will significantly enhance user experience and system reliability.
