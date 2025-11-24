# Testing Setup - Service Health Checks

This document describes how to run tests with external services.

## Overview

Integration tests require the following microservices to be running:
- **DataContract CLI Service** (port 8080)
- **DQ Service** (port 8083)
- **Compliance Service** (port 8082)
- **Semantic Service** (port 8081)

## Quick Start

### Start Services for Integration Tests

```bash
# Option 1: Use the Makefile command
make docker-up-services

# Option 2: Use the script directly
./scripts/start-services-for-tests.sh

# Option 3: Start services and run integration tests in one command
make test-integration-with-services
```

### Run Tests

```bash
# Run unit tests only (no services required)
make test-unit

# Run integration tests (requires services to be running)
make test-integration

# Run all tests
make test
```

## Service Health Checks

### Automatic Health Checks

Integration tests automatically check if services are available:

1. **Pytest Fixtures** (in `tests/conftest.py`):
   - `datacontract_service` - Ensures DataContract CLI service is healthy
   - `dq_service` - Ensures DQ service is healthy
   - `compliance_service` - Ensures Compliance service is healthy
   - `semantic_service` - Ensures Semantic service is healthy
   - `all_services` - Ensures all services are healthy

2. **Helper Function**:
   - `check_service_health(service_url, service_name)` - Can be used in Django TestCase setUp methods

### Manual Health Checks

Check service health manually:

```bash
# Check DataContract service
curl http://localhost:8080/health

# Check DQ service
curl http://localhost:8083/health

# Check Compliance service
curl http://localhost:8082/health

# Check Semantic service
curl http://localhost:8081/health
```

## Test Markers

Tests are marked with pytest markers:

- `@pytest.mark.integration` - Integration tests that require services
- `@pytest.mark.unit` - Unit tests (no services required)
- `@pytest.mark.e2e` - End-to-end tests

## CI/CD

The CI workflow (`.github/workflows/ci.yml`) automatically:
1. Builds service Docker images
2. Starts all services
3. Waits for health checks
4. Runs unit tests
5. Runs integration tests
6. Cleans up services

## Troubleshooting

### Services Not Starting

If services fail to start:
```bash
# Check service logs
docker-compose logs datacontract-service
docker-compose logs dq-service
docker-compose logs compliance-service
docker-compose logs semantic-service

# Check service status
docker-compose ps
```

### Tests Skipping

If tests are being skipped, check:
1. Services are running: `docker-compose ps`
2. Services are healthy: `curl http://localhost:8080/health`
3. Environment variables are set correctly

### Port Conflicts

If you get port conflicts, update ports in:
- `docker-compose.yml`
- Environment variables in tests
- Service URLs in `hub/settings.py`

## Environment Variables

Services can be configured via environment variables:

- `DATACONTRACT_SERVICE_URL` - Default: `http://localhost:8080`
- `DQ_SERVICE_URL` - Default: `http://localhost:8083`
- `COMPLIANCE_SERVICE_URL` - Default: `http://localhost:8082`
- `SEMANTIC_SERVICE_URL` - Default: `http://localhost:8081`

## Makefile Commands

- `make docker-up` - Start infrastructure only (postgres, redis, minio, fuseki)
- `make docker-up-services` - Start infrastructure + microservices
- `make docker-up-all` - Start everything including API and worker
- `make wait-for-services` - Wait for all services to be healthy
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests (requires services)
- `make test-integration-with-services` - Start services and run integration tests
- `make verify-deps` - Verify all dependencies are running

