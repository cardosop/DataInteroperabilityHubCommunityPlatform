# Testing with Real Services

This document explains how to run tests with real services instead of mocks.

## Overview

By default, E2E and integration tests use mocks for external services. However, you can configure tests to use real services when they're available.

## Quick Start

### 1. Start Services

```bash
# Start all services required for testing
make docker-up-services

# Or use the script directly
./scripts/start-services-for-tests.sh
```

### 2. Run Tests with Real Services

```bash
# Set environment variable to use real services
export USE_REAL_SERVICES=true

# Run E2E tests
cd hub && python manage.py test tests.e2e

# Run integration tests
pytest -m integration

# Or run all tests
make test
```

### 3. Verify Services are Running

```bash
# Check service health
curl http://localhost:8080/health  # DataContract service
curl http://localhost:8081/health  # Semantic service
curl http://localhost:8082/health  # Compliance service
curl http://localhost:8083/health  # DQ service

# Or use the Makefile command
make verify-deps
```

## Service Configuration

### Environment Variables

Tests check for services using these environment variables:

- `USE_REAL_SERVICES` - Set to `true` or `1` to enable real service usage
- `DATACONTRACT_SERVICE_URL` - Default: `http://localhost:8080`
- `DQ_SERVICE_URL` - Default: `http://localhost:8083`
- `COMPLIANCE_SERVICE_URL` - Default: `http://localhost:8082`
- `SEMANTIC_SERVICE_URL` - Default: `http://localhost:8081`

### Service URLs

When running tests locally (outside Docker), services should be accessible at:
- `http://localhost:8080` (DataContract)
- `http://localhost:8081` (Semantic)
- `http://localhost:8082` (Compliance)
- `http://localhost:8083` (DQ)

When running in Docker, services use service names:
- `http://datacontract-service:8080`
- `http://semantic-service:8081`
- `http://compliance-service:8082`
- `http://dq-service:8083`

## Test Behavior

### With Services Available

When `USE_REAL_SERVICES=true` and services are healthy:
- Tests use real service clients
- Actual HTTP requests are made to services
- Service responses are used in tests
- Tests may be slower but more realistic

### Without Services (Default)

When services are not available or `USE_REAL_SERVICES` is not set:
- Tests use mocks
- No actual HTTP requests are made
- Tests are faster
- Tests are isolated from service failures

## Example: Running E2E Tests with Services

```bash
# 1. Start services
make docker-up-services

# 2. Wait for services to be healthy
make wait-for-services

# 3. Run E2E tests with real services
USE_REAL_SERVICES=true cd hub && python manage.py test tests.e2e.test_complete_user_journeys

# 4. Check results
# Tests should now use real services instead of mocks
```

## CI/CD Integration

In CI/CD pipelines, services are automatically started:

```yaml
# .github/workflows/ci.yml
- name: Start microservices
  run: docker-compose up -d datacontract-service dq-service compliance-service semantic-service

- name: Run tests with services
  env:
    USE_REAL_SERVICES: true
  run: pytest -m integration
```

## Troubleshooting

### Services Not Starting

```bash
# Check service logs
docker-compose logs datacontract-service
docker-compose logs dq-service
docker-compose logs compliance-service
docker-compose logs semantic-service

# Check service status
docker-compose ps
```

### Tests Still Using Mocks

1. Verify `USE_REAL_SERVICES=true` is set
2. Check services are healthy: `curl http://localhost:8083/health`
3. Check service URLs in environment variables
4. Review test logs for service connection errors

### Port Conflicts

If ports are already in use:
1. Stop conflicting services
2. Update port mappings in `docker-compose.yml`
3. Update environment variables accordingly

## Best Practices

1. **Unit Tests**: Always use mocks (fast, isolated)
2. **Integration Tests**: Use real services when available (more realistic)
3. **E2E Tests**: Use real services in CI/CD, mocks for local development
4. **Service Health**: Always check service health before running tests
5. **Fallback**: Tests should gracefully fall back to mocks if services unavailable

## Makefile Commands

```bash
# Start services for testing
make docker-up-services

# Wait for services to be healthy
make wait-for-services

# Run tests with services
USE_REAL_SERVICES=true make test

# Verify all dependencies
make verify-deps

# Stop services
make docker-down
```

## Service Health Checks

Services must respond to `/health` endpoint with:
```json
{
  "status": "healthy"
}
```

Tests automatically check service health before using them. If a service is not healthy, tests fall back to mocks.

