# Test Execution Instructions

Complete guide for running tests in the Data Interoperability Hub project.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Running Unit Tests](#running-unit-tests)
4. [Running Integration Tests](#running-integration-tests)
5. [Running E2E Tests](#running-e2e-tests)
6. [Running Performance Tests](#running-performance-tests)
7. [Running Specific Test Categories](#running-specific-test-categories)
8. [Test Markers and Filtering](#test-markers-and-filtering)
9. [CI/CD Test Execution](#cicd-test-execution)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The test suite is organized into three main categories:

- **Unit Tests**: Fast, isolated tests for individual components (`tests/unit/`)
- **Integration Tests**: Tests for service interactions and API endpoints (`tests/integration/`)
- **E2E Tests**: End-to-end tests for complete user journeys (`tests/e2e/`)
- **Performance Tests**: Tests for performance targets (`tests/performance/`)

---

## Prerequisites

### Environment Setup

1. **Python Environment**: Python 3.12+ with virtual environment activated
2. **Django Settings**: `DJANGO_SETTINGS_MODULE=hub.settings` must be set
3. **Database**: PostgreSQL database accessible (test database created automatically)
4. **Redis**: Redis server running (for rate limiting and job queue tests)
5. **Services**: Required microservices running (DQ, Compliance, Semantic) or mocked

### Required Packages

All test dependencies are included in `requirements.txt`:
- `pytest>=7.0.0`
- `pytest-django>=4.5.0`
- `pytest-cov>=4.0.0`
- `factory-boy>=3.3.0`
- `faker>=19.0.0`

---

## Running Unit Tests

### Run All Unit Tests

```bash
pytest tests/unit/ -v
```

### Run Specific Unit Test File

```bash
pytest tests/unit/tenant_config/test_models.py -v
```

### Run Specific Test Class or Method

```bash
# Run specific test class
pytest tests/unit/tenant_config/test_models.py::TenantConfigModelTest -v

# Run specific test method
pytest tests/unit/tenant_config/test_models.py::TenantConfigModelTest::test_tenant_config_creation -v
```

### Run with Coverage

```bash
pytest tests/unit/ --cov=hub --cov-report=html --cov-report=term
```

**Expected Execution Time**: <5 minutes for all unit tests

---

## Running Integration Tests

### Run All Integration Tests

```bash
pytest tests/integration/ -v
```

### Run Specific Integration Test File

```bash
pytest tests/integration/test_tenant_config_api.py -v
```

### Run with Service Health Checks

Integration tests automatically check service health before running. If services are unavailable, tests are skipped.

**Expected Execution Time**: <15 minutes for all integration tests

---

## Running E2E Tests

### Run All E2E Tests

```bash
pytest tests/e2e/ -v
```

**Note**: E2E tests require all services to be running. See `TEST_ENVIRONMENT_SETUP.md` for details.

### Run E2E Tests by Batch

E2E tests are organized into 5 batches for parallel execution:

```bash
# Batch 1: Core API, Contracts, Assets
pytest tests/e2e/ -m e2e_batch1 -v

# Batch 2: Worker Service, Jobs, DQ, Compliance
pytest tests/e2e/ -m e2e_batch2 -v

# Batch 3: Email, Notifications, Rate Limiting
pytest tests/e2e/ -m e2e_batch3 -v

# Batch 4: Tenant Config, Personas, CLI
pytest tests/e2e/ -m e2e_batch4 -v

# Batch 5: Marketplace, Semantic, Monitoring, Edge Cases
pytest tests/e2e/ -m e2e_batch5 -v
```

### Run Multiple Batches

```bash
pytest tests/e2e/ -m "e2e_batch1 or e2e_batch2" -v
```

### Using Batch Script

```bash
# Run batch 1
./scripts/run_e2e_tests_batch.sh 1

# Run all batches
./scripts/run_e2e_tests_batch.sh all
```

**Expected Execution Time**: <60 minutes for all E2E tests (when run sequentially)

---

## Running Performance Tests

### Run All Performance Tests

```bash
pytest tests/performance/ -v
```

### Run Specific Performance Test

```bash
pytest tests/performance/test_performance.py::RateLimitPerformanceTest -v
```

**Note**: Performance tests measure latency, throughput, and overhead. Thresholds are adjusted for test environments.

**Expected Execution Time**: <30 minutes for all performance tests

---

## Running Specific Test Categories

### Run Tests by Phase

```bash
# Phase 1: Tenant Configuration
pytest tests/unit/tenant_config/ tests/integration/test_tenant_config_api.py tests/e2e/test_tenant_config_e2e.py -v

# Phase 2: Worker Service
pytest tests/unit/worker/ tests/integration/test_worker_service.py tests/e2e/test_worker_service_e2e.py -v

# Phase 3: Email Service
pytest tests/unit/notifications/ tests/integration/test_email_integration.py tests/e2e/test_email_service_e2e.py -v

# Phase 4: Rate Limiting
pytest tests/unit/rate_limiting/ tests/integration/test_rate_limiting_integration.py tests/e2e/test_rate_limiting_e2e.py -v

# Phase 5: CLI Tool
pytest tests/unit/cli/ tests/integration/test_cli_integration.py tests/e2e/test_cli_e2e.py -v

# Phase 6: Monitoring
pytest tests/unit/monitoring/ tests/integration/test_monitoring_integration.py tests/e2e/test_monitoring_e2e.py -v

# Phase 7: Enhanced Contracts
pytest tests/unit/contracts/ tests/unit/semantic/ tests/integration/test_normalization_rdf_flow.py -v
```

### Run Tests by Persona

```bash
# TENANT_ADMIN persona tests
pytest tests/e2e/test_persona_tenant_admin.py -v

# DATA_PROVIDER persona tests
pytest tests/e2e/test_persona_data_provider.py -v

# DATA_CONSUMER persona tests
pytest tests/e2e/test_persona_data_consumer.py -v

# AUDITOR persona tests
pytest tests/e2e/test_persona_auditor.py -v

# Platform Admin persona tests
pytest tests/e2e/test_persona_platform_admin.py -v
```

### Run Edge Case Tests

```bash
# Normalization edge cases
pytest tests/unit/contracts/test_normalization_edge_cases.py -v

# RDF mapping edge cases
pytest tests/unit/semantic/test_rdf_mapping_edge_cases.py -v

# API edge cases
pytest tests/integration/test_api_edge_cases.py -v

# Worker service edge cases
pytest tests/unit/worker/test_worker_edge_cases.py -v

# Email service edge cases
pytest tests/unit/notifications/test_email_edge_cases.py -v

# Rate limiting edge cases
pytest tests/unit/rate_limiting/test_rate_limiting_edge_cases.py -v
```

---

## Test Markers and Filtering

### Available Markers

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - E2E tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.e2e_batch1` through `@pytest.mark.e2e_batch5` - E2E test batches
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.skip` - Skipped tests

### Run Tests by Marker

```bash
# Run only unit tests
pytest -m unit -v

# Run only integration tests
pytest -m integration -v

# Run only E2E tests
pytest -m e2e -v

# Run only performance tests
pytest -m performance -v

# Exclude slow tests
pytest -m "not slow" -v
```

### Run Tests Matching Pattern

```bash
# Run tests matching pattern in name
pytest -k "tenant_config" -v

# Run tests matching multiple patterns
pytest -k "tenant_config or rate_limit" -v

# Exclude tests matching pattern
pytest -k "not slow" -v
```

---

## Running Tests in Parallel

### Using pytest-xdist

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest tests/unit/ -n 4 -v

# Auto-detect number of CPUs
pytest tests/unit/ -n auto -v
```

**Note**: Parallel execution works best for unit tests. E2E tests should run sequentially or in batches.

---

## Running Tests with Coverage

### Generate Coverage Report

```bash
# Terminal report
pytest --cov=hub --cov-report=term -v

# HTML report
pytest --cov=hub --cov-report=html -v
# Open htmlcov/index.html in browser

# XML report (for CI/CD)
pytest --cov=hub --cov-report=xml -v
```

### Coverage Targets

- **Unit Tests**: 100% coverage target
- **Integration Tests**: 90%+ coverage target
- **E2E Tests**: 100% coverage for user journeys
- **Edge Cases**: 90%+ coverage target

---

## Debugging Failing Tests

### Verbose Output

```bash
# Show all print statements and logs
pytest -v -s tests/unit/test_file.py

# Show local variables on failure
pytest -v --tb=long tests/unit/test_file.py

# Show only first failure
pytest -v -x tests/unit/test_file.py

# Show last 10 lines of traceback
pytest -v --tb=short tests/unit/test_file.py
```

### Debug with PDB

```bash
# Drop into debugger on failure
pytest --pdb tests/unit/test_file.py

# Drop into debugger on first failure
pytest -x --pdb tests/unit/test_file.py
```

### Run Last Failed Tests

```bash
# Run only tests that failed in last run
pytest --lf -v

# Run failed tests first, then rest
pytest --ff -v
```

---

## CI/CD Test Execution

### GitHub Actions

Tests are automatically executed in CI/CD pipelines:

1. **Unit Tests**: Run on every commit
2. **Integration Tests**: Run on every PR
3. **E2E Tests**: Run on main branch and before release
4. **Performance Tests**: Run weekly or on-demand

### Local CI Simulation

```bash
# Simulate CI test execution
pytest tests/unit/ tests/integration/ --cov=hub --cov-report=xml -v

# Run with same settings as CI
DJANGO_SETTINGS_MODULE=hub.settings pytest tests/unit/ -v
```

---

## Troubleshooting

### Common Issues

#### Issue: `django.core.exceptions.ImproperlyConfigured: Requested setting INSTALLED_APPS`

**Solution**: Set `DJANGO_SETTINGS_MODULE` environment variable:
```bash
export DJANGO_SETTINGS_MODULE=hub.settings
# Or inline:
DJANGO_SETTINGS_MODULE=hub.settings pytest tests/unit/ -v
```

#### Issue: `django.db.utils.OperationalError: connection to server failed`

**Solution**: Ensure PostgreSQL is running and accessible:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection
psql -U postgres -d hub_test
```

#### Issue: `redis.exceptions.ConnectionError`

**Solution**: Ensure Redis is running:
```bash
# Check Redis status
redis-cli ping
# Should return: PONG
```

#### Issue: Tests failing due to service unavailability

**Solution**: Tests automatically skip if services are unavailable. To run without services:
```bash
# Skip integration/E2E tests that require services
pytest tests/unit/ -v
```

#### Issue: `ModuleNotFoundError: No module named 'hub'`

**Solution**: Ensure you're in the project root and virtual environment is activated:
```bash
cd /path/to/DataInteroperabilityHub
source .venv/bin/activate
export PYTHONPATH=$PWD:$PYTHONPATH
```

#### Issue: Test database not created

**Solution**: Django automatically creates test database. If issues occur:
```bash
# Force test database creation
pytest tests/unit/ --create-db -v
```

#### Issue: Flaky tests (intermittent failures)

**Solution**: 
1. Check for race conditions or timing issues
2. Use `pytest --flaky` to rerun flaky tests
3. Add appropriate delays or synchronization
4. Review test isolation

### Getting Help

- Check test logs for detailed error messages
- Review `TEST_ENVIRONMENT_SETUP.md` for environment issues
- Check `TEST_MAINTENANCE.md` for test maintenance guidelines
- Review test code comments for test-specific requirements

---

## Best Practices

1. **Run tests frequently**: Run unit tests on every code change
2. **Fix failures immediately**: Don't let test failures accumulate
3. **Keep tests fast**: Unit tests should complete in <5 minutes
4. **Use appropriate test types**: Use unit tests for logic, integration for APIs, E2E for journeys
5. **Maintain test isolation**: Each test should be independent
6. **Clean up test data**: Tests should clean up after themselves
7. **Use factories**: Use Factory Boy for test data creation
8. **Follow naming conventions**: Test files and methods should be descriptive

---

## Quick Reference

```bash
# Run all tests
pytest -v

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest --cov=hub --cov-report=term -v

# Run specific test file
pytest tests/unit/tenant_config/test_models.py -v

# Run specific test
pytest tests/unit/tenant_config/test_models.py::TestClass::test_method -v

# Run E2E batch 1
pytest tests/e2e/ -m e2e_batch1 -v

# Run with verbose output and show print statements
pytest -v -s tests/unit/test_file.py

# Run last failed tests
pytest --lf -v

# Run in parallel (4 workers)
pytest tests/unit/ -n 4 -v
```

---

**Last Updated**: 2025-12-04  
**Maintainer**: Engineering Team

