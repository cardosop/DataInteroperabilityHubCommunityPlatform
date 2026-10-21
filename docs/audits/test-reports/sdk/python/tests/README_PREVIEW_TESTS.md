# Preview Methods Tests

## Overview

Tests for Transformation Preview API methods (`generate_preview` and `get_preview`) have been implemented following TDD principles with no mocks/stubs.

## Test Structure

### 1. Unit Tests (Validation Only)
**File:** `test_transformation_api.py`

These tests validate client-side validation logic without making API calls:
- `test_generate_preview_validation_pipeline_id_empty` - Empty pipeline_id validation
- `test_generate_preview_validation_pipeline_id_none` - None pipeline_id validation
- `test_generate_preview_validation_asset_id_empty` - Empty asset_id validation
- `test_generate_preview_validation_sample_size_invalid_type` - Invalid sample_size type
- `test_generate_preview_validation_sample_size_too_small` - Sample size < 1
- `test_generate_preview_validation_sample_size_too_large` - Sample size > 10000
- `test_generate_preview_validation_sampling_method_invalid` - Invalid sampling method
- `test_get_preview_validation_preview_id_empty` - Empty preview_id validation
- `test_get_preview_validation_preview_id_none` - None preview_id validation
- `test_get_preview_validation_preview_id_whitespace` - Whitespace-only preview_id validation

**No mocks/stubs used** - These tests only validate input parameters before API calls.

### 2. Integration Tests (Real API Calls)
**File:** `test_transformation_preview_integration.py`

These tests make real API calls against the running Docker Compose services:
- `test_generate_preview_success_integration` - Successful preview generation
- `test_generate_preview_with_defaults_integration` - Default parameters
- `test_generate_preview_with_random_sampling_integration` - Random sampling method
- `test_generate_preview_not_found_error_integration` - 404 error handling
- `test_get_preview_success_integration` - Successful preview retrieval
- `test_get_preview_not_found_error_integration` - 404 error handling
- `test_generate_preview_validation_sample_size_too_small` - Validation with real API
- `test_generate_preview_validation_sample_size_too_large` - Validation with real API
- `test_generate_preview_validation_sampling_method_invalid` - Validation with real API
- `test_generate_preview_sampling_method_case_insensitive` - Case-insensitive handling

**No mocks/stubs used** - All tests use real API connections.

## Running Tests

### Prerequisites
1. Docker Compose services must be running:
   ```bash
   docker compose ps
   ```

2. Install SDK dependencies:
   ```bash
   cd sdk/python
   pip install -r requirements.txt
   pip install pytest pytest-asyncio
   ```

3. Set up API authentication (one of):
   - Set `TEST_API_KEY` environment variable
   - Set `DATAHUB_API_KEY` environment variable
   - Tests will attempt to create API key via Django shell if not provided

### Run Unit Tests (Validation Only)
```bash
cd sdk/python
pytest tests/test_transformation_api.py -k "preview" -v
```

### Run Integration Tests (Real API)
```bash
cd sdk/python
export TEST_API_KEY=your-api-key  # Optional if auto-creation works
pytest tests/test_transformation_preview_integration.py -v -m integration
```

### Run All Preview Tests
```bash
cd sdk/python
pytest tests/test_transformation_api.py tests/test_transformation_preview_integration.py -k "preview" -v
```

## Test Environment Setup

If running tests outside Docker, ensure:
1. Python 3.8+ is installed
2. SDK dependencies are installed: `pip install -r requirements.txt`
3. Test dependencies: `pip install pytest pytest-asyncio`
4. API base URL is accessible (default: `http://localhost:8000/api/v1`)

## Implementation Details

### Validation Methods
- `_validate_asset_id()` - Validates asset ID format
- `_validate_sample_size()` - Validates sample size (1-10000)
- `_validate_sampling_method()` - Validates sampling method ("first_n" or "random")
- `_validate_preview_id()` - Validates preview ID format

### Error Handling
- 404 errors → `NotFoundError`
- 410 errors (expired preview) → `ServerError` with code "PREVIEW_EXPIRED"
- 429 errors → `RateLimitError`
- 500+ errors → `ServerError`
- Validation errors → `ValidationError`

### Features
- Case-insensitive sampling method handling
- Comprehensive parameter validation
- Proper error mapping from HTTP status codes
- Support for additional kwargs in `generate_preview()`

## Notes

- All tests follow TDD principles
- No mocks/stubs are used (except for unit tests that only test validation logic)
- Integration tests create and clean up test resources (pipelines, assets)
- Tests are marked with `@pytest.mark.integration` for easy filtering

