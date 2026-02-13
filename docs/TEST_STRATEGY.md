# Test Strategy

## No-Mocks Principle

This project follows a **no-mocks principle** for internal services and database operations. Tests should use real implementations whenever possible to ensure tests accurately reflect production behavior.

### Core Principles

1. **Prefer Real Implementations**: Use real database, real service layer, and real API clients in tests
2. **External Boundaries Only**: Mocks/stubs are acceptable only at external process boundaries (third-party services not available in test environment)
3. **Root Cause Fixes**: Address flakiness by fixing root causes (idempotency, explicit waits, timeouts) rather than retries or skipping tests

### Classification of Mocks

#### ✅ Acceptable (External Boundary)

Mocks are acceptable for:

- **Third-party HTTP services** not available in test environment (e.g., Stripe, SendGrid, external APIs)
- **External process boundaries** (e.g., Prefect flows, external connectors from `services/prefect-integration`)
- **Middleware testing** (e.g., mocking `get_response` for Django middleware tests)

**Justification Required**: All external boundary mocks must include a comment explaining why the mock is necessary and what external service it represents.

Example:
```python
# EXTERNAL BOUNDARY: Prefect is an external orchestration service
# Mocking is acceptable as Prefect server is not available in unit test environment
@patch('prefect.deployments.run_deployment')
def test_trigger_ingestion(self, mock_run_deployment):
    ...
```

#### ❌ Must Remove (Internal Services)

Mocks MUST be removed for:

- **Hub services** (`hub.apps.*`, `hub.core.*`, `hub.services.*`)
- **Database operations** (Django ORM, model methods, querysets)
- **Internal service clients** (DQServiceClient, ComplianceServiceClient, etc.)
- **Storage clients** (S3StorageClient, FileService)
- **Workflows** (ScheduledIngestionWorkflow, etc.)

**Migration Path**: Replace mocks with:
- Real database operations (using `TransactionTestCase` or `pytest.mark.django_db(transaction=True)`)
- Real service layer calls
- Real API clients (using `APIClient` with real backend)
- Real storage clients (using MinIO in test environment)

### Migration Guidelines

#### For Database Operations

**Before (with mock):**
```python
@patch('hub.apps.contracts.models.Contract.objects.filter')
def test_get_contracts(self, mock_filter):
    mock_filter.return_value = [Mock(id=1, name="Test")]
    contracts = get_contracts()
    ...
```

**After (real DB):**
```python
def test_get_contracts(self):
    # Create real contract in database
    contract = Contract.objects.create(
        tenant=self.tenant,
        name="Test Contract",
        ...
    )
    contracts = get_contracts()
    self.assertEqual(len(contracts), 1)
    self.assertEqual(contracts[0].id, contract.id)
```

#### For Service Clients

**Before (with mock):**
```python
@patch('hub.apps.dq.service_client.DQServiceClient')
def test_execute_dq_run(self, mock_client_class):
    mock_client = MagicMock()
    mock_client.run_dq.return_value = {"status": "success"}
    mock_client_class.return_value = mock_client
    ...
```

**After (real service):**
```python
def test_execute_dq_run(self):
    # Use real DQ service client
    # Ensure DQ service is available in test environment
    dq_client = DQServiceClient()
    result = dq_client.run_dq(...)
    self.assertEqual(result["status"], "success")
```

#### For Storage Clients

**Before (with mock):**
```python
@patch('hub.apps.files.storage.S3StorageClient')
def test_save_file(self, mock_storage_class):
    mock_storage = MagicMock()
    mock_storage.save_file.return_value = "path/to/file"
    mock_storage_class.return_value = mock_storage
    ...
```

**After (real storage with MinIO):**
```python
def test_save_file(self):
    # Use real S3StorageClient with MinIO in test environment
    storage = S3StorageClient()
    # Ensure MinIO is configured in test settings
    path = storage.save_file(...)
    self.assertIsNotNone(path)
    # Verify file exists in storage
    self.assertTrue(storage.file_exists(path))
```

### Handling Flakiness

When tests are flaky, fix the root cause rather than adding retries or skipping:

#### ✅ Good: Fix Root Cause

```python
def test_concurrent_operations(self):
    # Use explicit waits and timeouts
    import time
    start_time = time.time()
    timeout = 5.0

    while not condition_met():
        if time.time() - start_time > timeout:
            self.fail("Timeout waiting for condition")
        time.sleep(0.1)

    # Verify result
    self.assertTrue(condition_met())
```

#### ❌ Bad: Retry or Skip

```python
# DON'T DO THIS
@pytest.mark.flaky(reruns=3)  # ❌
def test_flaky_operation(self):
    ...

# DON'T DO THIS
@pytest.mark.skipif(condition, reason="Flaky")  # ❌
def test_flaky_operation(self):
    ...
```

### Test Environment Setup

Ensure test environment has:

1. **Real Database**: PostgreSQL with proper migrations
2. **Real Storage**: MinIO configured for S3StorageClient tests
3. **Real Services**: DQ, Compliance, and other services available (or use test doubles that behave like real services)
4. **Real Redis**: For caching and queue operations

### Priority Apps for Migration

Migrate in this order:

1. ✅ **scheduled_ingestion** - Replace S3StorageClient and ScheduledIngestionWorkflow mocks
2. ✅ **auth** - Replace internal mocks (keep middleware mocks)
3. ✅ **jobs** - Replace service client mocks with real clients
4. ✅ **contracts** - Replace caching and DB mocks
5. ✅ **assets** - Replace semantic service mocks
6. ✅ **billing/tenants** (Phase 25) - Replace storage and service mocks

### Verification

After migration:

1. ✅ All tests pass with real implementations
2. ✅ No mocks of `hub.*` services remain
3. ✅ External boundary mocks are documented with justification
4. ✅ Flakiness is addressed at root cause
5. ✅ Test execution time is acceptable (may increase slightly)

### References

- [Django Testing Best Practices](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)
