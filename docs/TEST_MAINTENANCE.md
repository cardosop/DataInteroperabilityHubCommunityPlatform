# Test Maintenance Guidelines

Complete guide for maintaining and updating tests in the Data Interoperability Hub test suite.

## Table of Contents

1. [Overview](#overview)
2. [Test Maintenance Best Practices](#test-maintenance-best-practices)
3. [When to Add New Tests](#when-to-add-new-tests)
4. [Test Organization Principles](#test-organization-principles)
5. [Test Naming Conventions](#test-naming-conventions)
6. [Test Review Process](#test-review-process)
7. [Test Refactoring Guidelines](#test-refactoring-guidelines)
8. [Maintaining Test Fixtures](#maintaining-test-fixtures)
9. [Updating Tests for Code Changes](#updating-tests-for-code-changes)
10. [Handling Flaky Tests](#handling-flaky-tests)

---

## Overview

Test maintenance is crucial for keeping the test suite reliable, maintainable, and effective. This document provides guidelines for maintaining tests as the codebase evolves.

**Key Principles**:
- **Keep tests up-to-date**: Update tests when code changes
- **Maintain test quality**: Follow best practices and conventions
- **Fix failures immediately**: Don't let test failures accumulate
- **Refactor when needed**: Improve tests as code improves

---

## Test Maintenance Best Practices

### 1. Keep Tests Synchronized with Code

- **Update tests when code changes**: If you change a function signature, update its tests
- **Add tests for new features**: Every new feature should have corresponding tests
- **Remove tests for removed features**: Delete tests for deprecated/removed functionality

### 2. Maintain Test Independence

- **No test dependencies**: Tests should not depend on other tests
- **Isolated test data**: Each test should create its own test data
- **Clean up after tests**: Tests should clean up any side effects

### 3. Keep Tests Fast

- **Optimize slow tests**: Identify and optimize slow-running tests
- **Use appropriate test types**: Use unit tests for logic, integration for APIs
- **Parallel execution**: Use pytest-xdist for parallel test execution when possible

### 4. Maintain Test Readability

- **Clear test names**: Test names should describe what is being tested
- **Well-organized code**: Follow consistent structure and organization
- **Good comments**: Add comments for complex test logic

### 5. Regular Test Review

- **Review test coverage**: Regularly review test coverage metrics
- **Identify gaps**: Identify missing test coverage
- **Refactor tests**: Improve tests as code improves

---

## When to Add New Tests

### Always Add Tests For

1. **New Features**: Every new feature should have tests
2. **Bug Fixes**: Add regression tests for bugs
3. **Edge Cases**: Add tests for edge cases discovered
4. **Performance Issues**: Add performance tests for performance-critical code
5. **Security Issues**: Add security tests for security-sensitive code

### Test Coverage Requirements

- **Unit Tests**: 100% coverage target for new code
- **Integration Tests**: 90%+ coverage for API endpoints
- **E2E Tests**: 100% coverage for user journeys
- **Edge Cases**: 90%+ coverage for edge case scenarios

### When Not to Add Tests

- **Trivial code**: Simple getters/setters may not need tests
- **Generated code**: Auto-generated code doesn't need tests
- **Third-party code**: Don't test third-party libraries
- **Configuration**: Simple configuration doesn't need tests

---

## Test Organization Principles

### Directory Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
│   ├── tenant_config/
│   ├── worker/
│   ├── notifications/
│   └── ...
├── integration/       # Integration tests (service interactions)
│   ├── test_tenant_config_api.py
│   ├── test_worker_service.py
│   └── ...
├── e2e/              # E2E tests (complete journeys)
│   ├── test_tenant_config_e2e.py
│   ├── test_persona_*.py
│   └── ...
└── performance/      # Performance tests
    └── test_performance.py
```

### File Naming

- **Unit tests**: `test_<module_name>.py` (e.g., `test_models.py`)
- **Integration tests**: `test_<feature>_integration.py` (e.g., `test_tenant_config_api.py`)
- **E2E tests**: `test_<feature>_e2e.py` (e.g., `test_tenant_config_e2e.py`)
- **Performance tests**: `test_<feature>_performance.py` (e.g., `test_rate_limit_performance.py`)

### Test Class Organization

```python
class FeatureTest(TestCase):
    """Tests for Feature"""
    
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def test_feature_basic_functionality(self):
        """Test basic feature functionality"""
        pass
    
    def test_feature_edge_case(self):
        """Test feature edge case"""
        pass
    
    def test_feature_error_handling(self):
        """Test feature error handling"""
        pass
```

---

## Test Naming Conventions

### Test Method Names

**Format**: `test_<what>_<condition>_<expected_result>`

**Examples**:
```python
def test_tenant_config_creation_with_defaults_returns_config(self):
    """Test tenant config creation with defaults returns config"""
    pass

def test_tenant_config_update_with_invalid_profile_raises_validation_error(self):
    """Test tenant config update with invalid profile raises validation error"""
    pass

def test_rate_limit_check_with_exceeded_limit_returns_false(self):
    """Test rate limit check with exceeded limit returns false"""
    pass
```

### Test Class Names

**Format**: `<Feature>Test` or `<Feature><Type>Test`

**Examples**:
```python
class TenantConfigModelTest(TestCase):
    """Tests for TenantConfig model"""
    pass

class RateLimitIntegrationTest(TestCase):
    """Integration tests for rate limiting"""
    pass

class TenantAdminPersonaTest(E2ETestBase):
    """E2E tests for TENANT_ADMIN persona"""
    pass
```

### Test File Names

- **Unit tests**: `test_<module>.py` (e.g., `test_models.py`)
- **Integration tests**: `test_<feature>_integration.py`
- **E2E tests**: `test_<feature>_e2e.py` or `test_persona_<persona>.py`

---

## Test Review Process

### Pre-Commit Review

Before committing test changes:

1. **Run tests locally**: Ensure all tests pass
2. **Check coverage**: Verify test coverage meets targets
3. **Review test quality**: Ensure tests follow best practices
4. **Update documentation**: Update test documentation if needed

### Code Review Checklist

When reviewing test code:

- [ ] Tests are well-organized and readable
- [ ] Test names clearly describe what is being tested
- [ ] Tests are independent (no dependencies on other tests)
- [ ] Tests use appropriate fixtures and factories
- [ ] Tests clean up after themselves
- [ ] Tests cover both success and failure cases
- [ ] Tests cover edge cases
- [ ] Test assertions are clear and meaningful
- [ ] Tests follow naming conventions
- [ ] Tests have appropriate docstrings

### Test Review Criteria

**Completeness**:
- [ ] All code paths are tested
- [ ] Edge cases are covered
- [ ] Error cases are covered
- [ ] Success cases are covered

**Quality**:
- [ ] Tests are readable and maintainable
- [ ] Tests follow best practices
- [ ] Tests use appropriate test types
- [ ] Tests are fast and efficient

**Documentation**:
- [ ] Test docstrings are clear
- [ ] Complex test logic is commented
- [ ] Test setup is documented

---

## Test Refactoring Guidelines

### When to Refactor Tests

1. **Duplication**: If test code is duplicated, extract common logic
2. **Complexity**: If tests are too complex, simplify them
3. **Performance**: If tests are slow, optimize them
4. **Maintainability**: If tests are hard to maintain, refactor them

### Refactoring Patterns

#### Extract Common Setup

```python
# Before: Duplicated setup
def test_feature1(self):
    tenant = TenantFactory()
    user = UserFactory(tenant=tenant)
    # Test logic

def test_feature2(self):
    tenant = TenantFactory()
    user = UserFactory(tenant=tenant)
    # Test logic

# After: Extracted setup
def setUp(self):
    self.tenant = TenantFactory()
    self.user = UserFactory(tenant=self.tenant)

def test_feature1(self):
    # Test logic using self.tenant, self.user

def test_feature2(self):
    # Test logic using self.tenant, self.user
```

#### Extract Helper Methods

```python
# Before: Duplicated helper logic
def test_feature1(self):
    # Complex setup logic
    result = do_something()
    # Assertions

# After: Extracted helper
def _setup_complex_scenario(self):
    """Helper method for complex setup"""
    # Complex setup logic
    return result

def test_feature1(self):
    result = self._setup_complex_scenario()
    # Assertions
```

#### Use Fixtures for Common Data

```python
# Before: Creating data in each test
def test_feature1(self):
    tenant = TenantFactory()
    config = TenantConfigFactory(tenant=tenant)
    # Test logic

# After: Using fixtures
@pytest.fixture
def tenant_with_config():
    tenant = TenantFactory()
    config = TenantConfigFactory(tenant=tenant)
    return tenant, config

def test_feature1(tenant_with_config):
    tenant, config = tenant_with_config
    # Test logic
```

---

## Maintaining Test Fixtures

### Factory Maintenance

**Update factories when models change**:
```python
# If Tenant model adds new field
class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant
    
    name = factory.Sequence(lambda n: f"Tenant {n}")
    new_field = factory.Faker('text')  # Add new field
```

**Keep factories up-to-date**:
- Update factories when model fields change
- Add new factory methods for new use cases
- Remove deprecated factory methods

### Fixture Maintenance

**Update fixtures when services change**:
```python
# If email service configuration changes
@pytest.fixture
def email_service_config(settings):
    """Update fixture for new email service config"""
    settings.EMAIL_BACKEND = 'new.backend'
    settings.NEW_SETTING = 'value'
    return settings
```

---

## Updating Tests for Code Changes

### When Code Changes

1. **Function signature changes**: Update test calls
2. **Return value changes**: Update test assertions
3. **Behavior changes**: Update test expectations
4. **New features**: Add new tests
5. **Removed features**: Remove obsolete tests

### Example: Updating Tests for API Changes

```python
# Before: Old API
def test_get_tenant_config(self):
    response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config")
    self.assertEqual(response.status_code, 200)

# After: New API (URL changed)
def test_get_tenant_config(self):
    response = self.client.get(f"/api/v1/tenants/tenants/{self.tenant.id}/config/")
    self.assertEqual(response.status_code, 200)
```

### Example: Updating Tests for Model Changes

```python
# Before: Old field name
def test_tenant_config(self):
    config = TenantConfigFactory(max_file_size_mb=500)
    self.assertEqual(config.max_file_size_mb, 500)

# After: New field name
def test_tenant_config(self):
    config = TenantConfigFactory(max_file_size_bytes=500 * 1024 * 1024)
    self.assertEqual(config.max_file_size_bytes, 500 * 1024 * 1024)
```

---

## Handling Flaky Tests

### Identifying Flaky Tests

**Symptoms**:
- Tests pass sometimes, fail other times
- Tests fail intermittently
- Tests depend on timing or order

**Common Causes**:
- Race conditions
- Timing issues
- Shared state
- External dependencies

### Fixing Flaky Tests

#### 1. Fix Race Conditions

```python
# Before: Race condition
def test_concurrent_updates(self):
    # Two threads update simultaneously
    # May cause race condition

# After: Proper synchronization
def test_concurrent_updates(self):
    # Use locks or transactions
    with transaction.atomic():
        # Update logic
        pass
```

#### 2. Fix Timing Issues

```python
# Before: Timing-dependent
def test_job_completion(self):
    job = create_job()
    # May fail if job completes too fast
    assert job.status == "COMPLETED"

# After: Proper waiting
def test_job_completion(self):
    job = create_job()
    # Wait for job completion
    wait_for_job_completion(job, timeout=30)
    assert job.status == "COMPLETED"
```

#### 3. Fix Shared State

```python
# Before: Shared state
def test_feature1(self):
    # Uses global state
    global_counter.increment()
    assert global_counter.value == 1

# After: Isolated state
def test_feature1(self):
    # Uses isolated state
    counter = Counter()
    counter.increment()
    assert counter.value == 1
```

### Preventing Flaky Tests

1. **Use transactions**: Ensure test isolation
2. **Avoid global state**: Use isolated test data
3. **Add proper delays**: Use time.sleep() or wait functions when needed
4. **Use mocks carefully**: Only mock when necessary (per project requirements, prefer real services)
5. **Test independently**: Ensure tests don't depend on each other

---

## Best Practices Summary

1. **Keep tests synchronized**: Update tests when code changes
2. **Maintain test quality**: Follow best practices and conventions
3. **Fix failures immediately**: Don't let test failures accumulate
4. **Refactor when needed**: Improve tests as code improves
5. **Use appropriate test types**: Unit for logic, integration for APIs, E2E for journeys
6. **Keep tests fast**: Optimize slow tests
7. **Maintain test isolation**: Each test should be independent
8. **Use factories**: Use Factory Boy for test data creation
9. **Follow naming conventions**: Use clear, descriptive names
10. **Document complex tests**: Add comments for complex test logic

---

## Troubleshooting

### Issue: Tests fail after code changes

**Solution**: Update tests to match new code behavior. Review test assertions and expectations.

### Issue: Tests are slow

**Solution**: 
1. Identify slow tests: `pytest --durations=10`
2. Optimize slow tests
3. Use appropriate test types (unit vs integration vs E2E)

### Issue: Tests are flaky

**Solution**: 
1. Identify root cause (race condition, timing, shared state)
2. Fix root cause
3. Add proper synchronization or delays

### Issue: Test maintenance is difficult

**Solution**:
1. Refactor tests to reduce duplication
2. Extract common logic into helpers
3. Use fixtures for common setup
4. Follow consistent organization

---

**Last Updated**: 2025-12-04  
**Maintainer**: Engineering Team

