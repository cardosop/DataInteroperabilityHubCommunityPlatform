# Integration Tests

Integration tests for cross-service communication and end-to-end workflows.

## Overview

These tests verify that services can communicate correctly and that end-to-end workflows function as expected.

## Test Structure

### Service Health Tests
- Verify all services have working health endpoints
- Test service availability

### API to Microservices Tests
- Test API service communication with all microservices
- Verify service-to-service calls work correctly

### Worker Service Tests
- Test worker service communication with Redis
- Test worker service communication with database
- Test worker service job processing

### Prefect Integration Tests
- Test Prefect integration service communication with Prefect Server
- Verify workflow deployment and execution

### Service Discovery Tests
- Test DNS resolution
- Test service URL accessibility

### End-to-End Workflow Tests
- Test complete workflows across multiple services
- Verify data flow and state management

## Running Tests

### Prerequisites

1. Start all services:
```bash
docker compose up -d
```

2. Wait for services to be healthy:
```bash
./scripts/deploy_health_check.sh
```

### Run Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test class
pytest tests/integration/cross_service_test.py::TestServiceHealth -v

# Run with coverage
pytest tests/integration/ --cov=. --cov-report=html
```

### Environment Variables

Set service URLs if different from defaults:

```bash
export API_SERVICE_URL=http://localhost:8000
export DATACONTRACT_SERVICE_URL=http://localhost:8080
# ... etc
```

## Test Coverage

- ✅ Service health checks
- ✅ API to microservices communication
- ✅ Worker service communication
- ✅ Prefect integration communication
- ✅ Service discovery
- ⏳ End-to-end workflows (placeholders for actual implementation)

## Adding New Tests

1. Create test class in `tests/integration/`
2. Follow naming convention: `Test{FeatureName}`
3. Use pytest fixtures for setup/teardown
4. Document test purpose and requirements

---

**Last Updated:** 2025-01-15

