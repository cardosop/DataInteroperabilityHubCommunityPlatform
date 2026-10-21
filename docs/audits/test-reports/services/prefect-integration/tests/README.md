# Prefect Integration Tests

## Setup

These tests require:
1. Docker Compose services running (API service, PostgreSQL, MinIO)
2. `USE_PRODUCTION_DB_FOR_SDK_TESTS=1` environment variable set
3. `HUB_BASE_URL` pointing to the API service (default: `http://api-service:8000`)

## Test Data Setup

**IMPORTANT**: The API service (running in a separate Docker container) uses connection pooling and may not see data created during tests immediately. To ensure tests work reliably:

1. **Create test data before running tests**:
   ```bash
   docker compose exec api-service bash -c "cd /app && USE_PRODUCTION_DB_FOR_SDK_TESTS=1 TEST_MINIO_BUCKET=test-exports TEST_MINIO_ACCESS_KEY=minio TEST_MINIO_SECRET_KEY=minio123 TEST_MINIO_ENDPOINT=http://minio:9000 python services/prefect-integration/tests/create_test_data.py"
   ```

2. **Restart the API service** to refresh its database connection pool:
   ```bash
   docker compose restart api-service
   ```

3. **Set the API key** from the script output:
   ```bash
   export HUB_WORKER_API_KEY=<key_from_script_output>
   ```

4. **Run the tests**:
   ```bash
   docker compose exec api-service bash -c "cd /app && USE_PRODUCTION_DB_FOR_SDK_TESTS=1 HUB_BASE_URL=http://api-service:8000 HUB_WORKER_API_KEY=<key> TEST_MINIO_BUCKET=test-exports TEST_MINIO_ACCESS_KEY=minio TEST_MINIO_SECRET_KEY=minio123 TEST_MINIO_ENDPOINT=http://minio:9000 python -m pytest services/prefect-integration/tests/test_scheduled_export_flow.py -v --reuse-db"
   ```

## Why This Is Needed

The API service runs in a separate process with its own database connection pool. Even with `transaction=False` in tests, the API service's connection pool may cache queries or not see newly committed data immediately. Creating test data before tests run and restarting the API service ensures the data is visible.

## Test Structure

- `test_scheduled_export_flow.py`: Integration tests for scheduled export flow
- `conftest.py`: Test fixtures (tenant, user, ScheduledExport, API key, etc.)
- `create_test_data.py`: Script to create test data (tenant, user, API key, ScheduledExport, etc.)
- `verify_test_data.py`: Script to verify test data exists

Tests use `@pytest.mark.django_db(transaction=False)` to ensure data is committed immediately, but the API service still needs to be restarted to see it.
