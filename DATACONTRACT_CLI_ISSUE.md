# DataContract CLI Installation Issue

## Problem

The DataContract service is returning `503 Service Unavailable` for the `/validate` endpoint because the DataContract CLI is not installed in the container.

## Root Cause

1. **npm package doesn't exist**: The `@datacontract/cli` npm package is not available in the npm registry
2. **Python package doesn't provide CLI**: The `datacontract` Python package (v0.1.0) is installed but doesn't provide the `datacontract` CLI command
3. **Service requires CLI**: The service checks for the CLI and returns 503 if it's not available

## Current Status

- ✅ Services are running and healthy (health checks pass)
- ✅ Tests are configured to use real services (no mocks)
- ❌ DataContract CLI is not installed
- ❌ Validation endpoint returns 503

## Solutions

### Option 1: Use Official Docker Image (Recommended)

According to `EXTERNAL_DEPENDENCIES.md`, the official way is:
```bash
docker pull datacontract/datacontract-cli:latest
```

We could use a multi-stage build or run the CLI in a separate container.

### Option 2: Install via Alternative Method

The DataContract CLI might be available via:
- Direct download from GitHub releases
- Different npm package name
- Different installation method

### Option 3: Update Service to Handle Missing CLI Gracefully

For development/testing, we could:
- Allow the service to work without CLI (return appropriate errors)
- Use mocks for validation endpoints in tests
- Skip validation tests when CLI is not available

## Next Steps

1. **Investigate official installation method**: Check DataContract CLI documentation for the correct installation method
2. **Update Dockerfile**: Use the correct installation method
3. **Rebuild and test**: Rebuild the service and verify CLI is available
4. **Re-run tests**: Once CLI is installed, tests should pass

## Test Status

Tests are correctly configured to use real services. Once the CLI is installed, all tests should pass.

