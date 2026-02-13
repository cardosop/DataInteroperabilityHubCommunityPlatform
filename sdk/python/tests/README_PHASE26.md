# Phase 26 SDK Integration Tests

## Overview

Integration tests for Phase 26 SDK methods using real backend API (no mocks/stubs).

## Prerequisites

1. **Backend Running**: DataHub backend must be running and accessible
2. **Environment Variables**:
   - `HUB_BASE_URL`: Backend API URL (default: `http://localhost:8000/api/v1`)
   - `DATAHUB_API_KEY`: Valid API key for authentication

## Setup

```bash
# Set environment variables
export HUB_BASE_URL=http://localhost:8000/api/v1
export DATAHUB_API_KEY=your-api-key-here

# Install SDK dependencies
cd sdk/python
pip install -e .

# Run tests
pytest tests/test_phase26_sdk_integration.py -v
```

## Test Structure

Tests are organized by SDK module:
- `TestScheduledExportSDK` - Scheduled export methods
- `TestBillingSDK` - Billing methods (Phase 25)
- `TestTenantsSDK` - Tenants methods (Phase 25)
- `TestGDPRSDK` - GDPR methods (Phase 25)

## Running Tests

### Run All Tests

```bash
pytest tests/test_phase26_sdk_integration.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_phase26_sdk_integration.py::TestBillingSDK -v
```

### Run Specific Test

```bash
pytest tests/test_phase26_sdk_integration.py::TestBillingSDK::test_get_subscription -v
```

## Test Data

Some tests require test data to be set up:
- Scheduled exports for get/update/delete tests
- Subscriptions for billing tests
- Export jobs/erasure requests for GDPR tests

Tests that require test data are marked with `pytest.skip()` and should be enabled once test data is available.

## Troubleshooting

### Authentication Errors

If you see authentication errors:
1. Verify `DATAHUB_API_KEY` is set correctly
2. Verify API key is valid and not expired
3. Check backend authentication configuration

### Connection Errors

If you see connection errors:
1. Verify `HUB_BASE_URL` is correct
2. Verify backend is running and accessible
3. Check network connectivity

### Test Failures

If tests fail:
1. Check test output for specific error messages
2. Verify backend API endpoints are working
3. Check backend logs for errors
4. Verify tenant context is set correctly

## Adding New Tests

When adding new SDK methods, add corresponding tests:

1. Create test class: `class TestNewModuleSDK:`
2. Add async test methods for each method
3. Use `client` fixture for SDK client
4. Assert on return types and structure
5. Handle cases where resources don't exist

Example:

```python
@pytest.mark.asyncio
class TestNewModuleSDK:
    async def test_list_resources(self, client):
        result = await client.new_module.list()
        assert isinstance(result, dict)
        assert "results" in result
```
