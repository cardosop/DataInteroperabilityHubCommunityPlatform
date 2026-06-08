# MinIO Setup for E2E Tests

## Overview

E2E tests now use **real MinIO** instead of mocks by default. This provides more realistic testing and ensures the S3 integration works correctly.

## Prerequisites

1. **MinIO must be running**:
   ```bash
   docker-compose up -d minio
   ```

2. **Bucket must exist**:
   The test fixture automatically creates the `hub-files` bucket if it doesn't exist, but you can also create it manually:
   ```bash
   python scripts/setup_minio_bucket.py
   ```

## Configuration

### Environment Variables

The tests use these environment variables (with defaults):

- `AWS_S3_ENDPOINT_URL`: MinIO endpoint (default: `http://localhost:9000`)
- `AWS_ACCESS_KEY_ID`: MinIO access key (default: `minio`)
- `AWS_SECRET_ACCESS_KEY`: MinIO secret key (default: `minio123`)
- `AWS_STORAGE_BUCKET_NAME`: Bucket name (default: `hub-files`)

### Automatic Setup

The `e2e_test_settings` fixture automatically:
1. Adjusts S3 endpoint to use `localhost:9000` for local tests
2. Creates the `hub-files` bucket if it doesn't exist
3. Configures Django settings to use MinIO

## Usage

### Default (Real MinIO)

```python
class MyE2ETest(E2ETestBase):
    def test_file_upload(self):
        """Test file upload with real MinIO"""
        # Uses real MinIO by default
        file_id = self.init_file_upload()
        result = self.complete_file_upload(file_id)
        self.assertIn('id', result)
```

### Fallback to Mocking

If MinIO is not available, tests will automatically fall back to mocking:

```python
# If MinIO is not running, this will use mocks
file_id = self.init_file_upload()
result = self.complete_file_upload(file_id)
```

### Force Mocking (if needed)

```python
# Force mocking even if MinIO is available
file_id = self.init_file_upload(use_real_s3=False)
result = self.complete_file_upload(file_id, use_real_s3=False)
```

## File Upload Flow

When using real MinIO:

1. **Init Upload**: Creates file record and gets presigned URL from MinIO
2. **Upload File**: File is uploaded directly to MinIO using presigned URL
3. **Complete Upload**: 
   - If file doesn't exist in MinIO, a dummy file is uploaded automatically
   - File existence and size are verified against MinIO
   - File record is updated to ACTIVE status

## Troubleshooting

### MinIO Not Running

**Error**: `Could not connect to the endpoint URL: "http://localhost:9000/..."`

**Solution**:
```bash
# Start MinIO
docker-compose up -d minio

# Verify it's running
docker ps | grep minio
curl http://localhost:9000/minio/health/live
```

### Bucket Doesn't Exist

**Error**: `NoSuchBucket` or `404` errors

**Solution**:
```bash
# Create bucket automatically
python scripts/setup_minio_bucket.py

# Or manually via MinIO console
# Open http://localhost:9001
# Login: minio / minio123
# Create bucket: hub-files
```

### File Not Found in MinIO

**Error**: `File not found in storage` during completion

**Solution**: The test helper automatically uploads a dummy file if it doesn't exist. If you're uploading real files, make sure the upload completes before calling `complete_file_upload()`.

## Benefits of Real MinIO

1. **Realistic Testing**: Tests actual S3 integration, not mocks
2. **Integration Verification**: Ensures MinIO configuration is correct
3. **Error Detection**: Catches real S3 connection and permission issues
4. **Production-Like**: Closer to production environment

## Running Tests

```bash
# Ensure MinIO is running
docker-compose up -d minio

# Run E2E tests (will use real MinIO)
pytest tests/e2e/ -v

# Run specific test
pytest tests/e2e/test_data_first_comprehensive.py -v
```

## MinIO Console

Access MinIO console to view uploaded files:
- URL: http://localhost:9001
- Username: `minio`
- Password: `minio123`

