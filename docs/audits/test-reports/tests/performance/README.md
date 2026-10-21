# Performance Tests

This directory contains Locust-based performance tests for the MVP foundation implementation.

## Tests

### T.15: File Upload/Download Load Test
- **File**: `test_file_upload_download.py`
- **Targets**:
  - 20 concurrent file uploads
  - Sustained ingress throughput of at least 50 MB/s aggregate
  - P95 latency ≤ 500ms for init/complete endpoints

### T.16: Job Queue Throughput Test
- **File**: `test_job_queue_throughput.py`
- **Targets**:
  - ≥ 100 jobs/hour for DQ/compliance jobs
  - Up to 50 new jobs within 5 minutes without queue latency > 5 minutes
  - P50 end-to-end duration ≤ 15 minutes
  - P95 end-to-end duration ≤ 30 minutes

### T.17: Database Query Performance Test
- **File**: `test_database_query_performance.py`
- **Targets**:
  - P50 query time ≤ 50ms
  - P95 query time ≤ 200ms
  - P99 query time ≤ 500ms

### T.18: API Endpoints Availability Test
- **File**: `test_api_endpoints_availability.py`
- **Targets**:
  - 99.5% availability (error rate ≤ 0.5%)
  - P95 API response time ≤ 300ms for typical CRUD endpoints
  - 30-50 RPS sustained throughput

## Prerequisites

1. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Ensure services are running:
```bash
docker-compose up -d
python manage.py runserver
```

3. Pre-create test users (recommended):
```bash
python manage.py shell
>>> from hub.apps.users.models import User, UserStatus
>>> from hub.apps.tenants.models import Tenant
>>> tenant = Tenant.objects.create(name="Perf Test Tenant", slug="perf-test", status="ACTIVE", kyc_status="VERIFIED")
>>> user = User.objects.create_user(email="perf-test@example.com", password="perf-test-password-123", tenant=tenant, status=UserStatus.ACTIVE)
```

Or set environment variables:
```bash
export PERF_TEST_USER_EMAIL=perf-test@example.com
export PERF_TEST_USER_PASSWORD=perf-test-password-123
```

## Running Tests

### Run All Tests
```bash
./tests/performance/run_performance_tests.sh
```

### Run Specific Test
```bash
# File upload/download
./tests/performance/run_performance_tests.sh TEST_TYPE=file

# Job queue throughput
./tests/performance/run_performance_tests.sh TEST_TYPE=job

# Database query performance
./tests/performance/run_performance_tests.sh TEST_TYPE=db

# API endpoints availability
./tests/performance/run_performance_tests.sh TEST_TYPE=api
```

### Run with Custom Parameters
```bash
API_HOST=http://localhost:8000 \
USERS=100 \
SPAWN_RATE=10 \
RUN_TIME=10m \
TEST_TYPE=all \
./tests/performance/run_performance_tests.sh
```

### Run Locust UI (Interactive)
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser.

### Run Specific User Class
```bash
locust -f tests/performance/locustfile.py FileUploadDownloadUser --host=http://localhost:8000
```

## Configuration

Environment variables:
- `API_HOST`: API base URL (default: http://localhost:8000)
- `USERS`: Number of concurrent users (default: 50)
- `SPAWN_RATE`: Users spawned per second (default: 5)
- `RUN_TIME`: Test duration (default: 5m)
- `TEST_TYPE`: Test type: file, job, db, api, or all (default: all)
- `PERF_TEST_USER_EMAIL`: Test user email
- `PERF_TEST_USER_PASSWORD`: Test user password
- `S3_ENDPOINT_URL`: S3 endpoint (default: http://localhost:9000)
- `AWS_ACCESS_KEY_ID`: S3 access key (default: minio)
- `AWS_SECRET_ACCESS_KEY`: S3 secret key (default: minio123)
- `S3_BUCKET_NAME`: S3 bucket name (default: hub-files)

## Results

Test results are saved to `tests/performance/results/YYYYMMDD_HHMMSS/`:
- HTML reports: `{test_name}.html`
- CSV data: `{test_name}_*.csv`

## Interpreting Results

### File Upload/Download
- Check upload throughput (MB/s)
- Check init/complete latency (should be < 500ms P95)
- Check download success rate

### Job Queue Throughput
- Check jobs/hour rate
- Check queue latency (PENDING → RUNNING)
- Check end-to-end duration (creation → completion)

### Database Query Performance
- Check P50, P95, P99 query times
- Should meet targets: P50 ≤ 50ms, P95 ≤ 200ms, P99 ≤ 500ms

### API Endpoints Availability
- Check error rate (should be ≤ 0.5%)
- Check P95 response time (should be ≤ 300ms)
- Check RPS (should sustain 30-50 RPS)

## Troubleshooting

**Import errors:**
- Ensure Django is set up: `python manage.py check`
- Ensure all dependencies are installed: `pip install -r requirements-dev.txt`

**Authentication errors:**
- Pre-create test users or set environment variables
- Check that API is running and accessible

**Connection errors:**
- Ensure services are running: `docker-compose ps`
- Check API health: `curl http://localhost:8000/health`

**S3 upload errors:**
- Ensure MinIO is running: `docker-compose ps | grep minio`
- Check S3 credentials and bucket exists

