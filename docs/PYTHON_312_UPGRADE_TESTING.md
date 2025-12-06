# Python 3.12+ Upgrade Testing Guide

This guide provides instructions for testing the Python 3.12+ upgrade implementation.

## Automated Test Scripts

We've created several automated test scripts to verify the Python 3.12+ upgrade:

### 1. Configuration Verification

**Script:** `scripts/verify_python_upgrade.py`

**Purpose:** Verifies that all configuration files are properly updated for Python 3.12+

**What it checks:**
- Python version (must be 3.12+)
- All Dockerfiles use Python 3.12+
- All GitHub Actions workflows use Python 3.12+
- Setup scripts check for Python 3.12+
- pyproject.toml files configured for Python 3.12+
- setup.py files require Python 3.12+

**Usage:**
```bash
python3 scripts/verify_python_upgrade.py
```

**Expected Output:**
- ✅ All configuration checks should pass
- ⚠️ Dependency installation check may show warnings in externally-managed environments (this is expected)

### 2. Docker Build Tests

**Script:** `scripts/test_docker_builds.sh`

**Purpose:** Tests that all Docker images build successfully with Python 3.12+

**What it does:**
- Builds all Docker images
- Verifies Python version in built images
- Cleans up test images

**Usage:**
```bash
bash scripts/test_docker_builds.sh
```

**Prerequisites:**
- Docker must be installed and running
- Sufficient disk space for image builds

**Expected Output:**
- All 6 services should build successfully
- Each image should contain Python 3.12+

### 3. Python Compatibility Tests

**Script:** `scripts/test_python_compatibility.sh`

**Purpose:** Tests Python 3.12+ compatibility of core components

**What it tests:**
- Core Python module imports
- Dependency installation (dry-run)
- SDK setup.py validation
- CLI setup.py validation
- Django compatibility (if Django is installed)

**Usage:**
```bash
bash scripts/test_python_compatibility.sh
```

**Expected Output:**
- All compatibility checks should pass
- Warnings may appear for components not installed (this is expected)

### 4. Comprehensive Test Runner

**Script:** `scripts/run_python_upgrade_tests.sh`

**Purpose:** Runs all automated tests and provides a summary

**Usage:**
```bash
bash scripts/run_python_upgrade_tests.sh
```

**What it does:**
1. Runs configuration verification
2. Runs Python compatibility tests
3. Runs Docker build tests (if Docker is available)
4. Provides a summary and manual testing checklist

## Manual Testing Checklist

After running automated tests, perform the following manual tests:

### 1. CI/CD Pipeline Testing

1. **Push to test branch:**
   ```bash
   git checkout -b test/python-312-upgrade
   git push origin test/python-312-upgrade
   ```

2. **Verify GitHub Actions:**
   - Go to GitHub Actions tab
   - Verify workflows trigger
   - Check that Python 3.12+ is used
   - Verify test matrix runs for 3.12, 3.13, 3.14
   - Ensure all jobs pass

### 2. Local Development Testing

1. **Create virtual environment:**
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Run Django migrations:**
   ```bash
   python hub/manage.py migrate
   ```

4. **Start development server:**
   ```bash
   python hub/manage.py runserver
   ```

5. **Test API endpoints:**
   ```bash
   curl http://localhost:8000/health/
   ```

### 3. Docker Services Testing

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Verify service health:**
   ```bash
   # API service
   curl http://localhost:8000/health/
   
   # Worker service
   curl http://localhost:8084/healthz
   
   # Datacontract service
   curl http://localhost:8080/health
   
   # Compliance service
   curl http://localhost:8082/health
   
   # DQ service
   curl http://localhost:8083/health
   
   # Semantic service
   curl http://localhost:8081/health
   ```

3. **Check service logs:**
   ```bash
   docker-compose logs api-service
   docker-compose logs worker-service
   # etc.
   ```

### 4. SDK and CLI Testing

1. **Test SDK:**
   ```bash
   cd sdk/python
   pip install -e .
   python -c "from datahub_interoperability import Client; print('SDK imported successfully')"
   cd ../..
   ```

2. **Test CLI:**
   ```bash
   cd cli
   pip install -e .
   datahub --help
   cd ..
   ```

### 5. Full Test Suite

1. **Run unit tests:**
   ```bash
   pytest tests/unit/ -v
   ```

2. **Run integration tests:**
   ```bash
   pytest tests/integration/ -v
   ```

3. **Run E2E tests:**
   ```bash
   pytest tests/e2e/ -v
   ```

## Troubleshooting

### Issue: "externally-managed-environment" error

**Solution:** Use a virtual environment:
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Docker build fails

**Check:**
- Docker is running: `docker ps`
- Dockerfile syntax is correct
- Base image is available: `docker pull python:3.12-slim`

### Issue: Service won't start

**Check:**
- Service logs: `docker-compose logs <service-name>`
- Environment variables are set correctly
- Dependencies are installed
- Database/Redis are accessible

### Issue: CI/CD pipeline fails

**Check:**
- GitHub Actions logs for specific errors
- Python version matrix is correct
- All workflow files are updated
- Dependencies are compatible with Python 3.12+

## Success Criteria

All tests should pass:
- ✅ Configuration verification: 7/7 checks
- ✅ Python compatibility: All tests pass
- ✅ Docker builds: All 6 services build successfully
- ✅ CI/CD pipelines: All jobs pass
- ✅ Local development: Server starts, migrations run
- ✅ Services: All services start and respond to health checks
- ✅ SDK/CLI: Install and import successfully
- ✅ Test suite: All tests pass

## Next Steps

After successful testing:
1. Update tasks.md to mark tests as complete
2. Proceed with Django 6 upgrade (Phase 0.1)
3. Document any compatibility issues found
4. Update deployment procedures if needed

---

**Last Updated:** 2025-01-15  
**Version:** 1.0.0

