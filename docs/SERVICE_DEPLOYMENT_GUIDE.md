# Service Deployment Guide

Complete guide for deploying workflow engine service, event bus service, and service layer components.

## Table of Contents

1. [Overview](#overview)
2. [Workflow Engine Service Deployment](#workflow-engine-service-deployment)
3. [Event Bus Service Deployment](#event-bus-service-deployment)
4. [Service Layer Deployment](#service-layer-deployment)
5. [Service Configuration](#service-configuration)
6. [Service Troubleshooting](#service-troubleshooting)

---

## Overview

This guide covers deployment procedures, configuration, and troubleshooting for:

- **Workflow Engine Service**: Processes workflow instances continuously
- **Event Bus Service**: Provides event-driven communication infrastructure
- **Service Layer**: Core business logic services with standardized communication

All services support deployment via Docker Compose (development/staging) and Kubernetes (production).

---

## Workflow Engine Service Deployment

### Overview

The Workflow Engine Service is a long-running service that processes workflow instances continuously. It polls for workflow instances in `DRAFT` or `RUNNING` status and executes them using the workflow engine.

**Key Features:**
- Continuous workflow processing
- Health check endpoints (`/healthz`, `/ready`, `/metrics`)
- Prometheus metrics integration
- OpenTelemetry tracing support
- Graceful shutdown support

### Architecture

```
┌─────────────────────────────────────┐
│   Workflow Engine Service          │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Health Check Server         │  │
│  │  (Port 8088)                 │  │
│  │  - /healthz (liveness)       │  │
│  │  - /ready (readiness)        │  │
│  │  - /metrics (Prometheus)      │  │
│  └─────────────────────────────┘  │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Workflow Processor          │  │
│  │  - Polls for DRAFT workflows │  │
│  │  - Polls for RUNNING workflows│  │
│  │  - Executes workflows        │  │
│  └─────────────────────────────┘  │
│                                     │
│  ┌─────────────────────────────┐  │
│  │  Workflow Engine             │  │
│  │  - Task registry             │  │
│  │  - Step execution            │  │
│  │  - Error handling            │  │
│  └─────────────────────────────┘  │
└─────────────────────────────────────┘
         │                    │
         ▼                    ▼
    PostgreSQL          Redis (Event Bus)
```

### Docker Compose Deployment

#### Configuration

The workflow engine service is configured in `docker-compose.yml`:

```yaml
workflow-engine-service:
  build:
    context: .
    dockerfile: services/workflow-engine/Dockerfile
  container_name: hub-workflow-engine
  command: python services/workflow-engine/main.py --poll-interval ${WORKFLOW_ENGINE_POLL_INTERVAL:-5} --batch-size ${WORKFLOW_ENGINE_BATCH_SIZE:-10}
  ports:
    - "${WORKFLOW_ENGINE_HEALTH_PORT:-8088}:8088"
  environment:
    # Database configuration
    - DATABASE_URL=postgresql://${POSTGRES_USER:-hub}:${POSTGRES_PASSWORD:-hub}@postgres:5432/${POSTGRES_DB:-hub}
    # Redis configuration
    - REDIS_URL=redis://redis:6379/0
    # Workflow engine configuration
    - WORKFLOW_ENGINE_HEALTH_PORT=${WORKFLOW_ENGINE_HEALTH_PORT:-8088}
    - WORKFLOW_ENGINE_POLL_INTERVAL=${WORKFLOW_ENGINE_POLL_INTERVAL:-5}
    - WORKFLOW_ENGINE_BATCH_SIZE=${WORKFLOW_ENGINE_BATCH_SIZE:-10}
    # Django settings
    - DJANGO_SETTINGS_MODULE=hub.settings
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8088/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
```

#### Deployment Steps

1. **Start Infrastructure Services**:
   ```bash
   docker compose up -d postgres redis
   ```

2. **Wait for Infrastructure Health**:
   ```bash
   # Wait for PostgreSQL
   docker compose exec postgres pg_isready -U hub
   
   # Wait for Redis
   docker compose exec redis redis-cli ping
   ```

3. **Start Workflow Engine Service**:
   ```bash
   docker compose up -d workflow-engine-service
   ```

4. **Verify Deployment**:
   ```bash
   # Check container status
   docker compose ps workflow-engine-service
   
   # Check health endpoint
   curl http://localhost:8088/healthz
   
   # Check readiness endpoint
   curl http://localhost:8088/ready
   
   # Check metrics endpoint
   curl http://localhost:8088/metrics
   ```

5. **Check Logs**:
   ```bash
   docker compose logs -f workflow-engine-service
   ```

### Kubernetes Deployment

#### Prerequisites

- Kubernetes cluster access
- kubectl configured
- PostgreSQL and Redis services available

#### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-engine-service
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: workflow-engine-service
  template:
    metadata:
      labels:
        app: workflow-engine-service
    spec:
      containers:
      - name: workflow-engine
        image: hub-workflow-engine:latest
        ports:
        - containerPort: 8088
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: WORKFLOW_ENGINE_POLL_INTERVAL
          value: "5"
        - name: WORKFLOW_ENGINE_BATCH_SIZE
          value: "10"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8088
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8088
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: workflow-engine-service
spec:
  selector:
    app: workflow-engine-service
  ports:
  - port: 8088
    targetPort: 8088
  type: ClusterIP
```

#### Deployment Steps

1. **Create Secrets**:
   ```bash
   kubectl create secret generic database-secret \
     --from-literal=url=postgresql://hub:hub@postgres:5432/hub
   
   kubectl create secret generic redis-secret \
     --from-literal=url=redis://redis:6379/0
   ```

2. **Deploy Service**:
   ```bash
   kubectl apply -f k8s/workflow-engine/deployment.yaml
   ```

3. **Verify Deployment**:
   ```bash
   # Check pods
   kubectl get pods -l app=workflow-engine-service
   
   # Check service
   kubectl get svc workflow-engine-service
   
   # Check logs
   kubectl logs -l app=workflow-engine-service --tail=100
   ```

### Configuration

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_ENGINE_HEALTH_PORT` | `8088` | Health check server port |
| `WORKFLOW_ENGINE_POLL_INTERVAL` | `5` | Polling interval in seconds |
| `WORKFLOW_ENGINE_BATCH_SIZE` | `10` | Number of workflows to process per batch |
| `DATABASE_URL` | - | PostgreSQL connection URL |
| `REDIS_URL` | - | Redis connection URL |
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | Django settings module |
| `OPENTELEMETRY_ENABLED` | `true` | Enable OpenTelemetry tracing |
| `OPENTELEMETRY_METRICS_ENABLED` | `true` | Enable Prometheus metrics |
| `JAEGER_AGENT_HOST` | `jaeger` | Jaeger agent host |
| `JAEGER_AGENT_PORT` | `6831` | Jaeger agent port |

#### Command-Line Arguments

```bash
python services/workflow-engine/main.py \
  --poll-interval 5 \
  --batch-size 10
```

- `--poll-interval`: Polling interval in seconds (default: 5)
- `--batch-size`: Number of workflows to process per batch (default: 10)

### Health Checks

#### Liveness Probe (`/healthz`)

Returns 200 OK if the process is running:

```bash
curl http://localhost:8088/healthz
```

Response:
```json
{
  "status": "ok"
}
```

#### Readiness Probe (`/ready`)

Returns 200 OK if dependencies (database, Redis) are available:

```bash
curl http://localhost:8088/ready
```

Response:
```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected"
}
```

#### Metrics Endpoint (`/metrics`)

Prometheus metrics endpoint:

```bash
curl http://localhost:8088/metrics
```

### Monitoring

#### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics`:

- `workflow_instances_created_total` - Total workflow instances created
- `workflow_instances_started_total` - Total workflow instances started
- `workflow_instances_completed_total` - Total workflow instances completed
- `workflow_instances_failed_total` - Total workflow instances failed
- `workflow_execution_duration_seconds` - Workflow execution duration histogram
- `workflow_instances_running` - Current running workflows (gauge)
- `workflow_instances_pending` - Current pending workflows (gauge)
- `workflow_instances_failed_current` - Current failed workflows (gauge)

#### Grafana Dashboard

Import the workflow orchestration dashboard:

```bash
# Dashboard file: monitoring/grafana/dashboards/workflow-orchestration.json
```

Dashboard includes:
- Workflow instance throughput
- Success/failure rates
- Execution duration (P95)
- Current workflow counts
- Retry and timeout rates

### Troubleshooting

#### Service Not Starting

**Symptoms**: Container exits immediately or fails health checks

**Diagnosis**:
```bash
# Check container logs
docker compose logs workflow-engine-service

# Check container status
docker compose ps workflow-engine-service

# Check health endpoint
curl http://localhost:8088/healthz
```

**Solutions**:
1. Verify database connection:
   ```bash
   docker compose exec postgres pg_isready -U hub
   ```

2. Verify Redis connection:
   ```bash
   docker compose exec redis redis-cli ping
   ```

3. Check environment variables:
   ```bash
   docker compose exec workflow-engine-service env | grep -E "DATABASE|REDIS|WORKFLOW"
   ```

4. Verify dependencies are healthy:
   ```bash
   docker compose ps postgres redis
   ```

#### Workflows Not Processing

**Symptoms**: Workflows remain in DRAFT or RUNNING status

**Diagnosis**:
```sql
-- Check workflow status distribution
SELECT status, COUNT(*) 
FROM workflow_instances 
GROUP BY status;

-- Check for failed workflows
SELECT id, workflow_name, status, error_message 
FROM workflow_instances 
WHERE status = 'FAILED' 
ORDER BY created_at DESC 
LIMIT 10;
```

**Solutions**:
1. Verify workflow tasks are registered:
   ```bash
   # Check service logs for "Registered task" messages
   docker compose logs workflow-engine-service | grep "Registered task"
   ```

2. Check workflow task registry:
   ```python
   from hub.apps.orchestration.engine import WorkflowEngine
   engine = WorkflowEngine()
   print(engine.task_registry.keys())
   ```

3. Verify workflow classes are imported:
   ```python
   # Check hub/apps/orchestration/workflows/__init__.py
   ```

4. Check for database locks:
   ```sql
   SELECT * FROM pg_locks WHERE relation = 'workflow_instances'::regclass;
   ```

#### Performance Issues

**Symptoms**: Slow workflow processing, high latency

**Diagnosis**:
```bash
# Check workflow execution metrics
curl http://localhost:8088/metrics | grep workflow_execution_duration

# Check database connections
docker compose exec postgres psql -U hub -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';"
```

**Solutions**:
1. Increase batch size:
   ```bash
   export WORKFLOW_ENGINE_BATCH_SIZE=20
   docker compose restart workflow-engine-service
   ```

2. Adjust poll interval:
   ```bash
   export WORKFLOW_ENGINE_POLL_INTERVAL=10
   docker compose restart workflow-engine-service
   ```

3. Scale horizontally (Kubernetes):
   ```bash
   kubectl scale deployment workflow-engine-service --replicas=3
   ```

4. Optimize database queries:
   - Add indexes on `workflow_instances.status`
   - Add indexes on `workflow_instances.created_at`
   - Review slow query log

---

## Event Bus Service Deployment

### Overview

The Event Bus Service provides event-driven communication infrastructure using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

**Key Features:**
- Redis Pub/Sub for real-time event delivery
- PostgreSQL persistence for replay and audit
- Connection pooling for optimal performance
- Health check endpoints (`/health`, `/healthz`, `/ready`, `/metrics`)
- Dead letter queue support
- Event replay functionality

### Architecture

```
┌─────────────────────────────────────┐
│   Event Bus Service                 │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Health Service              │   │
│  │  (Port 8090)                 │   │
│  │  - /health (comprehensive)   │   │
│  │  - /healthz (liveness)       │   │
│  │  - /ready (readiness)        │   │
│  │  - /metrics (Prometheus)     │   │
│  │  - /stats (pool stats)       │   │
│  └─────────────────────────────┘   │
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

### Docker Compose Deployment

#### Configuration

The event bus health service is configured in `docker-compose.yml`:

```yaml
event-bus-health-service:
  build:
    context: .
    dockerfile: services/event-bus/Dockerfile
  container_name: hub-event-bus-health
  ports:
    - "${EVENT_BUS_HEALTH_PORT:-8090}:8090"
  environment:
    # Database configuration
    - DATABASE_URL=postgresql://${POSTGRES_USER:-hub}:${POSTGRES_PASSWORD:-hub}@postgres:5432/${POSTGRES_DB:-hub}
    # Redis configuration
    - REDIS_URL=redis://redis:6379/0
    # Event bus configuration
    - EVENT_BUS_REDIS_POOL_SIZE=${EVENT_BUS_REDIS_POOL_SIZE:-50}
    - EVENT_BUS_REDIS_MAX_CONNECTIONS=${EVENT_BUS_REDIS_MAX_CONNECTIONS:-100}
    - EVENT_BUS_REDIS_SOCKET_TIMEOUT=${EVENT_BUS_REDIS_SOCKET_TIMEOUT:-5}
    - EVENT_BUS_CHANNEL_PREFIX=${EVENT_BUS_CHANNEL_PREFIX:-events}
    - EVENT_BUS_ENABLE_PERSISTENCE=${EVENT_BUS_ENABLE_PERSISTENCE:-true}
    - EVENT_BUS_MAX_RETRIES=${EVENT_BUS_MAX_RETRIES:-3}
    - EVENT_BUS_HEALTH_PORT=${EVENT_BUS_HEALTH_PORT:-8090}
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8090/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
```

#### Deployment Steps

1. **Start Infrastructure Services**:
   ```bash
   docker compose up -d postgres redis
   ```

2. **Wait for Infrastructure Health**:
   ```bash
   # Wait for PostgreSQL
   docker compose exec postgres pg_isready -U hub
   
   # Wait for Redis
   docker compose exec redis redis-cli ping
   ```

3. **Start Event Bus Health Service**:
   ```bash
   docker compose up -d event-bus-health-service
   ```

4. **Verify Deployment**:
   ```bash
   # Check container status
   docker compose ps event-bus-health-service
   
   # Check health endpoint
   curl http://localhost:8090/healthz
   
   # Check readiness endpoint
   curl http://localhost:8090/ready
   
   # Check comprehensive health
   curl http://localhost:8090/health
   
   # Check metrics endpoint
   curl http://localhost:8090/metrics
   
   # Check connection pool stats
   curl http://localhost:8090/stats
   ```

5. **Check Logs**:
   ```bash
   docker compose logs -f event-bus-health-service
   ```

### Kubernetes Deployment

#### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-bus-health-service
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: event-bus-health-service
  template:
    metadata:
      labels:
        app: event-bus-health-service
    spec:
      containers:
      - name: event-bus-health
        image: hub-event-bus-health:latest
        ports:
        - containerPort: 8090
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: EVENT_BUS_REDIS_POOL_SIZE
          value: "50"
        - name: EVENT_BUS_REDIS_MAX_CONNECTIONS
          value: "100"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8090
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8090
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
---
apiVersion: v1
kind: Service
metadata:
  name: event-bus-health-service
spec:
  selector:
    app: event-bus-health-service
  ports:
  - port: 8090
    targetPort: 8090
  type: ClusterIP
```

### Configuration

#### Environment Variables

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
| `DATABASE_URL` | - | PostgreSQL connection URL |

#### Redis Configuration

Redis is configured in `docker-compose.yml` with:

```yaml
redis:
  command: >
    redis-server
    --appendonly yes
    --maxmemory ${REDIS_MAX_MEMORY:-2gb}
    --maxmemory-policy ${REDIS_MAXMEMORY_POLICY:-allkeys-lru}
```

### Health Checks

#### Liveness Probe (`/healthz`)

Returns 200 OK if the process is running:

```bash
curl http://localhost:8090/healthz
```

#### Readiness Probe (`/ready`)

Returns 200 OK if dependencies (Redis, database) are available:

```bash
curl http://localhost:8090/ready
```

Response:
```json
{
  "status": "ready",
  "redis": {
    "connected": true,
    "latency_ms": 1.2
  },
  "database": {
    "connected": true
  }
}
```

#### Comprehensive Health Check (`/health`)

Returns detailed health status:

```bash
curl http://localhost:8090/health
```

Response:
```json
{
  "status": "healthy",
  "service": "event-bus-health-service",
  "timestamp": 1234567890.123,
  "redis": {
    "connected": true,
    "latency_ms": 1.2,
    "pool_stats": {
      "created_connections": 50,
      "available_connections": 45,
      "in_use_connections": 5,
      "max_connections": 100
    }
  },
  "database": {
    "connected": true
  }
}
```

#### Connection Pool Statistics (`/stats`)

Returns connection pool statistics:

```bash
curl http://localhost:8090/stats
```

Response:
```json
{
  "created_connections": 50,
  "available_connections": 45,
  "in_use_connections": 5,
  "max_connections": 100,
  "connection_utilization": 5.0
}
```

### Monitoring

#### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics`:

- `event_published_total` - Total events published
- `event_publish_failed_total` - Total publish failures
- `event_consumed_total` - Total events consumed
- `event_consume_failed_total` - Total consume failures
- `event_publish_duration_seconds` - Publish latency histogram
- `event_processing_duration_seconds` - Processing latency histogram
- `event_dlq_size` - Dead letter queue size (gauge)
- `event_bus_redis_connection_errors_total` - Redis connection errors
- `event_bus_redis_pool_utilization_percent` - Connection pool utilization

#### Grafana Dashboard

Import the event bus dashboard:

```bash
# Dashboard file: monitoring/grafana/dashboards/event-bus-health.json
```

### Troubleshooting

#### Connection Pool Exhausted

**Symptoms**: `ConnectionPoolExhausted` errors, high connection pool utilization

**Diagnosis**:
```bash
# Check connection pool stats
curl http://localhost:8090/stats

# Check health endpoint
curl http://localhost:8090/health | jq '.redis.pool_stats'
```

**Solutions**:
1. Increase max connections:
   ```bash
   export EVENT_BUS_REDIS_MAX_CONNECTIONS=200
   docker compose restart event-bus-health-service
   ```

2. Check for connection leaks:
   ```python
   from services.event_bus.client import get_event_bus_client
   client = get_event_bus_client()
   stats = client.get_connection_pool_stats()
   print(f"In-use connections: {stats['in_use_connections']}")
   ```

3. Monitor connection pool metrics:
   ```bash
   curl http://localhost:8090/metrics | grep event_bus_redis_pool
   ```

#### Redis Connection Failures

**Symptoms**: Health checks fail, events not publishing

**Diagnosis**:
```bash
# Check Redis health
curl http://localhost:8090/health | jq '.redis'

# Check Redis directly
docker compose exec redis redis-cli ping

# Check Redis logs
docker compose logs redis
```

**Solutions**:
1. Verify Redis is running:
   ```bash
   docker compose ps redis
   ```

2. Check Redis configuration:
   ```bash
   docker compose exec redis redis-cli CONFIG GET "*"
   ```

3. Verify Redis URL:
   ```bash
   docker compose exec event-bus-health-service env | grep REDIS_URL
   ```

4. Test Redis connectivity:
   ```bash
   docker compose exec event-bus-health-service python -c "
   import redis
   r = redis.from_url('redis://redis:6379/0')
   print(r.ping())
   "
   ```

#### High Latency

**Symptoms**: Slow event publishing/consumption

**Diagnosis**:
```bash
# Check Redis latency
curl http://localhost:8090/health | jq '.redis.latency_ms'

# Check event publish latency metrics
curl http://localhost:8090/metrics | grep event_publish_duration_seconds
```

**Solutions**:
1. Optimize Redis configuration:
   ```yaml
   redis:
     command: >
       redis-server
       --appendonly yes
       --maxmemory 4gb
       --maxmemory-policy allkeys-lru
   ```

2. Increase connection pool size:
   ```bash
   export EVENT_BUS_REDIS_POOL_SIZE=100
   export EVENT_BUS_REDIS_MAX_CONNECTIONS=200
   ```

3. Check network latency:
   ```bash
   docker compose exec event-bus-health-service ping redis
   ```

4. Monitor Redis performance:
   ```bash
   docker compose exec redis redis-cli --latency
   ```

#### Dead Letter Queue Growth

**Symptoms**: DLQ size increasing, events not being consumed

**Diagnosis**:
```bash
# Check DLQ size
curl http://localhost:8090/metrics | grep event_dlq_size

# Query DLQ events
python manage.py shell
>>> from hub.apps.core.events.models import DeadLetterQueue
>>> DeadLetterQueue.objects.count()
```

**Solutions**:
1. Review DLQ events:
   ```python
   from hub.apps.core.events.models import DeadLetterQueue
   events = DeadLetterQueue.objects.all()[:10]
   for event in events:
       print(f"Event: {event.event_type}, Error: {event.error_message}")
   ```

2. Replay DLQ events:
   ```python
   from hub.apps.core.events.bus import get_event_bus
   bus = get_event_bus()
   bus.replay_dlq_events(event_type="contract.created", limit=10)
   ```

3. Fix root cause:
   - Review error messages in DLQ
   - Fix subscriber handlers
   - Update event schemas if needed

---

## Service Layer Deployment

### Overview

The service layer provides core business logic services with standardized communication patterns, service discovery, and health checks.

**Key Components:**
- Service Discovery: Centralized service URL resolution
- Service-to-Service Communication: Standardized HTTP client
- Health Checks: Service health monitoring
- Configuration Management: Environment-based configuration

### Service Discovery

#### Docker Compose

Services are accessible via Docker DNS service names:

```python
from hub.apps.core.services.discovery import get_service_url

# Get service URL
url = get_service_url("api-service")
# Returns: "http://api-service:8000"
```

#### Kubernetes

Services are accessible via Kubernetes DNS:

```python
from hub.apps.core.services.discovery import get_service_url

# Get service URL
url = get_service_url("api-service", namespace="default")
# Returns: "http://api-service.default.svc.cluster.local:8000"
```

### Service-to-Service Communication

#### Using ServiceClient

```python
from hub.apps.core.services.cross_service_access import ServiceClient

# Create client
client = ServiceClient("api-service")

# Make GET request
data = client.get("/api/v1/contracts/123", tenant_id="tenant-uuid")

# Make POST request
result = client.post("/api/v1/contracts", data={"name": "..."}, tenant_id="tenant-uuid")
```

#### Features

- Automatic retry with exponential backoff
- Tenant isolation (automatic `X-Tenant-Id` header)
- OpenTelemetry tracing integration
- Error handling (converts HTTP errors to `ServiceError`)
- Configurable timeouts

### Health Checks

#### Check Single Service

```python
from hub.apps.core.services.health import check_service_health

result = check_service_health("api-service")
# Returns: {"status": "healthy", "latency_ms": 10.5, ...}
```

#### Monitor All Services

```python
from hub.apps.core.services.health import ServiceHealthMonitor

monitor = ServiceHealthMonitor()
results = monitor.check_all_services()
healthy_services = monitor.get_healthy_services()
unhealthy_services = monitor.get_unhealthy_services()
```

### Configuration

#### Environment Variables

Configure service URLs via environment variables:

```bash
# Docker Compose
API_SERVICE_URL=http://api-service:8000
CONTRACT_SERVICE_URL=http://contract-service:8001

# Kubernetes
API_SERVICE_URL=http://api-service.default.svc.cluster.local:8000
```

#### Django Settings

Service URLs can also be configured in Django settings:

```python
# settings.py
API_SERVICE_URL = env('API_SERVICE_URL', default='http://api-service:8000')
CONTRACT_SERVICE_URL = env('CONTRACT_SERVICE_URL', default='http://contract-service:8001')
```

### Docker Compose Configuration

```yaml
services:
  api-service:
    ports:
      - "8000:8000"
    environment:
      - CONTRACT_SERVICE_URL=http://contract-service:8001
      - ASSET_SERVICE_URL=http://asset-service:8002
    networks:
      - hub-net
```

### Kubernetes Configuration

```yaml
env:
  - name: API_SERVICE_URL
    value: "http://api-service.default.svc.cluster.local:8000"
  - name: CONTRACT_SERVICE_URL
    value: "http://contract-service.default.svc.cluster.local:8001"
```

### Troubleshooting

#### Service Not Found

**Symptoms**: `ServiceNotFoundError` or URL resolution fails

**Solutions**:
1. Check service is registered:
   ```python
   from hub.apps.core.services.discovery import ServiceRegistry
   config = ServiceRegistry.get_service_config("api-service")
   print(config)
   ```

2. Check environment variable:
   ```bash
   docker compose exec api-service env | grep API_SERVICE_URL
   ```

3. Verify Docker network:
   ```bash
   docker network inspect hub-net
   ```

4. Check Kubernetes service:
   ```bash
   kubectl get svc api-service
   ```

#### Health Check Failures

**Symptoms**: Health checks return "unhealthy"

**Solutions**:
1. Verify service is running:
   ```bash
   docker compose ps api-service
   # or
   kubectl get pods -l app=api-service
   ```

2. Check health endpoint:
   ```bash
   curl http://api-service:8000/health
   ```

3. Check network connectivity:
   ```bash
   docker compose exec api-service ping contract-service
   ```

4. Review service logs:
   ```bash
   docker compose logs api-service
   # or
   kubectl logs -l app=api-service
   ```

#### Service Communication Failures

**Symptoms**: Service-to-service calls fail

**Solutions**:
1. Check service URLs:
   ```python
   from hub.apps.core.services.discovery import get_service_url
   url = get_service_url("api-service")
   print(url)
   ```

2. Verify network connectivity:
   ```bash
   docker compose exec api-service curl http://contract-service:8001/health
   ```

3. Check firewall rules:
   - Ensure ports are open
   - Verify network policies (Kubernetes)

4. Verify tenant context:
   ```python
   # Ensure X-Tenant-Id header is set
   client = ServiceClient("api-service")
   result = client.get("/api/v1/contracts/123", tenant_id="tenant-uuid")
   ```

---

## Service Configuration

### Common Configuration Patterns

#### Environment-Based Configuration

All services support environment-based configuration:

```bash
# Development
export ENVIRONMENT=development
export DEBUG=True
export LOG_LEVEL=DEBUG

# Staging
export ENVIRONMENT=staging
export DEBUG=False
export LOG_LEVEL=INFO

# Production
export ENVIRONMENT=production
export DEBUG=False
export LOG_LEVEL=WARNING
```

#### Database Configuration

```bash
# PostgreSQL connection
export DATABASE_URL=postgresql://user:password@host:5432/database
export POSTGRES_HOST=postgres
export POSTGRES_PORT=5432
export POSTGRES_USER=hub
export POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub
```

#### Redis Configuration

```bash
# Redis connection
export REDIS_URL=redis://host:6379/0
export REDIS_HOST=redis
export REDIS_PORT=6379
export REDIS_MAX_MEMORY=2gb
export REDIS_MAXMEMORY_POLICY=allkeys-lru
```

#### OpenTelemetry Configuration

```bash
# Enable tracing and metrics
export OPENTELEMETRY_ENABLED=true
export OPENTELEMETRY_METRICS_ENABLED=true
export JAEGER_AGENT_HOST=jaeger
export JAEGER_AGENT_PORT=6831
export ENVIRONMENT=production
export APP_VERSION=1.0.0
```

### Service-Specific Configuration

#### Workflow Engine Service

```bash
export WORKFLOW_ENGINE_HEALTH_PORT=8088
export WORKFLOW_ENGINE_POLL_INTERVAL=5
export WORKFLOW_ENGINE_BATCH_SIZE=10
```

#### Event Bus Service

```bash
export EVENT_BUS_REDIS_POOL_SIZE=50
export EVENT_BUS_REDIS_MAX_CONNECTIONS=100
export EVENT_BUS_REDIS_SOCKET_TIMEOUT=5
export EVENT_BUS_CHANNEL_PREFIX=events
export EVENT_BUS_ENABLE_PERSISTENCE=true
export EVENT_BUS_MAX_RETRIES=3
export EVENT_BUS_HEALTH_PORT=8090
```

### Configuration Files

#### Docker Compose Environment Files

Create `.env.dev`, `.env.staging`, `.env.production` files:

```bash
# .env.dev
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://hub:hub@postgres:5432/hub
REDIS_URL=redis://redis:6379/0
```

#### Kubernetes ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: service-config
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  WORKFLOW_ENGINE_POLL_INTERVAL: "5"
  WORKFLOW_ENGINE_BATCH_SIZE: "10"
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: database-secret
type: Opaque
stringData:
  url: "postgresql://hub:hub@postgres:5432/hub"
  password: "secure-password"
```

---

## Service Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptoms**: Container exits immediately, health checks fail

**Diagnosis Steps**:
1. Check container logs:
   ```bash
   docker compose logs service-name
   # or
   kubectl logs pod-name
   ```

2. Check health endpoints:
   ```bash
   curl http://localhost:PORT/healthz
   curl http://localhost:PORT/ready
   ```

3. Verify dependencies:
   ```bash
   docker compose ps postgres redis
   # or
   kubectl get pods -l app=postgres
   ```

**Common Causes**:
- Database connection failure
- Redis connection failure
- Missing environment variables
- Port conflicts
- Insufficient resources

**Solutions**:
- Verify database/Redis are running and healthy
- Check environment variables are set correctly
- Verify ports are not in use
- Check resource limits (memory, CPU)

#### 2. Service Health Checks Failing

**Symptoms**: Health checks return unhealthy, service appears down

**Diagnosis Steps**:
1. Check health endpoint directly:
   ```bash
   curl -v http://service-name:port/health
   ```

2. Check dependency health:
   ```bash
   curl http://service-name:port/ready
   ```

3. Review service logs:
   ```bash
   docker compose logs -f service-name
   ```

**Common Causes**:
- Database connection issues
- Redis connection issues
- Service initialization failures
- Resource exhaustion

**Solutions**:
- Verify database/Redis connectivity
- Check service initialization logs
- Review resource usage (memory, CPU)
- Verify service dependencies are healthy

#### 3. Service Communication Failures

**Symptoms**: Service-to-service calls fail, timeouts, connection errors

**Diagnosis Steps**:
1. Test service connectivity:
   ```bash
   docker compose exec service1 curl http://service2:port/health
   ```

2. Check service URLs:
   ```python
   from hub.apps.core.services.discovery import get_service_url
   url = get_service_url("service-name")
   print(url)
   ```

3. Review service logs:
   ```bash
   docker compose logs service-name | grep -i error
   ```

**Common Causes**:
- Network connectivity issues
- Service not running
- Incorrect service URLs
- Firewall/network policies blocking traffic

**Solutions**:
- Verify services are on same network
- Check service URLs are correct
- Verify services are running
- Review network policies (Kubernetes)

#### 4. High Latency

**Symptoms**: Slow response times, timeouts

**Diagnosis Steps**:
1. Check service metrics:
   ```bash
   curl http://service-name:port/metrics | grep duration
   ```

2. Check database performance:
   ```sql
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   ```

3. Check Redis latency:
   ```bash
   docker compose exec redis redis-cli --latency
   ```

**Common Causes**:
- Database query performance issues
- Redis latency
- Network latency
- Resource constraints

**Solutions**:
- Optimize database queries
- Add database indexes
- Increase connection pool sizes
- Scale services horizontally
- Optimize Redis configuration

#### 5. Memory/CPU Issues

**Symptoms**: OOM kills, high CPU usage, slow performance

**Diagnosis Steps**:
1. Check resource usage:
   ```bash
   docker stats service-name
   # or
   kubectl top pod service-name
   ```

2. Check service metrics:
   ```bash
   curl http://service-name:port/metrics | grep memory
   ```

3. Review service logs for OOM errors:
   ```bash
   docker compose logs service-name | grep -i oom
   ```

**Common Causes**:
- Memory leaks
- Insufficient resource limits
- High load
- Inefficient code

**Solutions**:
- Increase resource limits
- Optimize memory usage
- Scale services horizontally
- Review code for memory leaks
- Use connection pooling

### Diagnostic Commands

#### Check Service Status

```bash
# Docker Compose
docker compose ps
docker compose ps service-name

# Kubernetes
kubectl get pods
kubectl get pods -l app=service-name
```

#### Check Service Logs

```bash
# Docker Compose
docker compose logs service-name
docker compose logs -f service-name
docker compose logs --tail=100 service-name

# Kubernetes
kubectl logs pod-name
kubectl logs -f pod-name
kubectl logs --tail=100 pod-name
```

#### Check Service Health

```bash
# Health endpoints
curl http://localhost:PORT/healthz
curl http://localhost:PORT/ready
curl http://localhost:PORT/health
curl http://localhost:PORT/metrics
```

#### Check Network Connectivity

```bash
# Docker Compose
docker compose exec service1 ping service2
docker compose exec service1 curl http://service2:port/health

# Kubernetes
kubectl exec pod-name -- ping service-name
kubectl exec pod-name -- curl http://service-name:port/health
```

#### Check Database Connectivity

```bash
# PostgreSQL
docker compose exec postgres pg_isready -U hub
docker compose exec service-name python -c "
import os
import psycopg2
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
print('Connected')
"

# Kubernetes
kubectl exec pod-name -- pg_isready -U hub
```

#### Check Redis Connectivity

```bash
# Redis
docker compose exec redis redis-cli ping
docker compose exec service-name python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
print(r.ping())
"

# Kubernetes
kubectl exec pod-name -- redis-cli ping
```

### Escalation Procedures

#### Level 1: Service Restart

```bash
# Docker Compose
docker compose restart service-name

# Kubernetes
kubectl rollout restart deployment/service-name
```

#### Level 2: Service Recreate

```bash
# Docker Compose
docker compose up -d --force-recreate service-name

# Kubernetes
kubectl delete pod pod-name
# Pod will be recreated automatically
```

#### Level 3: Full Service Redeployment

```bash
# Docker Compose
docker compose down service-name
docker compose up -d service-name

# Kubernetes
kubectl delete deployment service-name
kubectl apply -f deployment.yaml
```

#### Level 4: Infrastructure Check

```bash
# Check all infrastructure services
docker compose ps
docker compose logs

# Check Kubernetes cluster
kubectl get nodes
kubectl get pods --all-namespaces
kubectl get events --sort-by='.lastTimestamp'
```

### Best Practices

1. **Always Check Logs First**: Logs provide the most detailed information
2. **Verify Dependencies**: Ensure all dependencies are healthy before troubleshooting
3. **Use Health Endpoints**: Health endpoints provide quick status checks
4. **Monitor Metrics**: Use Prometheus metrics for performance analysis
5. **Test Connectivity**: Verify network connectivity between services
6. **Review Configuration**: Check environment variables and configuration files
7. **Scale Gradually**: Start with restart, then recreate, then redeploy
8. **Document Issues**: Keep track of issues and solutions for future reference

---

## Related Documentation

- [Docker Compose Deployment](./DOCKER_COMPOSE_DEPLOYMENT.md)
- [Kubernetes Deployment](./KUBERNETES_DEPLOYMENT.md)
- [Service Layer Deployment](./SERVICE_LAYER_DEPLOYMENT.md)
- [Workflow Monitoring Setup](./WORKFLOW_MONITORING_SETUP.md)
- [Event Bus Monitoring](./EVENT_BUS_MONITORING.md)
- [Service Layer Monitoring](./SERVICE_LAYER_MONITORING.md)
- [Deployment Scripts](./DEPLOYMENT_SCRIPTS.md)
- [Health Check Scripts](./HEALTH_CHECK_SCRIPTS.md)
- [Monitoring Scripts](./MONITORING_SCRIPTS.md)

