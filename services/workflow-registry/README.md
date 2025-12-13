# Workflow Registry Service

The Workflow Registry Service provides a REST API for managing workflow definitions, including registration, discovery, dependency tracking, and validation.

## Overview

The workflow registry service:
- Exposes REST API endpoints for workflow registry operations
- Manages workflow definitions and versions
- Tracks workflow dependencies
- Validates workflow DSL and dependencies
- Provides dependency graph visualization

## Architecture

```
┌─────────────────────────────────────┐
│   Workflow Registry Service         │
│   (FastAPI + Django ORM)            │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  REST API Endpoints         │   │
│  │  - POST /workflows          │   │
│  │  - GET /workflows           │   │
│  │  - GET /workflows/{name}    │   │
│  │  - GET /dependency-graph    │   │
│  │  - GET /workflows/{name}/   │   │
│  │    validate                 │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  WorkflowRegistry           │   │
│  │  - Registration             │   │
│  │  - Discovery                │   │
│  │  - Dependency tracking      │   │
│  │  - Validation               │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
         │
         ▼
    PostgreSQL
```

## API Endpoints

### Health Check

**GET /health**
- Returns service health status
- Response: `{"status": "healthy", "service": "workflow-registry-service", "timestamp": ...}`

**GET /metrics**
- Prometheus metrics endpoint
- Returns metrics in Prometheus format

### Workflow Registration

**POST /workflows**
- Register a new workflow definition
- Request body:
  ```json
  {
    "workflow_name": "contract_creation",
    "dsl_json": {
      "version": "1.0.0",
      "steps": [...]
    },
    "version": "1.0.0",
    "description": "Workflow description",
    "created_by_id": "user-uuid"
  }
  ```
- Response: `WorkflowDefinitionResponse` (201 Created)

### Workflow Discovery

**GET /workflows**
- Discover workflow definitions
- Query parameters:
  - `workflow_name` (optional): Filter by workflow name
  - `tags` (optional): Comma-separated list of tags
  - `is_active` (optional): Filter by active status (true/false)
- Response: `DiscoverWorkflowsResponse`

**GET /workflows/{workflow_name}**
- Get a specific workflow definition
- Query parameters:
  - `version` (optional): Workflow version (uses active version if not specified)
- Response: `WorkflowDefinitionResponse` (404 if not found)

### Dependency Management

**GET /workflows/{workflow_name}/dependencies**
- Get dependencies for a workflow
- Response: `{"dependencies": ["workflow1", "workflow2"]}`

**GET /workflows/{workflow_name}/dependents**
- Get workflows that depend on this workflow
- Response: `{"dependents": ["workflow1", "workflow2"]}`

**GET /dependency-graph**
- Get complete dependency graph
- Response: `{"graph": {"workflow1": ["dep1", "dep2"], ...}}`

**POST /dependency-graph/build**
- Rebuild dependency graph from all registered workflows
- Response: `{"status": "success", "message": "..."}`

### Workflow Validation

**GET /workflows/{workflow_name}/validate**
- Validate a workflow definition
- Query parameters:
  - `version` (optional): Workflow version
- Response: `{"valid": true/false, "errors": [...]}`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_REGISTRY_PORT` | `8089` | Service port |
| `DATABASE_URL` | - | PostgreSQL connection URL |
| `POSTGRES_HOST` | - | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | - | PostgreSQL user |
| `POSTGRES_PASSWORD` | - | PostgreSQL password |
| `POSTGRES_DB` | - | PostgreSQL database name |
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | Django settings module |
| `SECRET_KEY` | - | Django secret key |
| `DEBUG` | `False` | Django debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENVIRONMENT` | `development` | Environment name |

## Usage

### Running Locally

```bash
# Set environment variables
export DATABASE_URL=postgresql://hub:hub@localhost:5432/hub
export DJANGO_SETTINGS_MODULE=hub.settings
export SECRET_KEY=dev-secret-key

# Run the service
uvicorn services.workflow-registry.main:app --host 0.0.0.0 --port 8089
```

### Running with Docker Compose

The service is configured in `docker-compose.yml`:

```yaml
workflow-registry-service:
  build:
    context: .
    dockerfile: services/workflow-registry/Dockerfile
  ports:
    - "8089:8089"
  depends_on:
    - postgres
```

Start the service:

```bash
docker compose up workflow-registry-service
```

### Example API Calls

**Register a workflow:**
```bash
curl -X POST http://localhost:8089/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "test_workflow",
    "dsl_json": {
      "version": "1.0.0",
      "steps": [
        {
          "name": "step1",
          "type": "task",
          "task": "test_task"
        }
      ]
    },
    "version": "1.0.0",
    "description": "Test workflow"
  }'
```

**Discover workflows:**
```bash
curl http://localhost:8089/workflows
```

**Get workflow:**
```bash
curl http://localhost:8089/workflows/test_workflow
```

**Validate workflow:**
```bash
curl http://localhost:8089/workflows/test_workflow/validate
```

**Get dependency graph:**
```bash
curl http://localhost:8089/dependency-graph
```

## Development

### Running Tests

```bash
# Integration tests
pytest services/workflow-registry/tests/
```

### Adding New Endpoints

1. Add endpoint handler in `services/workflow-registry/main.py`
2. Add request/response models if needed
3. Add integration tests in `services/workflow-registry/tests/test_integration.py`

## Troubleshooting

### Service Not Starting

1. Check database connection:
   ```bash
   curl http://localhost:8089/health
   ```

2. Check logs:
   ```bash
   docker compose logs workflow-registry-service
   ```

3. Verify dependencies are running:
   ```bash
   docker compose ps postgres
   ```

### Workflow Registration Fails

1. Check workflow DSL format:
   - Must have `version` and `steps` fields
   - Steps must be a list
   - At least one step required

2. Check dependencies:
   - All dependencies must be registered first
   - No circular dependencies allowed

3. Check validation errors:
   ```bash
   curl http://localhost:8089/workflows/{workflow_name}/validate
   ```

### Dependency Graph Issues

1. Rebuild dependency graph:
   ```bash
   curl -X POST http://localhost:8089/dependency-graph/build
   ```

2. Check for circular dependencies:
   - Use validation endpoint
   - Check logs for dependency errors

## Related Documentation

- [Workflow Registry Documentation](../../hub/apps/orchestration/README.md)
- [Workflow DSL Documentation](../../hub/apps/orchestration/WORKFLOW_DSL.md)
- [Docker Compose Deployment](../../docs/DOCKER_COMPOSE_DEPLOYMENT.md)

