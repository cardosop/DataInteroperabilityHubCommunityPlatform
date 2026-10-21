# S3/MinIO Configuration for E2E Tests

## Problem

E2E tests fail with S3 connection errors when MinIO is not available or when running tests locally (outside Docker).

## Solution

### Option 1: Use S3 Mocking (Recommended for Tests)

The E2E test helper methods support S3 mocking by default:

```python
# This will automatically mock S3 operations
file_id = self.init_file_upload()
self.complete_file_upload(file_id, mock_s3=True)  # mock_s3=True is default
```

### Option 2: Use Real MinIO Service

If you want to test with real MinIO:

1. **Start MinIO**:
   ```bash
   docker-compose up -d minio
   ```

2. **Set Environment Variable**:
   ```bash
   export AWS_S3_ENDPOINT_URL=http://localhost:9000
   ```

3. **Run Tests Without Mocking**:
   ```python
   self.complete_file_upload(file_id, mock_s3=False)
   ```

### Option 3: Configure S3 Endpoint via Environment

The test fixture automatically adjusts the S3 endpoint:

- If `AWS_S3_ENDPOINT_URL` contains `minio:9000`, it's replaced with `localhost:9000` for local test execution
- You can override by setting `AWS_S3_ENDPOINT_URL` environment variable

## Configuration

### Environment Variables

- `AWS_S3_ENDPOINT_URL`: S3 endpoint URL (default: `http://minio:9000`)
  - For local tests: `http://localhost:9000`
  - For Docker: `http://minio:9000`

### Test Fixture

The `e2e_test_settings` fixture automatically:
- Uses localhost for services in test environment
- Adjusts S3 endpoint if needed
- Applies settings overrides

## Best Practices

1. **Default to Mocking**: Use `mock_s3=True` (default) for most tests
2. **Test Real S3 Separately**: Create specific tests that use `mock_s3=False` to verify real S3 integration
3. **Environment Configuration**: Use environment variables to control S3 endpoint
4. **Service Health Checks**: Tests verify services before running

## Troubleshooting

### Connection Errors

If you see `Could not connect to the endpoint URL: "http://minio:9000/..."`:

1. **Use Mocking**: Set `mock_s3=True` in helper methods
2. **Start MinIO**: `docker-compose up -d minio`
3. **Set Endpoint**: `export AWS_S3_ENDPOINT_URL=http://localhost:9000`

### Tests Failing with 500 Errors

If tests return 500 errors on file completion:

1. Check if MinIO is running: `docker ps | grep minio`
2. Verify endpoint: `curl http://localhost:9000/minio/health/live`
3. Use mocking: `mock_s3=True` in `complete_file_upload()`

## Example Usage

```python
class MyE2ETest(E2ETestBase):
    def test_file_upload_with_mocking(self):
        """Test file upload with S3 mocking (default)"""
        file_id = self.init_file_upload()
        result = self.complete_file_upload(file_id)  # Uses mocking by default
        self.assertIn('id', result)
    
    def test_file_upload_with_real_s3(self):
        """Test file upload with real MinIO"""
        # Requires MinIO to be running
        file_id = self.init_file_upload()
        result = self.complete_file_upload(file_id, mock_s3=False)
        self.assertIn('id', result)
```

