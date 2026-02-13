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

## Run Conditions and Required Services

Integration tests use real services; no mocks of application code. Some tests skip when a required service is unavailable.

| Service / condition | Required by (examples) | Skip behavior |
|---------------------|------------------------|----------------|
| **Redis** | Event bus, rate limiting, job queue, redis_streams | Tests skip with "Redis not available" or "Event bus/Redis unavailable". |
| **MinIO / S3** | File storage, asset uploads | test_asset_management_original_use_cases_comprehensive.py, test_files_service_comprehensive_validation.py skip file-upload steps when MinIO unavailable. |
| **ErasureService** | GDPR erasure workflow | test_erasure_workflow_integration.py skips when `execute_erasure` not implemented. |
| **Docker Compose** | Full stack | test_docker_compose*.py, test_traefik_routing.py skip when Compose not running. |
| **Rate limiting** | Rate-limit middleware test | test_middleware_integration.py skips when `RATE_LIMIT_ENABLED` is False. |
| **DQ / Compliance / Semantic** | Cross-service tests | Tests accept 503 when service is down; no mocks. |

**Recommendation**: Run integration tests in an environment where Redis (and optionally MinIO) are up for full coverage. See runbooks for CI and local setup.

## Test Coverage

- ✅ Service health checks (test_health_integration.py)
- ✅ API to microservices communication
- ✅ Worker service communication
- ✅ Prefect integration communication
- ✅ Service discovery
- ✅ P1 integration (Phase 3.3.1): Audit (test_audit_apis_comprehensive.py), Users (test_users_apis_comprehensive.py), Platform (test_platform_apis_integration.py); real client/DB, no mocks
- ⏳ End-to-end workflows (placeholders for actual implementation)

## Adding New Tests

1. Create test class in `tests/integration/`
2. Follow naming convention: `Test{FeatureName}`
3. Use pytest fixtures for setup/teardown
4. Document test purpose and requirements

---

**Last Updated:** 2026-02-07 (run conditions and required services added per Phase 3.3)

