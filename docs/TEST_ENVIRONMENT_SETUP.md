# Test Environment Setup Documentation

Complete guide for setting up the test environment for the Data Interoperability Hub test suite.

## Table of Contents

1. [Overview](#overview)
2. [Required Services](#required-services)
3. [Docker Compose Setup](#docker-compose-setup)
4. [Environment Variables](#environment-variables)
5. [Service Health Checks](#service-health-checks)
6. [Test Database Migrations](#test-database-migrations)
7. [Test Service Dependencies](#test-service-dependencies)
8. [Step-by-Step Local Setup](#step-by-step-local-setup)
9. [CI/CD Environment Setup](#cicd-environment-setup)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The test environment requires several services to be running:
- **PostgreSQL**: Database for test data
- **Redis**: For rate limiting and job queue tests
- **MinIO**: S3-compatible storage for file tests
- **Microservices**: DQ, Compliance, and Semantic services (optional, tests skip if unavailable)

---

## Required Services

### PostgreSQL

**Version**: PostgreSQL 16.x

**Configuration**:
- Database: `hub_test` (created automatically)
- User: `postgres` (or configured user)
- Port: `5432` (default)

**Setup**:
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql-16

# Start PostgreSQL
sudo systemctl start postgresql

# Verify connection
psql -U postgres -c "SELECT version();"
```

### Redis

**Version**: Redis 7.x

**Configuration**:
- Port: `6379` (default)
- Database: `0` (default, test uses separate database)

**Setup**:
```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server

# Verify connection
redis-cli ping
# Should return: PONG
```

### MinIO (S3-compatible)

**Version**: Latest

**Configuration**:
- Access Key: `minioadmin` (default)
- Secret Key: `minioadmin` (default)
- Port: `9000` (API), `9001` (Console)

**Setup**:
```bash
# Download MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio

# Start MinIO
./minio server /data --console-address ":9001"

# Or use Docker
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

### Microservices (Optional)

**DQ Service**: Data Quality service
- Port: `8001` (default)
- Health endpoint: `http://localhost:8001/healthz`

**Compliance Service**: Compliance scanning service
- Port: `8002` (default)
- Health endpoint: `http://localhost:8002/healthz`

**Semantic Service**: Semantic mapping service
- Port: `8003` (default)
- Health endpoint: `http://localhost:8003/healthz`

**Note**: Tests automatically skip if services are unavailable.

---

## Docker Compose Setup

### Using Docker Compose

A `docker-compose.test.yml` file can be created for test services:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: hub_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_test_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_test_data:/data

volumes:
  postgres_test_data:
  minio_test_data:
```

### Start Test Services

```bash
# Start all test services
docker-compose -f docker-compose.test.yml up -d

# Check service status
docker-compose -f docker-compose.test.yml ps

# View logs
docker-compose -f docker-compose.test.yml logs -f

# Stop services
docker-compose -f docker-compose.test.yml down
```

---

## Environment Variables

### Required Environment Variables

```bash
# Django settings
export DJANGO_SETTINGS_MODULE=hub.settings

# Database
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hub_test

# Redis
export REDIS_URL=redis://localhost:6379/0

# S3/MinIO
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export AWS_S3_ENDPOINT_URL=http://localhost:9000
export AWS_STORAGE_BUCKET_NAME=hub-test

# Email (optional, for email tests)
export SENDGRID_API_KEY=test_key
export AWS_SES_REGION=us-east-1
```

### Environment File

Create `.env.test` file:

```bash
DJANGO_SETTINGS_MODULE=hub.settings
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hub_test
REDIS_URL=redis://localhost:6379/0
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_S3_ENDPOINT_URL=http://localhost:9000
AWS_STORAGE_BUCKET_NAME=hub-test
```

Load environment file:

```bash
# Load .env.test
set -a
source .env.test
set +a

# Run tests
pytest tests/unit/ -v
```

---

## Service Health Checks

### Health Check Endpoints

Tests automatically check service health before running:

**PostgreSQL**:
```bash
psql -U postgres -d hub_test -c "SELECT 1;"
```

**Redis**:
```bash
redis-cli ping
# Should return: PONG
```

**MinIO**:
```bash
curl http://localhost:9000/minio/health/live
```

**DQ Service**:
```bash
curl http://localhost:8001/healthz
```

**Compliance Service**:
```bash
curl http://localhost:8002/healthz
```

**Semantic Service**:
```bash
curl http://localhost:8003/healthz
```

### Health Check in Tests

```python
from tests.e2e.conftest import E2ETestBase

class MyE2ETest(E2ETestBase):
    def setUp(self):
        super().setUp()  # Automatically checks service health
        # If services unavailable, test is skipped
```

---

## Test Database Migrations

### Automatic Migration

Django automatically runs migrations when creating test database:

```bash
# Migrations run automatically
pytest tests/unit/ -v
```

### Manual Migration

```bash
# Run migrations manually
python hub/manage.py migrate --database=default

# Create test database
python hub/manage.py migrate --database=default --run-syncdb
```

### Migration Issues

If migrations fail:

```bash
# Check migration status
python hub/manage.py showmigrations

# Fake migrations (if needed)
python hub/manage.py migrate --fake
```

---

## Test Service Dependencies

### Service Dependency Order

1. **PostgreSQL**: Required for all tests
2. **Redis**: Required for rate limiting and job queue tests
3. **MinIO**: Required for file operation tests
4. **Microservices**: Optional, tests skip if unavailable

### Service Availability Checks

Tests check service availability:

```python
# Tests automatically skip if services unavailable
@pytest.mark.skipif(not service_available(), reason="Service not available")
def test_requiring_service():
    pass
```

---

## Step-by-Step Local Setup

### 1. Install Dependencies

```bash
# Install system dependencies
sudo apt-get install postgresql-16 redis-server

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists
```

### 2. Start Services

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Start Redis
sudo systemctl start redis-server

# Start MinIO (if using Docker)
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

### 3. Configure Environment

```bash
# Set environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hub_test
export REDIS_URL=redis://localhost:6379/0
```

### 4. Verify Services

```bash
# Check PostgreSQL
psql -U postgres -c "SELECT version();"

# Check Redis
redis-cli ping

# Check MinIO
curl http://localhost:9000/minio/health/live
```

### 5. Run Tests

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run E2E tests
pytest tests/e2e/ -m e2e_batch1 -v
```

---

## CI/CD Environment Setup

### GitHub Actions

CI/CD automatically sets up test environment:

```yaml
# .github/workflows/ci.yml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_DB: hub_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

  redis:
    image: redis:7
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

  minio:
    image: minio/minio
    env:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    options: >-
      --health-cmd "curl http://localhost:9000/minio/health/live"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### Environment Variables in CI

```yaml
env:
  DJANGO_SETTINGS_MODULE: hub.settings
  DATABASE_URL: postgresql://postgres:postgres@localhost:5432/hub_test
  REDIS_URL: redis://localhost:6379/0
  AWS_ACCESS_KEY_ID: minioadmin
  AWS_SECRET_ACCESS_KEY: minioadmin
  AWS_S3_ENDPOINT_URL: http://localhost:9000
  AWS_STORAGE_BUCKET_NAME: hub-test
```

---

## Troubleshooting

### Issue: PostgreSQL connection failed

**Symptoms**: `django.db.utils.OperationalError: connection to server failed`

**Solutions**:
1. Check PostgreSQL is running: `sudo systemctl status postgresql`
2. Check connection: `psql -U postgres -d hub_test`
3. Verify `DATABASE_URL` environment variable
4. Check PostgreSQL logs: `sudo journalctl -u postgresql`

### Issue: Redis connection failed

**Symptoms**: `redis.exceptions.ConnectionError`

**Solutions**:
1. Check Redis is running: `sudo systemctl status redis-server`
2. Check connection: `redis-cli ping`
3. Verify `REDIS_URL` environment variable
4. Check Redis logs: `sudo journalctl -u redis-server`

### Issue: MinIO connection failed

**Symptoms**: `botocore.exceptions.ClientError` or S3 errors

**Solutions**:
1. Check MinIO is running: `docker ps | grep minio`
2. Check connection: `curl http://localhost:9000/minio/health/live`
3. Verify `AWS_S3_ENDPOINT_URL` and credentials
4. Check MinIO logs: `docker logs <minio_container>`

### Issue: Test database not created

**Symptoms**: `django.db.utils.OperationalError: database "hub_test" does not exist`

**Solutions**:
1. Create database manually: `createdb -U postgres hub_test`
2. Or let Django create it: `pytest --create-db tests/unit/ -v`
3. Check database permissions

### Issue: Migration errors

**Symptoms**: `django.db.migrations.exceptions.MigrationError`

**Solutions**:
1. Check migration status: `python hub/manage.py showmigrations`
2. Run migrations: `python hub/manage.py migrate`
3. Check for migration conflicts
4. Reset test database: `pytest --create-db tests/unit/ -v`

### Issue: Service health checks failing

**Symptoms**: Tests skipped with "Service not available"

**Solutions**:
1. Verify service is running
2. Check service health endpoint
3. Verify service URL/port configuration
4. Check firewall/network settings

### Issue: Port conflicts

**Symptoms**: `Address already in use`

**Solutions**:
1. Check what's using the port: `lsof -i :5432` (PostgreSQL)
2. Stop conflicting service
3. Use different port in configuration
4. Kill process using port: `kill -9 <PID>`

---

## Quick Reference

### Service Status Commands

```bash
# PostgreSQL
sudo systemctl status postgresql
psql -U postgres -c "SELECT version();"

# Redis
sudo systemctl status redis-server
redis-cli ping

# MinIO
docker ps | grep minio
curl http://localhost:9000/minio/health/live
```

### Start All Services

```bash
# Using systemd
sudo systemctl start postgresql
sudo systemctl start redis-server

# Using Docker Compose
docker-compose -f docker-compose.test.yml up -d
```

### Verify Environment

```bash
# Check environment variables
env | grep -E "(DJANGO|DATABASE|REDIS|AWS)"

# Run health checks
python -c "from django.conf import settings; print(settings.DATABASES)"
```

---

**Last Updated**: 2025-12-04  
**Maintainer**: Engineering Team

