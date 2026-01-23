# Marketplace Integration Comprehensive Validation - Test Execution Guide

## Overview

This guide provides instructions for running and troubleshooting the comprehensive validation test suite for task 10.1.36.

## Test File

**Location**: `hub/apps/integrations/tests/test_marketplace_integration_service_comprehensive_validation.py`
**Size**: ~3,000 lines
**Test Classes**: 15 comprehensive test classes
**Test Methods**: 100+ test methods

## Prerequisites

1. **Docker Compose Services Running**:
   ```bash
   docker compose ps
   # Ensure api-service, postgres, redis-cache are running
   ```

2. **Database Migrations Applied**:
   ```bash
   docker compose exec api-service python hub/manage.py migrate
   ```

## Running Tests

### Option 1: Complete Test Suite (Recommended)

```bash
./scripts/run_marketplace_comprehensive_tests.sh
```

This script:
- Runs all 15 test classes sequentially
- Captures output to `/tmp/marketplace_test_results_*/`
- Provides summary of passed/failed tests
- Timeout: 10 minutes per test class

### Option 2: Individual Test Class

```bash
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.ConnectionManagementTest \
   --verbosity=2 --keepdb --no-input"
```

### Option 3: Single Test Method

```bash
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.ConnectionManagementTest.test_connection_creation \
   --verbosity=2 --keepdb --no-input"
```

### Option 4: Background Execution with Monitoring

```bash
./scripts/run_marketplace_tests_background.sh
# Monitor: tail -f /tmp/marketplace_test_results_*/full_output.log
```

## Expected Timeline

### First Run (with migrations)
- **Duration**: 10-15 minutes per test class
- **Reason**: TransactionTestCase runs all migrations
- **Output**: Extensive migration logs followed by test results

### Subsequent Runs (with --keepdb)
- **Duration**: 2-5 minutes per test class
- **Reason**: Database already exists, only test execution
- **Output**: Test results only

## Test Classes

1. `ConnectionManagementTest` - Connection CRUD, authentication, encryption
2. `SyncJobTest` - Push/pull/bidirectional sync, status tracking
3. `MappingManagementTest` - Mapping CRUD, queries, metadata
4. `ConnectorTest` - All 15 connector types
5. `MetadataMappingTest` - Hub ↔ Marketplace mapping
6. `MarketplaceIntegrationAPITest` - API endpoints, validation
7. `MarketplaceIntegrationEventSystemTest` - Event publishing
8. `MarketplaceIntegrationPerformanceTest` - Performance testing
9. `MarketplaceIntegrationSecurityTest` - Security testing
10. `MarketplaceIntegrationUseCasesTest` - Use cases
11. `MarketplaceIntegrationUserJourneysTest` - User journeys
12. `MarketplaceIntegrationDatabaseStateTest` - Database state
13. `MarketplaceIntegrationMultiTenancyTest` - Multi-tenancy
14. `MarketplaceIntegrationErrorHandlingTest` - Error handling
15. `MarketplaceIntegrationODPSTest` - ODPS integration

## Monitoring Test Execution

### Check Test Progress

```bash
# Check if tests are running
ps aux | grep "marketplace.*test"

# Monitor test output
tail -f /tmp/marketplace_test_results_*/full_output.log

# Check for failures
grep -E "FAIL|ERROR|AssertionError" /tmp/marketplace_test_results_*/full_output.log
```

### Expected Output Format

```
System check identified no issues (0 silenced).
...
test_connection_creation (hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.ConnectionManagementTest) ... ok
test_connection_update (hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.ConnectionManagementTest) ... ok
...
----------------------------------------------------------------------
Ran 10 tests in 45.123s

OK
```

## Troubleshooting

### Issue 1: Tests Hang During Migrations

**Symptom**: Tests appear to hang, only showing migration logs
**Cause**: TransactionTestCase runs all migrations (expected behavior)
**Solution**: Wait 10-15 minutes for first run, subsequent runs are faster

### Issue 2: Database Connection Timeout

**Symptom**: `OperationalError: connection to server at "postgres" failed: timeout expired`
**Cause**: Database connection pool exhausted or database starting up
**Solution**:
- Tests include retry logic with exponential backoff
- Ensure database is healthy: `docker compose ps postgres`
- Wait and retry

### Issue 3: Import Errors

**Symptom**: `ImportError: No module named 'hub'`
**Cause**: Running tests from wrong directory
**Solution**: Always run from `/app` directory inside Docker container

### Issue 4: Test Connector Not Found

**Symptom**: `ValueError: No connector registered for marketplace type`
**Cause**: Test connectors not registered
**Solution**: Base class `setUp()` registers test connectors automatically

### Issue 5: API Endpoint Not Found

**Symptom**: `404 Not Found` for API endpoints
**Cause**: URL path incorrect
**Solution**: Verify paths use `/api/v1/integrations/marketplace/...`

## Fixes Applied

### 1. Database Connection Retry Logic ✅
- Added exponential backoff retry in `setUp()`
- Handles connection timeouts gracefully
- Max 10 retries with exponential backoff

### 2. Database Connection Cleanup ✅
- Added `tearDown()` to close connections
- Prevents connection pool exhaustion

### 3. Fixture Teardown Override ✅
- Added `_fixture_teardown()` to skip database flush
- Prevents foreign key constraint issues

### 4. Test Connector Registration ✅
- Base class registers test connectors automatically
- Test connectors are minimal implementations (not mocks)
- Proper cleanup in `tearDown()`

### 5. Removed Unused Imports ✅
- Removed `unittest.mock.patch` (not used, per requirements)
- Removed `Decimal` (not used)

## Next Steps

1. **Wait for test completion** (10-15 minutes for first run)
2. **Review test results** from output logs
3. **Fix any failures** found
4. **Re-run failed tests** to verify fixes
5. **Update tasks.md** with final status

## Files

- **Test File**: `hub/apps/integrations/tests/test_marketplace_integration_service_comprehensive_validation.py`
- **Test Runner**: `scripts/run_marketplace_comprehensive_tests.sh`
- **Background Runner**: `scripts/run_marketplace_tests_background.sh`
- **Status Doc**: `hub/apps/integrations/tests/MARKETPLACE_COMPREHENSIVE_VALIDATION_STATUS.md`
