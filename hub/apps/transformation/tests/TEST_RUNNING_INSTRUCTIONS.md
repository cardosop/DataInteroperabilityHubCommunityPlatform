# Quality Integration Tests - Running Instructions

## Overview

The quality integration tests are split into two files:

1. **test_quality_integration.py** - Unit tests with mocks (for fast execution, testing logic)
2. **test_quality_integration_real_services.py** - Integration tests with real services (no mocks/stubs)

## Running Tests

### Option 1: Run in Docker (Recommended)

Since all services run in Docker Compose, the best way to run tests is inside the Docker container:

```bash
# Start test services
docker-compose -f docker-compose.test.yml up -d

# Wait for services to be healthy
sleep 30

# Run tests inside API service container
docker-compose -f docker-compose.test.yml exec api-service-test bash -c \
  "cd /app && source venv/bin/activate && \
   python -m pytest hub/apps/transformation/tests/test_quality_integration_real_services.py -v --tb=short"

# Or use the provided script
./scripts/run_quality_integration_tests.sh
```

### Option 2: Run Unit Tests Locally (with mocks)

Unit tests that don't require services can be run locally:

```bash
# Set environment variables for database
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5434  # Test database port
export POSTGRES_USER=hub_test
export POSTGRES_PASSWORD=hub_test
export POSTGRES_DB=hub_test

# Run unit tests
source venv/bin/activate
python -m pytest hub/apps/transformation/tests/test_quality_integration.py -v --tb=short
```

### Option 3: Run All Tests with Make

```bash
# Run integration tests (requires services)
make test-integration-with-services

# Or run specific test file
make test-integration-with-services TEST_PATH="hub/apps/transformation/tests/test_quality_integration_real_services.py"
```

## Test Categories

### Unit Tests (test_quality_integration.py)
- Test quality metrics comparison logic
- Test file format detection
- Test status comparison
- Test check comparison
- Test execution log storage
- **Note**: These use mocks for DQ service and storage for fast execution

### Integration Tests (test_quality_integration_real_services.py)
- Test input quality check with real DQ service
- Test output quality check with real DQ service
- Test full workflow with real services
- **Note**: These use real services, no mocks/stubs
- Tests will be skipped if services are not available

## Service Requirements

For integration tests to run, the following services must be available:

1. **DQ Service** - Must be running and healthy
   - Default URL: `http://localhost:8084` (test port) or `http://dq-service-test:8083` (in Docker)
   - Check health: `curl http://localhost:8084/health`

2. **Storage Service (MinIO)** - Must be running
   - Default URL: `http://localhost:9010` (test port) or `http://minio-test:9000` (in Docker)
   - Check health: `curl http://localhost:9010/minio/health/live`

3. **PostgreSQL** - Must be running
   - Test database port: `5434` (or `5432` in Docker)
   - Database: `hub_test`

4. **Redis** - Must be running (for circuit breaker)
   - Test port: `6380` (or `6379` in Docker)

## Expected Test Results

### Unit Tests
- All tests should pass (they use mocks, so no service dependencies)

### Integration Tests
- Tests will be skipped if services are not available (this is expected)
- If services are available, tests should pass
- Tests validate:
  - Real DQ service responses
  - Real storage operations
  - End-to-end workflow

## Troubleshooting

### Tests Fail with "Service not available"
- Ensure test services are running: `docker-compose -f docker-compose.test.yml ps`
- Check service health: `docker-compose -f docker-compose.test.yml exec dq-service-test curl http://localhost:8083/health`
- Wait for services to be healthy before running tests

### Database Connection Errors
- Ensure PostgreSQL is running on the correct port
- Check environment variables: `POSTGRES_HOST`, `POSTGRES_PORT`, etc.
- For Docker: Use service names (e.g., `postgres-test`) not `localhost`

### Storage Errors
- Ensure MinIO is running and accessible
- Check AWS credentials are set correctly for test environment
- Verify bucket exists or can be created

## Test Coverage

The tests cover:
- ✅ Input asset quality check
- ✅ Output asset quality check
- ✅ Quality metrics comparison
- ✅ Execution log storage
- ✅ Quality degradation alert publishing
- ✅ File format detection
- ✅ Status comparison
- ✅ Check comparison
- ✅ Error handling (service unavailable, missing datasets, etc.)

