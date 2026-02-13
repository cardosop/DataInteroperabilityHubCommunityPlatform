# CI Configuration for Phase 7 Tests

## Overview

This document describes the CI configuration for Phase 7 comprehensive tests (no mocks) for scheduled ingestion.

## CI Jobs Added

### 1. Phase 7 Scheduled Ingestion Tests (`test-phase7-scheduled-ingestion`)

**Location**: `.github/workflows/ci.yml`

**Purpose**: Run comprehensive Phase 7 tests for scheduled ingestion API handlers with real services.

**Services Required**:
- PostgreSQL (via GitHub Actions services)
- Redis (via GitHub Actions services)
- datacontract-service (Docker)
- dq-service (Docker)
- compliance-service (Docker)
- semantic-service (Docker)
- search-service (Docker, optional)
- minio (Docker, optional)

**Test Files**:
- `hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py`

**Environment Variables**:
- `DATABASE_URL`: postgresql://hub:hub@localhost:5432/hub
- `REDIS_URL`: redis://localhost:6379/0
- `DATACONTRACT_SERVICE_URL`: http://localhost:8080
- `DQ_SERVICE_URL`: http://localhost:8083
- `COMPLIANCE_SERVICE_URL`: http://localhost:8082
- `SEMANTIC_SERVICE_URL`: http://localhost:8081
- `AWS_S3_ENDPOINT_URL`: http://localhost:9000
- `AWS_ACCESS_KEY_ID`: minio
- `AWS_SECRET_ACCESS_KEY`: minio123

**Timeout**: 20 minutes

**Artifacts**: `phase7-test-results.xml`

### 2. Prefect Integration Tests (`test-prefect-integration`)

**Location**: `.github/workflows/ci.yml`

**Purpose**: Run Prefect full flow integration tests with real Prefect server.

**Services Required**:
- PostgreSQL (via GitHub Actions services)
- Redis (via GitHub Actions services)
- Prefect Server (Docker)

**Test Files**:
- `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py`

**Environment Variables**:
- `DATABASE_URL`: postgresql://hub:hub@localhost:5432/hub
- `REDIS_URL`: redis://localhost:6379/0
- `PREFECT_API_URL`: http://localhost:4200/api
- `PREFECT_API_KEY`: ${{ secrets.PREFECT_API_KEY }} (optional)
- `HUB_BASE_URL`: http://localhost:8000
- `HUB_WORKER_API_KEY`: ${{ secrets.HUB_WORKER_API_KEY }}

**Timeout**: 20 minutes

**Artifacts**: `prefect-integration-test-results.xml`

**Secrets Required**:
- `PREFECT_API_KEY` (optional - for authenticated Prefect server)
- `HUB_WORKER_API_KEY` (required - API key with scope `scheduled_ingestion:internal`)

### 3. Scheduled Ingestion E2E Tests

**Location**: `.github/workflows/e2e.yml`

**Purpose**: Run E2E tests for scheduled ingestion with full service stack.

**Services Required**:
- All services from main E2E workflow
- Prefect Server (Docker)
- Prefect Database (Docker)

**Test Files**:
- `tests/e2e/test_scheduled_ingestion.py`
- `tests/e2e/test_scheduled_ingestion_use_cases.py`

**Environment Variables**: Same as main E2E tests, plus:
- `PREFECT_API_URL`: http://localhost:4200/api
- `HUB_WORKER_API_KEY`: ${{ secrets.HUB_WORKER_API_KEY }}

**Timeout**: 60 minutes (inherited from E2E workflow)

**Artifacts**: `scheduled-ingestion-e2e-test-results.xml`

### 4. Playwright Scheduled Ingestion Journey Tests

**Location**: `.github/workflows/playwright-e2e.yml`

**Purpose**: Run Playwright E2E tests for scheduled ingestion journey (create, trigger, view run).

**Services Required**:
- api-service (docker-compose)
- postgres (docker-compose)
- redis-cache (docker-compose)
- redis-queue (docker-compose)
- redis-events (docker-compose)
- prefect-server (docker-compose)
- prefect-db (docker-compose)
- prefect-worker (docker-compose)

**Test Files**:
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts`

**Environment Variables**:
- `VITE_API_BASE_URL`: http://localhost:8000/api/v1
- `VITE_WS_BASE_URL`: ws://localhost:8000
- `PREFECT_API_URL`: http://localhost:4200/api
- `HUB_WORKER_API_KEY`: ${{ secrets.HUB_WORKER_API_KEY }}

**Timeout**: 60 minutes (inherited from Playwright workflow)

**Artifacts**: `playwright-scheduled-ingestion-results-{browser}`

## Secrets Configuration

### Required Secrets

Add these secrets to GitHub repository settings:

1. **HUB_WORKER_API_KEY**
   - **Description**: API key for Prefect worker to authenticate with hub internal Worker API
   - **Scope**: `scheduled_ingestion:internal`
   - **Generation**: `python hub/manage.py create_api_key --scopes scheduled_ingestion:internal`
   - **Required for**: Prefect integration tests, E2E tests, Playwright tests

2. **PREFECT_API_KEY** (optional)
   - **Description**: Prefect API key for authenticated Prefect server
   - **Required for**: Prefect integration tests (if Prefect server requires authentication)

### Setting Secrets

1. Go to GitHub repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each secret with the appropriate value

## Test Execution

### Local Execution

Run Phase 7 tests locally:

```bash
# Run all Phase 7 comprehensive tests
./scripts/run_phase7_tests.sh

# Run specific test classes
docker compose exec -T api-service bash -c "
  cd /app && python -m pytest \
    hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py::TestAPIHandlersUnitTests \
    -v --tb=short --reuse-db -m integration
"
```

### CI Execution

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Manual workflow dispatch

## Troubleshooting

### Tests Fail in CI

1. **Check service health**: Verify all required services are running and healthy
2. **Check logs**: Review service logs in CI artifacts
3. **Check secrets**: Ensure `HUB_WORKER_API_KEY` is set correctly
4. **Check timeouts**: Increase timeout if tests are slow
5. **Check flakiness**: Use explicit waits and idempotency checks

### Prefect Services Not Available

- Prefect integration tests will skip if Prefect Server is not available
- E2E tests handle Prefect unavailability gracefully
- Playwright tests will fail if Prefect is required but not available

### Service Startup Issues

- Increase health check timeout
- Check Docker resource limits
- Verify service dependencies are met
- Check network connectivity between services

## Best Practices

1. **Idempotency**: All tests use idempotency checks to avoid flakiness
2. **Explicit Waits**: Tests use explicit waits instead of fixed sleeps
3. **Real Services**: No mocks - all tests use real services
4. **Root Cause Fixes**: Failures are fixed at root cause, not with skips or retries
5. **Artifact Upload**: Test results are always uploaded for debugging

## References

- Phase 7 Test Status: `docs/PHASE7_TEST_STATUS.md`
- Test Execution Script: `scripts/run_phase7_tests.sh`
- CI Workflow: `.github/workflows/ci.yml`
- E2E Workflow: `.github/workflows/e2e.yml`
- Playwright Workflow: `.github/workflows/playwright-e2e.yml`
