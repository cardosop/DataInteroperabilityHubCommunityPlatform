# Connection Validation Rules - Test Execution Guide

This document provides instructions for running and validating the connection validation rules tests.

## Overview

The connection validation rules implementation includes three main validation methods:
1. `validate_connection_config()` - Validates marketplace connection configuration
2. `validate_connection_access()` - Validates user permissions and tenant access
3. `validate_connection_test()` - Validates connection testability and test results

## Test Files

- **Unit Tests**: `hub/apps/integrations/tests/test_connection_validation_rules.py`
- **Integration Tests**: `hub/apps/integrations/tests/test_connection_validation_integration.py`

## Running Tests

### Using Docker Compose (Recommended)

Since services run in Docker Compose, use the following commands:

```bash
# Run unit tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --verbosity=2

# Run integration tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_integration --verbosity=2

# Run both test files
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules hub.apps.integrations.tests.test_connection_validation_integration --verbosity=2
```

### Using pytest (if configured)

```bash
# Run unit tests
pytest hub/apps/integrations/tests/test_connection_validation_rules.py -v

# Run integration tests
pytest hub/apps/integrations/tests/test_connection_validation_integration.py -v

# Run with coverage
pytest hub/apps/integrations/tests/test_connection_validation_rules.py --cov=hub.apps.integrations.business_rules --cov-report=html
```

### Using Makefile

```bash
# Run all tests
make test

# Run specific test file
pytest hub/apps/integrations/tests/test_connection_validation_rules.py -v
```

## Test Coverage

### Unit Tests (`test_connection_validation_rules.py`)

The unit tests cover:

1. **validate_connection_config()**:
   - ✅ Successful validation
   - ✅ Invalid marketplace type
   - ✅ Invalid config type
   - ✅ Empty connection name
   - ✅ Name uniqueness (duplicate name)
   - ✅ Name uniqueness on update (should pass)
   - ✅ Invalid credentials format

2. **validate_connection_access()**:
   - ✅ Successful validation with DATA_PROVIDER role
   - ✅ User not found
   - ✅ No permission (missing role)
   - ✅ Tenant mismatch
   - ✅ Platform admin access
   - ✅ Tenant not verified (KYC)
   - ✅ Quota exceeded (50 connections)
   - ✅ Quota warning (40 connections, 80% threshold)

3. **validate_connection_test()**:
   - ✅ Successful test validation
   - ✅ Inactive connection
   - ✅ Failed test results
   - ✅ High latency warning
   - ✅ Invalid config type
   - ✅ No test results provided

### Integration Tests (`test_connection_validation_integration.py`)

The integration tests cover:

1. **GovernanceService Integration**:
   - ✅ Permission pattern matches GovernanceService
   - ✅ Missing permissions match GovernanceService behavior
   - ✅ Platform admin handling matches GovernanceService

2. **TenantService Integration**:
   - ✅ Tenant verification via TenantService
   - ✅ Unverified tenant handling
   - ✅ Quota checking with TenantService

## Expected Test Results

All tests should pass. The tests are designed to:
- Use real services (no mocks/stubs)
- Test actual behavior, not implementation details
- Follow engineering best practices
- Fix root causes, not symptoms

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Django is properly installed and configured
2. **Database Errors**: Ensure PostgreSQL is running and migrations are applied
3. **Permission Errors**: Ensure test user has proper roles assigned
4. **Encryption Errors**: Ensure connection configs are properly encrypted/decrypted

### Debugging Failed Tests

```bash
# Run with verbose output
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --verbosity=3

# Run specific test
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules.ConnectionValidationRulesTest.test_validate_connection_config_success --verbosity=2

# Run with pdb debugger
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --pdb
```

## Implementation Details

### Method Signatures

```python
def validate_connection_config(
    self,
    marketplace_type: str,
    config: Dict[str, Any],
    connection_name: str,
    tenant_id: str,
    connection_id: Optional[str] = None
) -> ValidationResult

def validate_connection_access(
    self,
    user_id: str,
    tenant_id: str
) -> ValidationResult

def validate_connection_test(
    self,
    connection: MarketplaceConnection,
    test_results: Optional[Dict[str, Any]] = None
) -> ValidationResult
```

### Validation Rules

1. **Connection Config**:
   - Marketplace type must be supported by MarketplaceConnectorFactory
   - Config must be a dictionary
   - Config structure must match marketplace requirements
   - Credentials must be non-empty strings
   - Connection name must be unique within tenant

2. **Connection Access**:
   - User must have DATA_PROVIDER or TENANT_ADMIN role
   - Tenant must have VERIFIED KYC status and ACTIVE status
   - Tenant must not exceed max connections limit (50 default)

3. **Connection Test**:
   - Connection must be active
   - Config must be valid and decryptable
   - Test results must indicate success/failure
   - High latency (>5000ms) generates warning

## Next Steps

After running tests:
1. Review any failures and fix root causes
2. Ensure all tests pass
3. Update tasks.md to mark implementation complete
4. Document any edge cases discovered

