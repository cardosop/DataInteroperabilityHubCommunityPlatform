# Docker Compose Integration Tests

Comprehensive integration tests for Docker Compose deployment, service startup, health checks, service communication, and service dependencies.

## Overview

These tests verify that Docker Compose services:
- Deploy correctly
- Start in the correct order respecting dependencies
- Have working health check endpoints
- Can communicate with each other
- Handle dependency failures gracefully

## Test Structure

### Test Classes

1. **TestDockerComposeDeployment**: Static validation tests
   - Validates docker-compose.yml structure
   - Checks service definitions
   - Verifies health check configurations

2. **TestDockerComposeServiceStartup**: Runtime startup tests
   - Tests infrastructure service startup
   - Tests application service startup after infrastructure
   - Verifies startup order respects dependencies
   - Tests service restart capability

3. **TestDockerComposeHealthChecks**: Health check tests
   - Tests liveness probes (`/healthz`)
   - Tests readiness probes (`/ready`)
   - Tests comprehensive health endpoints (`/health`)
   - Tests Prometheus metrics endpoints (`/metrics`)

4. **TestDockerComposeServiceCommunication**: Service communication tests
   - Tests service-to-service network connectivity
   - Tests event bus Redis connection
   - Tests service discovery
   - Tests API service backend connectivity

5. **TestDockerComposeServiceDependencies**: Dependency tests
   - Tests workflow-engine dependencies (postgres, redis-cache)
   - Tests event-bus dependencies (postgres, redis-cache)
   - Tests API service dependencies
   - Tests dependency health conditions
   - Tests graceful failure without dependencies

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.10+
- pytest
- requests library

## Running Tests

### Option 1: Using the Test Runner Script (Recommended)

```bash
# Run all integration tests
./scripts/run_docker_compose_integration_tests.sh

# Keep services running after tests
./scripts/run_docker_compose_integration_tests.sh --keep-services

# Start specific services only (use redis-cache, not redis — matches docker-compose.yml)
./scripts/run_docker_compose_integration_tests.sh --services postgres,redis-cache,workflow-engine-service
```

### Option 2: Manual Docker Compose + pytest

```bash
# Start services manually (docker-compose.yml uses redis-cache, not redis)
docker compose up -d postgres redis-cache minio fuseki
docker compose up -d workflow-engine-service workflow-registry-service event-bus-health-service

# Wait for services to be healthy
sleep 30

# Run runtime tests (requires PYTEST_DOCKER_COMPOSE_RUNTIME=1)
export PYTEST_DOCKER_COMPOSE_RUNTIME=1
pytest tests/integration/test_docker_compose_deployment.py \
    -v \
    -m "integration and docker_compose_runtime"
```

### Option 3: Static Validation Only (No Docker Required)

```bash
# Run only static validation tests (no Docker Compose runtime required)
pytest tests/integration/test_docker_compose_deployment.py::TestDockerComposeDeployment -v
```

### Runtime tests (optional)

Runtime tests (service startup, health checks, communication, dependencies) are **skipped by default**. They use real Docker Compose and real HTTP — no mocks.

- **Enable:** Set `PYTEST_DOCKER_COMPOSE_RUNTIME=1` before running pytest.
- **Start services first:** Use `./scripts/run_docker_compose_integration_tests.sh` or start compose manually, then run pytest with the same env.
- **CI:** Normal CI runs do not set this variable, so only static validation runs. To run runtime tests in CI, add a dedicated job that sets `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and starts a minimal compose stack.

## Test Coverage

### Deployment Tests (Static)

- ✅ Docker Compose file exists
- ✅ Valid YAML structure
- ✅ Infrastructure services defined
- ✅ Application services defined
- ✅ Services have health checks

### Startup Tests (Runtime)

- ✅ Infrastructure services start successfully
- ✅ Application services start after infrastructure
- ✅ Startup order respects dependencies
- ✅ Services can be restarted

### Health Check Tests (Runtime)

- ✅ Health endpoints are accessible
- ✅ Liveness probes respond correctly
- ✅ Readiness probes respond correctly
- ✅ Comprehensive health checks work
- ✅ Metrics endpoints are accessible

### Communication Tests (Runtime)

- ✅ Services can reach each other via Docker network
- ✅ Event bus can connect to Redis
- ✅ Service discovery works
- ✅ API service can reach backend services

### Dependency Tests (Runtime)

- ✅ Workflow engine depends on postgres
- ✅ Workflow engine depends on redis-cache
- ✅ Event bus depends on postgres and redis-cache
- ✅ API service depends on infrastructure
- ✅ Dependency health conditions work
- ✅ Services fail gracefully without dependencies

## Test Fixtures

### docker_compose_file
Path to docker-compose.yml file.

### docker_compose_config
Loaded YAML configuration from docker-compose.yml.

### docker_compose_manager
DockerComposeManager instance for managing Docker Compose lifecycle.

### infrastructure_services
List of infrastructure service names (postgres, redis-cache, minio, fuseki) — matches docker-compose.yml.

### application_services
List of application service names (workflow-engine-service, etc.).

### started_services
Fixture that starts services for runtime tests.

## DockerComposeManager

The `DockerComposeManager` class provides utilities for managing Docker Compose:

```python
manager = DockerComposeManager(compose_file)

# Start services (use redis-cache to match docker-compose.yml)
manager.start_services(['postgres', 'redis-cache'], wait=True)

# Check service status
status = manager.get_service_status('workflow-engine-service')

# Wait for service to be healthy
manager.wait_for_service_healthy('workflow-engine-service', timeout=300)

# Get service logs
logs = manager.get_service_logs('workflow-engine-service', tail=100)

# Restart service
manager.restart_service('workflow-engine-service')

# Stop services
manager.stop_services()
```

## Test Markers

Tests are marked with pytest markers:

- `@pytest.mark.integration`: Integration test marker
- `@pytest.mark.docker_compose_runtime`: Requires Docker Compose runtime

## Coverage Requirements

- **Target Coverage**: 95%+
- **Coverage Report**: Generated in `tests/integration/coverage_html/`

## Troubleshooting

### Services Not Starting

If services fail to start:

1. Check Docker Compose logs:
   ```bash
   docker compose logs workflow-engine-service
   ```

2. Verify dependencies are healthy:
   ```bash
   docker compose ps
   ```

3. Check service health:
   ```bash
   curl http://localhost:8088/healthz
   ```

### Tests Timing Out

If tests timeout waiting for services:

1. Increase timeout in test:
   ```python
   manager.wait_for_service_healthy('service-name', timeout=600)
   ```

2. Check service logs for errors:
   ```bash
   docker compose logs --tail=100 service-name
   ```

3. Verify Docker resources:
   ```bash
   docker system df
   docker system prune  # If needed
   ```

### Health Checks Failing

If health checks fail:

1. Verify service is running:
   ```bash
   docker compose ps service-name
   ```

2. Test health endpoint manually:
   ```bash
   curl http://localhost:PORT/healthz
   ```

3. Check service logs:
   ```bash
   docker compose logs service-name | grep -i error
   ```

## Best Practices

1. **Always Clean Up**: Use fixtures to ensure services are stopped after tests
2. **Wait for Health**: Always wait for services to be healthy before testing
3. **Check Logs**: Review service logs when tests fail
4. **Isolate Tests**: Each test class should be independent
5. **Use Fixtures**: Leverage pytest fixtures for setup/teardown
6. **Handle Failures**: Tests should handle service failures gracefully

## Related Documentation

- [Docker Compose Deployment Guide](../../docs/DOCKER_COMPOSE_DEPLOYMENT.md)
- [Service Deployment Guide](../../docs/SERVICE_DEPLOYMENT_GUIDE.md)
- [Integration Tests README](./README.md)

