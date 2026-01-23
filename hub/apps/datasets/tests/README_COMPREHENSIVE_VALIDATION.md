# Datasets Service Comprehensive Validation Tests

## Overview

This test suite provides engineering-grade validation for task 10.1.29 "Datasets Service Comprehensive Validation" covering all 6 sub-tasks:

1. **10.1.29.1**: Dataset CRUD Operations Testing
2. **10.1.29.2**: Dataset Versioning Testing
3. **10.1.29.3**: Schema Evolution Testing
4. **10.1.29.4**: Time Travel Query Testing
5. **10.1.29.5**: Dataset Rollback Testing
6. **10.1.29.6**: Datasets Service Integration with ODPS

## Test File

`test_datasets_service_comprehensive_validation.py`

## Running Tests

### Prerequisites

- Docker Compose services must be running
- All required services (PostgreSQL, Redis, MinIO, etc.) must be healthy

### Option 1: Run All Tests (Recommended)

```bash
# Run all comprehensive validation tests
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation \
   --verbosity=2 --keepdb --no-input"
```

### Option 2: Run Specific Test Class

```bash
# Run only CRUD operations tests
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetCRUDOperations \
   --verbosity=2 --keepdb --no-input"

# Run only versioning tests
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetVersioning \
   --verbosity=2 --keepdb --no-input"
```

### Option 3: Run Single Test Method

```bash
# Run a specific test
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetCRUDOperations.test_dataset_creation \
   --verbosity=2 --keepdb --no-input"
```

### Option 4: Using pytest (Faster)

```bash
docker compose exec -T api-service bash -c \
  "cd /app && pytest hub/apps/datasets/tests/test_datasets_service_comprehensive_validation.py \
   -v --tb=short --reuse-db"
```

## Test Coverage

### 10.1.29.1: Dataset CRUD Operations
- ✅ Dataset creation (with/without asset)
- ✅ Dataset retrieval
- ✅ Dataset update
- ✅ Dataset deletion
- ✅ Dataset listing with filters
- ✅ Dataset pagination
- ✅ Dataset sorting

### 10.1.29.2: Dataset Versioning
- ✅ Version creation
- ✅ Version comparison
- ✅ Version rollback
- ✅ Version history
- ✅ Version queries

### 10.1.29.3: Schema Evolution
- ✅ Schema changes detection
- ✅ Backward compatibility
- ✅ Schema migration tracking
- ✅ Schema validation
- ✅ Schema evolution tracking

### 10.1.29.4: Time Travel Queries
- ✅ Time travel queries
- ✅ Historical data access
- ✅ Point-in-time queries
- ✅ Performance testing
- ✅ Query validation

### 10.1.29.5: Dataset Rollback
- ✅ Rollback to previous version
- ✅ Data integrity verification
- ✅ Event publishing
- ✅ Compensation logic
- ✅ Rollback validation

### 10.1.29.6: Datasets-ODPS Integration
- ✅ Datasets linked to ODPS contracts
- ✅ ODPS product data in datasets
- ✅ Dataset versioning with ODPS
- ✅ ODPS schema evolution
- ✅ ODPS time travel queries

## Key Features

- **No Mocks/Stubs**: All tests use real services
- **TDD Approach**: Tests written first, implementation validated
- **Engineering-Grade**: Comprehensive coverage of edge cases
- **Best Practices**: Follows Django and coding standards
- **Root Cause Focus**: Tests validate actual behavior

## Troubleshooting

### Tests Timeout

If tests timeout, it's likely due to database migrations. Use `--keepdb` flag to reuse the database:

```bash
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation \
   --keepdb --no-input"
```

### Import Errors

If you see `AppRegistryNotReady` errors, ensure you're running tests through Django's test framework, not directly importing the test module.

### Database Issues

If you encounter database-related errors:

1. Ensure PostgreSQL is running and healthy
2. Check database connection settings
3. Try recreating the test database: remove `--keepdb` flag

### Service Dependencies

Ensure all required services are running:
- PostgreSQL
- Redis (cache, queue, events, channels)
- MinIO (S3 storage)
- Other microservices as needed

## Notes

- Tests use `TransactionTestCase` to ensure proper database isolation
- All test data is cleaned up automatically after each test
- Tests are designed to run in parallel (each test class is independent)
