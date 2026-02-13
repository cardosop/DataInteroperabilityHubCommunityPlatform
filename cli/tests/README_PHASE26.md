# Phase 26 CLI Integration Tests

## Overview

Integration tests for Phase 26 CLI commands using real backend API (no mocks/stubs).

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

# Install CLI dependencies
cd cli
pip install -e .

# Run tests
pytest tests/integration/test_phase26_cli_integration.py -v
```

## Test Structure

Tests are organized by command group:
- `TestScheduledIngestionCLI` - Scheduled ingestion commands
- `TestScheduledExportCLI` - Scheduled export commands
- `TestWebhooksCLI` - Webhooks commands
- `TestAuditCLI` - Audit commands
- `TestHealthCLI` - Health check commands
- `TestBillingCLI` - Billing commands (Phase 25)
- `TestTenantsCLI` - Tenants commands (Phase 25)
- `TestGDPRCLI` - GDPR commands (Phase 25)
- `TestSearchCLI` - Search commands

## Running Tests

### Run All Tests

```bash
pytest tests/integration/test_phase26_cli_integration.py -v
```

### Run Specific Test Class

```bash
pytest tests/integration/test_phase26_cli_integration.py::TestSearchCLI -v
```

### Run Specific Test

```bash
pytest tests/integration/test_phase26_cli_integration.py::TestSearchCLI::test_search -v
```

## Test Data

Some tests require test data to be set up:
- Scheduled ingestions/exports for get/update/delete tests
- Webhooks for update/delete tests
- Audit events for query tests

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

When adding new CLI commands, add corresponding tests:

1. Create test class: `class TestNewCommandCLI:`
2. Add test methods for each command
3. Use `run_cli_command()` helper function
4. Assert on exit code and output format
5. Handle cases where resources don't exist

Example:

```python
class TestNewCommandCLI:
    def test_list_resources(self, cli_config):
        exit_code, stdout, stderr = run_cli_command([
            "new-command", "list", "--format", "json"
        ])
        assert exit_code == 0, f"Command failed: {stderr}"
        data = json.loads(stdout)
        assert isinstance(data, (list, dict))
```
