# CI/CD Integration for E2E Tests

## Overview

E2E tests are integrated into the CI/CD pipeline to ensure comprehensive testing on every commit and pull request.

## CI/CD Configuration

### GitHub Actions Workflows

#### 1. Main CI Workflow (`.github/workflows/ci.yml`)

The main CI workflow includes E2E tests as part of the test suite:

```yaml
- name: Run E2E tests
  env:
    DATABASE_URL: postgresql://hub:hub@localhost:5432/hub
    REDIS_URL: redis://localhost:6379/0
    DATACONTRACT_SERVICE_URL: http://localhost:8080
    DQ_SERVICE_URL: http://localhost:8083
    COMPLIANCE_SERVICE_URL: http://localhost:8082
    SEMANTIC_SERVICE_URL: http://localhost:8081
    DJANGO_SETTINGS_MODULE: hub.settings
    PYTHONPATH: ${{ github.workspace }}
  run: |
    pytest tests/e2e/ -v --cov=. --cov-report=xml --cov-append --tb=short
```

#### 2. Dedicated E2E Workflow (`.github/workflows/e2e.yml`)

A separate workflow for comprehensive E2E testing:

- **Triggers**: Push to main/develop, PRs, manual dispatch
- **Timeout**: 60 minutes (E2E tests can take longer)
- **Services**: PostgreSQL, Redis, Docker services
- **Steps**:
  1. Build service Docker images
  2. Start microservices
  3. Wait for services to be healthy
  4. Run database migrations
  5. Run E2E tests
  6. Upload test results
  7. Cleanup services

## Test Execution Strategy

### PR Pipeline (Fast Feedback)

For pull requests, run a subset of E2E tests:
- Critical path tests (happy paths)
- Smoke tests (quick validation)
- Tests related to changed code

```bash
# Run only critical E2E tests on PR
pytest tests/e2e/ -v -k "happy_path or smoke" --tb=short
```

### Main Branch Pipeline (Comprehensive)

On merge to main, run full E2E test suite:
- All success paths
- All failure scenarios
- All edge cases
- Full error handling tests

```bash
# Run all E2E tests on main
pytest tests/e2e/ -v --tb=short
```

### Nightly Pipeline (Optional)

Run extended E2E tests nightly:
- Performance tests
- Stress tests
- Extended edge case coverage

## Service Dependencies

### Required Services

E2E tests require these services to be running:

1. **DataContract Service** (port 8080)
   - Validates contracts
   - Lints contracts
   - Converts between formats

2. **DQ Service** (port 8083)
   - Runs data quality checks
   - Returns quality scores

3. **Compliance Service** (port 8082)
   - Scans for PII
   - Returns compliance status

4. **Semantic Service** (port 8081)
   - Handles RDF/SPARQL queries
   - Manages semantic mappings

### Service Health Checks

Services are checked for health before tests run:

```bash
# Wait for services to be healthy
timeout=120
for service in datacontract-service:8080 dq-service:8083 compliance-service:8082 semantic-service:8081; do
  name=${service%%:*}
  port=${service##*:}
  echo "Waiting for $name..."
  for i in $(seq 1 $timeout); do
    if curl -f http://localhost:$port/health > /dev/null 2>&1; then
      echo "✅ $name is healthy"
      break
    fi
    if [ $i -eq $timeout ]; then
      echo "❌ $name failed to become healthy"
      docker logs $name
      exit 1
    fi
    sleep 1
  done
done
```

## Test Results

### Artifacts

Test results are uploaded as artifacts:
- **JUnit XML**: `e2e-results.xml` (for test reporting)
- **Coverage Reports**: `coverage.xml` (for coverage tracking)
- **HTML Reports**: `htmlcov/` (for detailed coverage)

### Reporting

- **GitHub Actions**: Test results shown in Actions tab
- **Codecov**: Coverage reports uploaded (if configured)
- **Test Summary**: Displayed in PR comments

## Troubleshooting

### Common Issues

1. **Services Not Starting**
   - Check Docker logs: `docker logs <service-name>`
   - Verify service health endpoints
   - Check port conflicts

2. **Tests Timing Out**
   - Increase timeout in workflow
   - Check service response times
   - Verify database connectivity

3. **Flaky Tests**
   - Add retries for transient failures
   - Increase wait times for async operations
   - Check service stability

### Debugging

Enable verbose logging:

```bash
pytest tests/e2e/ -v -s --tb=long --log-cli-level=DEBUG
```

## Best Practices

1. **Keep Tests Fast**: E2E tests should complete within 30-60 minutes
2. **Isolate Tests**: Each test should be independent
3. **Clean Up**: Always clean up test data and services
4. **Handle Failures**: Tests should handle service failures gracefully
5. **Document Changes**: Update tests when API contracts change

## Future Improvements

- [ ] Parallel test execution
- [ ] Test result caching
- [ ] Performance benchmarking
- [ ] Visual regression testing (if UI added)
- [ ] Cross-browser testing (if UI added)

