# Workflow Engine Service

The Workflow Engine Service is a long-running service that processes workflow instances continuously. It polls for workflow instances in `DRAFT` or `RUNNING` status and executes them using the workflow engine.

## Overview

The workflow engine service:
- Polls for workflow instances that need processing (DRAFT or RUNNING status)
- Executes workflows using the WorkflowEngine
- Provides health check endpoints for Kubernetes/Docker Compose
- Supports graceful shutdown
- Registers all workflow tasks on startup

## Architecture

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

## Components

### Main Entry Point (`main.py`)

The main entry point starts:
1. Health check HTTP server (port 8088)
2. Workflow processor (via Django management command)

### Health Checks (`health.py`)

Implements Kubernetes-style health checks:
- **Liveness Probe** (`/healthz`): Returns 200 OK if process is running
- **Readiness Probe** (`/ready`): Returns 200 OK if dependencies (database, Redis) are available

### Management Command (`process_workflows`)

Django management command that:
- Registers all workflow tasks on startup
- Polls for DRAFT workflows (starts them)
- Polls for RUNNING workflows (continues execution)
- Processes workflows in batches
- Supports configurable poll interval and batch size

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_ENGINE_HEALTH_PORT` | `8088` | Health check server port |
| `WORKFLOW_ENGINE_POLL_INTERVAL` | `5` | Polling interval in seconds |
| `WORKFLOW_ENGINE_BATCH_SIZE` | `10` | Number of workflows to process per batch |
| `DATABASE_URL` | - | PostgreSQL connection URL |
| `REDIS_URL` | - | Redis connection URL |
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | Django settings module |

### Command-Line Arguments

```bash
python services/workflow-engine/main.py [--poll-interval SECONDS] [--batch-size N]
```

- `--poll-interval`: Polling interval in seconds (default: 5)
- `--batch-size`: Number of workflows to process per batch (default: 10)

## Usage

### Running Locally

```bash
# Set environment variables
export DATABASE_URL=postgresql://hub:hub@localhost:5432/hub
export REDIS_URL=redis://localhost:6379/0

# Run the service
python services/workflow-engine/main.py --poll-interval 5 --batch-size 10
```

### Running with Docker Compose

The service is configured in `docker-compose.yml`:

```yaml
workflow-engine-service:
  build:
    context: .
    dockerfile: services/workflow-engine/Dockerfile
  environment:
    - WORKFLOW_ENGINE_POLL_INTERVAL=5
    - WORKFLOW_ENGINE_BATCH_SIZE=10
  depends_on:
    - postgres
    - redis
```

Start the service:

```bash
docker compose up workflow-engine-service
```

### Health Checks

Check service health:

```bash
# Liveness probe
curl http://localhost:8088/healthz

# Readiness probe
curl http://localhost:8088/ready

# Prometheus metrics
curl http://localhost:8088/metrics
```

## Workflow Processing

### DRAFT Workflows

Workflows in `DRAFT` status are:
1. Started (transitioned to `RUNNING`)
2. Executed immediately

### RUNNING Workflows

Workflows in `RUNNING` status are:
1. Continued from current step
2. Executed until completion or failure

### Batch Processing

The service processes workflows in batches to:
- Avoid database lock contention
- Control resource usage
- Enable parallel processing (future enhancement)

### Error Handling

- Workflow failures are caught and logged
- Failed workflows are marked with error details
- Retry logic is handled by the workflow engine
- Dead letter queue (DLQ) support for failed workflows

## Monitoring

### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics`:
- Workflow execution duration
- Workflow instance counts (created, started, completed, failed)
- Workflow step execution metrics
- Error rates

### Logging

The service logs:
- Workflow processing events
- Error details
- Health check status
- Service startup/shutdown

## Development

### Running Tests

```bash
# Unit tests
pytest services/workflow-engine/tests/

# Integration tests
pytest services/workflow-engine/tests/test_integration.py
```

### Adding New Workflows

1. Create workflow class in `hub/apps/orchestration/workflows/`
2. Implement `register_tasks()` class method
3. Import workflow class in `hub/apps/orchestration/workflows/__init__.py`
4. Tasks will be automatically registered on service startup

## Troubleshooting

### Service Not Starting

1. Check database connection:
   ```bash
   curl http://localhost:8088/ready
   ```

2. Check logs:
   ```bash
   docker compose logs workflow-engine-service
   ```

3. Verify dependencies are running:
   ```bash
   docker compose ps postgres redis
   ```

### Workflows Not Processing

1. Check workflow instances in database:
   ```sql
   SELECT status, COUNT(*) FROM workflow_instances GROUP BY status;
   ```

2. Verify workflow tasks are registered:
   - Check service logs for "Registered task" messages
   - Verify workflow classes are imported correctly

3. Check for errors in workflow execution:
   ```sql
   SELECT id, workflow_name, status, error_message 
   FROM workflow_instances 
   WHERE status = 'FAILED' 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```

### Performance Issues

1. Adjust batch size:
   ```bash
   export WORKFLOW_ENGINE_BATCH_SIZE=20
   ```

2. Adjust poll interval:
   ```bash
   export WORKFLOW_ENGINE_POLL_INTERVAL=10
   ```

3. Monitor database connections:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';
   ```

## Related Documentation

- [Workflow Engine Documentation](../../hub/apps/orchestration/README.md)
- [Workflow DSL Documentation](../../hub/apps/orchestration/WORKFLOW_DSL.md)
- [Docker Compose Deployment](../../docs/DOCKER_COMPOSE_DEPLOYMENT.md)

