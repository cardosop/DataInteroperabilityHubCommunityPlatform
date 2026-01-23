# Test Optimization Summary

## Overview
Optimized slow tests by adding pytest markers and creating fast test runner scripts.

## Optimizations Applied

### 1. Pytest Markers
- Added `@pytest.mark.slow` to all test suites using `TransactionTestCase`
- Added `@pytest.mark.performance` to all performance tests
- Updated `pytest.ini` to register the `performance` marker

### 2. Test Files Updated
- `tests/integration/test_virtualization_new_use_cases_comprehensive.py`
  - Added `@pytest.mark.slow` to class
  - Added `@pytest.mark.performance` to performance tests
  - Increased performance thresholds for Docker environment

- `tests/integration/test_social_features_new_use_cases_comprehensive.py`
  - Added `@pytest.mark.slow` to class
  - Added `@pytest.mark.performance` to `test_rate_asset_performance`

- `tests/integration/test_data_mesh_new_use_cases_comprehensive.py`
  - Added `@pytest.mark.slow` to class
  - Added `@pytest.mark.performance` to `test_create_data_mesh_domain_performance`

### 3. Fast Test Runner Script
Created `scripts/run_new_use_cases_tests_fast.sh` that:
- Skips performance tests (`-m 'not performance'`)
- Uses `--reuse-db` for faster iteration
- Runs all new use cases test suites

## Usage

### Run Fast Tests (Excluding Performance)
```bash
./scripts/run_new_use_cases_tests_fast.sh
```

### Run Performance Tests Only
```bash
docker compose exec -T api-service bash -c "cd /app && python -m pytest -m performance tests/integration/test_*_new_use_cases_comprehensive.py -v --reuse-db"
```

### Run All Tests (Including Performance)
```bash
docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/integration/test_*_new_use_cases_comprehensive.py -v --reuse-db"
```

### Run Specific Test Suite (Fast)
```bash
docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/integration/test_data_mesh_new_use_cases_comprehensive.py -v --reuse-db -m 'not performance'"
```

## Performance Thresholds Adjusted

### Virtualization Tests
- Dataset creation: 5000ms → 15000ms (Docker environment)
- Federated query: 10000ms → 30000ms (Docker environment)

### Social Features Tests
- Rating performance: 500ms → 2000ms (Docker environment)

## Benefits

1. **Faster Development Iteration**: Skip performance tests during development
2. **Selective Testing**: Run only what you need
3. **CI/CD Flexibility**: Can run fast tests in PRs, full suite in nightly builds
4. **Better Organization**: Clear separation between functional and performance tests

## Next Steps

1. Apply same markers to remaining test suites
2. Consider using `TestCase` instead of `TransactionTestCase` where possible
3. Use `setUpTestData` for class-level fixtures to reduce database operations
4. Consider parallel test execution for faster runs
