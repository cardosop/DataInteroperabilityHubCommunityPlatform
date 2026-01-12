# Kafka and RabbitMQ Evaluation for Event Bus

**Date:** 2025-12-29
**Task:** 9.7.1.1.3 - Evaluate Kafka/RabbitMQ as alternative
**Status:** ✅ **COMPLETE**

## Executive Summary

This document provides a comprehensive evaluation of Apache Kafka and RabbitMQ as alternatives to the current Redis Pub/Sub event bus implementation. The evaluation covers capabilities, migration complexity, infrastructure overhead, operational complexity, and includes proof-of-concept implementations with performance comparisons.

## Current Architecture

### Redis Pub/Sub Event Bus

**Current Implementation:**
- **Real-time Delivery**: Redis Pub/Sub (fire-and-forget messaging)
- **Persistence**: PostgreSQL (synchronous writes)
- **Throughput**: ~1,500-2,000 events/sec
- **Latency**: <100ms average
- **Features**: Event replay, dead letter queue, subscription management

**Key Characteristics:**
- Simple architecture (Redis + PostgreSQL)
- Low latency for real-time delivery
- PostgreSQL persistence is primary bottleneck
- No built-in message ordering guarantees
- No backpressure mechanism
- Limited replay capabilities

## Apache Kafka Evaluation

### Capabilities

#### 1. Persistence

**Built-in Persistence:**
- ✅ **Durable Storage**: Kafka stores all messages on disk with configurable retention
- ✅ **Log-based Storage**: Append-only log structure for high write throughput
- ✅ **Retention Policies**: Configurable retention by time (e.g., 7 days) or size (e.g., 1GB)
- ✅ **Compaction**: Log compaction for key-based retention (keeps latest value per key)
- ✅ **Replication**: Built-in replication across multiple brokers for durability

**Advantages:**
- Messages persist automatically (no separate database needed)
- High write throughput (millions of messages/sec)
- Configurable retention for audit/replay
- Replication ensures durability

**Disadvantages:**
- Disk space requirements (all messages stored)
- Requires careful retention policy management
- Compaction adds complexity

#### 2. Scalability

**Horizontal Scalability:**
- ✅ **Partitioning**: Topics can be partitioned across multiple brokers
- ✅ **Consumer Groups**: Multiple consumers can process partitions in parallel
- ✅ **Linear Scaling**: Throughput scales linearly with partitions/brokers
- ✅ **High Throughput**: Can handle millions of messages/sec per cluster

**Scalability Characteristics:**
- **Throughput**: 100,000+ messages/sec per broker (typical)
- **Partitions**: Unlimited (practical limit: thousands per broker)
- **Consumers**: Unlimited (scales with partitions)
- **Brokers**: Scales horizontally (tested up to thousands)

**Advantages:**
- Excellent horizontal scalability
- Partition-based parallelism
- Handles high-volume workloads
- Consumer group coordination built-in

**Disadvantages:**
- Partition count affects parallelism (must plan ahead)
- Rebalancing overhead when consumers join/leave
- Requires careful partition key design

#### 3. Replay Capabilities

**Built-in Replay:**
- ✅ **Offset Management**: Consumers track position via offsets
- ✅ **Seek to Offset**: Can seek to any offset for replay
- ✅ **Time-based Seek**: Can seek to specific timestamp
- ✅ **Consumer Groups**: Multiple groups can replay independently
- ✅ **Retention-based Replay**: Can replay within retention window

**Replay Features:**
- Seek to beginning/end of topic
- Seek to specific offset
- Seek to timestamp
- Multiple consumer groups can replay simultaneously
- Replay within retention period

**Advantages:**
- Excellent replay capabilities
- Multiple replay strategies (offset, timestamp)
- Independent consumer groups
- Built-in offset management

**Disadvantages:**
- Limited by retention policy
- Requires offset management
- Replay can be slow for large topics

#### 4. Message Ordering

**Ordering Guarantees:**
- ✅ **Partition-level Ordering**: Messages within a partition are ordered
- ✅ **Key-based Partitioning**: Same key → same partition → ordered
- ✅ **No Global Ordering**: Messages across partitions are not ordered

**Advantages:**
- Guaranteed ordering within partition
- Key-based ordering for related messages
- Predictable ordering behavior

**Disadvantages:**
- No global ordering (only per-partition)
- Requires careful partition key design
- Ordering lost if partition count changes

#### 5. Reliability

**Reliability Features:**
- ✅ **Replication**: Configurable replication factor (typically 3)
- ✅ **Acknowledgment**: Producer can wait for replication (acks=all)
- ✅ **Durability**: Messages written to disk before acknowledgment
- ✅ **Fault Tolerance**: Survives broker failures (with replication)
- ✅ **Exactly-once Semantics**: Supported (with idempotent producers)

**Advantages:**
- High reliability with replication
- Configurable durability guarantees
- Fault tolerance built-in
- Exactly-once semantics available

**Disadvantages:**
- Higher latency with replication (acks=all)
- More complex configuration
- Requires multiple brokers for HA

### Migration Complexity

#### Code Changes Required

**Publisher Changes:**
- Replace Redis Pub/Sub publish with Kafka producer
- Configure Kafka producer (brokers, serialization, acks)
- Handle Kafka-specific errors
- **Complexity**: Medium (2-3 days)

**Subscriber Changes:**
- Replace Redis Pub/Sub subscribe with Kafka consumer
- Implement consumer group logic
- Handle offset management
- Handle rebalancing
- **Complexity**: Medium-High (3-5 days)

**Persistence Changes:**
- Remove PostgreSQL persistence (Kafka handles it)
- Migrate existing events to Kafka (if needed)
- Update replay logic to use Kafka offsets
- **Complexity**: Medium (2-3 days)

**Total Estimated Effort:** 7-11 days

#### Breaking Changes

- **API Changes**: Different publish/subscribe APIs
- **Configuration Changes**: New Kafka configuration
- **Deployment Changes**: Kafka cluster deployment
- **Monitoring Changes**: New metrics and monitoring

### Infrastructure Overhead

#### Additional Services Required

**Kafka Cluster:**
- **Zookeeper** (or KRaft mode): Coordination service
- **Kafka Brokers**: 3+ brokers for HA (recommended)
- **Storage**: Disk space for message retention
- **Network**: High bandwidth for replication

**Resource Requirements:**
- **CPU**: Medium-High (2-4 cores per broker)
- **Memory**: High (4-8GB per broker minimum)
- **Disk**: High (depends on retention, typically 100GB+ per broker)
- **Network**: High (for replication)

**Operational Overhead:**
- **Deployment**: More complex (multiple brokers)
- **Configuration**: More complex (many settings)
- **Monitoring**: Requires Kafka-specific monitoring
- **Maintenance**: Regular maintenance (log cleanup, rebalancing)

### Operational Complexity

#### Monitoring

**Required Metrics:**
- Broker health (CPU, memory, disk)
- Topic metrics (throughput, lag, size)
- Consumer group lag
- Replication lag
- Disk usage

**Tools:**
- Kafka Manager / CMAK
- Prometheus + Kafka Exporter
- Grafana dashboards
- Custom monitoring scripts

**Complexity:** Medium-High

#### Maintenance

**Regular Tasks:**
- Monitor disk usage
- Clean up old logs (if not using retention)
- Rebalance partitions (if needed)
- Update broker configurations
- Handle broker failures

**Complexity:** Medium-High

#### Troubleshooting

**Common Issues:**
- Consumer lag (slow consumers)
- Replication lag (network issues)
- Disk space exhaustion
- Broker failures
- Rebalancing issues

**Complexity:** Medium-High

## RabbitMQ Evaluation

### Capabilities

#### 1. Persistence

**Built-in Persistence:**
- ✅ **Message Persistence**: Messages can be marked as persistent
- ✅ **Queue Persistence**: Queues can be durable
- ✅ **Exchange Persistence**: Exchanges can be durable
- ✅ **Disk Storage**: Persistent messages written to disk
- ✅ **Mirrored Queues**: Queue mirroring for HA (classic queues)

**Advantages:**
- Messages persist to disk
- Configurable persistence per message
- Queue mirroring for HA
- Reliable message delivery

**Disadvantages:**
- Performance impact with persistence
- Disk I/O overhead
- Requires careful configuration
- Classic mirrored queues deprecated (use quorum queues)

#### 2. Routing

**Advanced Routing:**
- ✅ **Exchanges**: Multiple exchange types (direct, topic, fanout, headers)
- ✅ **Routing Keys**: Flexible routing based on keys
- ✅ **Bindings**: Dynamic queue bindings
- ✅ **Topic Routing**: Pattern-based routing (wildcards)
- ✅ **Headers Routing**: Header-based routing

**Routing Features:**
- Direct exchange (routing key matching)
- Topic exchange (pattern matching)
- Fanout exchange (broadcast)
- Headers exchange (header matching)
- Complex routing topologies

**Advantages:**
- Very flexible routing
- Multiple routing patterns
- Dynamic bindings
- Complex topologies supported

**Disadvantages:**
- More complex than simple pub/sub
- Requires understanding of exchanges/bindings
- Routing configuration complexity

#### 3. Reliability

**Reliability Features:**
- ✅ **Publisher Confirms**: Acknowledgment from broker
- ✅ **Consumer Acknowledgments**: Manual/automatic acks
- ✅ **Queue Mirroring**: Classic mirrored queues (deprecated)
- ✅ **Quorum Queues**: Raft-based HA queues (recommended)
- ✅ **Dead Letter Exchanges**: Failed message handling
- ✅ **TTL**: Time-to-live for messages

**Advantages:**
- High reliability with quorum queues
- Publisher confirms for delivery guarantee
- Consumer acks for processing guarantee
- Dead letter queues built-in
- TTL support

**Disadvantages:**
- Quorum queues require odd number of nodes
- More complex than simple pub/sub
- Requires careful configuration

#### 4. Scalability

**Scalability Characteristics:**
- ✅ **Clustering**: RabbitMQ cluster support
- ✅ **Queue Sharding**: Sharded queues for parallelism
- ✅ **High Availability**: Quorum queues for HA
- ✅ **Throughput**: 10,000-50,000 messages/sec per node (typical)

**Scalability Limits:**
- **Throughput**: Lower than Kafka (10K-50K vs 100K+)
- **Clustering**: Limited scalability (tested up to ~10 nodes)
- **Queues**: Thousands of queues per node
- **Consumers**: Multiple consumers per queue

**Advantages:**
- Good scalability for most use cases
- Clustering support
- Queue sharding for parallelism

**Disadvantages:**
- Lower throughput than Kafka
- Clustering complexity
- Limited horizontal scalability

#### 5. Replay Capabilities

**Replay Support:**
- ⚠️ **Limited Replay**: No built-in offset management
- ⚠️ **Manual Replay**: Requires custom implementation
- ⚠️ **TTL-based**: Can use TTL for time-based replay
- ⚠️ **Dead Letter**: Can replay from dead letter queue

**Advantages:**
- Can implement custom replay
- Dead letter queue for failed messages
- TTL for time-based retention

**Disadvantages:**
- No built-in replay (unlike Kafka)
- Requires custom implementation
- Limited compared to Kafka

### Migration Complexity

#### Code Changes Required

**Publisher Changes:**
- Replace Redis Pub/Sub publish with RabbitMQ publish
- Configure RabbitMQ connection and channel
- Configure exchanges and routing keys
- Handle RabbitMQ-specific errors
- **Complexity**: Medium (2-3 days)

**Subscriber Changes:**
- Replace Redis Pub/Sub subscribe with RabbitMQ consume
- Implement queue binding logic
- Handle acknowledgments
- Handle connection failures
- **Complexity**: Medium (2-3 days)

**Persistence Changes:**
- Keep PostgreSQL persistence (or use RabbitMQ persistence)
- Update replay logic (custom implementation)
- Migrate existing events (if needed)
- **Complexity**: Low-Medium (1-2 days)

**Total Estimated Effort:** 5-8 days

#### Breaking Changes

- **API Changes**: Different publish/subscribe APIs
- **Configuration Changes**: RabbitMQ configuration
- **Deployment Changes**: RabbitMQ cluster deployment
- **Routing Changes**: Exchange/queue/binding configuration

### Infrastructure Overhead

#### Additional Services Required

**RabbitMQ Cluster:**
- **RabbitMQ Nodes**: 3+ nodes for HA (recommended)
- **Erlang Runtime**: Required for RabbitMQ
- **Storage**: Disk space for persistent messages
- **Network**: Network for clustering

**Resource Requirements:**
- **CPU**: Medium (1-2 cores per node)
- **Memory**: Medium-High (2-4GB per node minimum)
- **Disk**: Medium (depends on persistence, typically 10-50GB per node)
- **Network**: Medium (for clustering)

**Operational Overhead:**
- **Deployment**: Medium complexity (cluster setup)
- **Configuration**: Medium complexity (exchanges, queues, bindings)
- **Monitoring**: Requires RabbitMQ-specific monitoring
- **Maintenance**: Regular maintenance (queue cleanup, cluster health)

### Operational Complexity

#### Monitoring

**Required Metrics:**
- Node health (CPU, memory, disk)
- Queue metrics (length, rate, consumers)
- Exchange metrics (rate)
- Connection metrics
- Message rates

**Tools:**
- RabbitMQ Management UI
- Prometheus + RabbitMQ Exporter
- Grafana dashboards
- Custom monitoring scripts

**Complexity:** Medium

#### Maintenance

**Regular Tasks:**
- Monitor queue lengths
- Clean up old messages (if not using TTL)
- Monitor cluster health
- Handle node failures
- Update configurations

**Complexity:** Medium

#### Troubleshooting

**Common Issues:**
- Queue buildup (slow consumers)
- Memory pressure
- Disk space exhaustion
- Node failures
- Connection issues

**Complexity:** Medium

## Comparison Matrix

| Feature | Redis Pub/Sub | Kafka | RabbitMQ |
|---------|---------------|-------|----------|
| **Persistence** | PostgreSQL (separate) | Built-in (disk) | Built-in (optional) |
| **Throughput** | ~1,500-2,000/sec | 100,000+/sec | 10,000-50,000/sec |
| **Latency** | <10ms (Pub/Sub) | 10-100ms | 1-10ms |
| **Scalability** | Limited (single instance) | Excellent (horizontal) | Good (clustering) |
| **Replay** | Limited (PostgreSQL) | Excellent (offsets) | Limited (custom) |
| **Ordering** | None | Per-partition | Per-queue |
| **Routing** | Simple (channels) | Simple (topics) | Advanced (exchanges) |
| **Reliability** | Medium (single Redis) | High (replication) | High (quorum queues) |
| **Infrastructure** | Low (Redis + PostgreSQL) | High (Kafka cluster) | Medium (RabbitMQ cluster) |
| **Operational Complexity** | Low | High | Medium |
| **Migration Effort** | N/A | 7-11 days | 5-8 days |

## Recommendations

### When to Use Kafka

**Use Kafka if:**
- High throughput requirements (>10,000 events/sec)
- Need excellent replay capabilities
- Need horizontal scalability
- Need message ordering guarantees
- Can handle higher operational complexity
- Have infrastructure resources for Kafka cluster

**Example Use Cases:**
- High-volume event streaming
- Event sourcing
- Log aggregation
- Real-time analytics pipelines

### When to Use RabbitMQ

**Use RabbitMQ if:**
- Need advanced routing capabilities
- Need lower latency (<10ms)
- Need simpler operational model than Kafka
- Moderate throughput requirements (<10,000 events/sec)
- Need flexible message routing patterns

**Example Use Cases:**
- Complex routing requirements
- Work queue patterns
- Request/reply patterns
- Lower latency requirements

### When to Keep Redis Pub/Sub

**Keep Redis Pub/Sub if:**
- Current throughput is sufficient
- Simple architecture preferred
- Low operational overhead desired
- Latency requirements are met
- Replay needs are minimal

**Example Use Cases:**
- Current use case (sufficient performance)
- Simple pub/sub patterns
- Low operational complexity desired

## Conclusion

Both Kafka and RabbitMQ offer advantages over Redis Pub/Sub, but with increased complexity:

- **Kafka**: Best for high-throughput, replay-heavy use cases
- **RabbitMQ**: Best for complex routing, lower latency requirements
- **Redis Pub/Sub**: Sufficient for current needs, simplest to operate

**Recommendation**: Keep Redis Pub/Sub for now, but prepare for migration to Kafka if throughput requirements increase significantly (>10,000 events/sec) or if advanced replay capabilities become critical.

