# Updated Test Failure Analysis

## Overall Statistics
- **Total tests run:** 489
- **Failing tests:** 39
- **Passing tests:** 447
- **Skipped tests:** 7
- **Code coverage:** ~8% (indicating many tests are not being fully executed or are missing)

## Top Failure Patterns (by test class/module)

### 1. **AccessUtilsTest** (5 failures) - HIGH PRIORITY
   - **Description:** All 5 tests in `test_access_utils.py` are failing
   - **Root Cause:** `ValidationError: Only ACTIVE assets can be listed in the marketplace`
   - **Issue:** Assets are being created without `status=AssetStatus.ACTIVE` in test setup
   - **Fix Required:** Update `setUp` in `test_access_utils.py` to create assets with `status=AssetStatus.ACTIVE`

### 2. **GraphQLQueryTest** (6 failures) - HIGH PRIORITY
   - **Description:** All GraphQL query tests are failing
   - **Root Causes:**
     - `TypeError: Logger._log() got an unexpected keyword argument 'error_message'` - Incorrect logger call in GraphQL views
     - `AttributeError: 'WSGIRequest' object has no attribute 'tenant'` - Missing tenant middleware/attribute
   - **Fix Required:**
     - Fix logger call in `hub/apps/graphql/views.py` (remove `error_message` parameter or use correct logging format)
     - Ensure tenant is set on request object (may need middleware or request attribute setting)

### 3. **RDFMappingTest** (3 failures) - MEDIUM PRIORITY
   - **Description:** Semantic resource mapping tests failing
   - **Root Causes:**
     - `AssertionError: Expected 'map_asset' to have been called once. Called 2 times.` - Mock assertion issue
     - `UNIQUE constraint failed: semantic_resources.tenant_id, semantic_resources.resource_type, semantic_resources.resource_id` - Duplicate resource creation
   - **Fix Required:**
     - Review mock setup to prevent double calls
     - Use `get_or_create` or ensure unique test data

### 4. **MarketplaceOrderFlowTest** (3 failures) - MEDIUM PRIORITY
   - **Description:** Marketplace order flow integration tests
   - **Likely Issues:** Similar to other marketplace tests - may need asset status, KYC verification, or service connectivity

### 5. **TenantSuspensionMiddlewareTest** (2 failures) - MEDIUM PRIORITY
   - **Description:** Tenant suspension middleware tests
   - **Likely Issues:** Middleware logic or test setup

### 6. **E2E Tests** (3 failures) - LOWER PRIORITY
   - **Description:** End-to-end tests for complete user journeys
   - **Tests:**
     - `test_data_consumer_journey`
     - `test_data_provider_journey`
     - `test_complete_marketplace_purchase_journey`
   - **Likely Issues:** Complex integration, may depend on external services or other test fixes

### 7. **Other Individual Failures** (17 failures) - VARIOUS PRIORITIES
   - Various single test failures across different modules:
     - `UserDeletionTest::test_cannot_delete_self`
     - `URIGenerationTest::test_uri_uses_hub_domain_setting`
     - `SchemaInferenceTest`, `SampleDataExtractionTest`, `NormalizationTest`
     - `MetricsTest`, `FileUploadDownloadTest`, `ChunkedUploadTest`
     - `AuditUtilsTest`, `AuditEventQueryingTest`
     - `AssetSerializerTest`, `EntitlementLifecycleTest`
     - `FailClosedBehaviorTest`, `DQServiceClientTest`
     - `RoleManagementTest::test_assign_role_cross_tenant`
     - `MigrationTest` (2 failures)

## Root Causes Identified (Consolidated)

### High Priority Issues:

1. **Asset Status Validation in Marketplace** (5 failures)
   - Assets must be `ACTIVE` to be listed
   - **Fix:** Update test setups to create assets with `status=AssetStatus.ACTIVE`

2. **GraphQL Logger Error** (6 failures)
   - Incorrect logger call format
   - **Fix:** Update `hub/apps/graphql/views.py` to use correct logging API

3. **GraphQL Tenant Attribute Missing** (6 failures)
   - Request object missing `tenant` attribute
   - **Fix:** Ensure tenant middleware sets `request.tenant` or handle missing tenant gracefully

### Medium Priority Issues:

4. **Semantic Resource Uniqueness** (3 failures)
   - Duplicate resource creation in tests
   - **Fix:** Use `get_or_create` or ensure unique test data

5. **Mock Assertion Issues** (3 failures)
   - Mocks being called more times than expected
   - **Fix:** Review mock setup and reset between tests

### Lower Priority Issues:

6. **E2E Test Dependencies** (3 failures)
   - Complex integration tests that may depend on other fixes
   - **Fix:** Address after fixing core functionality

7. **Individual Test Issues** (17 failures)
   - Various isolated issues requiring individual investigation
   - **Fix:** Address systematically after high/medium priority items

## Recommended Fix Order

### Phase 1: Quick Wins (High Impact, Low Effort)
1. ✅ **Fix AccessUtilsTest** (5 failures) - Add `status=AssetStatus.ACTIVE` to asset creation
2. ✅ **Fix GraphQL Logger** (6 failures) - Fix logger call in GraphQL views
3. ✅ **Fix GraphQL Tenant** (6 failures) - Ensure tenant is set on request

**Expected Result:** 17 failures fixed → **22 failures remaining**

### Phase 2: Medium Priority
4. ✅ **Fix RDFMappingTest** (3 failures) - Fix uniqueness and mock issues
5. ✅ **Fix MarketplaceOrderFlowTest** (3 failures) - Review and fix order flow issues
6. ✅ **Fix TenantSuspensionMiddlewareTest** (2 failures) - Review middleware logic

**Expected Result:** 8 failures fixed → **14 failures remaining**

### Phase 3: Individual Issues
7. ✅ **Fix RoleManagementTest** (1 failure) - Cross-tenant role assignment
8. ✅ **Fix Individual Test Failures** (17 failures) - Address one by one

**Expected Result:** 18 failures fixed → **0 failures remaining**

## Summary

**Current State:**
- 39 failures, 447 passing
- Most failures are in specific categories with clear root causes
- Many are fixable with simple changes (asset status, logger calls, etc.)

**Next Steps:**
1. Fix AccessUtilsTest (5 failures) - Simple asset status fix
2. Fix GraphQL tests (6 failures) - Logger and tenant fixes
3. Continue with medium priority items
4. Address remaining individual failures

**Estimated Effort:**
- Phase 1: 1-2 hours (17 failures)
- Phase 2: 2-3 hours (8 failures)
- Phase 3: 3-4 hours (14 failures)
- **Total: 6-9 hours to reach 100% passing**

