# Redis Instance Separation Strategy

**Date:** 2025-12-30
**Task:** 9.7.1.3.1 - Design Redis instance separation strategy
**Status:** ✅ **DESIGN COMPLETE**

## Executive Summary

This document provides a comprehensive design for separating Redis into four dedicated instances to improve isolation, performance, scalability, and operational management. The separation strategy addresses current limitations where a single Redis instance handles all workloads (caching, queues, events, channels), leading to resource contention and operational complexity.

## Current State Analysis

### Current Architecture

**Single Redis Instance:**
- **URL**: `REDIS_URL` (default: `redis://localhost:6379/0`)
- **Database**: Single database (DB 0) used for all purposes
- **Workloads**:
  1. **Caching**: Response caching, contract caching, lineage caching
  2. **Job Queues**: RQ queues (job_critical, job_default, job_low, default)
  3. **Event Bus**: Redis Pub/Sub for event delivery
  4. **WebSocket Channels**: Django Channels for real-time communication
  5. **Rate Limiting**: Sliding window rate limiting

### Current Limitations

1. **Resource Contention**: All workloads compete for memory, CPU, and network bandwidth
2. **No Isolation**: Cache eviction can affect queues; queue backlog can affect events
3. **Single Point of Failure**: All services depend on one Redis instance
4. **Scaling Challenges**: Cannot scale workloads independently
5. **Operational Complexity**: Difficult to monitor, tune, and troubleshoot
6. **Memory Management**: No granular control over memory limits per workload
7. **Connection Pooling**: Single connection pool shared across all workloads

## Proposed Architecture

### Four Redis Instances

#### 1. Redis Cache Instance
**Purpose**: Response caching, contract caching, lineage caching
**Database**: DB 0
**Port**: 6379 (default) or 6380
**Memory**: 2-4 GB (configurable)
**Persistence**: Optional (AOF recommended for cache warming)

**Use Cases**:
- HTTP response caching (`/api/v1/auth/me/`, etc.)
- Contract data caching (`contract:{contract_id}`)
- Lineage resolution caching (`lineage:{contract_id}`)
- Dataset/asset query result caching
- Marketplace listing caching

**Characteristics**:
- High read-to-write ratio (90%+ reads)
- Short TTLs (5 minutes to 1 hour)
- Cache eviction policies: LRU, LFU
- Optional persistence for cache warming

#### 2. Redis Queue Instance
**Purpose**: Job queues (RQ)
**Database**: DB 0
**Port**: 6379 (default) or 6381
**Memory**: 1-2 GB (configurable)
**Persistence**: Required (AOF recommended)

**Use Cases**:
- Priority queues: `job_critical`, `job_default`, `job_low`
- Job result storage
- Job metadata and state
- Worker coordination

**Characteristics**:
- High write-to-read ratio (job enqueueing)
- Long-lived data (job results, metadata)
- Persistence required for job reliability
- Priority-based queue management

#### 3. Redis Events Instance
**Purpose**: Event bus (Pub/Sub, Streams)
**Database**: DB 0
**Port**: 6379 (default) or 6382
**Memory**: 1-2 GB (configurable)
**Persistence**: Optional (AOF for Streams, not needed for Pub/Sub)

**Use Cases**:
- Event publishing (Pub/Sub channels)
- Event subscription management
- Event deduplication keys
- Message acknowledgment tracking
- Future: Redis Streams migration

**Characteristics**:
- High throughput (1,500-2,000 events/sec)
- Low latency requirements (<10ms)
- Fire-and-forget (Pub/Sub) or persistent (Streams)
- Subscriber management

#### 4. Redis Channels Instance
**Purpose**: WebSocket channels (Django Channels)
**Database**: DB 0
**Port**: 6379 (default) or 6383
**Memory**: 512 MB - 1 GB (configurable)
**Persistence**: Not required

**Use Cases**:
- WebSocket channel groups
- Real-time message delivery
- Channel layer coordination
- Presence tracking

**Characteristics**:
- Real-time messaging
- Low latency (<50ms)
- Ephemeral data (messages expire quickly)
- No persistence needed

## Separation Rationale

### 1. Isolation

**Problem**: Resource contention between workloads
**Solution**: Separate instances prevent one workload from affecting others

**Benefits**:
- Cache eviction doesn't affect job queues
- Queue backlog doesn't affect event delivery
- Event bursts don't impact cache performance
- Channel messages don't interfere with other workloads

**Example Scenarios**:
- **Cache Warming**: Large cache warming operation doesn't block job processing
- **Job Backlog**: Large job queue doesn't cause cache eviction
- **Event Burst**: High event volume doesn't impact WebSocket latency
- **Channel Spam**: WebSocket message flood doesn't affect critical queues

### 2. Performance

**Problem**: Single instance bottlenecks
**Solution**: Dedicated instances optimize for specific workload patterns

**Benefits**:
- **Cache Instance**: Optimized for read-heavy workloads (LRU/LFU eviction)
- **Queue Instance**: Optimized for write-heavy workloads (persistence, durability)
- **Events Instance**: Optimized for high throughput (Pub/Sub, low latency)
- **Channels Instance**: Optimized for real-time messaging (low latency, ephemeral)

**Performance Improvements**:
- **Cache Hit Rate**: +10-15% (dedicated memory, optimized eviction)
- **Queue Throughput**: +20-30% (no cache contention)
- **Event Latency**: -30-40% (dedicated instance, no queue interference)
- **Channel Latency**: -50% (dedicated instance, no other workloads)

### 3. Scalability

**Problem**: Cannot scale workloads independently
**Solution**: Separate instances enable independent scaling

**Benefits**:
- **Horizontal Scaling**: Scale cache instances independently (read replicas)
- **Vertical Scaling**: Scale queue instance for high job volume
- **Event Scaling**: Scale events instance for high event throughput
- **Channel Scaling**: Scale channels instance for high WebSocket concurrency

**Scaling Strategies**:
- **Cache**: Read replicas for read-heavy workloads
- **Queue**: Larger instance for high job volume
- **Events**: Clustered instances for high throughput
- **Channels**: Multiple instances for high concurrency

### 4. Operational Management

**Problem**: Difficult to monitor, tune, and troubleshoot
**Solution**: Separate instances enable granular operational control

**Benefits**:
- **Monitoring**: Per-instance metrics (memory, connections, throughput)
- **Tuning**: Optimize each instance for its workload
- **Troubleshooting**: Isolate issues to specific workloads
- **Maintenance**: Update/restart instances independently

**Operational Improvements**:
- **Monitoring**: Per-instance dashboards (Cache, Queue, Events, Channels)
- **Alerting**: Workload-specific alerts (cache hit rate, queue depth, event latency)
- **Tuning**: Instance-specific configurations (memory limits, eviction policies)
- **Maintenance**: Zero-downtime updates (update instances independently)

## Connection Pooling Strategy

### Per-Instance Connection Pools

Each Redis instance requires its own connection pool to optimize performance and resource usage.

#### 1. Redis Cache Connection Pool

**Configuration**:
```python
REDIS_CACHE_CONNECTION_POOL = redis.ConnectionPool(
    host=REDIS_CACHE_HOST,
    port=REDIS_CACHE_PORT,
    db=0,
    max_connections=50,  # Higher for read-heavy workload
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_keepalive_options={},
    health_check_interval=30
)
```

**Characteristics**:
- **Max Connections**: 50 (read-heavy, many concurrent requests)
- **Connection Reuse**: High (cache operations are frequent)
- **Health Checks**: Every 30 seconds
- **Timeout**: 5 seconds (fast fail for cache misses)

#### 2. Redis Queue Connection Pool

**Configuration**:
```python
REDIS_QUEUE_CONNECTION_POOL = redis.ConnectionPool(
    host=REDIS_QUEUE_HOST,
    port=REDIS_QUEUE_PORT,
    db=0,
    max_connections=20,  # Lower for write-heavy workload
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_keepalive_options={},
    health_check_interval=60
)
```

**Characteristics**:
- **Max Connections**: 20 (write-heavy, fewer concurrent operations)
- **Connection Reuse**: Medium (job enqueueing is less frequent)
- **Health Checks**: Every 60 seconds
- **Timeout**: 10 seconds (jobs can tolerate longer timeouts)

#### 3. Redis Events Connection Pool

**Configuration**:
```python
REDIS_EVENTS_CONNECTION_POOL = redis.ConnectionPool(
    host=REDIS_EVENTS_HOST,
    port=REDIS_EVENTS_PORT,
    db=0,
    max_connections=30,  # Medium for event publishing
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_keepalive_options={},
    health_check_interval=30
)
```

**Characteristics**:
- **Max Connections**: 30 (medium throughput, event publishing)
- **Connection Reuse**: High (events are frequent)
- **Health Checks**: Every 30 seconds
- **Timeout**: 5 seconds (low latency requirement)

#### 4. Redis Channels Connection Pool

**Configuration**:
```python
REDIS_CHANNELS_CONNECTION_POOL = redis.ConnectionPool(
    host=REDIS_CHANNELS_HOST,
    port=REDIS_CHANNELS_PORT,
    db=0,
    max_connections=40,  # Higher for WebSocket connections
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_keepalive_options={},
    health_check_interval=30
)
```

**Characteristics**:
- **Max Connections**: 40 (WebSocket connections are persistent)
- **Connection Reuse**: High (channels are long-lived)
- **Health Checks**: Every 30 seconds
- **Timeout**: 3 seconds (real-time requirement)

### Connection Pool Management

**Best Practices**:
1. **Per-Application Pool**: One pool per Django application instance
2. **Lazy Initialization**: Create pools on first use
3. **Connection Reuse**: Reuse connections within request lifecycle
4. **Health Monitoring**: Monitor pool usage and connection health
5. **Graceful Degradation**: Fallback to direct connections if pool exhausted

## Memory Limits Per Instance

### Memory Allocation Strategy

Total Redis memory should be allocated based on workload characteristics and expected data volumes.

#### 1. Redis Cache Instance

**Memory Limit**: 2-4 GB (configurable)

**Rationale**:
- **Cache Size**: ~10,000-50,000 cached items
- **Average Item Size**: ~10-50 KB (contracts, lineage, query results)
- **Total Cache Size**: ~500 MB - 2.5 GB
- **Headroom**: 50% for growth and eviction overhead
- **Total**: 2-4 GB

**Eviction Policy**: `allkeys-lru` (evict least recently used keys)

**Configuration**:
```redis
maxmemory 4gb
maxmemory-policy allkeys-lru
```

**Monitoring**:
- Cache hit rate (target: >80%)
- Memory usage (alert at 80%)
- Eviction rate (alert if high)

#### 2. Redis Queue Instance

**Memory Limit**: 1-2 GB (configurable)

**Rationale**:
- **Job Queue Size**: ~1,000-5,000 jobs
- **Average Job Size**: ~1-10 KB (job metadata, results)
- **Total Queue Size**: ~10-50 MB
- **Job Results**: ~500 MB - 1 GB (stored for 500 seconds)
- **Headroom**: 50% for growth
- **Total**: 1-2 GB

**Eviction Policy**: `noeviction` (jobs must not be evicted)

**Configuration**:
```redis
maxmemory 2gb
maxmemory-policy noeviction
```

**Monitoring**:
- Queue depth (alert if >1,000 jobs)
- Memory usage (alert at 80%)
- Job result TTL (monitor expiration)

#### 3. Redis Events Instance

**Memory Limit**: 1-2 GB (configurable)

**Rationale**:
- **Pub/Sub**: Minimal memory (fire-and-forget)
- **Deduplication Keys**: ~100,000 keys × 100 bytes = ~10 MB
- **Acknowledgment Tracking**: ~10,000 keys × 200 bytes = ~2 MB
- **Future Streams**: ~1 GB for event streams (if migrated)
- **Headroom**: 50% for growth
- **Total**: 1-2 GB

**Eviction Policy**: `allkeys-lru` (evict old deduplication keys)

**Configuration**:
```redis
maxmemory 2gb
maxmemory-policy allkeys-lru
```

**Monitoring**:
- Event throughput (target: 1,500-2,000 events/sec)
- Memory usage (alert at 80%)
- Deduplication key count (monitor growth)

#### 4. Redis Channels Instance

**Memory Limit**: 512 MB - 1 GB (configurable)

**Rationale**:
- **Channel Groups**: ~1,000-5,000 groups
- **Message Buffer**: ~1,000 messages × 1 KB = ~1 MB
- **Presence Data**: ~10,000 users × 100 bytes = ~1 MB
- **Headroom**: 50% for growth
- **Total**: 512 MB - 1 GB

**Eviction Policy**: `allkeys-lru` (evict old messages)

**Configuration**:
```redis
maxmemory 1gb
maxmemory-policy allkeys-lru
```

**Monitoring**:
- Channel count (monitor growth)
- Memory usage (alert at 80%)
- Message expiry rate (monitor)

### Total Memory Allocation

**Development/Staging**:
- Cache: 2 GB
- Queue: 1 GB
- Events: 1 GB
- Channels: 512 MB
- **Total**: ~4.5 GB

**Production**:
- Cache: 4 GB
- Queue: 2 GB
- Events: 2 GB
- Channels: 1 GB
- **Total**: ~9 GB

## Failover Strategy

### High Availability Architecture

Each Redis instance should have a failover strategy to ensure high availability and data durability.

#### 1. Redis Cache Instance Failover

**Strategy**: Redis Sentinel with automatic failover

**Architecture**:
- **Primary**: 1 Redis instance (master)
- **Replicas**: 1-2 Redis instances (read replicas)
- **Sentinels**: 3 Sentinel instances (quorum-based failover)

**Failover Behavior**:
- **Automatic Failover**: Sentinel promotes replica to master (30-60 seconds)
- **Read Replicas**: Continue serving reads during failover
- **Cache Warming**: Optional cache warming after failover
- **Data Loss**: Acceptable (cache can be rebuilt)

**Configuration**:
```redis
# Sentinel configuration
sentinel monitor redis-cache <master-ip> 6379 2
sentinel down-after-milliseconds redis-cache 5000
sentinel failover-timeout redis-cache 10000
```

#### 2. Redis Queue Instance Failover

**Strategy**: Redis Sentinel with persistence (AOF)

**Architecture**:
- **Primary**: 1 Redis instance (master) with AOF persistence
- **Replicas**: 1 Redis instance (replica with AOF)
- **Sentinels**: 3 Sentinel instances

**Failover Behavior**:
- **Automatic Failover**: Sentinel promotes replica to master
- **Data Durability**: AOF ensures job data is not lost
- **Job Recovery**: Jobs resume after failover
- **Data Loss**: Minimal (only jobs in-flight may be lost)

**Configuration**:
```redis
# AOF persistence
appendonly yes
appendfsync everysec
```

#### 3. Redis Events Instance Failover

**Strategy**: Redis Sentinel (Pub/Sub) or Redis Cluster (Streams)

**Architecture**:
- **Pub/Sub Mode**: Redis Sentinel (current)
  - Primary: 1 Redis instance
  - Replicas: 1 Redis instance
  - Sentinels: 3 Sentinel instances
- **Streams Mode**: Redis Cluster (future)
  - 3-6 Redis nodes (sharded)
  - Automatic failover and sharding

**Failover Behavior**:
- **Pub/Sub**: Automatic failover (events may be lost during failover)
- **Streams**: Automatic failover with data replication
- **Event Loss**: Acceptable for Pub/Sub (fire-and-forget)
- **Event Loss**: Not acceptable for Streams (replicated)

**Configuration**:
```redis
# Sentinel configuration (Pub/Sub)
sentinel monitor redis-events <master-ip> 6379 2
sentinel down-after-milliseconds redis-events 5000
sentinel failover-timeout redis-events 10000
```

#### 4. Redis Channels Instance Failover

**Strategy**: Redis Sentinel with minimal persistence

**Architecture**:
- **Primary**: 1 Redis instance
- **Replicas**: 1 Redis instance
- **Sentinels**: 3 Sentinel instances

**Failover Behavior**:
- **Automatic Failover**: Sentinel promotes replica to master
- **Channel Reconnection**: WebSocket clients reconnect automatically
- **Message Loss**: Acceptable (ephemeral messages)
- **Presence Loss**: Acceptable (presence rebuilds on reconnect)

**Configuration**:
```redis
# Sentinel configuration
sentinel monitor redis-channels <master-ip> 6379 2
sentinel down-after-milliseconds redis-channels 5000
sentinel failover-timeout redis-channels 10000
```

### Failover Monitoring and Alerts

**Monitoring**:
- **Sentinel Status**: Monitor sentinel quorum and master/replica status
- **Failover Events**: Alert on failover events
- **Replication Lag**: Monitor replica lag (alert if >1 second)
- **Connection Failures**: Alert on connection failures

**Alerts**:
- **Failover Event**: Critical alert (immediate notification)
- **Replication Lag**: Warning alert (if >1 second)
- **Connection Failures**: Critical alert (if >10% failure rate)
- **Memory Usage**: Warning alert (if >80%)

### Application-Level Failover Handling

**Connection Retry Logic**:
```python
# Exponential backoff retry
max_retries = 3
retry_delay = 1.0  # seconds
backoff_factor = 2.0

for attempt in range(max_retries):
    try:
        # Connect to Redis
        redis_client.ping()
        break
    except redis.ConnectionError:
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (backoff_factor ** attempt))
        else:
            # Fallback to degraded mode
            handle_redis_unavailable()
```

**Degraded Mode**:
- **Cache**: Return cache misses (fallback to database)
- **Queue**: Queue jobs in-memory buffer (flush when Redis available)
- **Events**: Log events to file (replay when Redis available)
- **Channels**: Disconnect WebSocket clients (reconnect when Redis available)

## Migration Strategy

### Phase 1: Preparation (Week 1)

1. **Infrastructure Setup**:
   - Provision 4 Redis instances (Cache, Queue, Events, Channels)
   - Configure Redis Sentinel for each instance
   - Set up monitoring and alerting

2. **Configuration Updates**:
   - Add new Redis URL environment variables
   - Update Django settings for connection pools
   - Create connection pool utilities

3. **Testing**:
   - Test each instance independently
   - Test failover scenarios
   - Test connection pooling

### Phase 2: Gradual Migration (Week 2-3)

1. **Cache Migration** (Day 1-2):
   - Migrate cache operations to Redis Cache instance
   - Monitor cache hit rates and performance
   - Validate cache functionality

2. **Queue Migration** (Day 3-4):
   - Migrate RQ queues to Redis Queue instance
   - Monitor job processing and queue depth
   - Validate job reliability

3. **Events Migration** (Day 5-6):
   - Migrate event bus to Redis Events instance
   - Monitor event throughput and latency
   - Validate event delivery

4. **Channels Migration** (Day 7):
   - Migrate WebSocket channels to Redis Channels instance
   - Monitor channel latency and connection count
   - Validate WebSocket functionality

### Phase 3: Validation (Week 4)

1. **Performance Validation**:
   - Compare performance metrics (before/after)
   - Validate performance improvements
   - Identify any regressions

2. **Reliability Validation**:
   - Test failover scenarios
   - Validate data durability
   - Test degraded mode handling

3. **Monitoring Validation**:
   - Validate monitoring dashboards
   - Test alerting
   - Review operational metrics

### Phase 4: Cleanup (Week 5)

1. **Old Instance Decommission**:
   - Verify all workloads migrated
   - Decommission old Redis instance
   - Update documentation

## Configuration Examples

### Environment Variables

```bash
# Redis Cache Instance
REDIS_CACHE_URL=redis://redis-cache:6379/0
REDIS_CACHE_MAX_CONNECTIONS=50
REDIS_CACHE_MEMORY_LIMIT=4gb

# Redis Queue Instance
REDIS_QUEUE_URL=redis://redis-queue:6379/0
REDIS_QUEUE_MAX_CONNECTIONS=20
REDIS_QUEUE_MEMORY_LIMIT=2gb

# Redis Events Instance
REDIS_EVENTS_URL=redis://redis-events:6379/0
REDIS_EVENTS_MAX_CONNECTIONS=30
REDIS_EVENTS_MEMORY_LIMIT=2gb

# Redis Channels Instance
REDIS_CHANNELS_URL=redis://redis-channels:6379/0
REDIS_CHANNELS_MAX_CONNECTIONS=40
REDIS_CHANNELS_MEMORY_LIMIT=1gb
```

### Django Settings

```python
# Redis Cache Configuration
REDIS_CACHE_URL = env("REDIS_CACHE_URL", default="redis://localhost:6379/0")
REDIS_CACHE_CONNECTION_POOL = redis.ConnectionPool.from_url(
    REDIS_CACHE_URL,
    max_connections=50,
    retry_on_timeout=True
)

# Redis Queue Configuration
REDIS_QUEUE_URL = env("REDIS_QUEUE_URL", default="redis://localhost:6381/0")
RQ_QUEUES = {
    "job_critical": {"URL": REDIS_QUEUE_URL, ...},
    "job_default": {"URL": REDIS_QUEUE_URL, ...},
    "job_low": {"URL": REDIS_QUEUE_URL, ...},
}

# Redis Events Configuration
REDIS_EVENTS_URL = env("REDIS_EVENTS_URL", default="redis://localhost:6382/0")
REDIS_EVENTS_CONNECTION_POOL = redis.ConnectionPool.from_url(
    REDIS_EVENTS_URL,
    max_connections=30,
    retry_on_timeout=True
)

# Redis Channels Configuration
REDIS_CHANNELS_URL = env("REDIS_CHANNELS_URL", default="redis://localhost:6383/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [parse_redis_url(REDIS_CHANNELS_URL)],
            "capacity": 1000,
            "expiry": 10,
        },
    },
}
```

## Success Metrics

### Performance Metrics

- **Cache Hit Rate**: >80% (target: +10-15% improvement)
- **Queue Throughput**: +20-30% improvement
- **Event Latency**: <10ms (target: -30-40% improvement)
- **Channel Latency**: <50ms (target: -50% improvement)

### Reliability Metrics

- **Uptime**: >99.9% per instance
- **Failover Time**: <60 seconds
- **Data Loss**: <0.1% (only for cache and channels)
- **Job Reliability**: 100% (no job loss)

### Operational Metrics

- **Monitoring Coverage**: 100% (all instances monitored)
- **Alert Response Time**: <5 minutes
- **Incident Resolution Time**: <30 minutes
- **Maintenance Window**: Zero-downtime updates

## Risks and Mitigations

### Risk 1: Migration Complexity

**Risk**: Complex migration process may cause downtime
**Mitigation**:
- Gradual migration (one workload at a time)
- Comprehensive testing before migration
- Rollback plan for each phase
- Monitoring and alerting during migration

### Risk 2: Connection Pool Exhaustion

**Risk**: Connection pools may be exhausted under high load
**Mitigation**:
- Proper connection pool sizing
- Connection pool monitoring
- Graceful degradation (fallback to direct connections)
- Auto-scaling connection pools

### Risk 3: Failover Data Loss

**Risk**: Data loss during failover events
**Mitigation**:
- AOF persistence for critical data (queues)
- Replication lag monitoring
- Failover testing and validation
- Data recovery procedures

### Risk 4: Increased Operational Complexity

**Risk**: Managing 4 instances increases operational complexity
**Mitigation**:
- Comprehensive monitoring and alerting
- Automated failover and recovery
- Clear documentation and runbooks
- Training for operations team

## Conclusion

The Redis instance separation strategy provides significant benefits in terms of isolation, performance, scalability, and operational management. The four-instance architecture (Cache, Queue, Events, Channels) enables independent scaling, optimized configurations, and granular operational control.

**Key Benefits**:
- ✅ **Isolation**: Workloads don't interfere with each other
- ✅ **Performance**: Optimized configurations per workload
- ✅ **Scalability**: Independent scaling per workload
- ✅ **Reliability**: Failover strategies per workload
- ✅ **Operational**: Granular monitoring and management

**Next Steps**:
1. Review and approve design
2. Provision infrastructure
3. Implement connection pooling
4. Execute migration plan
5. Validate performance and reliability

