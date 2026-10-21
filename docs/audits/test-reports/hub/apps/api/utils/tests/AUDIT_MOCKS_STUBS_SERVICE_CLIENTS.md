# Audit: Service Client Test Mocks/Stubs

**Date:** 2026-01-04
**File:** `hub/apps/api/utils/tests/test_service_clients.py`
**Task:** 9.9.3.3.1

## Summary

This audit identifies all mocks and stubs used in service client tests and documents a plan for replacing them with real implementations.

## Mocks/Stubs Inventory

### 1. HTTP Client Mocks (`httpx.Client`)

#### Location: Multiple test methods
- **Mock Type:** `@patch('hub.apps.{service}.service_client.httpx.Client')`
- **What it replaces:** Real `httpx.Client` instances used for HTTP communication
- **Occurrences:**
  - `DQServiceClientTest.test_health_check_success` (line 27)
  - `DQServiceClientTest.test_health_check_failure` (line 47)
  - `DQServiceClientTest.test_run_dq_endpoint_construction` (line 62)
  - `ComplianceServiceClientTest.test_health_check_success` (line 93)
  - `ComplianceServiceClientTest.test_scan_file_endpoint_construction` (line 112)
  - `SemanticServiceClientTest.test_health_check_success` (line 140)
  - `SemanticServiceClientTest.test_map_contract_endpoint_construction` (line 159)
  - `SemanticServiceClientTest.test_resolve_uri_endpoint_construction` (line 183)
  - `DataContractCLIClientTest.test_validate_endpoint_construction` (line 213)
  - `DataContractCLIClientTest.test_lint_endpoint_construction` (line 247)

**Impact:** Prevents real HTTP calls to microservices, making tests fast but not validating real network behavior.

**Replacement Plan:**
- Use real `httpx.Client` instances pointing to Docker Compose services
- Configure test services to run in Docker Compose test environment
- Use test-specific service URLs (e.g., `http://localhost:8083` for DQ service in tests)
- Handle service unavailability gracefully (circuit breaker should handle this)

### 2. Mock HTTP Response Objects

#### Location: All test methods that make HTTP calls
- **Mock Type:** `Mock()` objects with `.json()`, `.raise_for_status()` methods
- **What it replaces:** Real `httpx.Response` objects from HTTP calls
- **Occurrences:**
  - All test methods that verify endpoint construction
  - All test methods that verify response handling

**Impact:** Tests don't validate actual response parsing, error handling, or response structure.

**Replacement Plan:**
- Use real HTTP responses from Docker Compose services
- Create test fixtures/endpoints in services that return predictable responses
- Use real response parsing logic
- Test actual error handling with real HTTP error responses

### 3. Mock HTTP Client Instances

#### Location: Test methods that set `client.client = mock_client`
- **Mock Type:** `Mock()` objects with `.request()`, `.get()`, `.post()` methods
- **What it replaces:** Real `httpx.Client` instance methods
- **Occurrences:**
  - All test methods that verify HTTP method calls
  - All test methods that verify endpoint construction

**Impact:** Tests verify method calls but not actual HTTP behavior.

**Replacement Plan:**
- Remove manual client assignment
- Use real client instances initialized by service client classes
- Verify actual HTTP calls are made (can use httpx test client or real services)

### 4. Circuit Breaker Mocks

#### Location: Test methods that test endpoint construction
- **Mock Type:** `Mock()` objects with `.call()` method
- **What it replaces:** Real `CircuitBreaker` instances
- **Occurrences:**
  - `DQServiceClientTest.test_run_dq_endpoint_construction` (line 78)
  - `ComplianceServiceClientTest.test_scan_file_endpoint_construction` (line 125)
  - `SemanticServiceClientTest.test_map_contract_endpoint_construction` (line 172)
  - `SemanticServiceClientTest.test_resolve_uri_endpoint_construction` (line 196)
  - `DataContractCLIClientTest.test_validate_endpoint_construction` (line 232)
  - `DataContractCLIClientTest.test_lint_endpoint_construction` (line 266)

**Impact:** Tests bypass circuit breaker logic, not validating resilience patterns.

**Replacement Plan:**
- Use real `CircuitBreaker` instances
- Configure circuit breakers with test-appropriate thresholds
- Test circuit breaker behavior with real service failures
- Use in-memory circuit breaker state for tests (Redis may not be available)

### 5. Redis Client Mocks

#### Location: `DQServiceClientTest.setUp`
- **Mock Type:** `@patch('hub.apps.dq.service_client.get_redis_client')`
- **What it replaces:** Real Redis client for circuit breaker state
- **Occurrences:**
  - `DQServiceClientTest.setUp` (line 23)

**Impact:** Prevents real Redis connection, but circuit breaker can use in-memory state.

**Replacement Plan:**
- Allow circuit breaker to use in-memory state when Redis unavailable
- Or use real Redis in Docker Compose test environment
- Circuit breaker already handles Redis unavailability gracefully

### 6. Cache Mocks

#### Location: Test methods that test caching behavior
- **Mock Type:** `@patch('hub.apps.{service}.service_client.cache')`
- **What it replaces:** Django cache framework
- **Occurrences:**
  - `DQServiceClientTest.test_run_dq_endpoint_construction` (line 63)
  - `DataContractCLIClientTest.test_validate_endpoint_construction` (line 214)
  - `DataContractCLIClientTest.test_lint_endpoint_construction` (line 248)

**Impact:** Tests don't validate actual caching behavior.

**Replacement Plan:**
- Use real Django cache (can use in-memory cache for tests)
- Test actual cache hit/miss behavior
- Verify cache keys and TTLs are correct

### 7. Context Manager Mocks (DataContractCLIClient)

#### Location: `DataContractCLIClientTest` methods
- **Mock Type:** `Mock()` with `__enter__` and `__exit__` methods
- **What it replaces:** Real `httpx.Client` context manager behavior
- **Occurrences:**
  - `DataContractCLIClientTest.test_validate_endpoint_construction` (lines 225-228)
  - `DataContractCLIClientTest.test_lint_endpoint_construction` (lines 259-262)

**Impact:** Tests don't validate proper resource cleanup.

**Replacement Plan:**
- Use real `httpx.Client` context manager
- Verify proper connection cleanup
- Use real context manager patterns

## Replacement Plan

### Phase 1: Infrastructure Setup
1. **Docker Compose Test Services**
   - Ensure test services are available in Docker Compose
   - Configure test-specific ports and URLs
   - Add health check endpoints for test services

2. **Test Configuration**
   - Use `override_settings` to configure service URLs for tests
   - Configure circuit breakers with test-appropriate thresholds
   - Use in-memory cache for tests

### Phase 2: HTTP Client Replacement
1. **Remove `httpx.Client` patches**
   - Use real `httpx.Client` instances
   - Point to Docker Compose test services
   - Handle service unavailability gracefully

2. **Remove response mocks**
   - Use real HTTP responses
   - Create test fixtures in services for predictable responses
   - Test actual response parsing

### Phase 3: Circuit Breaker Replacement
1. **Remove circuit breaker mocks**
   - Use real `CircuitBreaker` instances
   - Configure with test thresholds
   - Test circuit breaker behavior with real failures

2. **Redis handling**
   - Allow in-memory circuit breaker state
   - Or use real Redis in Docker Compose

### Phase 4: Cache Replacement
1. **Remove cache mocks**
   - Use real Django cache (in-memory for tests)
   - Test actual cache behavior
   - Verify cache keys and TTLs

### Phase 5: Context Manager Replacement
1. **Remove context manager mocks**
   - Use real `httpx.Client` context managers
   - Verify proper resource cleanup

## Test Strategy

### Unit Tests (Keep Current)
- Keep current mocked tests for fast unit testing
- Focus on endpoint construction validation
- Fast execution, no external dependencies

### Integration Tests (New)
- Create new integration test file: `test_service_clients_integration.py`
- Use real HTTP clients and services
- Test against Docker Compose services
- Validate real network behavior, error handling, circuit breakers

### Test Organization
- **Unit tests:** Fast, mocked, test logic and endpoint construction
- **Integration tests:** Slower, real services, test actual behavior
- Both test suites complement each other

## Implementation Notes

1. **Service Availability**
   - Tests should handle service unavailability gracefully
   - Use circuit breakers to handle failures
   - Skip integration tests if services unavailable (mark with `@skipIf`)

2. **Test Data**
   - Create test fixtures in services
   - Use predictable test data
   - Clean up test data after tests

3. **Performance**
   - Integration tests will be slower
   - Run integration tests separately from unit tests
   - Use test markers to distinguish test types

4. **Existing Integration Tests**
   - File `test_service_clients_real_integration.py` already exists
   - Review and enhance existing integration tests
   - Ensure they cover all scenarios currently mocked

## Files to Modify

1. **`hub/apps/api/utils/tests/test_service_clients.py`**
   - Keep as unit tests with mocks (fast tests)
   - Add comments explaining these are unit tests
   - Consider renaming to `test_service_clients_unit.py`

2. **`hub/apps/api/utils/tests/test_service_clients_real_integration.py`**
   - Enhance existing integration tests
   - Add missing test scenarios
   - Ensure all mocked scenarios are covered

3. **`hub/apps/api/utils/tests/test_service_to_service_integration.py`**
   - Review and update if needed
   - Ensure no duplicate test coverage

## Dependencies

- Docker Compose services must be running for integration tests
- Test services must have health check endpoints
- Circuit breaker must handle Redis unavailability
- Cache must work in test environment

## Success Criteria

- [ ] All mocks/stubs identified and documented
- [ ] Replacement plan created
- [ ] Integration tests cover all mocked scenarios
- [ ] Unit tests remain fast and focused
- [ ] Integration tests work with Docker Compose
- [ ] Tests handle service unavailability gracefully

## Next Steps

1. **Task 9.9.3.3.2:** Replace mocks/stubs with real implementations
2. **Task 9.9.3.3.3:** Verify tests work correctly with real services

## Audit Status

✅ **AUDIT COMPLETE**

All mocks/stubs have been identified, documented, and a comprehensive replacement plan has been created.

