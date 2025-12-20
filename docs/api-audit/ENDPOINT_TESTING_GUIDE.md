# API Endpoint Testing Guide

**Purpose**: Comprehensive guide for testing all API endpoints to verify functionality, document status, and measure performance.

---

## Overview

The endpoint testing process verifies:
1. **Functionality**: Endpoints respond correctly
2. **Status**: Working, broken, or deprecated
3. **Performance**: Response times and latency metrics
4. **Authentication**: Proper auth/authz behavior
5. **Error Handling**: Appropriate error responses

---

## Testing Script

### Location

`scripts/test-api-endpoints.py`

### Usage

```bash
# Basic usage (tests public endpoints only)
python scripts/test-api-endpoints.py

# With authentication
python scripts/test-api-endpoints.py \
  --base-url http://localhost:8000 \
  --username admin@example.com \
  --password your-password

# Custom inventory and output
python scripts/test-api-endpoints.py \
  --inventory docs/api-audit/current-api-inventory.md \
  --output docs/api-audit/endpoint-test-report.md

# Skip authentication (test public endpoints only)
python scripts/test-api-endpoints.py --skip-auth
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--base-url` | API base URL | `http://localhost:8000` |
| `--username` | Username for authentication | None |
| `--password` | Password for authentication | None |
| `--inventory` | Path to API inventory file | `docs/api-audit/current-api-inventory.md` |
| `--output` | Path to output test report | `docs/api-audit/endpoint-test-report.md` |
| `--skip-auth` | Skip authentication | False |

---

## Test Process

### 1. Preparation

- Ensure backend API service is running
- Verify database is accessible
- Check that required services are available
- Prepare test credentials (if testing authenticated endpoints)

### 2. Authentication

The script automatically:
- Attempts to authenticate if credentials are provided
- Uses JWT token for subsequent requests
- Falls back to unauthenticated testing if auth fails

### 3. Endpoint Testing

For each endpoint:
1. **Parse endpoint** from inventory file
2. **Determine requirements**:
   - Authentication required?
   - Request body required?
3. **Make HTTP request** with appropriate method
4. **Measure response time**
5. **Analyze response**:
   - Status code
   - Response body (if applicable)
   - Error messages
6. **Classify status**:
   - ✅ Working (200, 201, 204)
   - ❌ Broken (4xx, 5xx errors)
   - ⚠️ Deprecated (410 Gone)
   - ⏭️ Skipped (requires auth but no token)

### 4. Performance Measurement

- **Response Time**: Time from request sent to response received
- **Metrics Calculated**:
  - Average response time
  - P50 (median)
  - P95 (95th percentile)
  - P99 (99th percentile)

### 5. Report Generation

Generates:
- **Markdown Report**: Human-readable test results
- **JSON Results**: Machine-readable data for automation
- **Inventory Update**: Updates inventory file with test results

---

## Test Results Classification

### Working Endpoints ✅

Endpoints that:
- Return 200, 201, or 204 status codes
- Respond within acceptable time (< 30s)
- Return valid response bodies (if applicable)

**Performance Grades**:
- ✅ Excellent: < 200ms
- ✅ Good: 200-500ms
- ⚠️ Acceptable: 500-1000ms
- ❌ Slow: > 1000ms

### Broken Endpoints ❌

Endpoints that:
- Return 4xx or 5xx status codes (except 401/403 which may be expected)
- Timeout (> 30s)
- Return connection errors
- Return invalid response formats

**Common Issues**:
- 401 Unauthorized: Missing or invalid authentication
- 403 Forbidden: Insufficient permissions
- 404 Not Found: Endpoint doesn't exist
- 500 Internal Server Error: Server-side error
- Connection Error: Service unavailable

### Deprecated Endpoints ⚠️

Endpoints that:
- Return 410 Gone status
- Include deprecation headers
- Are marked as deprecated in documentation

**Action Required**: Update clients to use new endpoints

### Skipped Endpoints ⏭️

Endpoints that:
- Require authentication but no token available
- Require special permissions
- Cannot be tested automatically

**Action Required**: Test manually or provide appropriate credentials

---

## Output Files

### Test Report (Markdown)

**Location**: `docs/api-audit/endpoint-test-report.md`

**Contents**:
- Summary statistics
- Performance metrics
- Working endpoints table
- Broken endpoints table
- Deprecated endpoints table
- Skipped endpoints table
- Detailed results for each endpoint

### JSON Results

**Location**: `docs/api-audit/endpoint-test-report.json`

**Contents**:
- Machine-readable test results
- Summary statistics
- Individual endpoint results
- Timestamps and metadata

**Use Cases**:
- CI/CD integration
- Automated analysis
- Dashboard generation
- Trend analysis

### Updated Inventory

**Location**: `docs/api-audit/current-api-inventory.md`

**Updates**:
- Adds "Endpoint Test Results" section
- Includes test status for each endpoint
- Performance metrics
- Test timestamps

---

## Best Practices

### Testing Frequency

- **Before Releases**: Test all endpoints
- **Weekly**: Test critical endpoints (P0)
- **After Deployments**: Test affected endpoints
- **After Schema Changes**: Test all endpoints

### Test Environment

- Use **staging environment** for comprehensive testing
- Use **development environment** for quick checks
- **Never test production** with automated scripts (use read-only checks)

### Credentials Management

- Use **test accounts** with appropriate permissions
- **Never commit** credentials to version control
- Use **environment variables** or secure credential storage
- Rotate test credentials regularly

### Error Analysis

- **Root Cause Analysis**: Investigate broken endpoints
- **Performance Analysis**: Identify slow endpoints
- **Trend Analysis**: Track performance over time
- **Documentation**: Update API docs with findings

---

## Troubleshooting

### Common Issues

#### Authentication Failures

**Symptom**: All authenticated endpoints return 401

**Solutions**:
- Verify credentials are correct
- Check token expiration
- Ensure authentication service is running
- Verify JWT secret key configuration

#### Connection Errors

**Symptom**: Connection refused or timeout errors

**Solutions**:
- Verify API service is running
- Check network connectivity
- Verify base URL is correct
- Check firewall rules

#### High Response Times

**Symptom**: Many endpoints have slow response times

**Solutions**:
- Check database performance
- Verify external service availability
- Check server resource usage
- Review query optimization

#### Missing Endpoints

**Symptom**: Endpoints in inventory but return 404

**Solutions**:
- Verify URL routing configuration
- Check API version prefix
- Verify endpoint is actually deployed
- Check for typos in inventory

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: API Endpoint Tests

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  test-endpoints:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install requests
      
      - name: Start services
        run: |
          docker-compose up -d
          sleep 30  # Wait for services to be ready
      
      - name: Run endpoint tests
        env:
          API_BASE_URL: http://localhost:8000
          TEST_USERNAME: ${{ secrets.TEST_USERNAME }}
          TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}
        run: |
          python scripts/test-api-endpoints.py \
            --base-url $API_BASE_URL \
            --username $TEST_USERNAME \
            --password $TEST_PASSWORD
      
      - name: Upload test report
        uses: actions/upload-artifact@v3
        with:
          name: endpoint-test-report
          path: docs/api-audit/endpoint-test-report.*
      
      - name: Check for broken endpoints
        run: |
          python -c "
          import json
          with open('docs/api-audit/endpoint-test-report.json') as f:
              data = json.load(f)
          if data['summary']['broken'] > 0:
              print(f'❌ Found {data[\"summary\"][\"broken\"]} broken endpoints')
              exit(1)
          print('✅ All endpoints working')
          "
```

---

## Performance Benchmarks

### Target Response Times

| Endpoint Type | Target | Acceptable | Slow |
|---------------|--------|------------|------|
| Authentication | < 500ms | < 1000ms | > 1000ms |
| List/Query | < 300ms | < 500ms | > 500ms |
| Get/Retrieve | < 200ms | < 300ms | > 300ms |
| Create | < 1000ms | < 2000ms | > 2000ms |
| Update | < 500ms | < 1000ms | > 1000ms |
| Delete | < 500ms | < 1000ms | > 1000ms |
| Complex Operations | < 5000ms | < 10000ms | > 10000ms |

### Performance Monitoring

Track these metrics over time:
- Average response time trends
- P95 response time trends
- Error rate trends
- Endpoint availability

---

## Next Steps

After testing:

1. **Fix Broken Endpoints**: Address root causes
2. **Optimize Slow Endpoints**: Performance improvements
3. **Update Documentation**: Reflect test results
4. **Update Inventory**: Mark endpoints as tested
5. **Create Issues**: Track broken endpoints
6. **Schedule Retests**: Regular testing cadence

---

**Last Updated**: 2025-12-13  
**Maintained By**: Development Team

