# Testing Guide

Complete guide for testing the Data Interoperability Hub.

## Overview

The platform uses a comprehensive testing strategy with multiple test types:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user journeys
- **Performance Tests**: Test system performance under load
- **Contract Tests**: Test API contracts

## Test Structure

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── e2e/              # End-to-end tests
├── performance/      # Performance tests
└── fixtures/         # Test fixtures
```

## Running Tests

### Run All Tests

```bash
# Using pytest
pytest

# Using Django test runner
python manage.py test

# Using Docker
docker compose exec api-service python manage.py test
```

### Run Specific Test Types

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only
pytest tests/e2e/

# Performance tests
pytest tests/performance/
```

### Run Specific Test Files

```bash
pytest tests/unit/test_contracts.py
pytest tests/integration/test_contract_workflow.py
```

### Run with Coverage

```bash
pytest --cov=hub --cov-report=html
```

## Test Configuration

### Environment Variables

```bash
# Test database
TEST_DATABASE_URL=postgresql://hub:hub@localhost:5432/hub_test

# Test settings
DJANGO_SETTINGS_MODULE=hub.settings_test
```

### Pytest Configuration

See `pytest.ini` for pytest configuration:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = hub.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
```

## Unit Tests

Unit tests test individual components in isolation.

### Example Unit Test

```python
import pytest
from hub.apps.contracts.services import ContractService

@pytest.mark.django_db
def test_create_contract():
    service = ContractService()
    contract = service.create_contract(
        tenant_id=tenant.id,
        user_id=user.id,
        contract_data={...}
    )
    assert contract.id is not None
    assert contract.status == 'DRAFT'
```

### Running Unit Tests

```bash
pytest tests/unit/ -v
```

## Integration Tests

Integration tests test component interactions.

### Example Integration Test

```python
import pytest
from django.test import Client

@pytest.mark.django_db
def test_contract_creation_workflow():
    client = Client()
    response = client.post('/api/v1/contracts/', {
        'name': 'Test Contract',
        'spec': {...}
    })
    assert response.status_code == 201
    assert response.json()['id'] is not None
```

### Running Integration Tests

```bash
pytest tests/integration/ -v
```

## End-to-End Tests

E2E tests test complete user journeys.

### Connector E2E Testing

For comprehensive documentation on end-to-end testing of marketplace connectors, see:

**[Connector End-to-End Testing Guide](testing/CONNECTOR_E2E_TESTING.md)**

This guide covers:
- Complete workflow testing (connection → discovery → asset creation → verification)
- Real connections only (no mocks/stubs)
- Detailed test scenarios for dados.gov.br and Snowflake connectors
- Troubleshooting guide for common issues
- Best practices for engineering-grade testing

### Example E2E Test

```python
import pytest
from tests.e2e.helpers import create_test_client, create_test_tenant

@pytest.mark.e2e
def test_contract_to_asset_journey():
    client = create_test_client()
    tenant = create_test_tenant()

    # Create contract
    contract = client.contracts.create({...})

    # Create asset
    asset = client.assets.create({...})

    # Attach contract to asset
    client.assets.attach_contract(asset.id, contract.id)

    # Activate asset
    client.assets.activate(asset.id)

    assert asset.status == 'ACTIVE'
```

### Running E2E Tests

```bash
# Requires Docker Compose services running
docker compose up -d
pytest tests/e2e/ -v

# Run connector E2E tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py \
  -v \
  -m integration

# Run connector E2E tests via management command
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source both \
  --limit 5 \
  --wait \
  --verify-assets
```

## Performance Tests

Performance tests test system performance under load.

### Running Performance Tests

```bash
# Load test
pytest tests/performance/test_load.py

# Stress test
pytest tests/performance/test_stress.py

# Endurance test
pytest tests/performance/test_endurance.py
```

### Performance Baselines

See [Performance Testing Guide](PERFORMANCE_TESTING_COMPREHENSIVE.md) for performance baselines and targets.

## Test Fixtures

Test fixtures are available in `tests/fixtures/`:

- `contracts.json` - Sample contracts
- `assets.json` - Sample assets
- `datasets.json` - Sample datasets

### Using Fixtures

```python
import json
from pathlib import Path

@pytest.fixture
def sample_contract():
    fixture_path = Path('tests/fixtures/contracts.json')
    with open(fixture_path) as f:
        return json.load(f)[0]
```

## Test Data Management

### Creating Test Data

```python
from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import Tenant

@pytest.fixture
def test_tenant():
    return Tenant.objects.create(name='Test Tenant')

@pytest.fixture
def test_contract(test_tenant):
    return Contract.objects.create(
        tenant=test_tenant,
        name='Test Contract',
        ...
    )
```

### Cleaning Up Test Data

Tests automatically clean up using Django's test database:

```python
@pytest.mark.django_db
def test_something():
    # Test database is automatically cleaned after test
    pass
```

## Mocking External Services

### Mocking HTTP Requests

```python
from unittest.mock import patch

@patch('requests.post')
def test_external_service_call(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {'result': 'success'}

    # Test code that calls external service
    result = call_external_service()
    assert result == {'result': 'success'}
```

## Test Coverage

### Coverage Targets

- **Unit Tests**: 95%+ coverage
- **Integration Tests**: 80%+ coverage
- **E2E Tests**: Critical paths covered

### Generating Coverage Report

```bash
pytest --cov=hub --cov-report=html --cov-report=term
```

Coverage report available at `htmlcov/index.html`.

## Continuous Integration

Tests run automatically in CI/CD:

- **Unit Tests**: Run on every commit
- **Integration Tests**: Run on pull requests
- **E2E Tests**: Run on merge to main
- **Performance Tests**: Run nightly

## Test Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Ensure PostgreSQL is running
   docker compose up -d postgres
   ```

2. **Test Isolation Issues**
   ```python
   # Use @pytest.mark.django_db for database access
   @pytest.mark.django_db
   def test_something():
       pass
   ```

3. **Fixture Not Found**
   ```python
   # Ensure fixtures are in conftest.py or imported
   ```

### Debugging Tests

```bash
# Run with verbose output
pytest -v -s

# Run with debugger
pytest --pdb

# Run specific test with output
pytest tests/unit/test_contracts.py::test_create_contract -v -s
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clear Test Names**: Use descriptive test names
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Test Edge Cases**: Test error conditions
5. **Keep Tests Fast**: Unit tests should be fast
6. **Use Fixtures**: Reuse test data with fixtures
7. **Mock External Services**: Don't call real external services
8. **Test Behavior**: Test what the code does, not how

## Related Documentation

- [Test Plan](TEST_PLAN.md) - Comprehensive test plan
- [Test Automation](TEST_AUTOMATION.md) - Test automation strategies
- [Performance Testing](PERFORMANCE_TESTING_COMPREHENSIVE.md) - Performance testing guide
- [API Testing Guide](API_TESTING_GUIDE.md) - API testing strategies

