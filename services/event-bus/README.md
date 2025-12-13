# Event Bus Service

The Event Bus Service provides event-driven communication infrastructure using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

## Overview

The event bus service:
- Uses Redis Pub/Sub for real-time event delivery
- Persists all events to PostgreSQL for replay and audit
- Provides connection pooling for optimal performance
- Includes health check endpoints for monitoring
- Supports dead letter queue for failed events
- Enables event replay functionality

## Architecture

```
┌─────────────────────────────────────┐
│   Event Bus Service                 │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  EventBusClient             │   │
│  │  - Connection pooling       │   │
│  │  - Health checks            │   │
│  │  - Retry logic              │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  EventBus                   │   │
│  │  - Publish/Subscribe         │   │
│  │  - Event persistence        │   │
│  │  - Dead letter queue        │   │
│  │  - Event replay             │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
         │                    │
         ▼                    ▼
    Redis Pub/Sub        PostgreSQL
```

## Components

### EventBusClient (`client.py`)

High-level client library that wraps EventBus with:
- Connection pooling management
- Health check capabilities
- Connection retry logic
- Metrics and monitoring

### Health Service (`health.py`)

FastAPI service providing health check endpoints:
- `/health` - Comprehensive health check
- `/healthz` - Liveness probe (Kubernetes)
- `/ready` - Readiness probe (Kubernetes)
- `/metrics` - Prometheus metrics
- `/stats` - Connection pool statistics

### EventBus (`hub/apps/core/events/bus.py`)

Core event bus implementation with:
- Redis Pub/Sub for real-time delivery
- PostgreSQL persistence
- Dead letter queue
- Event replay functionality

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `EVENT_BUS_REDIS_POOL_SIZE` | `50` | Initial connection pool size |
| `EVENT_BUS_REDIS_MAX_CONNECTIONS` | `100` | Maximum connections in pool |
| `EVENT_BUS_REDIS_SOCKET_TIMEOUT` | `5` | Socket timeout in seconds |
| `EVENT_BUS_REDIS_SOCKET_CONNECT_TIMEOUT` | `5` | Connection timeout in seconds |
| `EVENT_BUS_REDIS_RETRY_ON_TIMEOUT` | `true` | Retry on timeout |
| `EVENT_BUS_REDIS_HEALTH_CHECK_INTERVAL` | `30` | Health check interval in seconds |
| `EVENT_BUS_CHANNEL_PREFIX` | `events` | Redis channel prefix |
| `EVENT_BUS_ENABLE_PERSISTENCE` | `true` | Enable PostgreSQL persistence |
| `EVENT_BUS_MAX_RETRIES` | `3` | Maximum retry attempts |
| `EVENT_BUS_HEALTH_PORT` | `8090` | Health service port |

### Redis Configuration

Redis is configured in `docker-compose.yml` with:
- Persistence enabled (`--appendonly yes`)
- Memory limits (`--maxmemory`)
- Memory eviction policy (`--maxmemory-policy`)
- Connection settings optimized for event bus

## Usage

### Using EventBusClient

```python
from services.event_bus.client import get_event_bus_client

# Get client instance
client = get_event_bus_client()

# Publish an event
event_id = client.publish(
    event_type="contract.created",
    data={"contract_id": "..."},
    tenant_id="tenant-uuid"
)

# Subscribe to events
def handle_event(event):
    print(f"Received event: {event['event_type']}")

client.subscribe(
    subscriber_name="my_subscriber",
    event_type_pattern="contract.*",
    handler=handle_event
)

# Health check
health_status = client.health_check()
print(health_status)

# Get connection pool stats
stats = client.get_connection_pool_stats()
print(stats)
```

### Running Health Service

```bash
# Set environment variables
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://hub:hub@localhost:5432/hub
export DJANGO_SETTINGS_MODULE=hub.settings

# Run the service
uvicorn services.event-bus.health:app --host 0.0.0.0 --port 8090
```

### Running with Docker Compose

The service is configured in `docker-compose.yml`:

```yaml
event-bus-health-service:
  build:
    context: .
    dockerfile: services/event-bus/Dockerfile
  ports:
    - "8090:8090"
  depends_on:
    - postgres
    - redis
```

Start the service:

```bash
docker compose up event-bus-health-service
```

### Health Check Endpoints

**Liveness Probe:**
```bash
curl http://localhost:8090/healthz
```

**Readiness Probe:**
```bash
curl http://localhost:8090/ready
```

**Comprehensive Health Check:**
```bash
curl http://localhost:8090/health
```

**Prometheus Metrics:**
```bash
curl http://localhost:8090/metrics
```

**Connection Pool Statistics:**
```bash
curl http://localhost:8090/stats
```

## Connection Pooling

The event bus uses Redis connection pooling for optimal performance:

- **Pool Size**: Configurable initial pool size (default: 50)
- **Max Connections**: Maximum connections in pool (default: 100)
- **Health Checks**: Automatic connection health checks
- **Retry Logic**: Automatic retry on connection failures
- **Timeout Handling**: Configurable timeouts for connections

### Monitoring Connection Pool

```python
from services.event_bus.client import get_event_bus_client

client = get_event_bus_client()
stats = client.get_connection_pool_stats()

print(f"Created connections: {stats['created_connections']}")
print(f"Available connections: {stats['available_connections']}")
print(f"In-use connections: {stats['in_use_connections']}")
print(f"Max connections: {stats['max_connections']}")
print(f"Utilization: {stats['connection_utilization']}%")
```

## Health Checks

### Health Check Components

1. **Redis Connection**: Verifies Redis connectivity and latency
2. **Connection Pool**: Checks pool status and utilization
3. **Database Connection**: Verifies PostgreSQL connectivity (for persistence)

### Health Status Values

- `healthy`: All systems operational
- `degraded`: Non-critical systems unavailable (e.g., database)
- `unhealthy`: Critical systems unavailable (e.g., Redis)

## Development

### Running Tests

```bash
# Unit tests
pytest services/event-bus/tests/

# Integration tests
pytest services/event-bus/tests/test_client.py
pytest services/event-bus/tests/test_health.py
```

### Adding New Features

1. Add functionality to `EventBusClient` in `client.py`
2. Add corresponding health checks in `health.py`
3. Add tests in `tests/`
4. Update documentation

## Troubleshooting

### Connection Pool Exhausted

If you see connection pool errors:

1. Increase `EVENT_BUS_REDIS_MAX_CONNECTIONS`
2. Check for connection leaks
3. Monitor connection pool stats via `/stats` endpoint

### Redis Connection Failures

1. Check Redis health:
   ```bash
   curl http://localhost:8090/health
   ```

2. Verify Redis configuration:
   ```bash
   docker compose ps redis
   docker compose logs redis
   ```

3. Check Redis connection settings:
   - `REDIS_URL`
   - `EVENT_BUS_REDIS_SOCKET_TIMEOUT`
   - `EVENT_BUS_REDIS_SOCKET_CONNECT_TIMEOUT`

### High Latency

1. Check Redis latency:
   ```bash
   curl http://localhost:8090/health
   # Look for latency_ms in redis check
   ```

2. Monitor connection pool utilization:
   ```bash
   curl http://localhost:8090/stats
   ```

3. Consider:
   - Increasing connection pool size
   - Optimizing Redis configuration
   - Checking network latency

## Related Documentation

- [Event Bus Documentation](../../docs/EVENT_BUS.md)
- [Event Bus Implementation Summary](../../docs/EVENT_BUS_IMPLEMENTATION_SUMMARY.md)
- [Docker Compose Deployment](../../docs/DOCKER_COMPOSE_DEPLOYMENT.md)

