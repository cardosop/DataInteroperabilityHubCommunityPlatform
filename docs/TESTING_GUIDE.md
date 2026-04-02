# Testing Guide

> Test strategy, conventions, coverage matrix, and E2E requirements
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

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


---

# Test Strategy

## No-Mocks Principle

This project follows a **no-mocks principle** for internal services and database operations. Tests should use real implementations whenever possible to ensure tests accurately reflect production behavior.

### Core Principles

1. **Prefer Real Implementations**: Use real database, real service layer, and real API clients in tests
2. **External Boundaries Only**: Mocks/stubs are acceptable only at external process boundaries (third-party services not available in test environment)
3. **Root Cause Fixes**: Address flakiness by fixing root causes (idempotency, explicit waits, timeouts) rather than retries or skipping tests

### Classification of Mocks

#### ✅ Acceptable (External Boundary)

Mocks are acceptable for:

- **Third-party HTTP services** not available in test environment (e.g., Stripe, SendGrid, external APIs)
- **External process boundaries** (e.g., Prefect flows, external connectors from `services/prefect-integration`)
- **Middleware testing** (e.g., mocking `get_response` for Django middleware tests)

**Justification Required**: All external boundary mocks must include a comment explaining why the mock is necessary and what external service it represents.

Example:
```python
# EXTERNAL BOUNDARY: Prefect is an external orchestration service
# Mocking is acceptable as Prefect server is not available in unit test environment
@patch('prefect.deployments.run_deployment')
def test_trigger_ingestion(self, mock_run_deployment):
    ...
```

#### ❌ Must Remove (Internal Services)

Mocks MUST be removed for:

- **Hub services** (`hub.apps.*`, `hub.core.*`, `hub.services.*`)
- **Database operations** (Django ORM, model methods, querysets)
- **Internal service clients** (DQServiceClient, ComplianceServiceClient, etc.)
- **Storage clients** (S3StorageClient, FileService)
- **Workflows** (ScheduledIngestionWorkflow, etc.)

**Migration Path**: Replace mocks with:
- Real database operations (using `TransactionTestCase` or `pytest.mark.django_db(transaction=True)`)
- Real service layer calls
- Real API clients (using `APIClient` with real backend)
- Real storage clients (using MinIO in test environment)

### Migration Guidelines

#### For Database Operations

**Before (with mock):**
```python
@patch('hub.apps.contracts.models.Contract.objects.filter')
def test_get_contracts(self, mock_filter):
    mock_filter.return_value = [Mock(id=1, name="Test")]
    contracts = get_contracts()
    ...
```

**After (real DB):**
```python
def test_get_contracts(self):
    # Create real contract in database
    contract = Contract.objects.create(
        tenant=self.tenant,
        name="Test Contract",
        ...
    )
    contracts = get_contracts()
    self.assertEqual(len(contracts), 1)
    self.assertEqual(contracts[0].id, contract.id)
```

#### For Service Clients

**Before (with mock):**
```python
@patch('hub.apps.dq.service_client.DQServiceClient')
def test_execute_dq_run(self, mock_client_class):
    mock_client = MagicMock()
    mock_client.run_dq.return_value = {"status": "success"}
    mock_client_class.return_value = mock_client
    ...
```

**After (real service):**
```python
def test_execute_dq_run(self):
    # Use real DQ service client
    # Ensure DQ service is available in test environment
    dq_client = DQServiceClient()
    result = dq_client.run_dq(...)
    self.assertEqual(result["status"], "success")
```

#### For Storage Clients

**Before (with mock):**
```python
@patch('hub.apps.files.storage.S3StorageClient')
def test_save_file(self, mock_storage_class):
    mock_storage = MagicMock()
    mock_storage.save_file.return_value = "path/to/file"
    mock_storage_class.return_value = mock_storage
    ...
```

**After (real storage with MinIO):**
```python
def test_save_file(self):
    # Use real S3StorageClient with MinIO in test environment
    storage = S3StorageClient()
    # Ensure MinIO is configured in test settings
    path = storage.save_file(...)
    self.assertIsNotNone(path)
    # Verify file exists in storage
    self.assertTrue(storage.file_exists(path))
```

### Handling Flakiness

When tests are flaky, fix the root cause rather than adding retries or skipping:

#### ✅ Good: Fix Root Cause

```python
def test_concurrent_operations(self):
    # Use explicit waits and timeouts
    import time
    start_time = time.time()
    timeout = 5.0

    while not condition_met():
        if time.time() - start_time > timeout:
            self.fail("Timeout waiting for condition")
        time.sleep(0.1)

    # Verify result
    self.assertTrue(condition_met())
```

#### ❌ Bad: Retry or Skip

```python
# DON'T DO THIS
@pytest.mark.flaky(reruns=3)  # ❌
def test_flaky_operation(self):
    ...

# DON'T DO THIS
@pytest.mark.skipif(condition, reason="Flaky")  # ❌
def test_flaky_operation(self):
    ...
```

### Test Environment Setup

Ensure test environment has:

1. **Real Database**: PostgreSQL with proper migrations
2. **Real Storage**: MinIO configured for S3StorageClient tests
3. **Real Services**: DQ, Compliance, and other services available (or use test doubles that behave like real services)
4. **Real Redis**: For caching and queue operations

### Priority Apps for Migration

Migrate in this order:

1. ✅ **scheduled_ingestion** - Replace S3StorageClient and ScheduledIngestionWorkflow mocks
2. ✅ **auth** - Replace internal mocks (keep middleware mocks)
3. ✅ **jobs** - Replace service client mocks with real clients
4. ✅ **contracts** - Replace caching and DB mocks
5. ✅ **assets** - Replace semantic service mocks
6. ✅ **billing/tenants** (Phase 25) - Replace storage and service mocks

### Verification

After migration:

1. ✅ All tests pass with real implementations
2. ✅ No mocks of `hub.*` services remain
3. ✅ External boundary mocks are documented with justification
4. ✅ Flakiness is addressed at root cause
5. ✅ Test execution time is acceptable (may increase slightly)

### References

- [Django Testing Best Practices](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)

---

# API Testing Guide

Comprehensive guide for testing the Data Interoperability Hub API using various tools and methods.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Authentication](#authentication)
4. [Testing Tools](#testing-tools)
5. [Test Scenarios](#test-scenarios)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This guide provides comprehensive instructions for testing the Data Interoperability Hub API. The API follows RESTful principles and uses OpenAPI 3.0 specification for documentation.

### API Base URLs

- **Production**: `https://api.datahub.example.com/api/v1`
- **Staging**: `https://staging-api.datahub.example.com/api/v1`
- **Local Development**: `http://localhost:8000/api/v1`

### API Versioning

The API uses URL-based versioning. Current version: **v1**

---

## Getting Started

### Prerequisites

- API access credentials (email/password or API key)
- HTTP client tool (curl, Postman, Insomnia, etc.)
- Understanding of REST API principles
- Basic knowledge of JSON

### Quick Start

1. **Get Authentication Token**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "your-password"}'
   ```

2. **Use Token in Requests**:
   ```bash
   curl -X GET http://localhost:8000/api/v1/contracts/ \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

---

## Authentication

### JWT Bearer Token Authentication

**Step 1: Login**

```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Step 2: Use Token**

Include the token in the `Authorization` header for all subsequent requests:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Step 3: Refresh Token (when access token expires)**

```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### API Key Authentication

For service-to-service authentication, use API keys:

```bash
Authorization: ApiKey your-api-key-here
```

---

## Testing Tools

### 1. Swagger UI (Interactive Documentation)

**URL**: `http://localhost:8000/api-docs/`

Swagger UI provides an interactive interface to test all API endpoints directly from your browser.

**Features:**
- Try out endpoints with real requests
- See request/response examples
- View schema definitions
- Test authentication

**Usage:**
1. Navigate to `/api-docs/` in your browser
2. Click "Authorize" button to set authentication token
3. Expand any endpoint to see details
4. Click "Try it out" to test the endpoint
5. Fill in parameters and click "Execute"

### 2. Postman

**Import Collection:**

Generate Postman collection from OpenAPI spec:

```bash
# From running API server
python scripts/generate-postman-collection.py \
  --spec-url http://localhost:8000/api-docs/openapi.json \
  --base-url http://localhost:8000 \
  --output postman_collection.json

# From OpenAPI file
python scripts/generate-postman-collection.py \
  --spec-file api/openapi-hub-v1.yaml \
  --base-url http://localhost:8000 \
  --output postman_collection.json
```

**Import into Postman:**
1. Open Postman
2. Click "Import" button
3. Select `postman_collection.json`
4. Collection will be imported with all endpoints organized by tags

**Set Up Environment Variables:**
1. Create new environment in Postman
2. Add variables:
   - `base_url`: `http://localhost:8000`
   - `api_version`: `v1`
   - `access_token`: (will be set automatically after login)
   - `refresh_token`: (will be set automatically after login)

**Use Authentication:**
1. Run "Authentication > Login" request
2. Token will be automatically saved to `access_token` variable
3. All other requests will use this token

### 3. cURL

**Basic cURL Examples:**

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'

# Get contracts (with token)
curl -X GET http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Create contract
curl -X POST http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\"}",
    "original_format": "JSON"
  }'
```

### 4. Python Requests

**Example Script:**

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Login
response = requests.post(
    f"{BASE_URL}/auth/login/",
    json={"email": "user@example.com", "password": "your-password"}
)
tokens = response.json()
access_token = tokens["access_token"]

# Get contracts
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/contracts/", headers=headers)
contracts = response.json()
print(contracts)
```

### 5. JavaScript/TypeScript (Fetch API)

**Example:**

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Login
const loginResponse = await fetch(`${BASE_URL}/auth/login/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'your-password'
  })
});
const tokens = await loginResponse.json();
const accessToken = tokens.access_token;

// Get contracts
const contractsResponse = await fetch(`${BASE_URL}/contracts/`, {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const contracts = await contractsResponse.json();
console.log(contracts);
```

---

## Test Scenarios

### 1. Authentication Tests

**Test Login:**
- ✅ Valid credentials → 200 OK with tokens
- ✅ Invalid credentials → 401 Unauthorized
- ✅ Missing email → 400 Bad Request
- ✅ Missing password → 400 Bad Request

**Test Token Refresh:**
- ✅ Valid refresh token → 200 OK with new access token
- ✅ Invalid refresh token → 401 Unauthorized
- ✅ Expired refresh token → 401 Unauthorized

**Test Token Usage:**
- ✅ Valid token → Request succeeds
- ✅ Invalid token → 401 Unauthorized
- ✅ Expired token → 401 Unauthorized
- ✅ Missing token → 401 Unauthorized

### 2. Contract Management Tests

**Create Contract:**
```bash
POST /api/v1/contracts/
Authorization: Bearer {token}
Content-Type: application/json

{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\",\"name\":\"Test Contract\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}",
  "original_format": "JSON"
}
```

**Expected Responses:**
- ✅ Valid contract → 201 Created
- ✅ Invalid JSON → 400 Bad Request
- ✅ Missing required fields → 400 Bad Request
- ✅ Duplicate contract ID → 400 Bad Request

**List Contracts:**
```bash
GET /api/v1/contracts/?page=1&page_size=20
Authorization: Bearer {token}
```

**Expected Responses:**
- ✅ Valid request → 200 OK with paginated results
- ✅ Invalid page number → 400 Bad Request
- ✅ Invalid page size → 400 Bad Request

**Get Contract:**
```bash
GET /api/v1/contracts/{contract_id}/
Authorization: Bearer {token}
```

**Expected Responses:**
- ✅ Contract exists → 200 OK
- ✅ Contract not found → 404 Not Found
- ✅ Cross-tenant access → 404 Not Found (tenant isolation)

**Update Contract:**
```bash
PATCH /api/v1/contracts/{contract_id}/
Authorization: Bearer {token}
Content-Type: application/json

{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"test-contract\",\"name\":\"Updated Contract\"}"
}
```

**Expected Responses:**
- ✅ Valid update → 200 OK
- ✅ Invalid data → 400 Bad Request
- ✅ Contract not found → 404 Not Found

### 3. Asset Management Tests

**Create Asset:**
```bash
POST /api/v1/assets/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Test Asset",
  "description": "Test asset description",
  "asset_type": "DATASET",
  "domain": "analytics"
}
```

**Expected Responses:**
- ✅ Valid asset → 201 Created
- ✅ Missing required fields → 400 Bad Request
- ✅ Invalid asset type → 400 Bad Request

### 4. Error Handling Tests

**Test Error Responses:**

All error responses follow this format:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "field_name",
          "message": "Field-specific error",
          "code": "ERROR_CODE"
        }
      ]
    }
  }
}
```

**Test Scenarios:**
- ✅ 400 Bad Request - Validation errors
- ✅ 401 Unauthorized - Authentication required
- ✅ 403 Forbidden - Insufficient permissions
- ✅ 404 Not Found - Resource not found
- ✅ 429 Too Many Requests - Rate limit exceeded
- ✅ 500 Internal Server Error - Server error

### 5. Pagination Tests

**Test Pagination:**
```bash
GET /api/v1/contracts/?page=1&page_size=10
GET /api/v1/contracts/?page=2&page_size=10
```

**Expected Response:**
```json
{
  "count": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10,
  "has_next": true,
  "has_previous": false,
  "results": [...]
}
```

**Test Scenarios:**
- ✅ First page → `has_previous: false`
- ✅ Middle page → `has_next: true, has_previous: true`
- ✅ Last page → `has_next: false`
- ✅ Invalid page → 400 Bad Request
- ✅ Page size > max → 400 Bad Request

### 6. Filtering and Sorting Tests

**Test Filtering:**
```bash
GET /api/v1/contracts/?status=ACTIVE&domain=analytics
```

**Test Sorting:**
```bash
GET /api/v1/contracts/?ordering=created_at
GET /api/v1/contracts/?ordering=-created_at
```

**Test Scenarios:**
- ✅ Single filter → Returns filtered results
- ✅ Multiple filters → Returns results matching all filters
- ✅ Invalid filter value → 400 Bad Request
- ✅ Sort ascending → Results sorted ascending
- ✅ Sort descending → Results sorted descending

### 7. Multi-Tenant Isolation Tests

**Test Tenant Isolation:**
1. Create contract as Tenant A
2. Try to access contract as Tenant B
3. Expected: 404 Not Found (tenant isolation enforced)

**Test Scenarios:**
- ✅ Tenant A cannot access Tenant B's resources
- ✅ List operations only return tenant's own resources
- ✅ Cross-tenant access returns 404

---

## Best Practices

### 1. Authentication

- **Always use HTTPS in production** - Never send tokens over unencrypted connections
- **Store tokens securely** - Don't commit tokens to version control
- **Handle token expiration** - Implement automatic token refresh
- **Use environment variables** - Store base URLs and credentials in environment variables

### 2. Error Handling

- **Check response status codes** - Always verify status codes before processing responses
- **Parse error responses** - Use structured error format for user-friendly messages
- **Log request IDs** - Include request IDs in error logs for debugging
- **Implement retry logic** - Retry transient failures (5xx errors) with exponential backoff

### 3. Testing

- **Test happy paths first** - Verify basic functionality before edge cases
- **Test error scenarios** - Verify proper error handling
- **Test edge cases** - Test boundary conditions (empty lists, null values, etc.)
- **Test authentication** - Verify authentication and authorization
- **Test tenant isolation** - Ensure multi-tenant security

### 4. Performance

- **Use pagination** - Always paginate large result sets
- **Limit page size** - Use reasonable page sizes (10-50 items)
- **Cache tokens** - Cache access tokens to reduce authentication requests
- **Batch operations** - Use batch endpoints when available

### 5. Security

- **Never log tokens** - Don't log authentication tokens or sensitive data
- **Validate input** - Always validate input before sending requests
- **Use HTTPS** - Always use HTTPS in production
- **Follow principle of least privilege** - Use tokens with minimum required permissions

---

## Troubleshooting

### Common Issues

**1. 401 Unauthorized**
- **Cause**: Missing or invalid authentication token
- **Solution**: 
  - Verify token is included in `Authorization` header
  - Check token hasn't expired (refresh if needed)
  - Verify token format: `Bearer {token}`

**2. 403 Forbidden**
- **Cause**: Insufficient permissions
- **Solution**: 
  - Verify user has required role/permissions
  - Check if resource belongs to user's tenant

**3. 404 Not Found**
- **Cause**: Resource doesn't exist or belongs to different tenant
- **Solution**: 
  - Verify resource ID is correct
  - Check if resource belongs to your tenant
  - Verify endpoint URL is correct

**4. 400 Bad Request**
- **Cause**: Invalid request data
- **Solution**: 
  - Check request body format (must be valid JSON)
  - Verify required fields are present
  - Check field types match schema
  - Review error response for specific field errors

**5. 429 Too Many Requests**
- **Cause**: Rate limit exceeded
- **Solution**: 
  - Wait for rate limit window to reset
  - Check `Retry-After` header for wait time
  - Implement exponential backoff
  - Reduce request frequency

**6. 500 Internal Server Error**
- **Cause**: Server-side error
- **Solution**: 
  - Check server logs
  - Include request ID in support ticket
  - Retry request (may be transient error)

### Debugging Tips

**1. Enable Verbose Logging:**
```bash
curl -v -X GET http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer {token}"
```

**2. Check Response Headers:**
- `X-Request-ID`: Request identifier for debugging
- `X-RateLimit-Remaining`: Remaining rate limit
- `X-RateLimit-Reset`: Rate limit reset time

**3. Use Swagger UI:**
- Test endpoints interactively
- See request/response examples
- View schema definitions

**4. Review OpenAPI Spec:**
- Check endpoint documentation
- Verify request/response schemas
- Review error response formats

---

## Additional Resources

- **OpenAPI Specification**: `/api-docs/openapi.json`
- **Swagger UI**: `/api-docs/`
- **ReDoc**: `/api-docs/redoc/`
- **API Documentation**: `docs/API_DOCUMENTATION.md`
- **API Standards**: `docs/API_STANDARDS.md`
- **Error Codes**: `docs/API_ERROR_CODES.md`

---

## Support

For API support:
- **Email**: support@datahub.example.com
- **Documentation**: https://docs.datahub.example.com
- **Issue Tracker**: https://github.com/example/datahub/issues


---

# Test Assertion Conventions

**Last Updated**: 2026-03-22
**Task**: Phase 7.1.3 — When assertIn vs assertEqual is acceptable; intentional multi-status cases
**Related**: [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md), [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md)

---

## Overview

This document defines when to use `assertEqual` vs `assertIn` (or equivalent) in tests, and documents intentional multi-status cases where multiple HTTP status codes are valid. Following these conventions prevents loose assertions that mask bugs.

---

## 1. assertEqual vs assertIn

### 1.1 Prefer assertEqual (Single Expected Outcome)

Use `assertEqual` (or `expect(x).toBe(y)`) when the API contract or behavior has **exactly one** expected outcome.

| Scenario | Assertion | Rationale |
|----------|-----------|-----------|
| Unauthenticated access to protected endpoint | `assertEqual(401)` | Auth bypass is a bug; 200 must fail |
| Validation error (invalid input) | `assertEqual(400)` | 500 indicates server bug; must fail |
| Successful creation | `assertEqual(201)` | Single success status |
| Not found | `assertEqual(404)` | Single error status |
| Forbidden (no permission) | `assertEqual(403)` | Single error status |

**Examples**:

```python
# Backend: strict — single expected
self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

```typescript
// Frontend: strict — single expected
expect(response.status()).toBe(401);
expect(response.status()).toBe(400);
```

### 1.2 When assertIn Is Acceptable

Use `assertIn` (or `expect([a,b]).toContain(x)`) **only** when the API contract or specification explicitly allows multiple valid outcomes. Each multi-status case must be documented (see Section 2).

**Rule**: If you use `assertIn`, add a one-line comment explaining why each status is valid, and reference this document or the specific section.

---

## 2. Intentional Multi-Status Cases

These are the documented cases where multiple HTTP status codes are valid. All other cases should use `assertEqual`.

### 2.1 Async / Long-Running Operations (200 vs 202)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Async job creation / trigger | 200, 202 | 200 = synchronous completion; 202 = accepted, processing async |
| Workflow trigger | 200, 202 | Same as above |

**Example**:

```python
# Async trigger: 200 = immediate; 202 = accepted for async processing
self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
```

### 2.2 Health Endpoints (200 vs 503)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Main health `/health/` | 200, 503 | 200 = healthy; 503 = unhealthy (e.g. DB/Redis down) |
| Circuit breakers `/health/circuit-breakers/` | 200, 404, 500 | 200 = healthy; 404 = endpoint not implemented; 500 = error fetching downstream |

**Example**:

```python
# Health: 200 = healthy, 503 = unhealthy (dependency down)
self.assertIn(response.status_code, [200, 503])
```

### 2.3 Auth / Existence Checks (200 vs 401 vs 403)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| API root / tenants / assets (may be public or protected) | 200, 401, 403 | Depends on endpoint configuration; 200 if public, 401/403 if protected |
| Login with empty body | 400, 401 | 400 = validation; 401 = auth rejection |

**Example**:

```python
# Endpoint may require auth or be public
self.assertIn(response.status_code, [200, 401, 403])
```

### 2.4 Validation / Business Logic (400 vs 404 vs 409)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Create with duplicate / conflict | 201, 400, 409 | 201 = created; 400 = validation; 409 = conflict |
| Update with invalid reference | 200, 400, 404 | 200 = success; 400 = validation; 404 = resource not found |
| Delete non-existent | 204, 404 | 204 = deleted; 404 = already gone |

**Example**:

```python
# Create: 201 = success, 400 = validation error
self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
```

### 2.5 Optional / External Service Integration (200 vs 404 vs 503 vs 500)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Circuit breaker / downstream health | 200, 404, 500 | 200 = healthy; 404 = not implemented; 500 = downstream error |
| DQ/Compliance run when service down | 400, 503 | 400 = validation (e.g. invalid asset); 503 = service unavailable |
| ML/ODH inference (optional service) | 200, 400, 404, 405, 503, 500 | Service may be down (503), not implemented (404), or return validation (400) |

**Note**: For ML/ODH, 500 is acceptable only when the test explicitly documents that circuit breakers or downstream failures can return 500. See [test_health_integration.py](../tests/integration/test_health_integration.py) and [test_odh_integration_comprehensive_validation.py](../hub/apps/ml/tests/test_odh_integration_comprehensive_validation.py) for existing patterns.

### 2.6 File Storage (init, download, delete)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Init upload (POST /api/v1/files/init/) | 201, 400, 500, 503 | 201 = success; 400 = validation; 503 = S3 unavailable; 500 = internal error |
| Download (file exists, ACTIVE) | 200, 404, 500, 503 | 200 = success; 404 = tenant isolation; 503 = S3 unavailable; 500 = internal |
| Download (deleted file) | 400 | can_download() = False → 400 |
| Delete | 200, 204, 404 | 200/204 = success; 404 = not found |
| Unauthorized | 401 | Single expected |

See [test_file_storage_operations_comprehensive.py](../tests/integration/test_file_storage_operations_comprehensive.py) for implementation.

---

## 3. Anti-Patterns (Do Not Use)

| Anti-Pattern | Problem | Correct Approach |
|--------------|---------|------------------|
| `assertIn(status, [200, 401])` for auth test | Masks auth bypass (200 when 401 expected) | `assertEqual(401)` |
| `assertIn(status, [400, 500])` for validation test | Masks server bug (500) | `assertEqual(400)` |
| `assertIn(status, [200, 403])` for permission test | Masks wrong behavior | Use `assertEqual` for the expected case |
| Multi-status without comment | Future readers cannot verify | Add comment: `# 200/202: async; see TEST_ASSERTION_CONVENTIONS` |
| Broad assertIn (e.g. [200, 201, 400, 404, 500, 503]) | Hides real failures | Narrow to documented valid set; fail on unexpected |

---

## 4. Adding New Multi-Status Cases

When introducing a new `assertIn` with multiple statuses:

1. Add a row to Section 2 (Intentional Multi-Status Cases) with scenario, valid statuses, and rationale.
2. Add a one-line comment at the assertion site: `# 200/202: async; see docs/TEST_ASSERTION_CONVENTIONS.md`.
3. Ensure the rationale is defensible (API contract or spec allows it).

---

## 5. References

- [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md) — Strict vs environment-dependent vs deferred
- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Service availability
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution

---

## 6. Frontend Real-API Integration Tests (Task 7.10)

### 6.1 Decision and Rationale

**Decision**: Critical frontend flows (auth, assets, contracts, marketplace) use **real API integration tests** instead of axios mocks. Tests run against a live backend (docker compose up).

**Rationale**:

- Axios mocks hide integration bugs (wrong URLs, auth headers, error handling).
- Real API tests validate end-to-end behavior: client → API → backend.
- Aligns with project rule: no mocks/stubs; fix root cause.
- E2E tests already use real backend; integration tests extend that coverage at the service/hook level.

### 6.2 How to Run

```bash
cd frontend && npm run test:integration:api
```

**Prerequisites**: Backend running (`docker compose -f docker-compose.test.yml up -d` or dev stack). E2E users: `docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`.

### 6.3 Script and Conventions

- **Script**: `test:integration:api` invokes `scripts/run-integration-api-tests.sh`, which auto-detects API port (8000/8001), sets `VITE_API_BASE_URL`, and runs `vitest --run src/integration/`.
- **Test files**: `frontend/src/integration/*.integration.test.ts`.
- **Assertions**: Use `expect(response.status).toBe(200)` (or appropriate status) per Section 1; avoid broad `assertIn` for auth/validation.

### 6.4 Migration Plan

See [FRONTEND_INTEGRATION_API_MIGRATION_PLAN.md](FRONTEND_INTEGRATION_API_MIGRATION_PLAN.md) for order (auth → assets → contracts → marketplace), environment requirements, and layout.

---

# Comprehensive Test Plan

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Status**: ✅ Active
**Task**: Phase 1.1 - Comprehensive Test Plan Documentation

**Related**: [TEST_SUITE_GAP_ANALYSIS.md](TEST_SUITE_GAP_ANALYSIS.md) — gap analysis (unit, integration, e2e, security, performance, CI, traceability).

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Test Strategy](#test-strategy)
3. [Test Coverage Matrix](#test-coverage-matrix)
4. [Backend Test Plan](#backend-test-plan)
5. [Frontend Test Plan](#frontend-test-plan)
6. [Integration Test Plan](#integration-test-plan)
7. [Infrastructure Test Plan](#infrastructure-test-plan)
8. [Security Test Plan](#security-test-plan)
9. [Performance Test Plan](#performance-test-plan)
10. [Concurrency Test Plan](#concurrency-test-plan)
11. [Regression Test Plan](#regression-test-plan)
12. [Test Execution Plan](#test-execution-plan)
13. [Evidence Collection Plan](#evidence-collection-plan)
14. [Test Summary Report Template](#test-summary-report-template)

---

## Executive Summary

### Purpose

This comprehensive test plan establishes the testing strategy, coverage requirements, execution plans, and evidence collection procedures for the Data Interoperability Hub platform. The plan ensures engineering-grade test coverage across all 29 features, ~109 use cases, 96 user journeys, and 13 personas.

### Scope

**Features Covered**: 29 features (Auth, Contracts, ODPS, Assets, Datasets, DQ, Compliance, Marketplace, Governance, Search, Observability, Workflows, Lineage, Versioning, BaaS, Integrations, Jobs, Files, Semantic, AI, ML, Social, Data Mesh, Virtualization, Scheduled Ingestion, Scheduled Export, Webhooks, Audit, Health)

**Use Cases Covered**: ~109 use cases across all categories

**User Journeys Covered**: 96 journeys (4 authentication + 92 role-based)

**Personas Covered**: 13 personas (Visitor + 12 role-based)

**Test Types**: Unit, Integration, E2E, Regression, Security, Performance, Concurrency

### Key Principles

1. **Real Services Only**: All tests MUST use real services, real databases, real APIs, and real infrastructure. No mock or stub implementations permitted except at external process boundaries (e.g., third-party APIs).

2. **No Error Masking**: Tests MUST NOT mask errors or problems. All error conditions must be tested explicitly. No silent exception catching or skipped error scenarios.

3. **Root Cause Fixes**: When tests fail or are flaky, root cause MUST be identified and fixed. No workarounds, bypasses, retries without fixes, or "skip if flaky" patterns permitted.

4. **No Quality Reduction**: Software quality MUST NOT be reduced to make tests pass. Application code must be fixed, not tests relaxed.

5. **Never Bypass Problems**: Problems MUST be fixed at root cause. No bypassing, ignoring, or working around problems.

6. **Development Best Practices**: All tests MUST follow TDD, DRY, SOLID, clean code, and Django best practices.

### Test Statistics

- **Total Test Files**: 1,000+ test files
- **Total Test Cases**: 5,000+ test cases
- **Backend Test Files**: 800+ files
- **Frontend Test Files**: 200+ files
- **E2E Test Files**: 100+ files
- **Integration Test Files**: 150+ files
- **Security Test Files**: 20+ files
- **Performance Test Files**: 30+ files

---

## Test Strategy

### Test Pyramid

```
        /\
       /  \      E2E Tests (10%)
      /    \     - Complete user journeys
     /      \    - Critical business flows
    /________\   - Multi-tenant isolation
   /          \  Integration Tests (20%)
  /            \ - API endpoint testing
 /              \ - Service interactions
/________________\ Unit Tests (70%)
                  - Individual components
                  - Business logic
                  - Utilities and helpers
```

**Distribution**:
- **70% Unit Tests**: Fast, isolated, test individual components (< 1 second per test)
- **20% Integration Tests**: Moderate speed, test API endpoints and service interactions (5-30 seconds per test)
- **10% E2E Tests**: Slower, test complete workflows and user journeys (30-300 seconds per test)

### Testing Principles

1. **Test User Behavior**: Test what users see and do, not implementation details
2. **Fast Feedback**: Tests should run quickly and provide immediate feedback
3. **Reliable**: Tests should be deterministic and not flaky
4. **Maintainable**: Tests should be easy to update when code changes
5. **Comprehensive**: Cover critical paths, edge cases, and error scenarios
6. **Real Services**: Use real implementations (DB, services, APIs) except at external boundaries
7. **Root Cause Fixes**: Fix flakiness at root cause (idempotency, explicit waits, timeouts)
8. **TDD Approach**: Write failing tests first, then implement functionality
9. **No Mocks/Stubs**: Use real services except justified at external process boundaries
10. **Error Exposure**: Test all error conditions explicitly, no masking

### Test Categories

#### 1. Unit Tests
- **Purpose**: Test individual components in isolation
- **Scope**: Business logic, utilities, models, serializers, views (isolated)
- **Speed**: < 1 second per test
- **Coverage Target**: 100% business logic, 90%+ views/serializers/models, 80%+ utilities
- **Framework**: pytest with Django test client
- **Location**: `hub/apps/*/tests/test_*.py`

#### 2. Integration Tests
- **Purpose**: Test component interactions and API endpoints
- **Scope**: API endpoints, service interactions, database operations, external integrations
- **Speed**: 5-30 seconds per test
- **Coverage Target**: 90%+ API endpoints, 100% critical service interactions, 80%+ database operations
- **Framework**: pytest with Django REST Framework test client
- **Location**: `tests/integration/test_*.py`

#### 3. E2E Tests
- **Purpose**: Test complete user journeys and workflows
- **Scope**: Complete user journeys, multi-tenant isolation, critical business flows
- **Speed**: 30-300 seconds per test
- **Coverage Target**: 100% critical journeys, 90%+ all journeys, 100% multi-tenant isolation
- **Framework**: pytest with Django REST Framework test client (backend), Playwright (frontend)
- **Location**: `tests/e2e/test_*.py` (backend), `frontend/e2e/**/*.spec.ts` (frontend)

#### 4. Regression Tests
- **Purpose**: Verify existing functionality continues to work
- **Scope**: All API endpoints, features, database operations, service integrations
- **Speed**: 5-30 seconds per test
- **Coverage Target**: 100% API endpoints, 100% features, 100% critical workflows
- **Framework**: pytest
- **Location**: `tests/regression/test_*.py`

#### 5. Security Tests
- **Purpose**: Test authentication, authorization, data protection, and vulnerabilities
- **Scope**: Authentication flows, authorization checks, data protection, vulnerability scanning
- **Speed**: 10-60 seconds per test
- **Coverage Target**: 100% authentication, 100% authorization, 100% data protection, 100% vulnerabilities
- **Framework**: pytest with security testing tools
- **Location**: `tests/security/test_*.py`

#### 6. Performance Tests
- **Purpose**: Test system performance under load
- **Scope**: Load tests, stress tests, endurance tests, spike tests
- **Speed**: 60-120 minutes per test suite
- **Coverage Target**: All critical endpoints, baselines established
- **Framework**: pytest with Locust, pytest-benchmark
- **Location**: `tests/performance/test_*.py`, `tests/performance/locustfile.py`

#### 7. Concurrency Tests
- **Purpose**: Test race conditions, thread safety, and concurrent workflows
- **Scope**: Race conditions, thread safety, concurrent workflows, lock mechanisms
- **Speed**: 20-40 minutes per test suite
- **Coverage Target**: Race conditions, thread safety, concurrent workflows
- **Framework**: pytest with threading/concurrent execution
- **Location**: `tests/concurrency/test_*.py`

---

## Test Coverage Matrix

### Feature Coverage Matrix

| Feature | Unit Tests | Integration Tests | E2E Tests | Security Tests | Performance Tests | Status |
|---------|-----------|------------------|----------|----------------|-------------------|--------|
| Auth | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Contracts | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| ODPS | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Assets | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Datasets | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| DQ | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Compliance | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Marketplace | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Governance | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Search | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Observability | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Workflows | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Lineage | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Versioning | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |
| BaaS | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Integrations | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Jobs | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Files | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Semantic | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| AI | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |
| ML | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |
| Social | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |
| Data Mesh | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |
| Virtualization | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Scheduled Export | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| Webhooks | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Audit | ✅ | ✅ | ✅ | ✅ | ⏳ | Partial |
| Health | ✅ | ✅ | ✅ | ⏳ | ⏳ | Partial |

**Legend**:
- ✅ Complete coverage
- ⏳ Partial coverage (needs improvement)
- ❌ Missing coverage

### Use Case Coverage Matrix

**Total Use Cases**: ~109 use cases

**Coverage by Category**:

| Category | Total Use Cases | Unit Tests | Integration Tests | E2E Tests | Status |
|----------|----------------|-----------|------------------|----------|--------|
| Authentication & Access | 4 | ✅ | ✅ | ✅ | Complete |
| Asset Management | ~8 | ✅ | ✅ | ✅ | Complete |
| Contract Management | ~6 | ✅ | ✅ | ✅ | Complete |
| Data Quality | ~6 | ✅ | ✅ | ✅ | Complete |
| Compliance | ~6 | ✅ | ✅ | ✅ | Complete |
| Marketplace | ~8 | ✅ | ✅ | ✅ | Complete |
| AI/ML | ~10 | ✅ | ✅ | ⏳ | Partial |
| Social Features | ~6 | ✅ | ✅ | ⏳ | Partial |
| Data Mesh | ~5 | ✅ | ✅ | ⏳ | Partial |
| Virtualization | ~4 | ✅ | ✅ | ✅ | Complete |
| Advanced Marketplace | ~5 | ✅ | ✅ | ⏳ | Partial |
| Advanced Governance | ~4 | ✅ | ✅ | ⏳ | Partial |
| Advanced Observability | ~4 | ✅ | ✅ | ⏳ | Partial |
| Integration Ecosystem | ~5 | ✅ | ✅ | ⏳ | Partial |
| Developer Experience | ~4 | ✅ | ✅ | ⏳ | Partial |
| Transformation | ~8 | ✅ | ✅ | ⏳ | Partial |
| Lineage | ~4 | ✅ | ✅ | ⏳ | Partial |
| Versioning | ~3 | ✅ | ✅ | ⏳ | Partial |
| BaaS | ~4 | ✅ | ✅ | ✅ | Complete |
| ODH Integration | ~4 | ✅ | ✅ | ⏳ | Partial |
| ODPS | ~6 | ✅ | ✅ | ✅ | Complete |
| Semantic | ~4 | ✅ | ✅ | ✅ | Complete |
| Scheduled Ingestion | ~3 | ✅ | ✅ | ✅ | Complete |
| Webhooks | ~3 | ✅ | ✅ | ⏳ | Partial |
| Audit | ~3 | ✅ | ✅ | ✅ | Complete |

### User Journey Coverage Matrix

**Total Journeys**: 96 journeys

**Coverage by Persona**:

| Persona | Total Journeys | Backend E2E | Frontend E2E | Status |
|---------|----------------|------------|-------------|--------|
| Visitor / Authentication | 4 | ✅ | ✅ | Complete |
| Data Product Owner | 17 | ✅ | ✅ | Complete |
| Data Engineer | 14 | ✅ | ✅ | Complete |
| Compliance Officer | 10 | ✅ | ✅ | Complete |
| Data Consumer | 15 | ✅ | ✅ | Complete |
| Tenant Admin | 8 | ✅ | ✅ | Complete |
| Platform Admin | 10 | ✅ | ✅ | Complete |
| External Developer | 9 | ✅ | ✅ | Complete |
| Auditor | 6 | ✅ | ✅ | Complete |
| Data Scientist | 5 | ✅ | ⏳ | Partial |
| Data Analyst | 4 | ✅ | ⏳ | Partial |
| Community Manager | 4 | ✅ | ⏳ | Partial |
| Data Mesh Domain Owner | 5 | ✅ | ⏳ | Partial |

**Coverage Target**: 100% critical journeys, 90%+ all journeys, 100% multi-tenant isolation

### Persona Coverage Matrix

**Total Personas**: 13 personas

| Persona | Journey Coverage | Test Coverage | Status |
|---------|------------------|--------------|--------|
| Visitor / Prospect | ✅ | ✅ | Complete |
| Data Product Owner | ✅ | ✅ | Complete |
| Data Engineer | ✅ | ✅ | Complete |
| Compliance Officer | ✅ | ✅ | Complete |
| Data Consumer | ✅ | ✅ | Complete |
| Tenant Admin | ✅ | ✅ | Complete |
| Platform Admin | ✅ | ✅ | Complete |
| External Developer | ✅ | ✅ | Complete |
| Auditor | ✅ | ✅ | Complete |
| Data Scientist | ⏳ | ⏳ | Partial |
| Data Analyst | ⏳ | ⏳ | Partial |
| Community Manager | ⏳ | ⏳ | Partial |
| Data Mesh Domain Owner | ⏳ | ⏳ | Partial |

---

## Backend Test Plan

### Unit Tests

#### Coverage Requirements

- **Business Logic**: 100% coverage
- **Views/Serializers/Models**: 90%+ coverage
- **Utilities**: 80%+ coverage

#### Test Structure

```
hub/apps/{app}/tests/
├── test_views.py          # View tests
├── test_services.py       # Service tests
├── test_serializers.py    # Serializer tests
├── test_models.py        # Model tests
├── test_business_rules.py # Business rules tests
├── test_caching.py        # Caching tests
└── test_utils.py          # Utility tests
```

#### Test Execution

```bash
# Run all unit tests
pytest hub/apps/*/tests/test_*.py -v --cov=hub --cov-report=html

# Run unit tests for specific app
pytest hub/apps/{app}/tests/test_*.py -v --cov=hub.apps.{app} --cov-report=html

# Run unit tests with markers
pytest hub/apps/*/tests/test_*.py -v -m unit
```

#### Duration Estimate

- **Total Duration**: 5-10 minutes
- **Per Test**: < 1 second
- **Parallel Execution**: Yes (pytest-xdist)

### Integration Tests

#### Coverage Requirements

- **API Endpoints**: 90%+ coverage
- **Critical Service Interactions**: 100% coverage
- **Database Operations**: 80%+ coverage

#### Test Structure

```
tests/integration/
├── test_api_*.py              # API endpoint tests
├── test_service_*.py           # Service interaction tests
├── test_database_*.py          # Database operation tests
├── test_external_*.py          # External integration tests
└── test_docker_compose_*.py    # Docker Compose tests
```

#### Test Execution

```bash
# Run all integration tests
pytest tests/integration/ -v --docker-compose-runtime

# Run specific integration test category
pytest tests/integration/test_api_*.py -v --docker-compose-runtime
```

#### Duration Estimate

- **Total Duration**: 15-30 minutes
- **Per Test**: 5-30 seconds
- **Parallel Execution**: Yes (where possible)

### E2E Tests

#### Coverage Requirements

- **Critical User Journeys**: 100% coverage
- **All User Journeys**: 90%+ coverage
- **Multi-Tenant Isolation**: 100% coverage

#### Test Structure

```
tests/e2e/
├── test_data_first_comprehensive.py
├── test_contract_first_comprehensive.py
├── test_contract_only_comprehensive.py
├── test_marketplace_comprehensive.py
├── test_marketplace_purchase_flow.py
├── test_multi_tenant_isolation.py
├── test_audit_compliance_journeys.py
├── test_complete_user_journeys.py
└── test_scheduled_ingestion.py
```

#### Test Execution

```bash
# Run all E2E tests
pytest tests/e2e/ -v --docker-compose-runtime

# Run specific E2E test
pytest tests/e2e/test_marketplace_comprehensive.py -v --docker-compose-runtime
```

#### Duration Estimate

- **Total Duration**: 30-60 minutes
- **Per Test**: 30-300 seconds
- **Parallel Execution**: Sequential recommended (full stack)

### Regression Tests

#### Coverage Requirements

- **API Endpoints**: 100% coverage
- **Features**: 100% coverage
- **Database Operations**: 100% coverage
- **Service Integrations**: 100% coverage
- **Workflows**: 100% coverage
- **Middleware**: 100% coverage
- **Tenant Isolation**: 100% coverage
- **File Storage**: 100% coverage
- **Job Queue**: 100% coverage

#### Test Structure

```
tests/regression/
├── test_api_endpoints.py
├── test_existing_functionality_verification.py
├── test_phase25_regression.py
├── test_phase26_cli_sdk_regression.py
├── test_database_operations.py
├── test_file_storage.py
├── test_integrations.py
├── test_job_queue.py
├── test_middleware.py
├── test_tenant_isolation.py
└── test_workflows.py
```

#### Test Execution

```bash
# Run all regression tests
pytest tests/regression/ -v

# Run specific regression test
pytest tests/regression/test_api_endpoints.py -v
```

#### Duration Estimate

- **Total Duration**: 30-60 minutes
- **Per Test**: 5-30 seconds
- **Parallel Execution**: Yes (where possible)

### Security Tests

#### Coverage Requirements

- **Authentication**: 100% coverage (login, logout, token refresh, session management, password reset, MFA)
- **Authorization**: 100% coverage (RBAC, ABAC, permission checks, resource-level authorization)
- **Data Protection**: 100% coverage (encryption, masking, PII detection, GDPR compliance)
- **Vulnerabilities**: 100% coverage (SQL injection, XSS, CSRF, SSRF, path traversal, command injection)
- **Penetration Testing**: Security scanning, vulnerability assessment

#### Test Structure

```
tests/security/
├── test_allowany_public_endpoints.py
├── test_gateway_headers_forged.py
├── test_marketplace_security.py
├── test_phase25_security.py
├── test_production_secrets.py
├── test_security_features.py
├── test_security_features_enhanced.py
└── penetration_test_odps_ref_resolver.py
```

#### Test Execution

```bash
# Run all security tests
pytest tests/security/ -v

# Run specific security test
pytest tests/security/test_security_features.py -v
```

#### Duration Estimate

- **Total Duration**: 10-20 minutes
- **Per Test**: 10-60 seconds
- **Parallel Execution**: Yes

### Performance Tests

#### Coverage Requirements

- **Load Tests**: 100, 500, 1000 concurrent users
- **Stress Tests**: System limits, resource exhaustion
- **Endurance Tests**: 24-hour continuous load
- **Spike Tests**: 10x, 50x, 100x load spikes
- **Performance Baselines**: Established for all critical endpoints

#### Test Structure

```
tests/performance/
├── locustfile.py
├── locust_api_endpoints_availability.py
├── locust_database_query_performance.py
├── locust_file_upload_download.py
├── locust_job_queue_throughput.py
├── locust_odps_ingestion.py
├── locust_odps_ref_resolution.py
├── locust_endurance_test.py
├── locust_spike_test.py
├── locust_stress_test.py
├── test_performance_baseline.py
└── test_performance.py
```

#### Test Execution

```bash
# Run performance tests
pytest tests/performance/ -v --performance-baseline

# Run Locust load tests
locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 60s
```

#### Duration Estimate

- **Total Duration**: 60-120 minutes
- **Per Test Suite**: 5-60 minutes
- **Parallel Execution**: Sequential (resource intensive)

### Concurrency Tests

#### Coverage Requirements

- **Race Conditions**: Concurrent CRUD operations, concurrent updates, concurrent deletions, concurrent reads, lock contention, deadlock detection, data consistency
- **Thread Safety**: Multi-threaded access, shared state protection, synchronization mechanisms, atomic operations, thread-local storage
- **Concurrent Workflows**: Concurrent workflow execution, workflow state consistency, workflow conflict resolution, workflow recovery, workflow rollback

#### Test Structure

```
tests/concurrency/
├── test_race_conditions.py
├── test_concurrent_access.py
├── test_data_consistency.py
├── test_lock_mechanisms.py
├── test_thread_safety.py
├── test_shared_state.py
├── test_synchronization.py
├── test_atomic_operations.py
├── test_concurrent_workflows.py
├── test_workflow_state_management.py
├── test_workflow_conflicts.py
└── test_workflow_recovery.py
```

#### Test Execution

```bash
# Run concurrency tests
pytest tests/concurrency/ -v --concurrent

# Run specific concurrency test
pytest tests/concurrency/test_race_conditions.py -v --concurrent
```

#### Duration Estimate

- **Total Duration**: 20-40 minutes
- **Per Test Suite**: 5-20 minutes
- **Parallel Execution**: Sequential (test concurrency)

---

## Frontend Test Plan

### Unit Tests

#### Coverage Requirements

- **Components**: 90%+ coverage
- **Hooks**: 90%+ coverage
- **Services**: 90%+ coverage
- **Business Logic**: 100% coverage
- **Utilities**: 80%+ coverage

#### Test Structure

```
frontend/src/
├── features/
│   └── {feature}/
│       ├── components/
│       │   └── __tests__/
│       │       └── {Component}.test.tsx
│       ├── hooks/
│       │   └── __tests__/
│       │       └── {hook}.test.ts
│       └── services/
│           └── __tests__/
│               └── {service}.test.ts
└── shared/
    └── __tests__/
        └── {utility}.test.ts
```

#### Test Execution

```bash
# Run all frontend unit tests
cd frontend && npm test

# Run tests in watch mode
cd frontend && npm test -- --watch

# Run tests with coverage
cd frontend && npm test -- --coverage
```

#### Duration Estimate

- **Total Duration**: 5-10 minutes
- **Per Test**: < 1 second
- **Parallel Execution**: Yes (Jest)

### Integration Tests

#### Coverage Requirements

- **Component Integration**: 90%+ coverage
- **Service Integration**: 90%+ coverage
- **API Integration**: 90%+ coverage

#### Test Structure

```
frontend/src/
└── features/
    └── {feature}/
        └── __tests__/
            └── {feature}.integration.test.tsx
```

#### Test Execution

```bash
# Run integration tests
cd frontend && npm test -- --testPathPattern=integration
```

#### Duration Estimate

- **Total Duration**: 10-15 minutes
- **Per Test**: 1-5 seconds
- **Parallel Execution**: Yes (Jest)

### E2E Tests

#### Coverage Requirements

- **Critical User Journeys**: 100% coverage
- **All User Journeys**: 90%+ coverage
- **Every JOURNEY-* in USER_JOURNEYS.md**: Has a Playwright spec
- **All Routes**: At least one success test

#### Test Structure

```
frontend/e2e/
├── journeys/
│   ├── auth/
│   │   ├── JOURNEY-AUTH-001.spec.ts
│   │   ├── JOURNEY-AUTH-002.spec.ts
│   │   ├── JOURNEY-AUTH-003.spec.ts
│   │   └── JOURNEY-AUTH-004.spec.ts
│   ├── dpo/
│   │   ├── JOURNEY-DPO-001.spec.ts
│   │   └── ...
│   └── ...
├── personas/
│   ├── visitor.spec.ts
│   ├── data-product-owner.spec.ts
│   └── ...
└── features/
    ├── auth.spec.ts
    ├── contracts.spec.ts
    └── ...
```

#### Test Execution

```bash
# Run all E2E tests
cd frontend && npm run test:e2e

# Run E2E tests in visible mode
cd frontend && E2E_VISIBLE=1 npm run test:e2e

# Run specific E2E test
cd frontend && npm run test:e2e -- JOURNEY-AUTH-001.spec.ts
```

#### Duration Estimate

- **Total Duration**: 30-60 minutes
- **Per Test**: 30-300 seconds
- **Parallel Execution**: Sequential recommended (full stack)

---

## Integration Test Plan

### API Integration Tests

#### Coverage Requirements

- **API Endpoints**: 90%+ coverage
- **Request/Response Validation**: 100% coverage
- **Error Handling**: 100% coverage
- **Authentication/Authorization**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_api_endpoints.py
├── test_api_versioning.py
├── test_api_error_handling.py
├── test_api_rate_limiting.py
├── test_api_authentication.py
└── test_api_authorization.py
```

#### Test Execution

```bash
# Run API integration tests
pytest tests/integration/test_api_*.py -v --docker-compose-runtime
```

### Service Integration Tests

#### Coverage Requirements

- **Critical Service Interactions**: 100% coverage
- **Service Communication**: 100% coverage
- **Event Bus Integration**: 100% coverage
- **Workflow Integration**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_service_interactions.py
├── test_event_bus_integration.py
├── test_workflow_integration.py
└── test_database_integration.py
```

#### Test Execution

```bash
# Run service integration tests
pytest tests/integration/test_service_*.py -v --docker-compose-runtime
```

### External Integration Tests

#### Coverage Requirements

- **External Integrations**: 100% coverage
- **Third-Party APIs**: 100% coverage (with justified mocks at external boundary)
- **Marketplace Integrations**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_marketplace_integration.py
├── test_external_services.py
└── test_third_party_apis.py
```

#### Test Execution

```bash
# Run external integration tests
pytest tests/integration/test_external_*.py -v --docker-compose-runtime
```

---

## Infrastructure Test Plan

### Docker Compose Tests

#### Coverage Requirements

- **Service Deployment**: 100% coverage
- **Service Startup Order**: 100% coverage
- **Health Checks**: 100% coverage
- **Service Communication**: 100% coverage
- **Service Dependencies**: 100% coverage
- **Network Connectivity**: 100% coverage
- **Volume Mounts**: 100% coverage
- **Environment Variables**: 100% coverage
- **Resource Limits**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_docker_compose.py
├── test_docker_compose_deployment.py
├── test_docker_compose_dev.py
├── test_docker_compose_staging.py
└── test_docker_compose_standalone.py
```

#### Test Execution

```bash
# Run Docker Compose tests
pytest tests/integration/test_docker_compose_*.py -v --docker-compose-runtime
```

### Kubernetes Tests

#### Coverage Requirements

- **Pod Deployment**: 100% coverage
- **Service Creation**: 100% coverage
- **ConfigMap and Secret Management**: 100% coverage
- **Persistent Volume Claims**: 100% coverage
- **Ingress Rules**: 100% coverage
- **Horizontal Pod Autoscaling**: 100% coverage
- **Rolling Updates**: 100% coverage
- **Health Checks**: 100% coverage
- **Resource Quotas**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_kubernetes_deployment.py
├── test_kubernetes_service_discovery.py
├── test_kubernetes_config.py
└── test_kubernetes_scaling.py
```

#### Test Execution

```bash
# Run Kubernetes tests
pytest tests/integration/test_kubernetes_*.py -v
```

### Monitoring Tests

#### Coverage Requirements

- **Prometheus Metrics Collection**: 100% coverage
- **Grafana Dashboards**: 100% coverage
- **Jaeger Tracing**: 100% coverage
- **Alertmanager Alerts**: 100% coverage
- **Service Discovery**: 100% coverage
- **Scrape Configuration**: 100% coverage

#### Test Structure

```
tests/integration/
├── test_prometheus_metrics.py
├── test_grafana_dashboards.py
├── test_jaeger_tracing.py
└── test_alertmanager.py
```

#### Test Execution

```bash
# Run monitoring tests
pytest tests/integration/test_monitoring_*.py -v
```

---

## Security Test Plan

### Authentication Tests

#### Coverage Requirements

- **Login**: Success, failure, edge cases, error handling
- **Logout**: Success, failure, edge cases, error handling
- **Token Refresh**: Success, failure, edge cases, error handling
- **Session Management**: Success, failure, edge cases, error handling
- **Password Reset**: Success, failure, edge cases, error handling
- **MFA**: Success, failure, edge cases, error handling

#### Test Execution

```bash
# Run authentication security tests
pytest tests/security/ -k "auth" -v
```

### Authorization Tests

#### Coverage Requirements

- **RBAC**: Role-based access control tests
- **ABAC**: Attribute-based access control tests
- **Permission Checks**: Resource-level permission tests
- **Resource-Level Authorization**: Resource access control tests

#### Test Execution

```bash
# Run authorization security tests
pytest tests/security/ -k "authorization" -v
```

### Data Protection Tests

#### Coverage Requirements

- **Encryption**: Data encryption tests
- **Masking**: Data masking tests
- **PII Detection**: PII detection tests
- **GDPR Compliance**: GDPR compliance tests

#### Test Execution

```bash
# Run data protection security tests
pytest tests/security/ -k "data_protection" -v
```

### Vulnerability Tests

#### Coverage Requirements

- **SQL Injection**: SQL injection prevention tests
- **XSS**: Cross-site scripting prevention tests
- **CSRF**: Cross-site request forgery prevention tests
- **SSRF**: Server-side request forgery prevention tests
- **Path Traversal**: Path traversal prevention tests
- **Command Injection**: Command injection prevention tests

#### Test Execution

```bash
# Run vulnerability security tests
pytest tests/security/ -k "vulnerability" -v
```

### Penetration Tests

#### Coverage Requirements

- **Security Scanning**: Automated security scanning
- **Vulnerability Assessment**: Vulnerability assessment tests

#### Test Execution

```bash
# Run penetration tests
pytest tests/security/penetration_test_*.py -v
```

---

## Performance Test Plan

### Load Tests

#### Coverage Requirements

- **100 Concurrent Users**: Baseline load test
- **500 Concurrent Users**: Medium load test
- **1000 Concurrent Users**: High load test

#### Test Execution

```bash
# Run load tests with 100 concurrent users
locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 60s

# Run load tests with 500 concurrent users
locust -f tests/performance/locustfile.py --headless -u 500 -r 50 -t 120s

# Run load tests with 1000 concurrent users
locust -f tests/performance/locustfile.py --headless -u 1000 -r 100 -t 180s
```

### Stress Tests

#### Coverage Requirements

- **System Limits**: Test system under maximum load
- **Resource Exhaustion**: Test system behavior when resources are exhausted

#### Test Execution

```bash
# Run stress tests
locust -f tests/performance/locust_stress_test.py --headless -u 2000 -r 200 -t 300s
```

### Endurance Tests

#### Coverage Requirements

- **24-Hour Continuous Load**: Test system stability over extended period

#### Test Execution

```bash
# Run endurance tests (24 hours)
locust -f tests/performance/locust_endurance_test.py --headless -u 100 -r 10 -t 86400s
```

### Spike Tests

#### Coverage Requirements

- **10x Load Spike**: Test system response to 10x load increase
- **50x Load Spike**: Test system response to 50x load increase
- **100x Load Spike**: Test system response to 100x load increase

#### Test Execution

```bash
# Run spike tests
locust -f tests/performance/locust_spike_test.py --headless -u 1000 -r 1000 -t 60s
```

### Performance Baselines

#### Coverage Requirements

- **Critical Endpoints**: Baselines established for all critical endpoints
- **Performance Metrics**: Response time, throughput, error rate baselines

#### Test Execution

```bash
# Run performance baseline tests
pytest tests/performance/test_performance_baseline.py -v --performance-baseline
```

---

## Concurrency Test Plan

### Race Condition Tests

#### Coverage Requirements

- **Concurrent CRUD Operations**: Test concurrent create, read, update, delete operations
- **Concurrent Updates**: Test concurrent update operations
- **Concurrent Deletions**: Test concurrent delete operations
- **Concurrent Reads**: Test concurrent read operations
- **Lock Contention**: Test lock contention scenarios
- **Deadlock Detection**: Test deadlock detection and resolution
- **Data Consistency**: Test data consistency under concurrent access

#### Test Execution

```bash
# Run race condition tests
pytest tests/concurrency/test_race_conditions.py -v --concurrent
```

### Thread Safety Tests

#### Coverage Requirements

- **Multi-Threaded Access**: Test multi-threaded access to shared resources
- **Shared State Protection**: Test shared state protection mechanisms
- **Synchronization Mechanisms**: Test synchronization mechanisms
- **Atomic Operations**: Test atomic operations
- **Thread-Local Storage**: Test thread-local storage

#### Test Execution

```bash
# Run thread safety tests
pytest tests/concurrency/test_thread_safety.py -v --concurrent
```

### Concurrent Workflow Tests

#### Coverage Requirements

- **Concurrent Workflow Execution**: Test concurrent workflow execution
- **Workflow State Consistency**: Test workflow state consistency
- **Workflow Conflict Resolution**: Test workflow conflict resolution
- **Workflow Recovery**: Test workflow recovery mechanisms
- **Workflow Rollback**: Test workflow rollback mechanisms

#### Test Execution

```bash
# Run concurrent workflow tests
pytest tests/concurrency/test_concurrent_workflows.py -v --concurrent
```

---

## Regression Test Plan

### API Endpoint Regression Tests

#### Coverage Requirements

- **All API Endpoints**: 100% coverage
- **Request/Response Formats**: 100% coverage
- **Error Responses**: 100% coverage

#### Test Execution

```bash
# Run API endpoint regression tests
pytest tests/regression/test_api_endpoints.py -v
```

### Feature Regression Tests

#### Coverage Requirements

- **All Features**: 100% coverage
- **Feature Functionality**: 100% coverage
- **Feature Integration**: 100% coverage

#### Test Execution

```bash
# Run feature regression tests
pytest tests/regression/test_existing_functionality_verification.py -v
```

### Database Operation Regression Tests

#### Coverage Requirements

- **Database Operations**: 100% coverage
- **Data Integrity**: 100% coverage
- **Transaction Handling**: 100% coverage

#### Test Execution

```bash
# Run database operation regression tests
pytest tests/regression/test_database_operations.py -v
```

### Service Integration Regression Tests

#### Coverage Requirements

- **Service Integrations**: 100% coverage
- **Service Communication**: 100% coverage
- **Service Dependencies**: 100% coverage

#### Test Execution

```bash
# Run service integration regression tests
pytest tests/regression/test_integrations.py -v
```

### Workflow Regression Tests

#### Coverage Requirements

- **Workflows**: 100% coverage
- **Workflow Execution**: 100% coverage
- **Workflow State Management**: 100% coverage

#### Test Execution

```bash
# Run workflow regression tests
pytest tests/regression/test_workflows.py -v
```

---

## Test Execution Plan

### Test Execution Strategy

#### Pre-Commit Hooks

- **Test Type**: Unit tests (fast)
- **Duration**: 5-10 minutes
- **Command**: `pytest hub/apps/*/tests/test_*.py -v -m unit`
- **Coverage**: Business logic, utilities, fast tests only

#### Pull Request Checks

- **Test Type**: Unit + Integration tests
- **Duration**: 20-40 minutes
- **Command**: `pytest hub/apps/*/tests/test_*.py tests/integration/ -v --docker-compose-runtime`
- **Coverage**: All unit tests + integration tests

#### Merge to Main

- **Test Type**: Full test suite
- **Duration**: 60-120 minutes
- **Command**: `pytest tests/ -v --docker-compose-runtime --cov=hub --cov-report=html`
- **Coverage**: All test types except performance and security (run nightly)

#### Nightly Builds

- **Test Type**: Full suite + Performance + Security
- **Duration**: 120-180 minutes
- **Command**: `pytest tests/ tests/performance/ tests/security/ -v --docker-compose-runtime --cov=hub --cov-report=html`
- **Coverage**: All test types including performance and security

#### Release Builds

- **Test Type**: Full suite + Performance + Security + Concurrency
- **Duration**: 180-240 minutes
- **Command**: `pytest tests/ tests/performance/ tests/security/ tests/concurrency/ -v --docker-compose-runtime --cov=hub --cov-report=html`
- **Coverage**: All test types including concurrency tests

### Test Execution Order

1. **Unit Tests** (5-10 minutes)
   - Fast, no dependencies
   - Run first to catch quick failures
   - Can run in parallel

2. **Integration Tests** (15-30 minutes)
   - Service dependencies required
   - Run second after unit tests pass
   - Can run in parallel where possible

3. **E2E Tests** (30-60 minutes)
   - Full stack required
   - Run third after integration tests pass
   - Sequential recommended (full stack)

4. **Security Tests** (10-20 minutes)
   - Can run in parallel with other tests
   - Run fourth (parallel with E2E)

5. **Performance Tests** (60-120 minutes)
   - Long-running, resource intensive
   - Run fifth (sequential)

6. **Concurrency Tests** (20-40 minutes)
   - Test concurrency behavior
   - Run sixth (sequential)

7. **Regression Tests** (30-60 minutes)
   - Verify existing functionality
   - Run seventh (can run in parallel where possible)

### Parallelization Strategy

- **Unit Tests**: Run in parallel (pytest-xdist)
- **Integration Tests**: Run in parallel where possible
- **E2E Tests**: Sequential recommended (full stack)
- **Security Tests**: Run in parallel
- **Performance Tests**: Sequential (resource intensive)
- **Concurrency Tests**: Sequential (test concurrency)
- **Regression Tests**: Run in parallel where possible

### Duration Estimates

| Test Type | Duration | Per Test | Parallel Execution |
|-----------|----------|----------|-------------------|
| Unit Tests | 5-10 minutes | < 1 second | Yes |
| Integration Tests | 15-30 minutes | 5-30 seconds | Yes (where possible) |
| E2E Tests | 30-60 minutes | 30-300 seconds | Sequential recommended |
| Security Tests | 10-20 minutes | 10-60 seconds | Yes |
| Performance Tests | 60-120 minutes | 5-60 minutes | Sequential |
| Concurrency Tests | 20-40 minutes | 5-20 minutes | Sequential |
| Regression Tests | 30-60 minutes | 5-30 seconds | Yes (where possible) |

---

## Evidence Collection Plan

### Evidence Storage Structure

```
test_reports_comprehensive/
├── {date}/
│   ├── unit/
│   │   ├── results.json
│   │   ├── coverage.html
│   │   └── logs/
│   ├── integration/
│   │   ├── results.json
│   │   ├── coverage.html
│   │   └── logs/
│   ├── e2e/
│   │   ├── results.json
│   │   ├── screenshots/
│   │   ├── videos/
│   │   └── logs/
│   ├── security/
│   │   ├── results.json
│   │   ├── scan-report.html
│   │   └── logs/
│   ├── performance/
│   │   ├── results.json
│   │   ├── metrics.csv
│   │   ├── charts/
│   │   └── logs/
│   ├── concurrency/
│   │   ├── results.json
│   │   └── logs/
│   ├── regression/
│   │   ├── results.json
│   │   └── logs/
│   └── summary.json
```

### Evidence Collection Tools

#### pytest-html

- **Purpose**: HTML test reports
- **Installation**: `pip install pytest-html`
- **Usage**: `pytest tests/ --html=test_reports_comprehensive/report.html --self-contained-html`

#### pytest-cov

- **Purpose**: Coverage reports
- **Installation**: `pip install pytest-cov`
- **Usage**: `pytest tests/ --cov=hub --cov-report=html --cov-report=term`

#### pytest-json-report

- **Purpose**: JSON test reports
- **Installation**: `pip install pytest-json-report`
- **Usage**: `pytest tests/ --json-report --json-report-file=test_reports_comprehensive/report.json`

#### Playwright

- **Purpose**: Screenshots and videos for E2E tests
- **Installation**: `npm install -D @playwright/test`
- **Usage**: Configured in `playwright.config.ts`

#### Locust

- **Purpose**: Performance metrics
- **Installation**: `pip install locust`
- **Usage**: `locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 60s --csv=test_reports_comprehensive/performance/metrics`

#### Allure

- **Purpose**: Test reporting
- **Installation**: `pip install allure-pytest`
- **Usage**: `pytest tests/ --alluredir=test_reports_comprehensive/allure-results && allure serve test_reports_comprehensive/allure-results`

### Evidence Collection Commands

#### HTML Test Report

```bash
pytest tests/ --html=test_reports_comprehensive/{date}/report.html --self-contained-html
```

#### JSON Test Report

```bash
pytest tests/ --json-report --json-report-file=test_reports_comprehensive/{date}/report.json
```

#### Coverage Report

```bash
pytest tests/ --cov=hub --cov-report=html --cov-report=term --cov-report=json:test_reports_comprehensive/{date}/coverage.json
```

#### Allure Report

```bash
pytest tests/ --alluredir=test_reports_comprehensive/{date}/allure-results
allure serve test_reports_comprehensive/{date}/allure-results
```

#### Performance Metrics

```bash
locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 60s --csv=test_reports_comprehensive/{date}/performance/metrics
```

#### Security Scan Report

```bash
pytest tests/security/ --html=test_reports_comprehensive/{date}/security/scan-report.html --self-contained-html
```

---

## Test Summary Report Template

### Test Execution Summary

**Date**: {date}
**Version**: {version}
**Test Suite**: {suite_name}
**Total Tests**: {total}
**Passed**: {passed}
**Failed**: {failed}
**Skipped**: {skipped}
**Duration**: {duration}

### Test Results by Category

| Category | Total | Passed | Failed | Skipped | Duration | Status |
|----------|-------|--------|--------|---------|----------|--------|
| Unit Tests | {unit_total} | {unit_passed} | {unit_failed} | {unit_skipped} | {unit_duration} | {unit_status} |
| Integration Tests | {integration_total} | {integration_passed} | {integration_failed} | {integration_skipped} | {integration_duration} | {integration_status} |
| E2E Tests | {e2e_total} | {e2e_passed} | {e2e_failed} | {e2e_skipped} | {e2e_duration} | {e2e_status} |
| Security Tests | {security_total} | {security_passed} | {security_failed} | {security_skipped} | {security_duration} | {security_status} |
| Performance Tests | {performance_total} | {performance_passed} | {performance_failed} | {performance_skipped} | {performance_duration} | {performance_status} |
| Concurrency Tests | {concurrency_total} | {concurrency_passed} | {concurrency_failed} | {concurrency_skipped} | {concurrency_duration} | {concurrency_status} |
| Regression Tests | {regression_total} | {regression_passed} | {regression_failed} | {regression_skipped} | {regression_duration} | {regression_status} |

### Test Results by Feature

| Feature | Unit Tests | Integration Tests | E2E Tests | Security Tests | Performance Tests | Status |
|---------|-----------|------------------|----------|----------------|-------------------|--------|
| Auth | {auth_unit} | {auth_integration} | {auth_e2e} | {auth_security} | {auth_performance} | {auth_status} |
| Contracts | {contracts_unit} | {contracts_integration} | {contracts_e2e} | {contracts_security} | {contracts_performance} | {contracts_status} |
| ODPS | {odps_unit} | {odps_integration} | {odps_e2e} | {odps_security} | {odps_performance} | {odps_status} |
| ... | ... | ... | ... | ... | ... | ... |

### Test Results by Use Case

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AUTH-001 | User Registers | {uc_auth_001_unit} | {uc_auth_001_integration} | {uc_auth_001_e2e} | {uc_auth_001_status} |
| UC-AUTH-002 | User Logs In | {uc_auth_002_unit} | {uc_auth_002_integration} | {uc_auth_002_e2e} | {uc_auth_002_status} |
| ... | ... | ... | ... | ... | ... |

### Test Results by User Journey

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | {journey_auth_001_backend} | {journey_auth_001_frontend} | {journey_auth_001_status} |
| JOURNEY-AUTH-002 | User Logs In | {journey_auth_002_backend} | {journey_auth_002_frontend} | {journey_auth_002_status} |
| ... | ... | ... | ... | ... |

### Failed Tests Table

| Test ID | Test Name | Category | Failure Reason | Fix Status |
|---------|-----------|----------|----------------|------------|
| {test_id_1} | {test_name_1} | {category_1} | {failure_reason_1} | {fix_status_1} |
| {test_id_2} | {test_name_2} | {category_2} | {failure_reason_2} | {fix_status_2} |
| ... | ... | ... | ... | ... |

### Performance Metrics Table

| Metric | Baseline | Current | Change | Status |
|--------|----------|---------|--------|--------|
| API Response Time (p50) | {baseline_p50} | {current_p50} | {change_p50} | {status_p50} |
| API Response Time (p95) | {baseline_p95} | {current_p95} | {change_p95} | {status_p95} |
| API Response Time (p99) | {baseline_p99} | {current_p99} | {change_p99} | {status_p99} |
| Throughput | {baseline_throughput} | {current_throughput} | {change_throughput} | {status_throughput} |
| Error Rate | {baseline_error_rate} | {current_error_rate} | {change_error_rate} | {status_error_rate} |

### Security Scan Results Table

| Vulnerability | Severity | Status | Fix Status |
|---------------|----------|--------|------------|
| {vulnerability_1} | {severity_1} | {status_1} | {fix_status_1} |
| {vulnerability_2} | {severity_2} | {status_2} | {fix_status_2} |
| ... | ... | ... | ... |

### Recommendations

1. **Test Coverage Improvements**: {recommendations_coverage}
2. **Performance Optimizations**: {recommendations_performance}
3. **Security Enhancements**: {recommendations_security}
4. **Test Quality Improvements**: {recommendations_quality}
5. **Infrastructure Improvements**: {recommendations_infrastructure}

### Evidence Links

- **Test Results**: `test_reports_comprehensive/{date}/results.json`
- **Coverage Report**: `test_reports_comprehensive/{date}/coverage.html`
- **Performance Metrics**: `test_reports_comprehensive/{date}/performance/metrics.csv`
- **Security Scan Report**: `test_reports_comprehensive/{date}/security/scan-report.html`
- **Allure Report**: `test_reports_comprehensive/{date}/allure-results/`
- **E2E Screenshots**: `test_reports_comprehensive/{date}/e2e/screenshots/`
- **E2E Videos**: `test_reports_comprehensive/{date}/e2e/videos/`

---

## Test Coverage Requirements Summary

### Unit Tests

- **Business Logic**: 100% coverage
- **Views/Serializers/Models**: 90%+ coverage
- **Utilities**: 80%+ coverage

### Integration Tests

- **API Endpoints**: 90%+ coverage
- **Critical Service Interactions**: 100% coverage
- **Database Operations**: 80%+ coverage

### E2E Tests

- **Critical User Journeys**: 100% coverage
- **All User Journeys**: 90%+ coverage
- **Multi-Tenant Isolation**: 100% coverage

### Security Tests

- **Authentication**: 100% coverage
- **Authorization**: 100% coverage
- **Data Protection**: 100% coverage
- **Vulnerabilities**: 100% coverage

### Performance Tests

- **All Critical Endpoints**: Baselines established
- **Load Tests**: 100, 500, 1000 concurrent users
- **Stress Tests**: System limits, resource exhaustion
- **Endurance Tests**: 24-hour continuous load
- **Spike Tests**: 10x, 50x, 100x load spikes

### Concurrency Tests

- **Race Conditions**: Race conditions, thread safety, concurrent workflows
- **Thread Safety**: Multi-threaded access, shared state protection
- **Concurrent Workflows**: Concurrent workflow execution, workflow state consistency

---

## Test Execution Strategy Summary

### Pre-Commit

- **Test Type**: Unit tests (fast)
- **Duration**: 5-10 minutes
- **Command**: `pytest hub/apps/*/tests/test_*.py -v -m unit`

### Pull Request

- **Test Type**: Unit + Integration tests
- **Duration**: 20-40 minutes
- **Command**: `pytest hub/apps/*/tests/test_*.py tests/integration/ -v --docker-compose-runtime`

### Merge to Main

- **Test Type**: Full test suite
- **Duration**: 60-120 minutes
- **Command**: `pytest tests/ -v --docker-compose-runtime --cov=hub --cov-report=html`

### Nightly

- **Test Type**: Full suite + Performance + Security
- **Duration**: 120-180 minutes
- **Command**: `pytest tests/ tests/performance/ tests/security/ -v --docker-compose-runtime --cov=hub --cov-report=html`

### Release

- **Test Type**: Full suite + Performance + Security + Concurrency
- **Duration**: 180-240 minutes
- **Command**: `pytest tests/ tests/performance/ tests/security/ tests/concurrency/ -v --docker-compose-runtime --cov=hub --cov-report=html`

---

## Test Execution Order and Duration Estimates

| Test Type | Duration | Per Test | Parallel Execution |
|-----------|----------|----------|-------------------|
| Unit Tests | 5-10 minutes | < 1 second | Yes |
| Integration Tests | 15-30 minutes | 5-30 seconds | Yes (where possible) |
| E2E Tests | 30-60 minutes | 30-300 seconds | Sequential recommended |
| Security Tests | 10-20 minutes | 10-60 seconds | Yes |
| Performance Tests | 60-120 minutes | 5-60 minutes | Sequential |
| Concurrency Tests | 20-40 minutes | 5-20 minutes | Sequential |
| Regression Tests | 30-60 minutes | 5-30 seconds | Yes (where possible) |

---

## Conclusion

This comprehensive test plan establishes the foundation for engineering-grade test coverage across all features, use cases, user journeys, and personas. The plan emphasizes:

1. **Real Services**: No mocks/stubs except at external boundaries
2. **Root Cause Fixes**: Fix flakiness at root cause, not workarounds
3. **TDD Principles**: Write failing tests first, then implement
4. **Development Best Practices**: DRY, SOLID, clean code, Django best practices
5. **Comprehensive Coverage**: 100% critical paths, 90%+ all paths
6. **Evidence Collection**: Comprehensive test reports, coverage, metrics
7. **CI/CD Integration**: Automated test execution at all stages

The plan will be continuously updated as the codebase evolves and new features are added.

---

## Related Documents

- **[TEST_TRACEABILITY.md](TEST_TRACEABILITY.md)** - Detailed mapping of features, use cases, and journeys to test files
- **[FEATURES.md](FEATURES.md)** - Complete feature documentation (29 features)
- **[USE_CASES.md](USE_CASES.md)** - Complete use case documentation (~109 use cases)
- **[USER_JOURNEYS.md](USER_JOURNEYS.md)** - Complete user journey documentation (96 journeys)
- **[USER_PERSONAS.md](USER_PERSONAS.md)** - Complete persona documentation (13 personas)
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Testing strategies and test execution guide
- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** - Development workflows and practices

---

**Document Status**: ✅ Complete
**Last Updated**: 2026-03-22
**Next Steps**: Execute Phase 2 - Backend Unit Test Review

---

# Test Coverage Matrix

**Document Version**: 1.5.0
**Last Updated**: 2026-03-22
**Status**: ✅ Active
**Task**: Phase 1.2 - Test Coverage Matrix Documentation; Phase 6 Gap Remediation (traceability and supporting capabilities); gapfix1 Phase 2.5 (traceability and gapfix1 section); Task 6.8.2 UC/journey/persona coverage status

---

## Table of Contents

1. [Overview](#overview)
2. [Feature Coverage Matrix](#feature-coverage-matrix) — includes [Supporting Capabilities](#supporting-capabilities-traceability) and [Gap Remediation Coverage](#gap-remediation-coverage)
3. [Use Case Coverage Matrix](#use-case-coverage-matrix)
4. [User Journey Coverage Matrix](#user-journey-coverage-matrix)
5. [Persona Coverage Matrix](#persona-coverage-matrix)
6. [UC/Journey/Persona E2E Coverage (Task 6.7)](#ucjourney-persona-e2e-coverage-task-67)
7. [Coverage Status Summary](#coverage-status-summary)
8. [Coverage Gaps and Recommendations](#coverage-gaps-and-recommendations)

---

## Overview

This document provides comprehensive test coverage matrices for the Data Interoperability Hub platform, showing test coverage across all features, use cases, user journeys, and personas.

### Coverage Dimensions

- **Features**: 29 product features (Auth through Health, as listed in [FEATURES.md](FEATURES.md)). Supporting capabilities (Notifications, Billing, Platform, Tenants, Users, Analytics, Events) are documented separately and covered via the features that use them; see [Supporting Capabilities (Traceability)](#supporting-capabilities-traceability) and [Gap Remediation Coverage](#gap-remediation-coverage).
- **Use Cases**: ~109 use cases
- **User Journeys**: 96 journeys
- **Personas**: 13 personas

### Test Types

- **Unit Tests**: Individual component tests (< 1 second per test)
- **Integration Tests**: Component interaction tests (5-30 seconds per test)
- **E2E Tests**: Complete user journey tests (30-300 seconds per test)
- **Security Tests**: Authentication, authorization, vulnerability tests (10-60 seconds per test)
- **Performance Tests**: Load, stress, endurance tests (5-60 minutes per test suite)

### Status Indicators

- ✅ **Complete**: Full coverage with all test types
- ⏳ **Partial**: Coverage exists but needs improvement
- ❌ **Missing**: No coverage or minimal coverage

---

## Feature Coverage Matrix

### All 29 Features

| # | Feature | Unit Tests | Integration Tests | E2E Tests | Security Tests | Performance Tests | Overall Status |
|---|---------|-----------|------------------|----------|----------------|-------------------|----------------|
| 1 | Auth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 2 | Contracts | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 3 | ODPS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 4 | Assets | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 5 | Datasets | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 6 | DQ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 7 | Compliance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 8 | Marketplace | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 9 | Governance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 10 | Search | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 11 | Observability | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 12 | Workflows | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 13 | Lineage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 14 | Versioning | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 15 | BaaS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 16 | Integrations | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 17 | Jobs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 18 | Files | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 19 | Semantic | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 20 | AI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 21 | ML | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 22 | Social | ✅ | ✅ | ✅ | ⏳ | ✅ | ⏳ Partial |
| 23 | Data Mesh | ✅ | ✅ | ✅ | ⏳ | ✅ | ⏳ Partial |
| 24 | Virtualization | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 25 | Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 26 | Scheduled Export | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 27 | Webhooks | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 28 | Audit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 29 | Health | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |

### Feature Coverage Statistics

- **Complete Coverage**: 27 features (93%)
- **Partial Coverage**: 2 features (7%)
- **Missing Coverage**: 0 features (0%)

### Resource Pickers (UX)

**Coverage**: Searchable pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker) for selecting assets, contracts, datasets, files. Unit: 102 (pickers + picker-using pages). Backend list API: 51 tests. Integration: `picker-form-api.integration.test.ts`. E2E: `odps-asset-link`, `asset-attach-contract-dataset`, `dq-compliance-access-request`, `scheduled-export-retention-odps-link`, `dataset-edit`, `picker-a11y`. **Run**: `./scripts/run_resource_picker_tests.sh`. See [TEST_TRACEABILITY.md — Resource Pickers](TEST_TRACEABILITY.md#resource-pickers-ux).

---

### Supporting Capabilities (Traceability)

Supporting capabilities (Notifications, Billing, Platform, Tenants, Users, Analytics, Events) are documented in [FEATURES.md](FEATURES.md#supporting-capabilities). They are not standalone product features; coverage is via the features that use them (Auth, BaaS, Marketplace, Governance, Audit, Webhooks, etc.). See [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#supporting-capabilities) for the mapping. **Platform app** (`hub/apps/platform/`): dedicated minimal unit tests in `hub/apps/platform/tests/test_views.py` (permission enforcement for platform tenant and user endpoints; Gap #2, task 1.5). No tests-by-design exemption; the app contains view-layer logic and delegates to tenants/gdpr services.

### Gap Remediation Coverage

Gap Remediation Plan phases (see [openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)) are reflected in this matrix as follows:

| Phase | Scope | Coverage in this matrix |
|-------|--------|-------------------------|
| 0 | Doc-only fixes (Versioning/Workflows/Observability notes; Supporting capabilities; transformation deferred) | Supporting capabilities table above; 29-feature list unchanged |
| 1 | Observability lineage API | Observability feature row (integration + lineage tests) |
| 2 | Versioning API | Versioning feature row (integration tests: `hub/apps/versioning/tests/`) |
| 3 | Workflows API | Workflows feature row (integration tests: `hub/apps/orchestration/tests/test_workflows_api_integration.py`) |
| 4 | Data preview & trust signals | Marketplace feature row (preview: `hub/apps/marketplace/tests/test_preview.py`; trust signals config API: `tests/integration/test_trust_signals_config_api_comprehensive.py`) |
| 5 | Transformation pipeline | Deferred; no implementation; deferred journeys/use cases in [USER_JOURNEYS.md](USER_JOURNEYS.md) / [USE_CASES.md](USE_CASES.md) |
| 6 | Feature list & traceability | This section; [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#gap-remediation-traceability) |
| **gapfix1** | Full Phase 12A-style test run, evidence collection, test summary report, sign-off | [TEST_TRACEABILITY.md — Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off); Phase 16 GR-7 (16.1–16.3) in [testreview1/tasks.md](../openspec/changes/testreview1/tasks.md); evidence layout `test_reports_comprehensive/{date}/`; report script `scripts/generate_test_summary_report.sh` |

**Gap implementation plan (gapfix1)** — Phase 12A execution, evidence layout, test summary report, and sign-off are defined and linked as follows:

- **Phase 12A execution**: Backend: `scripts/run_phase_12a_backend_suites.sh`. Full suite: `scripts/run_phase_12a_full_suites.sh` (backend → frontend unit/E2E → security, performance, concurrency, regression). Commands: [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md).
- **Evidence layout**: `test_reports_comprehensive/{date}/` with subdirs: unit, integration, e2e, security, performance, concurrency, regression, frontend-unit, frontend-e2e; summaries: `phase_12a_1_summary.json`, `phase_12a_3_summary.json`. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md).
- **Test summary report**: Generated by `scripts/generate_test_summary_report.sh` (gapfix1 Phase 7.4); includes pass/fail, duration, coverage, evidence links. Template: [TEST_SUMMARY_REPORT_TEMPLATE.md](TEST_SUMMARY_REPORT_TEMPLATE.md).
- **Sign-off**: [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md); Phase 16 (GR-7, 16.1–16.3) in [testreview1/tasks.md — Phase 16](../openspec/changes/testreview1/tasks.md#16-phase-16--gap-remediation-plan-data-interoperability-hub).
- **Links**: This change: [gapfix1 tasks](../openspec/changes/gapfix1/tasks.md); [openspec/changes/gapfix1](../openspec/changes/gapfix1). Full traceability: [TEST_TRACEABILITY.md — Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off).
- **Features covered by full test run** (appear in test summary report by feature/category): **(1) Scheduled Export** (feature #26; [FEATURES.md](FEATURES.md#scheduled-export); UC-EXPORT-001–004, JOURNEY-EXPORT-001–002). **(2) Trust signals config API** (Marketplace Phase 4; planned or implemented). **(3) §11→Phase 16** (GR-7 / 16.1–16.3: full run, report, sign-off).

**Scheduled Export and trust signals**: Scheduled Export (feature row 26) and trust signals config API (Marketplace, Phase 4) are fully traced in [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) (Feature → Test, Use Case, User Journey). See [Scheduled Export](#26-scheduled-export--complete) below and [TEST_TRACEABILITY.md — Scheduled Export](TEST_TRACEABILITY.md#scheduled-export), [Marketplace / trust signals](TEST_TRACEABILITY.md#marketplace).

**Phase 28.2 — Phases 10–19 (P1/P2) Test Coverage** (Task 28.2.2):

| Phase | Feature | Unit | Integration | E2E | Run Script |
|-------|---------|------|-------------|-----|------------|
| 10 | Admin user edit | `hub/apps/users/tests/test_views.py`, `test_admin_user_edit.py` (PUT/PATCH /api/v1/users/{id}/) | — | `JOURNEY-TA-002.spec.ts` (Manage Users; /admin), `admin-audit-settings-routes.spec.ts` (/admin; PA-009 Manage System Users) | `run_phase10_tests.sh` |
| 11 | Trust signals config | `test_tenant_me_views`, `test_services` | `test_trust_signals_config_api_comprehensive` | `JOURNEY-TA-TENANT-SETTINGS` (Phase 11) | `run_phase11_tests.sh` |
| 12 | Versioning config | `test_tenant_me_views`, `test_services`, `test_views` (datasets) | — | `JOURNEY-TA-TENANT-SETTINGS` (Phase 12) | `run_phase12_tests.sh` |
| 13 | GDPR export/erasure | `test_gdpr_views`, `test_gdpr_services` | `test_erasure_workflow_integration` | `JOURNEY-AUTH-PRIVACY` | `run_phase13_tests.sh` |
| 14 | Workflows config | `test_tenant_me_views`, `test_services`, `test_tenant_config_serializers`, `test_workflows_api_integration` | — | `JOURNEY-TA-TENANT-SETTINGS` (Phase 14) | `run_phase14_tests.sh` |
| 15 | Platform admin | `hub/apps/platform/tests/test_views`, `hub/apps/tenants/tests/test_views` | — | `JOURNEY-PA-015` | `run_phase15_tests.sh` |
| 16–19 | Tenant onboarding, change plan, cost tracking, gap docs | Per phase scripts | Per phase | Per phase | `run_phase16_tests.sh`, etc. |

**Unified run**: `./scripts/run_phase28_2_tests.sh` (Phases 11–15 backend + E2E). See [TEST_TRACEABILITY.md — useronboardfix Gap Coverage](TEST_TRACEABILITY.md#useronboardfix-gap-coverage-phases-7-17) (Phase 28.2 table).

Full phase-to-test mapping: [TEST_TRACEABILITY.md — Gap Remediation Traceability](TEST_TRACEABILITY.md#gap-remediation-traceability).

### Feature Coverage Details

#### 1. Auth ✅ Complete

**Unit Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Login, logout, token refresh
- `hub/apps/auth/tests/test_authorization.py` - Permission checks, RBAC
- `hub/apps/auth/tests/test_sessions.py` - Session management
- `hub/apps/auth/tests/test_register_me.py` - User registration
- `hub/apps/auth/tests/test_middleware.py` - Auth middleware

**Integration Tests**:
- `tests/integration/test_tenant_isolation.py` - Tenant isolation
- `tests/integration/test_auth_apis_comprehensive.py` - Auth API endpoints
- `tests/integration/test_api_endpoints_comprehensive.py` - API endpoints

**E2E Tests**:
- `tests/e2e/test_multi_tenant_isolation.py` - Multi-tenant isolation
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access

**Security Tests**:
- `tests/security/test_allowany_public_endpoints.py` - Public endpoints
- `tests/security/test_security_features.py` - Security features

**Performance Tests**:
- `tests/performance/locust_api_endpoints_availability.py` - Auth endpoints

#### 2. Contracts ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_views.py` - Contract CRUD
- `hub/apps/contracts/tests/test_services.py` - Contract services
- `hub/apps/contracts/tests/test_validation.py` - Contract validation
- `hub/apps/contracts/tests/test_odps_normalizer.py` - ODPS normalization
- `hub/apps/contracts/tests/test_ref_resolver.py` - Reference resolution

**Integration Tests**:
- `tests/integration/test_contract_apis_comprehensive.py` - Contract API endpoints
- `tests/integration/test_contract_management_original_use_cases_comprehensive.py` - Contract workflows
- `hub/apps/contracts/tests/test_lineage_service.py` - Lineage integration

**E2E Tests**:
- `tests/e2e/test_contract_first_comprehensive.py` - Contract-first flow
- `tests/e2e/test_contract_only_comprehensive.py` - Contract-only flow
- `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts` - Contract creation

**Security Tests**:
- `hub/apps/contracts/tests/security/test_ref_resolver_security.py` - Security
- `tests/security/penetration_test_odps_ref_resolver.py` - Penetration testing

**Performance Tests**:
- `tests/performance/locust_odps_ref_resolution.py` - Ref resolution performance

#### 3. ODPS ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py` - ODPS generation
- `hub/apps/contracts/tests/test_odps_normalizer.py` - ODPS normalization
- `hub/apps/contracts/tests/test_odps_metrics.py` - ODPS metrics

**Integration Tests**:
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation
- `hub/apps/orchestration/tests/test_odps_workflow_events.py` - Workflow events

**E2E Tests**:
- `tests/e2e/test_odps_journeys_comprehensive.py` - ODPS journeys
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - ODPS routes

**Security Tests**:
- `tests/security/penetration_test_odps_ref_resolver.py` - Security testing

**Performance Tests**:
- `tests/performance/locust_odps_ingestion.py` - ODPS ingestion performance
- `tests/performance/test_odps_export_performance.py` - Export performance

#### 4. Assets ✅ Complete

**Unit Tests**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset CRUD
- `hub/apps/assets/tests/test_data_first_asset_api.py` - Data-first API (POST /assets/data-first/)
- `hub/apps/assets/tests/test_services.py` - Asset services
- `hub/apps/assets/tests/test_asset_relationships.py` - Relationships
- `hub/apps/assets/tests/test_health_score.py` - Health score

**Integration Tests**:
- `tests/integration/test_asset_apis_comprehensive.py` - Asset API endpoints
- `tests/integration/test_asset_management_original_use_cases_comprehensive.py` - Asset workflows
- `tests/integration/test_cross_service_integration_comprehensive.py` - Service interactions
- `tests/integration/test_data_first_asset_flow.py` - Data-first flow (asset+dataset+contract)

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation, "I have data" redirect
- `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts` - Asset activation
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)

**Security Tests**:
- `tests/security/test_security_features.py` - Asset security
- `tests/security/test_data_first_asset_idor.py` - Data-first IDOR (cross-tenant file_id)

**Performance Tests**:
- `tests/performance/locust_api_endpoints_availability.py` - Asset endpoints

#### 5. Datasets ✅ Complete

**Unit Tests**:
- `hub/apps/datasets/tests/test_views.py` - Dataset views
- `hub/apps/datasets/tests/test_services.py` - Dataset services

**Integration Tests**:
- `tests/integration/test_dataset_apis_comprehensive.py` - Dataset API endpoints
- `tests/integration/test_database_operations_comprehensive.py` - Dataset workflows

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)
- `frontend/e2e/use-cases/ux/dataset-edit.spec.ts` - Dataset edit, link to asset (Phase 29.66.15)
- `frontend/e2e/use-cases/ux/asset-dataset-flow.spec.ts` - Asset → dataset → DQ flow (Phase 29.66.15)

**Security Tests**:
- `tests/security/test_security_features.py` - Dataset security

**Performance Tests**:
- `tests/performance/test_datasets_performance.py` - Datasets list P95 latency

#### 6. DQ ✅ Complete

**Unit Tests**:
- `hub/apps/dq/tests/test_views.py` - DQ views
- `hub/apps/dq/tests/test_service_client.py` - DQ service client

**Integration Tests**:
- `tests/integration/test_dq_apis_comprehensive.py` - DQ API endpoints
- `tests/integration/test_cross_service_integration_comprehensive.py` - DQ workflows

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - DQ checks in data-first flow
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - DQ routes

**Security Tests**:
- `tests/security/test_security_features.py` - DQ security

**Performance Tests**:
- `tests/performance/test_dq_performance.py` - DQ runs list P95 latency

#### 7. Compliance ✅ Complete

**Unit Tests**:
- `hub/apps/compliance/tests/test_views.py` - Compliance views
- `hub/apps/compliance/tests/test_services.py` - Compliance services

**Integration Tests**:
- `tests/integration/test_compliance_apis_comprehensive.py` - Compliance API endpoints
- `tests/integration/test_compliance_original_use_cases_comprehensive.py` - Compliance workflows

**E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Compliance journeys
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - Compliance routes

**Security Tests**:
- `tests/security/test_security_features.py` - Compliance security

**Performance Tests**:
- `tests/performance/test_compliance_performance.py` - Compliance runs list P95 latency

#### 8. Marketplace ✅ Complete

**Unit Tests**:
- `hub/apps/marketplace/tests/test_views.py` - Marketplace views
- `hub/apps/marketplace/tests/test_services.py` - Marketplace services
- `hub/apps/marketplace/tests/test_kyc_enforcement.py` - KYC enforcement

**Integration Tests**:
- `tests/integration/test_marketplace_integration.py` - Marketplace integration
- `tests/integration/test_trust_signals_config_api_comprehensive.py` - Trust signals config API (CRUD, tenant isolation)

**E2E Tests**:
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_marketplace_purchase_flow.py` - Purchase flow
- `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts` - Marketplace routes

**Security Tests**:
- `tests/security/test_marketplace_security.py` - Marketplace security

**Performance Tests**:
- `tests/performance/test_marketplace_performance.py` - Marketplace performance

#### 9. Governance ✅ Complete

**Unit Tests**:
- `hub/apps/governance/tests/test_access_request_views.py` - Access requests
- `hub/apps/governance/tests/test_retention_service.py` - Retention service

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Governance workflows

**E2E Tests**:
- `tests/e2e/test_governance_e2e.py` - Governance E2E
- `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts` - Retention CRUD

**Security Tests**:
- `tests/security/test_security_features.py` - Governance security

**Performance Tests**:
- `tests/performance/test_governance_performance.py` - Access requests list P95 latency

#### 10. Search ✅ Complete

**Unit Tests**:
- `hub/apps/search/tests/test_views.py` - Search views
- `hub/apps/search/tests/test_search_engine.py` - Search engine
- `hub/apps/search/tests/test_indexing.py` - Indexing

**Integration Tests**:
- `tests/integration/test_search_apis_comprehensive.py` - Search API endpoints
- `tests/integration/test_api_client_usage_search.py` - Search integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Search in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search routes

**Security Tests**:
- `tests/security/test_security_features.py` - Search security

**Performance Tests**:
- `tests/performance/test_search_performance.py` - Search performance

#### 11. Observability ✅ Complete

**Unit Tests**:
- `hub/apps/observability/tests/test_otel_metrics.py` - OpenTelemetry metrics
- `hub/apps/observability/tests/test_metrics.py` - Metrics

**Integration Tests**:
- `tests/integration/test_monitoring_infrastructure.py` - Monitoring infrastructure

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Observability in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Observability security

**Performance Tests**:
- `tests/performance/test_otel_metrics_performance.py` - Metrics performance

#### 12. Workflows ✅ Complete

**Unit Tests**:
- `hub/apps/orchestration/tests/test_workflow_engine.py` - Workflow engine
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Workflow integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Workflows in journeys
- `tests/e2e/test_workflow_user_journey_integration_e2e.py` - Workflow journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Workflow security

**Performance Tests**:
- `tests/performance/test_workflows_performance.py` - Workflows list P95 latency

#### 13. Lineage ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_lineage_service.py` - Lineage service
- `hub/apps/contracts/tests/test_lineage_traversal.py` - Lineage traversal
- `hub/apps/contracts/tests/test_lineage_visualization.py` - Lineage visualization

**Integration Tests**:
- `tests/integration/test_lineage_service_comprehensive_validation.py` - Lineage integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Lineage in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Lineage security

**Performance Tests**:
- `tests/performance/test_lineage_performance.py` - Lineage visualization P95 latency

#### 14. Versioning ✅ Complete

**Unit Tests**:
- `hub/apps/datasets/tests/test_versioning.py` - Dataset versioning

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Versioning integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Versioning in journeys

**Security Tests**:
- `tests/security/test_versioning_security.py` - Auth (401), tenant isolation (list, retrieve, compare)

**Performance Tests**:
- `tests/performance/test_versioning_performance.py` - Versions list P95 latency

#### 15. BaaS ✅ Complete

**Unit Tests**:
- `hub/apps/baas/tests/test_developer_portal.py` - Developer portal

**Integration Tests**:
- `hub/apps/baas/tests/test_integration.py` - BaaS integration
- `tests/integration/test_cross_service_integration_comprehensive.py` - BaaS service integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - BaaS in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - BaaS security

**Performance Tests**:
- `tests/performance/test_baas_cli_sdk_performance.py` - BaaS performance

#### 16. Integrations ✅ Complete

**Unit Tests**:
- `hub/apps/integrations/tests/test_views.py` - Integration views
- `hub/apps/integrations/tests/test_services.py` - Integration services
- `hub/apps/integrations/tests/test_gcp_marketplace_connector.py` - GCP connector

**Integration Tests**:
- `tests/integration/test_integrations.py` - Integration tests
- `hub/apps/integrations/tests/test_services_integration.py` - Service integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Integrations in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integration routes

**Security Tests**:
- `hub/apps/integrations/tests/test_gcp_marketplace_connector_security.py` - Connector security

**Performance Tests**:
- `tests/performance/test_integrations_performance.py` - Marketplace connections list P95 latency

#### 17. Jobs ✅ Complete

**Unit Tests**:
- `hub/apps/jobs/tests/test_job_creation_processing.py` - Job creation
- `hub/apps/jobs/tests/test_job_processors.py` - Job processors
- `hub/apps/jobs/tests/test_scheduled_ingestion_job.py` - Scheduled ingestion jobs

**Integration Tests**:
- `tests/integration/test_job_queue.py` - Job queue

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Jobs in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Job routes

**Security Tests**:
- `tests/security/test_security_features.py` - Job security

**Performance Tests**:
- `tests/performance/locust_job_queue_throughput.py` - Job queue performance

#### 18. Files ✅ Complete

**Unit Tests**:
- `hub/apps/files/tests/test_views.py` - File views
- `hub/apps/files/tests/test_services.py` - File services
- `hub/apps/files/tests/test_storage.py` - File storage

**Integration Tests**:
- `tests/integration/test_file_storage.py` - File storage integration

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - File upload in data-first flow
- `frontend/e2e/journeys/dpo/file-upload-flow.spec.ts` - File upload flow
- `frontend/e2e/use-cases/ux/files-upload.spec.ts` - Files page upload (Phase 29.66.15)

**Security Tests**:
- `tests/security/test_security_features.py` - File security

**Performance Tests**:
- `tests/performance/locust_file_upload_download.py` - File upload/download performance

#### 19. Semantic ✅ Complete

**Unit Tests**:
- `hub/apps/semantic/tests/test_models.py` - Semantic models
- `hub/apps/semantic/tests/test_uri_validators.py` - URI validators
- `hub/apps/semantic/tests/test_external_resource_sparql.py` - SPARQL endpoints

**Integration Tests**:
- `tests/integration/test_odps_semantic_layer_validation.py` - Semantic layer validation
- `tests/integration/test_normalization_rdf_flow.py` - Semantic RDF flow

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Semantic in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Semantic security

**Performance Tests**:
- `tests/performance/test_semantic_performance.py` - Semantic performance

#### 20. AI ✅ Complete

**Unit Tests**:
- `hub/apps/ai/tests/test_views.py` - AI views
- `hub/apps/ai/tests/test_llm_client.py` - LLM client

**Integration Tests**:
- `tests/integration/test_ai_ml_new_use_cases_comprehensive.py` - AI/ML integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - AI in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - AI routes

**Security Tests**:
- `tests/security/test_ai_security.py` - Auth (401), tenant isolation for natural-language search

**Performance Tests**:
- `tests/performance/test_ai_performance.py` - AI search P95 latency

#### 21. ML ✅ Complete

**Unit Tests**:
- `hub/apps/ml/tests/test_views.py` - ML views

**Integration Tests**:
- `tests/integration/test_ai_ml_new_use_cases_comprehensive.py` - ML integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - ML in journeys

**Security Tests**:
- `tests/security/test_ml_security.py` - Auth (401), tenant isolation for models list/retrieve

**Performance Tests**:
- `tests/performance/test_ml_performance.py` - ML models list P95 latency

#### 22. Social ⏳ Partial

**Unit Tests**:
- `hub/apps/social/tests/test_views.py` - Social views
- `hub/apps/social/tests/test_social_service.py` - Social service

**Integration Tests**:
- `hub/apps/social/tests/test_social_api_integration.py` - Social API integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Social in journeys
- `frontend/e2e/features/social.spec.ts` - Communities route, /social redirect to /communities, asset Community section (Phase 27.1–27.3)
- `frontend/e2e/journeys/dc/JOURNEY-DC-008.spec.ts`, `JOURNEY-DC-009.spec.ts` - Rate/review on asset page
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-009.spec.ts`, `JOURNEY-DPO-011.spec.ts`, `JOURNEY-DPO-012.spec.ts` - Asset Community section, data stewards, join community
- `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` through `JOURNEY-CM-004.spec.ts` - Community Manager journeys
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - /communities route

**Social embed (Phase 27)**: /social redirects to /communities; ratings, reviews, Community section on asset detail page (`/assets/:id`). Run: `./scripts/run_phase28_5_tests.sh`.

**Security Tests**:
- ⏳ Missing security tests for social

**Performance Tests**:
- `tests/performance/test_social_performance.py` - Social communities list P95 latency

#### 23. Data Mesh ⏳ Partial

**Unit Tests**:
- `hub/apps/mesh/tests/test_views.py` - Data mesh views
- `hub/apps/mesh/tests/test_services.py` - Data mesh services

**Integration Tests**:
- `tests/integration/test_data_mesh_new_use_cases_comprehensive.py` - Data mesh integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Data mesh in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Data mesh routes

**Security Tests**:
- ⏳ Missing security tests for data mesh

**Performance Tests**:
- `tests/performance/test_data_mesh_performance.py` - Mesh domains list P95 latency

#### 24. Virtualization ✅ Complete

**Unit Tests**:
- `hub/apps/virtualization/tests/test_views.py` - Virtualization views
- `hub/apps/virtualization/tests/test_services.py` - Virtualization services (incl. VirtualizationServiceODBCTest: host_only, database_only, connection_string_empty config validation)
- `hub/apps/virtualization/tests/test_execute_query.py` - Query execution

**Integration Tests**:
- `hub/apps/virtualization/tests/test_execute_query_integration.py` - Query integration
- `hub/apps/virtualization/tests/test_real_source_integration.py` - Real PostgreSQL, ODBC (host+database, connection_string), REST, SPARQL (Phase 20, 28.4.1)
- `hub/apps/virtualization/tests/test_virtualization_real_federated_e2e.py` - Federated E2E (Phase 21)

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Virtualization in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Virtualization routes
- `frontend/e2e/phase6-mesh-virtualization.spec.ts` - ODBC create via UI form (Host+Database), execute query (Phase 28.4.2)

**ODBC (Phase 28.4)**: Unit (config validation), integration (test_odbc_execute_against_hub_postgresql, test_odbc_execute_connection_string_mode), E2E (phase6-mesh-virtualization.spec.ts). Run: `./scripts/run_phase25_odbc_tests.sh`; E2E: `./scripts/e2e-detect-api.sh e2e/phase6-mesh-virtualization.spec.ts -g "ODBC"`.

**Security Tests**:
- `hub/apps/virtualization/tests/test_security.py` - Virtualization security

**Performance Tests**:
- `tests/performance/test_virtualization_performance.py` - Virtual datasets list P95 latency

#### 25. Scheduled Ingestion ✅ Complete

**Unit Tests**:
- `hub/apps/scheduled_ingestion/tests/test_views.py` - Scheduled ingestion views
- `hub/apps/scheduled_ingestion/tests/test_services.py` - Scheduled ingestion services
- `hub/apps/scheduled_ingestion/tests/test_ingestion.py` - Ingestion logic

**Integration Tests**:
- `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py` - Prefect integration
- `tests/integration/test_scheduled_ingestion_integration.py` - Scheduled ingestion integration

**E2E Tests**:
- `tests/e2e/test_scheduled_ingestion.py` - Scheduled ingestion E2E
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts` - Scheduled ingestion journey

**Security Tests**:
- `tests/security/test_security_features.py` - Scheduled ingestion security

**Performance Tests**:
- `tests/performance/test_scheduled_ingestion_performance.py` - Scheduled ingestion performance

#### 26. Scheduled Export ✅ Complete

**Behaviour covered**: List scheduled exports (tenant-scoped), filter by status (`?status=ACTIVE`), tenant isolation (list, retrieve, runs), CRUD, manual trigger, internal worker API. See USE_CASES.md UC-EXPORT-001–004.

**Unit Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Scheduled export views (list, filter by status, tenant isolation, CRUD, trigger, runs)
- `hub/apps/scheduled_export/tests/test_services.py` - Scheduled export services
- `hub/apps/scheduled_export/tests/test_models.py` - Scheduled export models

**Integration Tests**:
- `tests/integration/test_scheduled_export_apis_comprehensive.py` - Scheduled export APIs (CRUD, list and filter by status, tenant isolation, plan limits)

**Frontend Unit Tests**:
- `frontend/src/features/scheduledExport/services/scheduledExportService.test.ts` - Service (real; axios mocked)
- `frontend/src/features/scheduledExport/hooks/useScheduledExport.test.tsx` - Hooks (real; axios mocked)
- `frontend/src/features/scheduledExport/components/ScheduledExportListPage.test.tsx` - List page component

**E2E Tests**:
- `tests/e2e/test_scheduled_export.py` - Scheduled export E2E
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export journey

**Security Tests**:
- `tests/security/test_security_features.py` - Scheduled export security

**Performance Tests**:
- `tests/performance/test_scheduled_export_performance.py` - Scheduled export performance

#### 27. Webhooks ⏳ Partial

**Unit Tests**:
- `hub/apps/webhooks/tests/test_webhook_service.py` - Webhook service
- `hub/apps/webhooks/tests/test_webhook_api_integration.py` - Webhook API integration

**Integration Tests**:
- `tests/integration/run_webhook_payloads_tests.py` - Webhook payloads
- `tests/integration/test_webhook_payloads_and_events_search.py` - Webhook events

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Webhooks in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Webhook routes

**Security Tests**:
- `tests/security/test_security_features.py` - Webhook security

**Performance Tests**:
- `tests/performance/test_webhooks_performance.py` - Webhooks list P95 latency

#### 28. Audit ✅ Complete

**Unit Tests**:
- `hub/apps/audit/tests/test_audit_event_querying.py` - Audit event querying
- `hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py` - ODPS audit validation
- `hub/apps/audit/tests/test_views.py` - Audit views

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Audit integration

**E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Audit journeys
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit routes

**Security Tests**:
- `tests/security/test_security_features.py` - Audit security

**Performance Tests**:
- `tests/performance/test_audit_performance.py` - Audit events list P95 latency

#### 29. Health ✅ Complete

**Unit Tests**:
- `hub/apps/health/tests/test_views.py` - Health views
- `hub/apps/health/tests/test_services.py` - Health services

**Integration Tests**:
- `tests/integration/test_service_availability_comprehensive.py` - Health and service availability

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Health in journeys

**Security Tests**:
- `tests/security/test_health_security.py` - Public endpoints; no sensitive data in /health/, /health/live/, /health/circuit-breakers/

**Performance Tests**:
- `tests/performance/test_health_performance.py` - Health check P95 latency

---

## Use Case Coverage Matrix

### Use Case Categories

| Category | Total Use Cases | Unit Tests | Integration Tests | E2E Tests | Overall Status |
|----------|----------------|-----------|------------------|----------|----------------|
| Authentication & Access | 4 | ✅ | ✅ | ✅ | ✅ Complete |
| Asset Management | ~8 | ✅ | ✅ | ✅ | ✅ Complete |
| Contract Management | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Data Quality | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Compliance | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Marketplace | ~8 | ✅ | ✅ | ✅ | ✅ Complete |
| AI/ML | ~10 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Social Features | ~6 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Data Mesh | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Virtualization | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| Advanced Marketplace | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Advanced Governance | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Advanced Observability | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Integration Ecosystem | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Developer Experience | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Transformation | ~8 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Lineage | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Versioning | ~3 | ✅ | ✅ | ⏳ | ⏳ Partial |
| BaaS | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| ODH Integration | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| ODPS | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Semantic | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| Scheduled Ingestion | ~3 | ✅ | ✅ | ✅ | ✅ Complete |
| Webhooks | ~3 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Audit | ~3 | ✅ | ✅ | ✅ | ✅ Complete |

**Total Use Cases**: ~109

### Use Case Coverage Statistics

- **Complete Coverage**: ~50 use cases (46%)
- **Partial Coverage**: ~59 use cases (54%)
- **Missing Coverage**: 0 use cases (0%)

### Detailed Use Case Coverage

#### Authentication & Access Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AUTH-001 | User Registers | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-002 | User Logs In | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-003 | User Resets Password | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-005 | User Switches Active Tenant | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/auth/tests/test_register_me.py`, `hub/apps/auth/tests/test_authentication.py`, `hub/apps/auth/tests/test_authorization.py`, `hub/apps/auth/tests/test_sessions.py`, `hub/apps/auth/tests/test_middleware.py`
- Integration: `tests/integration/test_auth_apis_comprehensive.py`, `tests/integration/test_api_endpoints_comprehensive.py`, `tests/integration/test_tenant_isolation.py`, `tests/integration/test_tenant_switch_integration.py`
- E2E: `tests/e2e/test_multi_tenant_isolation.py`, `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` through `JOURNEY-AUTH-004.spec.ts`, `frontend/e2e/use-cases/auth/tenant-switch.spec.ts`

#### Asset Management Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AM-001 | Create Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-002 | Update Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-003 | Delete Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-004 | List Assets | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-005 | Get Asset Details | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-006 | Link Asset to Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-007 | Activate Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-008 | Deactivate Asset | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/assets/tests/test_asset_crud.py`, `hub/apps/assets/tests/test_services.py`, `hub/apps/assets/tests/test_asset_relationships.py`, `hub/apps/assets/tests/test_health_score.py`
- Integration: `tests/integration/test_asset_apis_comprehensive.py`, `tests/integration/test_asset_management_original_use_cases_comprehensive.py`, `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_data_first_comprehensive.py`, `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts`, `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts`

#### Contract Management Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-CM-001 | Create Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-002 | Validate Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-003 | Normalize Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-004 | Convert Contract Format | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-005 | Link Contract to Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-006 | Get Contract Lineage | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/contracts/tests/test_views.py`, `hub/apps/contracts/tests/test_services.py`, `hub/apps/contracts/tests/test_validation.py`, `hub/apps/contracts/tests/test_odps_normalizer.py`, `hub/apps/contracts/tests/test_ref_resolver.py`
- Integration: `tests/integration/test_contract_apis_comprehensive.py`, `tests/integration/test_contract_management_original_use_cases_comprehensive.py`, `hub/apps/contracts/tests/test_lineage_service.py`
- E2E: `tests/e2e/test_contract_first_comprehensive.py`, `tests/e2e/test_contract_only_comprehensive.py`, `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts`

#### Data Quality Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-DQ-001 | Run Data Quality Check | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-002 | Get Data Quality Results | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-003 | Configure Data Quality Rules | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-004 | Monitor Data Quality Metrics | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-005 | Remediate Data Quality Issues | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-006 | Get Data Quality History | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/dq/tests/test_views.py`, `hub/apps/dq/tests/test_service_client.py`
- Integration: `tests/integration/test_dq_apis_comprehensive.py`, `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_data_first_comprehensive.py`, `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts`

#### Compliance Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-COMP-001 | Run Compliance Scan | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-002 | Get Compliance Results | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-003 | Configure Compliance Rules | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-004 | Generate Compliance Report | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-005 | Monitor Compliance Status | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-006 | Remediate Compliance Issues | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/compliance/tests/test_views.py`, `hub/apps/compliance/tests/test_services.py`
- Integration: `tests/integration/test_compliance_apis_comprehensive.py`, `tests/integration/test_compliance_original_use_cases_comprehensive.py`
- E2E: `tests/e2e/test_audit_compliance_journeys.py`, `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts`

#### Marketplace Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-MKT-001 | Publish Asset to Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-002 | Browse Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-003 | Search Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-004 | Purchase Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-005 | Access Purchased Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-006 | Manage Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-007 | Review Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-008 | Rate Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/marketplace/tests/test_views.py`, `hub/apps/marketplace/tests/test_services.py`, `hub/apps/marketplace/tests/test_kyc_enforcement.py`, `hub/apps/marketplace/tests/test_business_rules.py`
- Integration: `tests/integration/test_marketplace_apis_comprehensive.py`, `tests/integration/test_marketplace_original_use_cases_comprehensive.py`, `tests/integration/test_advanced_marketplace_new_use_cases_comprehensive.py`
- E2E: `tests/e2e/test_marketplace_comprehensive.py`, `tests/e2e/test_marketplace_purchase_flow.py`, `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts`

#### ODPS Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-ODPS-001 | Create ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-002 | Link ODPS to Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-003 | Export ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-004 | Import ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-005 | Update ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-006 | Get ODPS Product Details | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py`, `hub/apps/contracts/tests/test_odps_normalizer.py`
- Integration: `hub/apps/orchestration/tests/test_product_creation_workflow.py`
- E2E: `tests/e2e/test_odps_journeys_comprehensive.py`, `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts`

#### Scheduled Ingestion Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-SI-001 | Create Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |
| UC-SI-002 | Execute Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |
| UC-SI-003 | Monitor Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/scheduled_ingestion/tests/test_views.py`, `hub/apps/scheduled_ingestion/tests/test_services.py`
- Integration: `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py`
- E2E: `tests/e2e/test_scheduled_ingestion.py`, `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts`

#### Scheduled Export Use Cases ✅ Complete

Use case IDs and titles aligned with [USE_CASES.md](USE_CASES.md#category-scheduled-export--data-operations).

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-EXPORT-001 | Schedule Recurring Export | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-002 | Configure Export Destination | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-003 | Monitor Export Runs | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-004 | Manual Trigger of Scheduled Export | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/scheduled_export/tests/test_views.py`, `hub/apps/scheduled_export/tests/test_services.py`
- Integration: `tests/integration/test_scheduled_export_apis_comprehensive.py`
- E2E: `tests/e2e/test_scheduled_export.py`, `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts`

#### Audit Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AUDIT-001 | Query Audit Events | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUDIT-002 | Generate Audit Report | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUDIT-003 | Monitor Audit Logs | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/audit/tests/test_audit_event_querying.py`, `hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py`, `hub/apps/audit/tests/test_views.py`
- Integration: `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_audit_compliance_journeys.py`, `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts`

---

## User Journey Coverage Matrix

### All 96 User Journeys

| Persona | Total Journeys | Backend E2E | Frontend E2E | Overall Status |
|---------|----------------|------------|-------------|----------------|
| Visitor / Authentication | 4 | ✅ | ✅ | ✅ Complete |
| Data Product Owner | 17 | ✅ | ✅ | ✅ Complete |
| Data Engineer | 14 | ✅ | ✅ | ✅ Complete |
| Compliance Officer | 10 | ✅ | ✅ | ✅ Complete |
| Data Consumer | 15 | ✅ | ✅ | ✅ Complete |
| Tenant Admin | 8 | ✅ | ✅ | ✅ Complete |
| Platform Admin | 10 | ✅ | ✅ | ✅ Complete |
| External Developer | 9 | ✅ | ✅ | ✅ Complete |
| Auditor | 6 | ✅ | ✅ | ✅ Complete |
| Data Scientist | 5 | ✅ | ✅ | ✅ Complete |
| Data Analyst | 4 | ✅ | ✅ | ✅ Complete |
| Community Manager | 4 | ✅ | ✅ | ✅ Complete |
| Data Mesh Domain Owner | 5 | ✅ | ✅ | ✅ Complete |

**Total**: 96 journeys

### Journey Coverage Statistics

- **Complete Coverage**: 88 journeys (92%)
- **Partial Coverage**: 8 journeys (8%)
- **Missing Coverage**: 0 journeys (0%)

### Detailed Journey Coverage

#### Visitor / Authentication Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-002 | User Logs In | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-003 | User Resets Password | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_multi_tenant_isolation.py` - Multi-tenant isolation
- `tests/integration/test_tenant_isolation.py` - Tenant isolation

**Frontend E2E Tests**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access

#### Data Product Owner Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DPO-001 | Create Data Product (Data-First) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-002 | Create Data Product (Contract-First) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-003 | Create Data Product (Contract-Only) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-004 | Activate Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-005 | Link Contract to Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-006 | Publish to Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-007 | Manage Marketplace Listing | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-008 | Update Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-009 | Version Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-010 | Monitor Data Product Health | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-011 | Configure Data Quality Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-012 | Generate Compliance Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-013 | Manage Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-014 | Configure Retention Policies | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-015 | Create ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-016 | Export ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-017 | Link ODPS to Contract | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `tests/e2e/test_contract_first_comprehensive.py` - Contract-first flow
- `tests/e2e/test_contract_only_comprehensive.py` - Contract-only flow
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_odps_journeys_comprehensive.py` - ODPS journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts` - Data-first
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts` - Contract-first
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation
- `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts` - Contract creation
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)
- `frontend/e2e/journeys/dpo/file-upload-flow.spec.ts` - File upload
- `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts` - Asset activation

#### Data Engineer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DE-001 | Create Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-002 | Validate Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-003 | Normalize Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-004 | Create Transformation Pipeline | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-005 | Execute Transformation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-006 | Monitor Transformation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-007 | Create Scheduled Ingestion | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-008 | Monitor Scheduled Ingestion | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-009 | Create Scheduled Export | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-010 | Monitor Scheduled Export | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-011 | Configure Data Quality Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-012 | View Data Lineage | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-013 | Create Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-014 | Create ODPS Product | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_contract_first_comprehensive.py` - Contract workflows
- `tests/e2e/test_scheduled_ingestion.py` - Scheduled ingestion
- `tests/e2e/test_scheduled_export.py` - Scheduled export
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - Contracts/ODPS
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts` - Scheduled ingestion
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integrations/jobs

#### Compliance Officer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-CPO-001 | Run Compliance Scan | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-002 | View Compliance Results | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-003 | Generate Compliance Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-004 | Configure Compliance Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-005 | Monitor Compliance Status | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-006 | Remediate Compliance Issues | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-007 | Review Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-008 | Approve Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-009 | Configure Retention Policies | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-010 | View Audit Logs | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Compliance journeys
- `tests/e2e/test_data_first_comprehensive.py` - Compliance in data-first flow

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - Compliance routes
- `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts` - Retention policies
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit settings

#### Data Consumer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DC-001 | Browse Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-002 | Search Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-003 | View Asset Details | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-004 | Purchase Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-005 | Access Purchased Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-006 | Search Data Catalog | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-007 | Request Access to Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-008 | View Data Lineage | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-009 | View Data Quality Metrics | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-010 | Download Data | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-011 | Query Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-012 | View Asset Versions | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-013 | Rate Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-014 | Import ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-015 | Use ODPS Product | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_marketplace_purchase_flow.py` - Purchase flow
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts` - Marketplace routes
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search/virtualization

#### Tenant Admin Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-TA-001 | Invite User | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-002 | Manage Users | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-003 | Configure Tenant Settings | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-004 | View Tenant Usage | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-005 | Manage Tenant Subscriptions | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-006 | Configure Tenant Limits | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-007 | View Tenant Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-008 | Manage Tenant Integrations | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_phase25_tenant_onboarding_e2e.py` - Tenant onboarding
- `tests/integration/test_tenant_onboarding_service_comprehensive_validation.py` - Tenant onboarding validation

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Admin settings

#### Platform Admin Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-PA-001 | Manage All Tenants | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-002 | Configure Platform Settings | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-003 | View Platform Metrics | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-004 | Manage Platform Integrations | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-005 | View Platform Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-006 | Manage Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-007 | Configure Rate Limits | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-008 | Monitor System Health | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-009 | Manage System Users | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-010 | Export Platform Data | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys
- `tests/integration/test_monitoring_infrastructure.py` - Monitoring

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Admin settings

#### External Developer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DEV-001 | Access Developer Portal | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-002 | Create API Key | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-003 | Use SDK | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-004 | Use CLI | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-005 | Search API Documentation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-006 | Create Webhook Subscription | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-007 | Monitor Webhook Deliveries | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-008 | Integrate with External System | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-009 | Test Integration | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys
- `cli/tests/integration/test_phase26_cli_integration.py` - CLI integration
- `sdk/python/tests/test_phase26_sdk_integration.py` - SDK integration

**Frontend E2E Tests**:
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integrations/webhooks

#### Auditor Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-AUD-001 | Query Audit Events | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-002 | Generate Audit Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-003 | View Compliance Reports | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-004 | Monitor Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-005 | Export Audit Data | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-006 | Analyze Audit Trends | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Audit journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit settings

#### Data Scientist Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DS-001 | Search Data Catalog | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-002 | Access ML Datasets | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-003 | Create ML Model | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-004 | Train ML Model | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-005 | Deploy ML Model | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/ds/JOURNEY-DS-001.spec.ts` … `JOURNEY-DS-005.spec.ts` (test2 Phase 3)

#### Data Analyst Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DA-001 | Search Data Catalog | ✅ | ✅ | ✅ Complete (deferred) |
| JOURNEY-DA-002 | Query Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DA-003 | Create Data Visualization | ✅ | ✅ | ✅ Complete |
| JOURNEY-DA-004 | Export Data for Analysis | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/da/JOURNEY-DA-001.spec.ts` … `JOURNEY-DA-004.spec.ts` (test2 Phase 3; DA-001 deferred)

#### Community Manager Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-CM-001 | Manage Community | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-002 | Moderate Content | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-003 | View Community Analytics | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-004 | Configure Community Settings | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` … `JOURNEY-CM-004.spec.ts` (test2 Phase 3)

#### Data Mesh Domain Owner Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DMO-001 | Create Data Mesh Domain | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-002 | Configure Federated Governance | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-003 | Manage Domain Topology | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-004 | Transfer Asset Ownership | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-005 | Monitor Domain Health | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dmo/JOURNEY-DMO-001.spec.ts` … `JOURNEY-DMO-005.spec.ts` (test2 Phase 3)

---

## Persona Coverage Matrix

### All 13 Personas

| # | Persona | Journey Coverage | Test Coverage | Overall Status |
|---|---------|------------------|--------------|----------------|
| 0 | Visitor / Prospect | ✅ | ✅ | ✅ Complete |
| 1 | Data Product Owner | ✅ | ✅ | ✅ Complete |
| 2 | Data Engineer | ✅ | ✅ | ✅ Complete |
| 3 | Compliance Officer | ✅ | ✅ | ✅ Complete |
| 4 | Data Consumer | ✅ | ✅ | ✅ Complete |
| 5 | Tenant Admin | ✅ | ✅ | ✅ Complete |
| 6 | Platform Admin | ✅ | ✅ | ✅ Complete |
| 7 | External Developer | ✅ | ✅ | ✅ Complete |
| 8 | Auditor | ✅ | ✅ | ✅ Complete |
| 9 | Data Scientist | ✅ | ✅ | ✅ Complete |
| 10 | Data Analyst | ✅ | ✅ | ✅ Complete |
| 11 | Community Manager | ✅ | ✅ | ✅ Complete |
| 12 | Data Mesh Domain Owner | ✅ | ✅ | ✅ Complete |

### Persona Coverage Statistics

- **Complete Coverage**: 13 personas (100%)
- **Partial Coverage**: 0 personas (0%)
- **Missing Coverage**: 0 personas (0%)

### Detailed Persona Coverage

#### Persona 0: Visitor / Prospect ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- JOURNEY-AUTH-001 ✅
- JOURNEY-AUTH-002 ✅
- JOURNEY-AUTH-003 ✅
- JOURNEY-AUTH-004 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/auth/tests/test_*.py`, `tests/integration/test_tenant_isolation.py`
- Frontend: `frontend/e2e/journeys/auth/JOURNEY-AUTH-*.spec.ts`

#### Persona 1: Data Product Owner ✅ Complete

**Journey Coverage**: 17/17 journeys (100%)
- All JOURNEY-DPO-001 through JOURNEY-DPO-017 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/assets/tests/test_*.py`, `hub/apps/contracts/tests/test_*.py`, `tests/e2e/test_data_first_comprehensive.py`
- Frontend: `frontend/e2e/journeys/dpo/*.spec.ts`

#### Persona 2: Data Engineer ✅ Complete

**Journey Coverage**: 14/14 journeys (100%)
- All JOURNEY-DE-001 through JOURNEY-DE-014 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/contracts/tests/test_*.py`, `hub/apps/scheduled_ingestion/tests/test_*.py`, `tests/e2e/test_contract_first_comprehensive.py`
- Frontend: `frontend/e2e/journeys/contracts-odps/*.spec.ts`, `frontend/e2e/journeys/scheduled-ingestion/*.spec.ts`

#### Persona 3: Compliance Officer ✅ Complete

**Journey Coverage**: 10/10 journeys (100%)
- All JOURNEY-CPO-001 through JOURNEY-CPO-010 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/compliance/tests/test_*.py`, `tests/e2e/test_audit_compliance_journeys.py`
- Frontend: `frontend/e2e/journeys/dq-compliance-governance/*.spec.ts`, `frontend/e2e/journeys/governance-retention/*.spec.ts`

#### Persona 4: Data Consumer ✅ Complete

**Journey Coverage**: 15/15 journeys (100%)
- All JOURNEY-DC-001 through JOURNEY-DC-015 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/marketplace/tests/test_*.py`, `tests/e2e/test_marketplace_comprehensive.py`
- Frontend: `frontend/e2e/journeys/marketplace-dc/*.spec.ts`

#### Persona 5: Tenant Admin ✅ Complete

**Journey Coverage**: 8/8 journeys (100%)
- All JOURNEY-TA-001 through JOURNEY-TA-008 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/tenants/tests/test_*.py`, `tests/e2e/test_phase25_tenant_onboarding_e2e.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 6: Platform Admin ✅ Complete

**Journey Coverage**: 10/10 journeys (100%)
- All JOURNEY-PA-001 through JOURNEY-PA-010 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `tests/e2e/test_complete_user_journeys.py`, `tests/integration/test_monitoring_infrastructure.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 7: External Developer ✅ Complete

**Journey Coverage**: 9/9 journeys (100%)
- All JOURNEY-DEV-001 through JOURNEY-DEV-009 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `cli/tests/integration/test_phase26_cli_integration.py`, `sdk/python/tests/test_phase26_sdk_integration.py`
- Frontend: `frontend/e2e/journeys/integrations-jobs-webhooks/*.spec.ts`

#### Persona 8: Auditor ✅ Complete

**Journey Coverage**: 6/6 journeys (100%)
- All JOURNEY-AUD-001 through JOURNEY-AUD-006 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/audit/tests/test_*.py`, `tests/e2e/test_audit_compliance_journeys.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 9: Data Scientist ✅ Complete

**Journey Coverage**: 5/5 journeys (100%)
- All JOURNEY-DS-001 through JOURNEY-DS-005 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/ml/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/ds/JOURNEY-DS-001.spec.ts` … `JOURNEY-DS-005.spec.ts`

#### Persona 10: Data Analyst ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- All JOURNEY-DA-001 through JOURNEY-DA-004 ✅ (DA-001 deferred)

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/da/JOURNEY-DA-001.spec.ts` … `JOURNEY-DA-004.spec.ts`

#### Persona 11: Community Manager ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- All JOURNEY-CM-001 through JOURNEY-CM-004 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/social/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` … `JOURNEY-CM-004.spec.ts`

#### Persona 12: Data Mesh Domain Owner ✅ Complete

**Journey Coverage**: 5/5 journeys (100%)
- All JOURNEY-DMO-001 through JOURNEY-DMO-005 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/mesh/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/dmo/JOURNEY-DMO-001.spec.ts` … `JOURNEY-DMO-005.spec.ts`

---

## UC/Journey/Persona E2E Coverage (Task 6.7)

Backend E2E tests with `uc_journey_persona` marker form a canonical subset for UC-, journey-, and persona-tagged validation. Run via `./scripts/run_uc_journey_persona_tests.sh` or `pytest tests/e2e/ -v -m uc_journey_persona`. See [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md).

| Dimension | Coverage | Status |
|-----------|----------|--------|
| **Test files** | 17 backend E2E files | ✅ Complete |
| **Use cases** | UC-AUTH-001…005, UC-AM-001, UC-CM-001, UC-MKT-001, UC-MKT-002, UC-DC-001, UC-DQ-001, UC-COMP-001 | ✅ Covered |
| **Journeys** | JOURNEY-AUTH-001…005, JOURNEY-DPO-001…017, JOURNEY-DE-001…014, JOURNEY-CPO-001…010, JOURNEY-DC-001…015, JOURNEY-TA-001…008, JOURNEY-PA-001, JOURNEY-MPA-001…009, JOURNEY-DEV-001…009, JOURNEY-AUD-001…006, JOURNEY-ODPS-001…005 | ✅ Covered |
| **Personas** | Visitor, Data Product Owner, Data Engineer, Compliance Officer, Data Consumer, Tenant Admin, Platform Admin, Marketplace Platform Admin, External Developer, Auditor | ✅ Covered |
| **Phase 12A** | 12A.1.3b in `run_phase_12a_backend_suites.sh`; artifacts in `test_reports_comprehensive/{date}/uc_journey_persona/` | ✅ Integrated |
| **Report** | `generate_test_summary_report.py` includes uc_journey_persona category | ✅ Integrated |

**Test files**: `tests/e2e/test_authentication.py`, `test_persona_dpo_comprehensive.py`, `test_persona_data_engineer_comprehensive.py`, `test_persona_cpo_comprehensive.py`, `test_persona_dc_comprehensive.py`, `test_persona_ta_comprehensive.py`, `test_persona_pa_comprehensive.py`, `test_persona_dev_comprehensive.py`, `test_persona_aud_comprehensive.py`, `test_user_journeys_comprehensive.py`, `test_new_user_journeys_comprehensive.py`, `test_persona_failure_paths_comprehensive.py`, `test_enhanced_journeys_with_odps.py`, `test_enhanced_use_cases_with_odps.py`, `test_workflow_use_case_integration_e2e.py`, `test_workflow_user_journey_integration_e2e.py`, `test_odps_journeys_comprehensive.py`.

---

## Coverage Status Summary

### Overall Coverage Statistics

| Category | Total | Complete | Partial | Missing | Coverage % |
|----------|-------|----------|---------|---------|------------|
| Features | 29 | 13 | 16 | 0 | 100% (45% complete, 55% partial) |
| Use Cases | ~109 | ~50 | ~59 | 0 | 100% (46% complete, 54% partial) |
| User Journeys | 96 | 88 | 8 | 0 | 100% (92% complete, 8% partial) |
| Personas | 13 | 13 | 0 | 0 | 100% (100% complete) |

### Test Type Coverage

| Test Type | Features Covered | Use Cases Covered | Journeys Covered | Status |
|-----------|-----------------|------------------|------------------|--------|
| Unit Tests | 29/29 (100%) | ~109/~109 (100%) | N/A | ✅ Complete |
| Integration Tests | 29/29 (100%) | ~109/~109 (100%) | N/A | ✅ Complete |
| E2E Tests (Backend) | 29/29 (100%) | ~109/~109 (100%) | 96/96 (100%) | ✅ Complete |
| E2E Tests (Frontend) | 29/29 (100%) | ~109/~109 (100%) | 88/96 (92%) | ⏳ Partial |
| Security Tests | 29/29 (100%) | ~95/~109 (87%) | N/A | ✅ Complete |
| Performance Tests | 29/29 (100%) | ~50/~109 (46%) | N/A | ✅ Complete |

---

## Coverage Gaps and Recommendations

### Feature Coverage Gaps

#### High Priority Gaps

1. ~~**Performance Tests Missing** (16 features)~~ — **RESOLVED** (test2 Phase 1):
   - ~~Datasets, DQ, Compliance, Governance, Workflows, Lineage, Versioning, Integrations, AI, ML, Social, Data Mesh, Virtualization, Webhooks, Audit, Health~~
   - **Status**: All 16 features now have performance tests in `tests/performance/test_*_performance.py` (P95 latency assertions; no mocks/stubs). Run with `pytest tests/performance/ -v -m performance`.

2. ~~**Security Tests Missing** (4 features)~~ — **RESOLVED** (test2 Phase 2):
   - ~~Versioning, AI, ML, Health~~
   - **Status**: All 4 features now have security tests in `tests/security/test_versioning_security.py`, `test_ai_security.py`, `test_ml_security.py`, `test_health_security.py`.

#### Medium Priority Gaps

1. ~~**Frontend E2E Tests Missing** (4 personas)~~ — **RESOLVED** (test2 Phase 3):
   - ~~Data Scientist, Data Analyst, Community Manager, Data Mesh Domain Owner~~
   - **Status**: All 4 personas now have frontend E2E specs in `frontend/e2e/journeys/ds/`, `da/`, `cm/`, `dmo/`. 62 passed, 2 skipped (DA-001 deferred).

### Use Case Coverage Gaps

#### High Priority Gaps

1. **E2E Tests Missing** (~59 use cases):
   - AI/ML use cases (~10)
   - Social Features use cases (~6)
   - Data Mesh use cases (~5)
   - Advanced Marketplace use cases (~5)
   - Advanced Governance use cases (~4)
   - Advanced Observability use cases (~4)
   - Integration Ecosystem use cases (~5)
   - Developer Experience use cases (~4)
   - Transformation use cases (~8)
   - Lineage use cases (~4)
   - Versioning use cases (~3)
   - ODH Integration use cases (~4)
   - Webhooks use cases (~3)
   - **Recommendation**: Create E2E tests for all use cases, prioritizing critical paths

### User Journey Coverage Gaps

#### High Priority Gaps

1. ~~**Frontend E2E Tests Missing** (8 journeys)~~ — **RESOLVED** (test2 Phase 3):
   - ~~Data Scientist (5), Data Analyst (4), Community Manager (4), Data Mesh Domain Owner (5)~~
   - **Status**: Specs exist and pass; run with `npm run test:e2e -- e2e/journeys/ds/ da/ cm/ dmo/`

### Persona Coverage Gaps

#### High Priority Gaps

1. ~~**Frontend E2E Tests Missing** (4 personas)~~ — **RESOLVED** (test2 Phase 3)

### Recommendations Summary

1. **Immediate Actions**:
   - ~~Create performance test suites for 16 features missing performance tests~~ ✅ Done (test2 Phase 1)
   - ~~Add security tests for 4 features missing security tests~~ ✅ Done (test2 Phase 2)
   - Create frontend E2E tests for 8 missing journeys

2. **Short-Term Actions**:
   - Create E2E tests for ~59 use cases missing E2E coverage
   - Enhance existing test coverage for partial features

3. **Long-Term Actions**:
   - Achieve 100% complete coverage for all features
   - Achieve 100% complete coverage for all use cases
   - Achieve 100% complete coverage for all journeys
   - Achieve 100% complete coverage for all personas

---

## Related Documents

- **[COMPREHENSIVE_TEST_PLAN.md](COMPREHENSIVE_TEST_PLAN.md)** - Complete test plan documentation
- **[TEST_TRACEABILITY.md](TEST_TRACEABILITY.md)** - Detailed test traceability matrix (includes [Gap Remediation Traceability](TEST_TRACEABILITY.md#gap-remediation-traceability) and [Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off))
- **[TEST_SCENARIO_MATRIX.md](TEST_SCENARIO_MATRIX.md)** - Scenario coverage per feature (Success, Failure 400/401/403/404/429, Edge empty/max/special chars); coverage gaps visible per feature; integrated with traceability report
- **[FEATURES.md](FEATURES.md)** - Complete feature documentation (29 features + [Supporting capabilities](FEATURES.md#supporting-capabilities))
- **[openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)** - Gap Remediation Plan (phases 0–6; §11 validation and sign-off)
- **[openspec/changes/gapfix1](../openspec/changes/gapfix1)** - Gap implementation plan (full Phase 12A test run, evidence, test summary report, sign-off); [gapfix1 tasks.md](../openspec/changes/gapfix1/tasks.md); [gapfix1 proposal.md](../openspec/changes/gapfix1/proposal.md)
- **[USE_CASES.md](USE_CASES.md)** - Complete use case documentation (~109 use cases)
- **[USER_JOURNEYS.md](USER_JOURNEYS.md)** - Complete user journey documentation (96 journeys)
- **[USER_PERSONAS.md](USER_PERSONAS.md)** - Complete persona documentation (13 personas)

---

**Document Status**: ✅ Complete
**Last Updated**: 2026-03-22
**Next Steps**: Address coverage gaps per [TEST_COVERAGE_EXPANSION_PLAN.md](TEST_COVERAGE_EXPANSION_PLAN.md) — Immediate (performance, security, frontend E2E), Short-term (E2E use cases), Long-term (100% coverage). UC/Journey/Persona E2E: [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md).

---

# E2E Environment Requirements

**Last Updated**: 2026-03-22
**Task**: Phase 7.1.2 — Services per test group, health checks, availability detection
**Related**: [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md), [DOCKER_COMPOSE_DEPLOYMENT.md](DOCKER_COMPOSE_DEPLOYMENT.md)

---

## Overview

This document lists services required per E2E test group, how to detect their availability, and health check procedures. Use it to determine which services must be running before a test run and when tests may skip due to optional service unavailability.

---

## 1. Test Groups and Service Requirements

### 1.1 Core Test Group (Required for All E2E)

These services **must** be running. If any is unavailable, E2E tests will fail (not skip). Do not run E2E without them.

| Service | Compose Service Name | Default Host Port | Health Check | Detection |
|---------|---------------------|------------------|---------------|-----------|
| **API** | `api-service-test` | 8001 | `GET /health/` → 200 | `curl -s http://localhost:8001/health/` |
| **PostgreSQL** | `postgres-test` | 5434 | `pg_isready -U hub_test -d hub_test` | `pg_isready -h localhost -p 5434 -U hub_test -d hub_test` |
| **Redis (Cache)** | `redis-cache-test` | 6379 | `redis-cli ping` | `redis-cli -h localhost -p 6379 ping` |
| **Redis (Queue)** | `redis-queue-test` | 6380 | `redis-cli ping` | `redis-cli -h localhost -p 6380 ping` |
| **MinIO** | `minio-test` | 9010 (API), 9011 (Console) | `GET http://localhost:9010/minio/health/live` | `curl -sf http://localhost:9010/minio/health/live` |

**Environment Variables** (override defaults):

- `API_BASE_URL` / `E2E_API_BASE_URL` / `VITE_API_BASE_URL` — API base (e.g. `http://localhost:8001/api/v1` for test stack)
- `POSTGRES_TEST_PORT`, `REDIS_CACHE_TEST_PORT`, `MINIO_TEST_API_PORT` — Port overrides

**Start Command**:

```bash
docker compose -f docker-compose.test.yml up -d postgres-test redis-cache-test redis-queue-test redis-events-test redis-channels-test minio-test api-service-test
```

---

### 1.2 Optional Services (Tests May Skip If Unavailable)

Some E2E tests require additional services. If unavailable, tests skip with a clear reason (see [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md)).

| Service | Compose Service Name | Default Host Port | Health Check | Used By |
|---------|---------------------|------------------|---------------|---------|
| **Prefect** (server, db, worker, integration) | `prefect-db-test`, `prefect-server-test`, `prefect-worker-test`, `prefect-integration-service-test` | 4202 (server), 8114 (integration) | `GET http://localhost:8114/health` | `scheduled-ingestion-journey.spec.ts`, `scheduled-export-journey.spec.ts` |
| **MailHog** | `mailhog-test` | 8025 (UI/API), 1025 (SMTP) | `GET http://localhost:8025/api/v2/messages?limit=1` | `JOURNEY-AUTH-003.spec.ts`, `auth-visitor-journeys.spec.ts` (password reset) |
| **AI/ML (ODH Inference Scheduler)** | `odh-inference-scheduler-test` | 8080 | `GET http://localhost:8080/health` | `hub/apps/ml/tests/test_inference_real_integration.py` |

**Start Commands**:

```bash
# Prefect (scheduled ingestion/export)

docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test

# MailHog (password reset E2E)

docker compose -f docker-compose.test.yml up -d mailhog-test

# AI/ML (ODH Inference Scheduler)

docker compose -f docker-compose.test.yml up -d odh-inference-scheduler-test odh-training-operator-test
```

**Environment Variables**:

- `PREFECT_INTEGRATION_SERVICE_URL` — Prefect integration service URL (default: `http://localhost:8084`; host: `http://localhost:8114` when using docker-compose.test.yml)
- `MAILHOG_URL` — MailHog API URL (default: `http://localhost:8025`)
- `ODH_INFERENCE_SCHEDULER_URL` — ODH Inference Scheduler URL (default: `http://odh-inference-scheduler-test:8080` in Docker)

---

## 2. Health Checks

### 2.1 Scripted Health Checks

Use the health check scripts before running E2E:

```bash
# E2E test stack (recommended — checks core services only)

./scripts/health-checks/health-check-e2e.sh

# Or explicitly:

COMPOSE_FILE=docker-compose.test.yml ./scripts/health-checks/health-check-e2e.sh
```

**Alternative** — full stack with `health-check-all.sh` (uses main compose by default; for test stack, set `COMPOSE_FILE` or `ENVIRONMENT=test`; note: service names differ between compose files):

```bash
COMPOSE_FILE=docker-compose.test.yml ./scripts/health-checks/health-check-all.sh
```

**Note**: `health-check-e2e.sh` is designed for the test stack and checks `postgres-test`, `redis-cache-test`, `minio-test`, `api-service-test`. The `health_check_lib.sh` respects explicit `COMPOSE_FILE` and supports `ENVIRONMENT=test` → `docker-compose.test.yml`.

### 2.2 Manual Health Checks

| Service | Check Command |
|---------|---------------|
| API | `curl -s http://localhost:8001/health/` |
| PostgreSQL | `pg_isready -h localhost -p 5434 -U hub_test -d hub_test` |
| Redis | `redis-cli -h localhost -p 6379 ping` |
| MinIO | `curl -sf http://localhost:9010/minio/health/live` |
| Prefect Integration | `curl -sf http://localhost:8114/health` |
| MailHog | `curl -sf http://localhost:8025/api/v2/messages?limit=1` |
| ODH Inference Scheduler | `curl -sf http://localhost:8080/health` |

### 2.3 How to Detect Availability

**In tests** (Playwright / pytest):

- **ConnectionRefused, Timeout, ConnectTimeout**: Transient — service not running or unreachable. Skip with clear reason.
- **Wrong URL, malformed response, 4xx/5xx from health endpoint**: Non-transient — configuration or service bug. Re-raise; do not skip.
- **Health endpoint returns 200**: Service available; proceed.

**Example (Playwright)**:

```typescript
let healthOk = false;
try {
  const res = await fetch(`${PREFECT_INTEGRATION_URL}/health`, { signal: AbortSignal.timeout(5000) });
  healthOk = res.ok;
} catch (e) {
  // ConnectionRefused, Timeout, etc. → skip
  test.skip(true, `Prefect not reachable: ${e}. Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`);
}
if (!healthOk) {
  test.skip(true, `Prefect unhealthy. Start: docker compose -f docker-compose.test.yml up -d ...`);
}
```

---

## 3. Test Group → Service Mapping

| Test Group | Core Services | Optional Services |
|------------|---------------|-------------------|
| Backend E2E (pytest) | API, Postgres, Redis, MinIO | Prefect (scheduled ingestion/export), ODH (ML inference) |
| Frontend E2E (Playwright) | API, Postgres, Redis, MinIO | Prefect, MailHog |
| Auth journeys (JOURNEY-AUTH-001, JOURNEY-AUTH-004) | Core | — |
| Auth password reset (JOURNEY-AUTH-003) | Core | MailHog |
| Scheduled ingestion/export | Core | Prefect |
| ML inference integration | Core | ODH Inference Scheduler |

---

## 4. Compose File Reference

| File | Purpose | API Port |
|------|---------|----------|
| `docker-compose.yml` | Production-style full stack | 8000 |
| `docker-compose.dev.yml` | Development with hot-reload | 8000 |
| `docker-compose.test.yml` | Test stack (isolated DB) | 8001 |

---

## 5. E2E User Setup

Before running frontend E2E, ensure E2E user roles exist:

```bash
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles
```

If this is not run, tests that require TA, PA, CPO, AUD, DEV, or DMO roles may redirect to login or fail.

---

## 6. Pytest Markers (Test Requirements Discoverability)

Use these markers to discover which tests require which services. See `pytest.ini` and `tests/e2e/conftest.py`.

| Marker | Service | Behavior When Unavailable | Used By |
|--------|---------|---------------------------|---------|
| `@pytest.mark.requires_minio` | MinIO/S3 | Skip (fixture `require_minio`) | Backend E2E file upload tests |
| `@pytest.mark.requires_prefect` | Prefect (server, worker, integration) | Fail (Phase 7.4.3) | `scheduled-ingestion-journey.spec.ts`, `scheduled-export-journey.spec.ts`, backend scheduled ingestion/export |
| `@pytest.mark.requires_mailhog` | MailHog | Skip (Phase 7.4.4) | `JOURNEY-AUTH-003.spec.ts`, `auth-visitor-journeys.spec.ts` (password reset) |

**Usage**:

```bash
# Run only tests that require MinIO
pytest -m requires_minio

# Exclude tests that require Prefect (e.g. when Prefect not started)
pytest -m "not requires_prefect"

# Exclude tests that require MailHog
pytest -m "not requires_mailhog"
```

**Note**: Playwright E2E tests use runtime checks (not pytest markers). The markers above apply to backend pytest E2E. Frontend test requirements are documented in [E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md).

### 6.1 Optional: Core vs Optional CI Job Separation

For CI optimization, tests can be split into:

- **Core job** (strict, required services only): `pytest -m "not requires_prefect and not requires_mailhog"` — runs with API, Postgres, Redis, MinIO. Fails fast when core stack is down.
- **Optional job** (Prefect, MailHog): `pytest -m "requires_prefect or requires_mailhog"` — runs when optional services are started. Can be a separate CI job or run in parallel.

See [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) for current CI structure.

---

## 7. References

- [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md) — When to skip vs fail
- [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md) — Skip conventions
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution order, CI
- [frontend/e2e/README.md](../frontend/e2e/README.md) — Frontend E2E setup
- [pytest.ini](../pytest.ini) — Marker definitions

---

# E2E Test Semantics

**Last Updated**: 2026-03-22
**Task**: Phase 7.1.1 — Canonical definition of test semantics for E2E tests
**Related**: [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md), [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md), [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md)

---

## Overview

This document defines the canonical semantics for E2E tests across backend (pytest) and frontend (Playwright). All E2E tests fall into one of three categories: **strict**, **environment-dependent**, or **deferred**. These rules ensure tests fail when they should and skip only when justified.

---

## 1. Strict Tests (Single Expected Outcome)

**Definition**: Tests that have exactly one expected outcome. The test must **fail** if the actual outcome differs.

### Rules

- Use `assertEqual` (or equivalent) for single expected values.
- Do **not** use `assertIn` with multiple allowed values unless the API contract explicitly allows multiple statuses (see [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md)).
- Security tests (e.g., unauthenticated access to protected endpoints) must assert the single expected status (e.g., `401`).
- Validation tests must assert the single expected status (e.g., `400` for invalid input); never accept `500` as valid for validation errors.
- When a required precondition fails (e.g., API unreachable, DB down), the test must **fail** (throw/re-raise), not skip.

### Examples

```python
# Backend: strict — single expected outcome
self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

# Backend: validation error — only 400 is valid
self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

```typescript
// Frontend: strict — single expected outcome
expect(response.status()).toBe(401);
```

---

## 2. Environment-Dependent Tests (Skip Only When Required Service Unavailable)

**Definition**: Tests that require an optional service (Prefect, MailHog, AI/ML, etc.). Skip **only** when the required service is demonstrably unavailable, with a clear, actionable reason.

### Rules

- Skip **only** when the required service is unavailable (connection refused, timeout, health check fails).
- The skip reason must include:
  - Which service is missing
  - How to start it (e.g., `docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test ...`)
  - A reference to [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) if applicable
- Do **not** skip for:
  - Precondition failures that indicate a bug (e.g., `createAssetViaApi` returns no assets due to API/tenant mismatch)
  - Wrong URL, malformed response, or other non-transient errors
- Use `test.skip(condition, reason)` at **describe level** when the entire spec depends on an optional service and the service is checked once at the start.
- For transient errors only (ConnectionRefused, Timeout, ConnectTimeout): skip with a clear reason. For other exceptions (wrong URL, malformed response): re-raise.

### Examples

```typescript
// Frontend: environment-dependent — skip when Prefect unavailable
test.beforeEach(async () => {
  const healthRes = await fetch(`${PREFECT_INTEGRATION_URL}/health`);
  if (!healthRes.ok) {
    test.skip(
      true,
      `Prefect integration service unhealthy (${healthRes.status}). Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
    );
  }
});
```

```python
# Backend: environment-dependent — skip when MinIO unavailable
if not minio_available:
    pytest.skip("MinIO service not available - skipping file upload test. Start: docker compose -f docker-compose.test.yml up -d minio-test")
```

### Precondition Failures → Fail, Not Skip

When a **required** precondition fails (e.g., API should be up, assets should exist after `createAssetViaApi`), the test must **fail** (throw), not skip. Skipping hides real bugs.

| Scenario | Action | Rationale |
|----------|--------|-----------|
| `createAssetViaApi` returns no assets (API/tenant mismatch) | **Fail** (throw) | Indicates setup or API bug |
| Prefect for scheduled ingestion/export journeys | **Fail** (throw) | Required for that journey; fail when unreachable (Phase 7.4.3) |
| Prefect for other optional flows | **Skip** (with reason) | Optional service unavailable |
| MailHog not reachable for password reset | **Skip** (with reason) | Optional service for that flow |
| Login redirect when roles not set up | **Fail** (throw) | Required setup missing; run `ensure_e2e_user_roles` |
| File in API but not visible in UI after retries | **Skip** (with reason) | Timing/cache; optional to verify |

---

## 3. Deferred Tests (test.skip for Intentionally Unimplemented Features)

**Definition**: Tests for features that are **intentionally not yet implemented** (backlog, deferred). Use `test.skip` or `test.describe.skip` with a documented reason.

### Rules

- Use `test.skip('reason')` or `test.describe.skip('reason')` for deferred journeys/features.
- The skip reason must include:
  - UC ID and/or JOURNEY ID
  - Short description of what is missing
  - Reference to backlog/spec (e.g., `docs/BACKLOG_TRANSFORMATION_PIPELINE.md`)
- Deferred tests are **never** run until the feature is implemented; they are placeholders for traceability.
- Do **not** use `test.skip(true, reason)` for deferred tests — use `test.skip(reason)` (condition = always skip).

### Examples

```typescript
// Frontend: deferred — transformation pipeline not implemented
test.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', async ({ page }) => {
  // Deferred: Transformation pipeline backend not implemented.
  // See: docs/USER_JOURNEYS.md, docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

```typescript
// Frontend: deferred — entire spec
test.describe.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', () => {
  // Deferred: UC-TRANS-001, JOURNEY-DPO-008 — Transformation pipeline not implemented.
  // Backlog: docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

---

## 4. Summary Table

| Test Type | When to Use | Skip Allowed? | Fail When |
|-----------|-------------|---------------|-----------|
| **Strict** | Single expected outcome | No | Actual ≠ expected; required precondition fails |
| **Environment-dependent** | Optional service required | Yes, only when service unavailable | Wrong URL, malformed response, non-transient errors |
| **Deferred** | Feature not implemented | Always skipped | N/A (never runs) |

---

## 5. Anti-Patterns (Do Not Use)

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| `test.skip(true, 'No assets after createAssetViaApi')` for precondition failure | **Fail** (throw) with clear error; fix root cause |
| `assertIn(response.status_code, [200, 401])` for auth test | Use `assertEqual(401)` — auth bypass is a bug |
| `assertIn(response.status_code, [400, 500])` for validation test | Use `assertEqual(400)` — 500 indicates server bug |
| `except: pytest.skip(...)` for any exception | Only skip on ConnectionRefused, Timeout, ConnectTimeout; re-raise others |
| S3 fallback to mock when MinIO fails | When real S3 required: re-raise; no silent fallback |
| `.catch(() => false)` or `.catch(() => null)` hiding failures | Propagate failures; handle optional steps explicitly |

---

## 6. When Multiple Status Codes Are Valid

When the API contract allows multiple valid statuses (e.g. 200/202 for async, 200/503 for health), document the case in [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) Section 2 and add a one-line comment at the assertion. See [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) for the full list of intentional multi-status cases.

---

## 7. References

- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Services per test group, health checks
- [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) — assertIn vs assertEqual, multi-status cases
- [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md) — Skip conventions, deferred journeys
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution order, CI integration

---

# Post-Deploy Test Strategy

> Defines what tests run after each deployment and how to verify success.
> Updated: 2026-03-21 | Phase 112.M.4

## Strategy Summary

| Environment | Tests Run | Trigger | Rollback |
|-------------|-----------|---------|----------|
| Staging | T12 smoke only | Automatic on push to `main` | Automatic on failure |
| Production | T12 smoke + manual T5 security | Manual via tag/workflow_dispatch | Automatic on smoke failure |

## T12 — Smoke Tests (Automatic)

Run by `.github/workflows/deploy.yml` after every deployment:

```bash
pytest tests/smoke/ --base-url="${SMOKE_BASE_URL}" -v --timeout=60
```

**9 test files** covering:
- API health + readiness (`test_api_health.py`, `test_health.py`)
- Authentication flow (`test_auth.py`)
- Core CRUD (`test_dataset_crud.py`)
- Compliance service (`test_compliance.py`)
- Prefect integration (`test_prefect_integration.py`)
- Job queue (`test_job_queue.py`)
- Expanded deployment paths (`test_deployment_smoke.py`)

**On failure**: automatic `helm rollback` to previous revision.

**Evidence**: `smoke-results.xml` uploaded as GitHub artifact (30-day retention).

## T5 — Security Spot-Check (Manual, Production Only)

After production deploy, run security tests against the live endpoint:

```bash
pytest tests/security/ --base-url="${PROD_URL}" -v --timeout=120
```

Covers: IDOR, auth bypass, tenant isolation, injection, SSRF guard.

**When to run**: after every production deploy, before announcing GA.

## Observability Verification (T13)

After deploy, verify observability stack:

```bash
# Prometheus scrape working
curl -s ${BASE_URL}/metrics/ | head -5

# Structured logs flowing
kubectl logs -n <ns> deploy/hub-api --tail=5 | jq .level

# Jaeger traces (if enabled)
curl -s http://jaeger:16686/api/traces?service=hub-api&limit=1
```

## Staging Checklist (M.3)

Before first staging deploy, verify:

- [ ] DNS records created for staging hostnames
- [ ] TLS certificate provisioned (cert-manager or manual)
- [ ] Placeholder hostnames in `helm/values.staging.yaml` replaced with real domains
- [ ] Vault KV paths populated (`secret/hub/staging/`)
- [ ] ExternalSecret sync healthy (`kubectl get externalsecret -n hub-staging`)
- [ ] S3 bucket created and accessible
- [ ] Prefect Server deployed (if scheduled ingestion required)

See `docs/operator-external-setup-checklist.md` for full details.

## Evidence Bundle

After successful deploy + smoke tests, the following artifacts constitute
the evidence bundle for release sign-off:

| Artifact | Source | Retention |
|----------|--------|-----------|
| `smoke-results.xml` | deploy.yml smoke job | 30 days (GitHub) |
| Helm release revision | `helm history hub -n <ns>` | In-cluster |
| Container image SHA | `kubectl get deploy -o jsonpath` | In registry |
| CI run URL | GitHub Actions link | Permanent |

---

# Security Test Coverage Matrix

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Overview

This document provides a comprehensive matrix of **service × vulnerability × test file** for the Data Interoperability Hub security test suite. All tests use real implementations (no mocks/stubs except at external boundaries per project policy).

**Related**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md), [RUNBOOKS.md — Security suite](RUNBOOKS.md#security-suite-phase-12a3), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md).

---

## Table of Contents

1. [Vulnerability Categories](#vulnerability-categories)
2. [Service × Vulnerability × Test File Matrix](#service--vulnerability--test-file-matrix)
3. [Test Execution](#test-execution)
4. [CI Integration](#ci-integration)

---

## Vulnerability Categories

| ID | Category | Description |
|----|----------|-------------|
| IDOR | Insecure Direct Object Reference | Cross-tenant access to resources by ID |
| AUTH | Authentication | Unauthenticated access, 401 enforcement |
| INJ | Injection | SQL injection, command injection, path traversal, XSS |
| TENANT | Tenant Isolation | Cross-tenant data leakage, membership validation |
| SECRETS | Secrets & Config | Production secrets, credential exposure |
| HEADERS | Security Headers | CSP, XSS protection, CSRF, forged gateway headers |
| RATE | Rate Limiting | Abuse prevention, rate limit enforcement |
| ODPS | ODPS $ref Security | URL validation, path traversal, SSRF, size/timeout limits |

---

## Service × Vulnerability × Test File Matrix

| Service | Vulnerability | Test File | Notes |
|---------|---------------|-----------|-------|
| **API (general)** | AUTH, HEADERS | `tests/security/test_allowany_public_endpoints.py` | Public endpoints return only public data; no sensitive leakage |
| **API (general)** | HEADERS | `tests/security/test_security_features.py` | CSRF, password hashing, session, JWT, API key, permissions, SQL injection prevention, input validation, security headers |
| **API (general)** | HEADERS | `tests/security/test_security_features_enhanced.py` | CSP, XSS prevention, output encoding, email security, security headers |
| **API (general)** | HEADERS | `tests/security/test_gateway_headers_forged.py` | Forged gateway headers do not override auth; middleware ignores forged headers |
| **API (general)** | SECRETS | `tests/security/test_production_secrets.py` | Production fails on dev default SECRET_KEY/JWT_SECRET_KEY |
| **Auth** | AUTH, TENANT | `tests/security/test_tenant_switch_security.py` | Switch tenant without membership → 403; X-Tenant-Id without membership → 403 |
| **Auth** | AUTH | `tests/security/test_vulnerability_security.py` | Token rotation, PATCH /me cannot set tenant_id/is_platform_admin, SSO redirect validation, login timing |
| **Auth** | TENANT | `tests/security/test_personal_tenant_security.py` | Personal tenant isolation, rate limits, slug collision info not leaked |
| **Users** | TENANT, AUTH | `tests/security/test_admin_user_edit_security.py` | Tenant admin cannot edit other-tenant user; regular user cannot edit any user |
| **Assets** | IDOR | `tests/security/test_idor.py` | Asset, audit retrieve cross-tenant → 403/404 |
| **Assets** | IDOR | `tests/security/test_data_first_asset_idor.py` | Data-first cross-tenant file_id → 403/404 |
| **Contracts** | AUTH, IDOR | `tests/security/test_datacontract_security.py` | Contracts list/create/retrieve unauthenticated → 401; cross-tenant retrieve → 403/404 |
| **Contracts** | IDOR | `tests/security/test_idor_contracts.py` | Contract retrieve cross-tenant → 403/404 |
| **Contracts (ODPS)** | ODPS | `hub/apps/contracts/tests/security/test_ref_resolver_security.py` | URL validation, path traversal, rate limiting, size/timeout, audit |
| **Contracts (ODPS)** | ODPS | `tests/security/penetration_test_odps_ref_resolver.py` | Path traversal, URL injection (SSRF/XSS), rate/size bypass attempts |
| **Datasets** | IDOR | `tests/security/test_idor_datasets.py` | Dataset retrieve cross-tenant; list asset_id filter tenant isolation |
| **Data Quality** | AUTH, IDOR | `tests/security/test_dq_security.py` | DQ runs list/retrieve unauthenticated → 401; tenant isolation |
| **Data Quality** | IDOR | `tests/security/test_idor_dq.py` | DQ run retrieve cross-tenant → 403/404 |
| **Compliance** | AUTH, IDOR | `tests/security/test_compliance_security.py` | Compliance runs list/retrieve unauthenticated → 401; tenant isolation |
| **Compliance** | IDOR | `tests/security/test_idor_compliance.py` | Compliance run retrieve cross-tenant → 403/404 |
| **Governance** | IDOR | `tests/security/test_idor_governance.py` | Access request retrieve cross-tenant → 403/404 |
| **Webhooks** | AUTH, IDOR | `tests/security/test_webhook_security.py` | Webhooks list/retrieve unauthenticated → 401; tenant isolation |
| **Webhooks** | IDOR | `tests/security/test_idor_webhooks.py` | Webhook retrieve cross-tenant → 403/404 |
| **Scheduled Ingestion/Export** | IDOR | `tests/security/test_idor_scheduled.py` | Scheduled ingestion/export retrieve cross-tenant → 403/404 |
| **Jobs** | IDOR | `tests/security/test_idor_jobs.py` | Job retrieve cross-tenant → 403/404 |
| **Marketplace** | IDOR | `tests/security/test_idor_marketplace.py` | Listing retrieve cross-tenant → 403/404 |
| **Marketplace** | INJ, TENANT, SECRETS, RATE | `tests/security/test_marketplace_security.py` | Connector auth, tenant isolation, SQL/XSS/path/command injection, credential encryption, rate limiting |
| **Search** | AUTH, TENANT | `tests/security/test_search_security.py` | Search unauthenticated → 401; tenant isolation |
| **Search** | INJ | `tests/security/test_injection_search.py` | SQL-like query/type/tags params |
| **Virtualization** | INJ | `tests/security/test_injection_virtualization.py` | Virtual datasets list SQL-like search/ordering/status |
| **Files** | AUTH, INJ, TENANT | `tests/security/test_files_security.py` | Unauthenticated list → 401; path traversal, disallowed file type, tenant isolation |
| **Health** | AUTH, HEADERS | `tests/security/test_health_security.py` | Liveness/health unauthenticated OK; no sensitive data in response |
| **Versioning** | AUTH, IDOR | `tests/security/test_versioning_security.py` | Versioning list/retrieve/compare unauthenticated → 401; cross-tenant → 404 |
| **AI** | AUTH, TENANT | `tests/security/test_ai_security.py` | Natural language search, schema matching unauthenticated → 401; tenant isolation |
| **ML** | AUTH, IDOR | `tests/security/test_ml_security.py` | ML models list unauthenticated → 401; retrieve cross-tenant → 404 |
| **Data Mesh** | AUTH, IDOR | `tests/security/test_data_mesh_security.py` | Mesh domains list unauthenticated → 401; retrieve cross-tenant → 404 |
| **Social** | AUTH, IDOR | `tests/security/test_social_security.py` | Ratings/communities unauthenticated → 401; rating cross-tenant → 403/404 |
| **Phase 25 (SaaS)** | TENANT, AUTH, SECRETS | `tests/security/test_phase25_security.py` | Billing tenant isolation, tenant suspend/usage PA-only, erasure user-only, Stripe webhook signature, worker API key/tenant isolation |
| **Audit, Assets, etc.** | INJ | `tests/security/test_injection.py` | Audit/contracts/assets/datasets/marketplace SQL-like params; health command injection |
| **Cross-tenant** | IDOR | `tests/security/test_security_fixtures.py` | two_tenant_setup cross-tenant IDOR validation |

---

## Test Execution

### Full Security Suite

```bash
# Run tests/security/ (pytest)
pytest tests/security/ -v --tb=short --junit-xml=security-test-results.xml

# Run ODPS ref resolver security (Django test)
cd hub && python manage.py test hub.apps.contracts.tests.security.test_ref_resolver_security --verbosity=2 --failfast

# Run ODPS ref resolver penetration tests
cd hub && python manage.py test tests.security.penetration_test_odps_ref_resolver --verbosity=2 --failfast
```

**Target duration**: <10 minutes for full security suite (tests/security/ + ODPS ref resolver + penetration).

**Validation script**: `./scripts/run_validation_29_7.sh --security` runs the full security suite (tests/security/ + ODPS ref resolver + penetration) and asserts <10 min.

### Via Phase 12A Script

```bash
./scripts/run_phase_12a_full_suites.sh
```

Security runs as Phase 12A.3.1; artifacts under `test_reports_comprehensive/{date}/security/`.

---

## CI Integration

| CI Job | Command | Artifacts |
|--------|---------|-----------|
| `test-security` | `pytest tests/security/ -v --tb=short --junit-xml=security-test-results.xml` | `security-test-results-suite-{run_id}` (JUnit XML) |
| `test-odps-ref-resolver-security` | `python manage.py test hub.apps.contracts.tests.security.test_ref_resolver_security` + `tests.security.penetration_test_odps_ref_resolver` | `security-test-results-{run_id}` (JUnit XML) |
| `test` (main) | Includes ODPS ref resolver + penetration in backend phase | `test-results-{run_id}-py{version}` (includes e2e, unit, integration) |

**Artifact retention**: 30 days.

---

## Maintenance

Update this matrix when:
1. New security tests are added
2. New services or vulnerability categories are introduced
3. Test files are renamed or reorganized

**Update frequency**: After each security-related change or phase completion.

---

# Contract Test Design

This document describes the API contract testing approach: schema baseline, breaking-change rules, CI integration, and how to update the baseline for intentional API changes.

## 1. Overview

Contract tests ensure that API changes do not break existing consumers. The **current** OpenAPI schema (generated by drf-spectacular from the Django codebase) is compared against a **baseline** schema stored in version control. CI fails if the current schema introduces breaking changes relative to the baseline.

- **Baseline:** `docs/api/openapi-baseline.json` (generated once, then committed; updated only when we intentionally change the API).
- **Current:** Generated at CI time (and locally) using the same pipeline as the runtime schema (SchemaGenerator + validation + enhancement).
- **Comparison:** Script `scripts/contract_test_openapi.py` compares current vs baseline and exits with non-zero on breaking changes. The baseline is validated for required structure (`openapi`, `paths`) after load.

## 2. Schema Baseline

- **Location:** `docs/api/openapi-baseline.json`
- **Format:** OpenAPI 3.x JSON, same structure as the schema served at `/api-docs/openapi.json` and `/api/v1/openapi.json`.
- **Generation:** Use the same code path as runtime and CI:
  - `drf_spectacular.generators.SchemaGenerator` with `hub.urls`
  - Validation via `hub.apps.api.openapi_validation.OpenAPISpecValidator`
  - Enhancement via `hub.apps.api.openapi_validation.OpenAPISpecValidator.enhance_spec` and `hub.apps.api.openapi_enhancement.OpenAPISpecEnhancer.enhance_spec`
- **Creating/updating the baseline:** See [Section 5. Updating the baseline](#5-updating-the-baseline).

## 3. Breaking vs Non-Breaking Rules

### 3.1 Breaking (CI must fail)

| Rule | Description |
|------|-------------|
| **Removed endpoint** | A path + HTTP method present in the baseline is missing in the current schema. |
| **Removed required field** | For a given path + method, a property that was in `required` in the baseline (request body or response schema) is no longer required or is missing in the current schema. |
| **Renamed required field** | A required field present in the baseline is missing in the current schema for the same operation (treated as removal). |
| **Type change** | A property that exists in both baseline and current has a different `type` (e.g. `string` → `number`, or `array` → `object`). |

Comparison is done after resolving `$ref` from `components/schemas` so that request/response bodies that reference shared schemas are compared correctly.

### 3.2 Non-breaking (allowed)

| Change | Description |
|--------|-------------|
| **New endpoint** | New path or new HTTP method on an existing path. |
| **New optional field** | New property added to a schema without adding it to `required`. |
| **New required field** | Adding a new property and listing it in `required` (additive; may break strict clients but is often acceptable; can be tightened in policy if needed). |
| **New schema** | New entry in `components/schemas`. |
| **Documentation / description changes** | Changes to `description`, `example`, or similar metadata. |

## 4. CI Integration

- **Job name:** `contract-test` (or similar) in `.github/workflows/ci.yml`.
- **Steps:**
  1. Checkout code.
  2. Set up Python and install dependencies (e.g. `requirements.txt`, `requirements-dev.txt`).
  3. Set `DJANGO_SETTINGS_MODULE` and `PYTHONPATH`.
  4. Run: `python scripts/contract_test_openapi.py`
- **Behavior:** The script generates the current schema (in memory or to a temp file), loads `docs/api/openapi-baseline.json`, runs the comparison, and:
  - **Exit 0:** No breaking changes (new endpoints/optional fields allowed).
  - **Exit 1:** Breaking changes detected; script prints a list of violations.
- **Artifact on failure:** The CI job runs the script with `--write-current openapi-current.json`. When the contract test fails, the script writes the current schema to that file before exiting; a follow-up step uploads it as artifact `openapi-current-on-contract-failure` for debugging.

## 5. Updating the baseline

When you **intentionally** change the API (e.g. remove an endpoint, change a type, or rename a field):

1. **Implement the code change** (views, serializers, etc.).
2. **Regenerate the baseline** so it matches the new intended contract:
   ```bash
   python scripts/contract_test_openapi.py --update-baseline
   ```
   This overwrites `docs/api/openapi-baseline.json` with the current generated schema.
3. **Commit both** the code change and the updated `docs/api/openapi-baseline.json`.
4. **Document in the PR** that the baseline was updated intentionally and why (e.g. "Deprecated GET /api/v1/old/ removed; baseline updated.").

If the baseline file is missing (e.g. first run), run with `--update-baseline` once to create it, then commit.

The repository may ship with a **minimal baseline** (e.g. empty `paths`) so that CI passes until the team locks the API. To lock the current API as the contract, run `python scripts/contract_test_openapi.py --update-baseline` with Django and dependencies installed, then commit `docs/api/openapi-baseline.json`.

## 6. Run commands summary

| Action | Command |
|--------|--------|
| Run contract test (CI / local) | `python scripts/contract_test_openapi.py` |
| Run and write current schema on failure (e.g. CI) | `python scripts/contract_test_openapi.py --write-current openapi-current.json` |
| Generate or update baseline | `python scripts/contract_test_openapi.py --update-baseline` |
| Generate schema only (e.g. to inspect) | `python scripts/regenerate-openapi-spec.py` (writes to `docs/api-audit/`); or use `--update-baseline` and then inspect `docs/api/openapi-baseline.json` |

## 7. References

- **DEVELOPMENT_GUIDE:** Service and API consistency (e.g. Phase 24.7).
- **OpenAPI 3.0:** https://spec.openapis.org/oas/v3.0.3
- **drf-spectacular:** https://drf-spectacular.readthedocs.io/
- **Schema generation:** `hub/apps/api/views.py` (OpenAPISchemaView), `scripts/regenerate-openapi-spec.py`, `hub/apps/api/openapi_validation.py`, `hub/apps/api/openapi_enhancement.py`
