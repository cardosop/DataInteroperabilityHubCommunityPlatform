# E2E Test Setup Guide

## Prerequisites

### Required Services

E2E tests require the following services to be running:

1. **PostgreSQL** (port 5432)
   - Database for test data
   - Automatically set up in CI/CD

2. **Redis** (port 6379)
   - Job queue and caching
   - Automatically set up in CI/CD

3. **DataContract Service** (port 8080)
   - Contract validation
   - Required for contract tests

4. **DQ Service** (port 8083)
   - Data quality checks
   - Required for DQ tests

5. **Compliance Service** (port 8082)
   - Compliance scanning
   - Required for compliance tests

6. **Semantic Service** (port 8081)
   - RDF/SPARQL queries
   - Required for semantic tests

7. **MinIO** (port 9000) - Optional
   - S3-compatible storage
   - Can be mocked for most tests

## Local Setup

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Verify services are healthy
docker-compose ps

# Run E2E tests
pytest tests/e2e/ -v
```

### Option 2: Manual Service Setup

```bash
# Start PostgreSQL
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_USER=hub \
  -e POSTGRES_PASSWORD=hub \
  -e POSTGRES_DB=hub \
  postgres:16-alpine

# Start Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Start microservices (build first)
docker-compose up -d datacontract-service dq-service compliance-service semantic-service

# Start MinIO (optional)
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

### Option 3: S3 Mocking (No MinIO Required)

Most tests can run without MinIO by using S3 mocking:

```bash
# Tests will automatically mock S3 operations
pytest tests/e2e/ -v
```

## Environment Variables

Set these environment variables before running tests:

```bash
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH=/home/ph/Desktop/DataInteroperabilityHub:$PYTHONPATH
export DATACONTRACT_SERVICE_URL=http://localhost:8080
export COMPLIANCE_SERVICE_URL=http://localhost:8082
export DQ_SERVICE_URL=http://localhost:8083
export SEMANTIC_SERVICE_URL=http://localhost:8081
export DATABASE_URL=postgresql://hub:hub@localhost:5432/hub
export REDIS_URL=redis://localhost:6379/0
```

## Running Tests

### All E2E Tests

```bash
pytest tests/e2e/ -v
```

### Specific Test File

```bash
pytest tests/e2e/test_contract_only_comprehensive.py -v
```

### Specific Test

```bash
pytest tests/e2e/test_contract_only_comprehensive.py::ContractOnlyFlowSuccessTests::test_complete_contract_only_journey_happy_path -v
```

### With Coverage

```bash
pytest tests/e2e/ --cov=hub --cov-report=html --cov-report=term-missing
```

### With Detailed Output

```bash
pytest tests/e2e/ -v -s --tb=long
```

## Troubleshooting

### Services Not Available

If services are not available, tests will be skipped:

```
SKIPPED [1] tests/e2e/test_data_first_comprehensive.py: Required services are not available: COMPLIANCE_SERVICE_URL (http://localhost:8082)
```

**Solution**: Start the required services or skip tests that require them.

### S3 Connection Errors

If you see S3 connection errors:

```
Could not connect to the endpoint URL: "http://minio:9000/..."
```

**Solution**: 
- Start MinIO: `docker-compose up -d minio`
- Or use S3 mocking (automatic in most tests)

### Database Errors

If you see database errors:

```
django.db.utils.OperationalError: could not connect to server
```

**Solution**:
- Start PostgreSQL: `docker-compose up -d postgres`
- Run migrations: `python hub/manage.py migrate`

### Test Timeouts

If tests are timing out:

**Solution**:
- Increase timeout in test configuration
- Check service response times
- Verify network connectivity

## CI/CD Setup

### GitHub Actions

E2E tests run automatically in CI/CD:

1. **PR Pipeline**: Fast subset of tests
2. **Main Branch**: Full test suite
3. **Manual Trigger**: Via workflow_dispatch

### Service Setup in CI

Services are automatically started in CI:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ...
  redis:
    image: redis:7-alpine
    ...

steps:
  - name: Build service images
    run: |
      docker build -t hub-datacontract:test ...
  
  - name: Start microservices
    run: |
      docker run -d --name datacontract-service ...
```

## Best Practices

1. **Use Helper Methods**: Use `E2ETestBase` helper methods for common operations
2. **Mock External Services**: Mock S3 and other external services when possible
3. **Clean Up**: Always clean up test data after tests
4. **Isolate Tests**: Ensure tests are independent and can run in any order
5. **Handle Failures**: Add retries and better error handling for transient failures

## Resources

- **Test Documentation**: `tests/e2e/README.md`
- **CI Integration**: `tests/e2e/CI_INTEGRATION.md`
- **Coverage Guide**: `tests/e2e/COVERAGE.md`
- **Test Status**: `tests/e2e/TEST_EXECUTION_STATUS.md`

