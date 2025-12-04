# Test Data Setup Documentation

Complete guide for creating and managing test data in the Data Interoperability Hub test suite.

## Table of Contents

1. [Overview](#overview)
2. [Test Factories](#test-factories)
3. [Test Fixtures](#test-fixtures)
4. [Creating Test Data](#creating-test-data)
5. [Test Data Cleanup](#test-data-cleanup)
6. [Test Database Setup](#test-database-setup)
7. [Test S3 Bucket Setup](#test-s3-bucket-setup)
8. [Test Redis Setup](#test-redis-setup)
9. [Test Email Service Setup](#test-email-service-setup)
10. [Test Isolation Strategies](#test-isolation-strategies)

---

## Overview

The test suite uses **Factory Boy** for test data creation and **pytest fixtures** for test setup and cleanup. All test data is created in isolated test databases to ensure test independence.

**Key Principles**:
- **No mocks/stubs**: Tests use real services and data (per project requirements)
- **Test isolation**: Each test runs in its own database transaction
- **Automatic cleanup**: Test data is automatically cleaned up after each test
- **Factory-based**: Use factories for consistent test data creation

---

## Test Factories

### Location

Test factories are located in:
- `tests/factories.py` - Main factories for core models
- `hub/apps/contracts/tests/factories.py` - Contract-specific factories

### Available Factories

#### Core Factories (`tests/factories.py`)

**TenantFactory**
```python
from tests.factories import TenantFactory

# Create tenant with defaults
tenant = TenantFactory()

# Create tenant with custom values
tenant = TenantFactory(
    name="Custom Tenant",
    slug="custom-tenant",
    status="ACTIVE",
    kyc_status="VERIFIED"
)
```

**TenantConfigFactory**
```python
from tests.factories import TenantConfigFactory

# Create tenant config with defaults
config = TenantConfigFactory(tenant=tenant)

# Create tenant config with custom rate limits
config = TenantConfigFactory(
    tenant=tenant,
    rate_limits={
        "dq_runs": {
            "burst_per_10s": 50,
            "sustained_per_min": 200
        }
    }
)
```

**UserFactory**
```python
from tests.factories import UserFactory

# Create user with defaults
user = UserFactory(tenant=tenant)

# Create user with custom values
user = UserFactory(
    tenant=tenant,
    email="custom@example.com",
    status=UserStatus.ACTIVE
)
```

**APIKeyFactory**
```python
from tests.factories import APIKeyFactory

# Create API key
api_key = APIKeyFactory(user=user, tenant=tenant)
```

**EmailDeliveryFactory**
```python
from tests.factories import EmailDeliveryFactory

# Create email delivery record
delivery = EmailDeliveryFactory(
    tenant=tenant,
    user=user,
    email_type="USER_INVITATION",
    status="SENT"
)
```

**JobFactory**
```python
from tests.factories import JobFactory

# Create job
job = JobFactory(
    tenant=tenant,
    user=user,
    job_type=JobType.DQ_RUN,
    status=JobStatus.PENDING
)
```

#### Contract Factories (`hub/apps/contracts/tests/factories.py`)

**ContractFactoryEnhanced**
```python
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

# Create contract with complete HubContract JSON
contract = ContractFactoryEnhanced.create_contract_with_all_sections(
    tenant=tenant,
    asset=asset
)

# Create HubContract JSON only
contract_json = ContractFactoryEnhanced.create_hub_contract_json()
```

---

## Test Fixtures

### Location

Test fixtures are located in:
- `tests/conftest.py` - Global pytest fixtures
- `tests/e2e/conftest.py` - E2E-specific fixtures
- `tests/fixtures/email_service_fixtures.py` - Email service fixtures

### Available Fixtures

#### Database Fixtures

**`db`** (pytest-django)
- Automatically creates test database
- Runs migrations
- Cleans up after tests

**`transactional_db`**
- For tests that require transaction support
- Use `@pytest.mark.django_db(transaction=True)`

#### Service Fixtures

**`sendgrid_email_service_config`**
```python
def test_email_sending(sendgrid_email_service_config):
    # Email service configured for SendGrid
    # Test email sending logic
    pass
```

**`ses_email_service_config`**
```python
def test_email_sending(ses_email_service_config):
    # Email service configured for AWS SES
    pass
```

**`smtp_email_service_config`**
```python
def test_email_sending(smtp_email_service_config):
    # Email service configured for SMTP
    pass
```

#### E2E Fixtures

**`E2ETestBase`** (from `tests/e2e/conftest.py`)
- Base class for E2E tests
- Provides `setUp()` with tenant, user, and API client
- Includes service health checks

---

## Creating Test Data

### Basic Test Data Creation

```python
import pytest
from tests.factories import TenantFactory, UserFactory, TenantConfigFactory

@pytest.mark.django_db
def test_example():
    # Create tenant
    tenant = TenantFactory()
    
    # Create user
    user = UserFactory(tenant=tenant)
    
    # Create tenant config
    config = TenantConfigFactory(tenant=tenant)
    
    # Use in test
    assert tenant.name is not None
    assert user.tenant == tenant
```

### Using Factories in setUp

```python
from django.test import TestCase
from tests.factories import TenantFactory, UserFactory

class MyTestCase(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
```

### Creating Related Objects

```python
# Create tenant with config
tenant = TenantFactory()
config = TenantConfigFactory(tenant=tenant)

# Create user with roles
user = UserFactory(tenant=tenant)
role = Role.objects.create(tenant=tenant, name="DATA_PROVIDER")
UserRole.objects.create(user=user, role=role)
```

### Creating Complex Test Data

```python
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

# Create contract with all sections
contract = ContractFactoryEnhanced.create_contract_with_all_sections(
    tenant=tenant,
    asset=asset,
    owners=[{"name": "Owner 1", "email": "owner1@example.com"}],
    tags=["tag1", "tag2"],
    quality_rules=[{
        "rule_id": "rule1",
        "dimension": "completeness",
        "expression": "field IS NOT NULL"
    }]
)
```

---

## Test Data Cleanup

### Automatic Cleanup

Django's test framework automatically:
- Creates a fresh test database for each test run
- Rolls back transactions after each test
- Cleans up test database after test run

### Manual Cleanup

If needed, manually clean up test data:

```python
def tearDown(self):
    # Clean up specific objects
    MyModel.objects.filter(tenant=self.tenant).delete()
    
    # Or clean up all test data
    Tenant.objects.all().delete()
```

### Cleanup in Fixtures

```python
@pytest.fixture
def clean_tenant():
    tenant = TenantFactory()
    yield tenant
    # Cleanup after test
    tenant.delete()
```

---

## Test Database Setup

### Automatic Setup

Django automatically:
1. Creates test database (`hub_test` by default)
2. Runs all migrations
3. Sets up test database schema
4. Cleans up after test run

### Manual Database Setup

```python
# Force database creation
pytest --create-db tests/unit/ -v

# Use specific database
DATABASE_URL=postgresql://user:pass@localhost/hub_test pytest tests/unit/ -v
```

### Database Isolation

Each test runs in a transaction that is rolled back after the test:

```python
@pytest.mark.django_db(transaction=True)
def test_with_transaction():
    # Test runs in transaction
    # Automatically rolled back after test
    pass
```

---

## Test S3 Bucket Setup

### Using MinIO for Tests

Tests use MinIO (S3-compatible storage) for file operations:

```python
# S3/MinIO is automatically configured in test settings
# Files are stored in test bucket
# Bucket is cleaned up after test run
```

### Creating Test Files

```python
from hub.apps.files.models import File

# Create file record
file_obj = File.objects.create(
    tenant=tenant,
    user=user,
    name="test.csv",
    size=1024,
    content_type="text/csv",
    s3_key="test/test.csv"
)

# Upload actual file content (if needed)
# File content is stored in MinIO test bucket
```

### S3 Mocking (if needed)

```python
# Tests can use S3 mocking for faster execution
# See test helper methods for S3 mocking
```

---

## Test Redis Setup

### Automatic Setup

Redis is automatically configured for tests:
- Test Redis instance (separate from production)
- Test data is isolated
- Cleanup after test run

### Using Redis in Tests

```python
from django_rq import get_connection

# Get Redis connection
redis_conn = get_connection()

# Use Redis for test data
redis_conn.set("test_key", "test_value")
value = redis_conn.get("test_key")
```

### Redis Cleanup

```python
def tearDown(self):
    # Clean up Redis keys
    redis_conn = get_connection()
    redis_conn.flushdb()  # Clear all keys
```

---

## Test Email Service Setup

### Email Service Fixtures

Tests use real email service configurations (not mocks):

```python
@pytest.fixture
def sendgrid_email_service_config(settings):
    """Configure email service for SendGrid"""
    settings.EMAIL_BACKEND = 'hub.apps.notifications.services.SendGridEmailService'
    settings.SENDGRID_API_KEY = 'test_key'
    return settings
```

### Email Delivery Tracking

```python
from tests.factories import EmailDeliveryFactory

# Create email delivery record
delivery = EmailDeliveryFactory(
    tenant=tenant,
    user=user,
    email_type="USER_INVITATION",
    status="PENDING"
)

# Test email sending
# Delivery status is updated automatically
```

---

## Test Isolation Strategies

### Transaction Isolation

Each test runs in its own transaction:

```python
@pytest.mark.django_db(transaction=True)
def test_isolated():
    # Test runs in transaction
    # Changes are rolled back after test
    pass
```

### Database Isolation

Test database is separate from development database:
- Database name: `hub_test` (by default)
- Schema is created fresh for each test run
- Data is cleaned up after test run

### Redis Isolation

Test Redis instance is separate:
- Use test Redis connection
- Keys are namespaced for tests
- Cleanup after test run

### S3 Isolation

Test S3 bucket is separate:
- Test bucket: `hub-test` (by default)
- Files are isolated from production
- Cleanup after test run

---

## Example Test Data Creation

### Complete Example

```python
import pytest
from django.test import TestCase
from tests.factories import (
    TenantFactory,
    UserFactory,
    TenantConfigFactory,
    JobFactory
)
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.users.models import Role, UserRole, UserStatus

@pytest.mark.django_db(transaction=True)
class CompleteTestExample(TestCase):
    def setUp(self):
        # Create tenant
        self.tenant = TenantFactory(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        # Create tenant config
        self.config = TenantConfigFactory(
            tenant=self.tenant,
            default_dq_profile="intake_basic_gx",
            rate_limits={
                "dq_runs": {
                    "burst_per_10s": 50,
                    "sustained_per_min": 200
                }
            }
        )
        
        # Create user with role
        self.user = UserFactory(
            tenant=self.tenant,
            email="test@example.com",
            status=UserStatus.ACTIVE
        )
        
        role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_PROVIDER"
        )
        UserRole.objects.create(user=self.user, role=role)
        
        # Create contract
        self.contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            owners=[{"name": "Owner", "email": "owner@example.com"}],
            tags=["test"]
        )
    
    def test_example(self):
        # Test uses self.tenant, self.user, self.contract
        assert self.tenant.name == "Test Tenant"
        assert self.user.tenant == self.tenant
        assert self.contract.tenant == self.tenant
```

---

## Best Practices

1. **Use Factories**: Always use factories for test data creation
2. **Keep Tests Isolated**: Each test should be independent
3. **Clean Up**: Let Django handle cleanup automatically (transaction rollback)
4. **Use Real Data**: Use real service configurations (not mocks)
5. **Consistent Data**: Use factories for consistent test data
6. **Minimal Data**: Create only the data needed for the test
7. **Descriptive Names**: Use descriptive names for test data

---

## Troubleshooting

### Issue: Test data persists between tests

**Solution**: Ensure tests use `@pytest.mark.django_db(transaction=True)` for transaction isolation.

### Issue: Foreign key constraints fail

**Solution**: Create parent objects before child objects:
```python
tenant = TenantFactory()  # Parent first
user = UserFactory(tenant=tenant)  # Child second
```

### Issue: Test data conflicts

**Solution**: Use unique values or let factories generate unique values:
```python
tenant = TenantFactory(slug=f"tenant-{uuid.uuid4()}")  # Unique slug
```

---

**Last Updated**: 2025-12-04  
**Maintainer**: Engineering Team

