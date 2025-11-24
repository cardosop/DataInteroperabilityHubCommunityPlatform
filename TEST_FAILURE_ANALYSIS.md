# Test Failure Analysis

## Summary
- **Total Failures**: 179 tests
- **Total Passed**: 308 tests  
- **Test Coverage**: ~21%

## Top Failing Test Classes (by count)
1. **OpenAPIValidationTest**: 10 failures - OpenAPI schema generation issues
2. **TenantViewSetTest**: 9 failures - Tenant CRUD/view issues
3. **OrderFlowTest**: 9 failures - Marketplace order processing
4. **AccessCheckTest**: 9 failures - Access control logic
5. **KYCEnforcementTest**: 8 failures - KYC status enforcement
6. **SPARQLEndpointTest**: 7 failures - SPARQL query endpoint
7. **ListingCRUDTest**: 7 failures - Marketplace listing CRUD
8. **EntitlementLifecycleTest**: 7 failures - Entitlement management
9. **SPARQLLimitsTest**: 6 failures - SPARQL query limits
10. **JobProcessingTest**: 6 failures - Background job processing

## Top Failing Test Types (by pattern)
1. **test_models**: 16 failures - Model creation/validation issues
2. **test_views**: 13 failures - View/endpoint issues
3. **test_openapi_validation**: 10 failures - OpenAPI schema issues
4. **test_order_flow**: 9 failures - Order processing logic
5. **test_access_checks**: 9 failures - Access control
6. **test_kyc_enforcement**: 8 failures - KYC enforcement
7. **test_sparql_endpoint**: 7 failures - SPARQL endpoint
8. **test_listing_crud**: 7 failures - Listing CRUD operations
9. **test_entitlement_lifecycle**: 7 failures - Entitlement lifecycle
10. **test_sparql_limits**: 6 failures - SPARQL limits

## Failure Patterns Identified

### 1. OpenAPI Schema Generation Issues (11 failures)
**Location**: `hub/apps/api/tests/test_openapi_validation.py`

**Root Causes**:
- OpenAPI schema endpoint returns invalid JSON (empty response or HTML)
- Missing serializer classes for `@api_view` decorated functions
- Missing OpenAPI authentication extensions for custom authenticators
- Views need to be converted to `GenericAPIView` or have explicit `serializer_class`

**Affected Views**:
- `api_info`, `api_not_found` (API views)
- `login`, `logout`, `refresh_token`, `password_reset_request`, `password_reset_confirm`, `accept_invitation` (Auth views)
- `sparql_query` (Semantic view)

**Affected Authenticators**:
- `JWTAuthentication`
- `APIKeyAuthentication`

### 2. Database Integrity Errors (Multiple failures)
**Location**: `hub/apps/auth/tests/test_authorization.py`

**Root Cause**: 
- UNIQUE constraint failures on `roles.tenant_id, roles.name`
- Test setup creating duplicate roles without proper cleanup
- Signals creating default roles conflicting with test fixtures

**Error**: `sqlite3.IntegrityError: UNIQUE constraint failed: roles.tenant_id, roles.name`

### 3. Missing URL Patterns / 404 Errors (Multiple failures)
**Locations**: 
- `hub/apps/contracts/tests/test_views_validation.py`
- `hub/apps/audit/tests/test_audit_event_querying.py`

**Root Causes**:
- Contract validation endpoint `/api/v1/contracts/{id}/validate/` returns 404
- Audit export endpoint `/api/v1/audit/audit-events/export/` returns 404
- Router actions not properly registered or URL patterns missing

### 4. Business Logic / Assertion Errors (Multiple failures)
**Locations**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset update not persisting
- `hub/apps/compliance/tests/` - Compliance execution logic
- `hub/apps/dq/tests/` - DQ execution logic
- `hub/apps/contracts/tests/` - Contract validation/migration logic

**Root Causes**:
- Update operations not saving to database
- Service execution logic not working correctly
- Missing model methods or incorrect business logic

### 5. External Service Connection Errors (Multiple failures)
**Locations**:
- `hub/apps/contracts/tests/` - DataContract CLI service
- `hub/apps/semantic/tests/` - Semantic service
- `hub/apps/compliance/tests/` - Compliance service
- `hub/apps/dq/tests/` - DQ service

**Root Cause**: 
- Tests trying to connect to external services that aren't running
- Network errors: `[Errno -3] Temporary failure in name resolution`
- Tests should either mock services or skip when services unavailable

### 6. Model/Serializer Issues (Multiple failures)
**Locations**:
- `hub/apps/datasets/tests/test_models.py`
- `hub/apps/compliance/tests/test_models.py`
- `hub/apps/dq/tests/test_models.py`

**Root Causes**:
- Model creation failing
- Missing required fields
- Serializer validation issues

## Priority Fix Order

### High Priority (Blocks API functionality)
1. **OpenAPI Schema Generation** - Blocks API documentation
2. **Missing URL Patterns** - Blocks contract validation and audit export
3. **Database Integrity Errors** - Blocks authorization tests

### Medium Priority (Business Logic)
4. **Asset Update Logic** - CRUD operations not working
5. **Service Execution Logic** - DQ/Compliance execution failing
6. **Model Creation Issues** - Basic model operations failing

### Low Priority (Test Infrastructure)
7. **External Service Mocking** - Tests should mock or skip when services unavailable
8. **Test Setup/Cleanup** - Database state management in tests

## Recommended Fix Strategy

1. **Fix OpenAPI Schema Generation**:
   - Add serializer classes to `@api_view` functions
   - Create OpenAPI authentication extensions
   - Fix schema generation endpoint

2. **Fix URL Routing**:
   - Verify router action registration
   - Add missing URL patterns
   - Test URL resolution

3. **Fix Database Issues**:
   - Add proper test cleanup
   - Fix role creation signals
   - Use transactions or fixtures properly

4. **Fix Business Logic**:
   - Review update operations
   - Fix service execution logic
   - Add missing model methods

5. **Improve Test Infrastructure**:
   - Add service mocking
   - Improve test isolation
   - Add proper fixtures

