# Detailed Test Failure Analysis

## Executive Summary
- **Total Tests:** 493
- **Passing:** 460 (93.3%)
- **Failing:** 26 (5.3%)
- **Skipped:** 7 (1.4%)
- **Progress:** Fixed 13 failures (from 39 → 26)

---

## Category 1: GraphQL Authentication (4 failures)

### Tests Affected
1. `GraphQLQueryTest::test_me_query`
2. `GraphQLQueryTest::test_assets_query`
3. `GraphQLQueryTest::test_asset_query`
4. `GraphQLQueryTest::test_jobs_query`

### Root Cause Analysis
**Primary Issue:** Strawberry GraphQL's context system doesn't automatically inherit Django's authentication state from DRF's test client.

**Technical Details:**
- DRF's `APIClient.force_authenticate()` sets `request.user` on the Django request
- Strawberry GraphQL creates its own context object that may not reference the same request object
- The `get_context()` override attempts to copy user/tenant, but authentication check still fails
- `is_authenticated` property may not be properly set on the user object in GraphQL context

**Error Pattern:**
```
Exception: Authentication required
```

**Investigation Steps:**
1. Verify `get_context()` is being called
2. Check if `context.request` is the same object as the original `request`
3. Verify user object has `is_authenticated` property set correctly
4. Consider using Strawberry's authentication decorators instead of manual checks

**Potential Solutions:**
1. Use Strawberry's `@strawberry.field` with authentication decorators
2. Ensure middleware runs before GraphQL view processes request
3. Use Django's authentication middleware explicitly for GraphQL endpoint
4. Create custom authentication resolver for GraphQL

**Files Involved:**
- `hub/apps/graphql/views.py` - Context setup
- `hub/apps/graphql/schema.py` - Query resolvers
- `hub/apps/graphql/tests/test_graphql_queries.py` - Test setup

---

## Category 2: E2E Tests (3 failures)

### Tests Affected
1. `CompleteUserJourneysE2ETest::test_data_consumer_journey`
2. `CompleteUserJourneysE2ETest::test_data_provider_journey`
3. `MarketplacePurchaseE2ETest::test_complete_marketplace_purchase_journey`

### Root Cause Analysis
**Primary Issue:** Complex integration tests that exercise full user workflows across multiple services.

**Technical Details:**
- E2E tests require all services to be running (DQ, Compliance, Semantic, DataContract)
- Tests may fail due to:
  - Service connectivity issues
  - Timing/race conditions
  - Missing test data setup
  - Authentication/authorization issues
  - Business logic errors in workflows

**Investigation Steps:**
1. Run individual E2E tests with verbose output
2. Check service health status
3. Verify test data setup
4. Check for timing issues or race conditions
5. Review workflow logic

**Potential Solutions:**
1. Ensure all required services are running
2. Add proper wait/retry logic for service calls
3. Fix any business logic issues in workflows
4. Improve test data setup
5. Add better error handling and logging

**Files Involved:**
- `tests/e2e/test_complete_user_journeys.py`
- `tests/e2e/test_marketplace_purchase_flow.py`

---

## Category 3: Marketplace Integration Tests (3 failures)

### Tests Affected
1. `MarketplaceOrderFlowTest::test_free_listing_auto_approval_flow`
2. `MarketplaceOrderFlowTest::test_order_rejection_flow`
3. `MarketplaceOrderFlowTest::test_request_approval_listing_manual_approval_flow`

### Root Cause Analysis
**Primary Issue:** Order flow logic issues in marketplace integration tests.

**Technical Details:**
- These are integration tests (not unit tests) in `test_integration_order_flow.py`
- Tests exercise complete order workflows:
  - Free listing auto-approval
  - Order rejection
  - Request approval listing manual approval
- May fail due to:
  - Order status transition logic
  - Entitlement creation logic
  - Approval/rejection workflow
  - Service integration issues

**Investigation Steps:**
1. Review order flow logic in `hub/apps/marketplace/order_views.py`
2. Check order status transitions
3. Verify entitlement creation on approval
4. Check approval/rejection permissions
5. Review test setup and assertions

**Potential Solutions:**
1. Fix order status transition logic
2. Ensure entitlements are created correctly
3. Fix approval/rejection workflow
4. Update test assertions if business logic changed

**Files Involved:**
- `hub/apps/marketplace/tests/test_integration_order_flow.py`
- `hub/apps/marketplace/order_views.py`
- `hub/apps/marketplace/models.py`

---

## Category 4: Individual Test Failures (16 failures)

### 4.1 Asset Tests (1 failure)
- **Test:** `AssetSerializerTest::test_asset_update_serializer`
- **Likely Issue:** Serializer validation or update logic
- **Files:** `hub/apps/assets/tests/test_serializers.py`, `hub/apps/assets/serializers.py`

### 4.2 Audit Tests (2 failures)
- **Tests:**
  - `AuditEventQueryingTest::test_filter_by_time_range`
  - `AuditUtilsTest::test_redact_string`
- **Likely Issues:** Query filtering logic or utility function
- **Files:** `hub/apps/audit/tests/test_audit_event_querying.py`, `hub/apps/audit/tests/test_utils.py`

### 4.3 Compliance Tests (1 failure)
- **Test:** `FailClosedBehaviorTest::test_fail_closed_blocks_asset_activation`
- **Likely Issue:** Fail-closed logic for compliance checks
- **Files:** `hub/apps/compliance/tests/test_fail_closed_behavior.py`

### 4.4 Contract Tests (3 failures)
- **Tests:**
  - `MigrationTest::test_can_migrate`
  - `MigrationTest::test_needs_migration`
  - `NormalizationTest::test_normalize_datacontract_com_to_hubcontract`
- **Likely Issues:** Contract migration or normalization logic
- **Files:** `hub/apps/contracts/tests/test_migration.py`, `hub/apps/contracts/tests/test_normalization.py`

### 4.5 Dataset Tests (2 failures)
- **Tests:**
  - `SampleDataExtractionTest::test_extract_sample_data_json_array`
  - `SchemaInferenceTest::test_infer_schema_from_json_array`
- **Likely Issues:** Data extraction or schema inference logic
- **Files:** `hub/apps/datasets/tests/test_sample_data_extraction.py`, `hub/apps/datasets/tests/test_schema_inference.py`

### 4.6 DQ Tests (1 failure)
- **Test:** `DQServiceClientTest::test_run_dq_with_failures`
- **Likely Issue:** DQ service client error handling
- **Files:** `hub/apps/dq/tests/test_service_client.py`

### 4.7 File Tests (2 failures)
- **Tests:**
  - `ChunkedUploadTest::test_init_chunk_upload`
  - `FileUploadDownloadTest::test_init_file_upload_simple`
- **Likely Issues:** File upload initialization logic
- **Files:** `hub/apps/files/tests/test_chunked_upload.py`, `hub/apps/files/tests/test_file_upload_download.py`

### 4.8 Marketplace Tests (1 failure)
- **Test:** `EntitlementLifecycleTest::test_entitlement_created_on_order_approval`
- **Likely Issue:** Entitlement creation on order approval
- **Files:** `hub/apps/marketplace/tests/test_entitlement_lifecycle.py`

### 4.9 Observability Tests (1 failure)
- **Test:** `MetricsTest::test_metrics_endpoint`
- **Likely Issue:** Metrics endpoint configuration or response format
- **Files:** `hub/apps/observability/tests/test_metrics.py`

### 4.10 Semantic Tests (1 failure)
- **Test:** `URIGenerationTest::test_uri_uses_hub_domain_setting`
- **Likely Issue:** URI generation using hub domain setting
- **Files:** `hub/apps/semantic/tests/test_uri_generation.py`

### 4.11 User Tests (1 failure)
- **Test:** `UserDeletionTest::test_cannot_delete_self`
- **Likely Issue:** User deletion validation logic
- **Files:** `hub/apps/users/tests/test_user_deletion.py`

---

## Recommended Fix Strategy

### Phase 1: GraphQL Authentication (High Priority)
1. Investigate Strawberry GraphQL authentication patterns
2. Try using Strawberry's authentication decorators
3. Ensure middleware runs for GraphQL requests
4. Fix user/tenant context propagation

### Phase 2: Quick Wins - Individual Failures (Medium Priority)
1. Start with simple utility/function tests
2. Fix serializer/validation issues
3. Address file upload tests
4. Fix user deletion validation

### Phase 3: Integration Tests (Medium Priority)
1. Fix marketplace order flow tests
2. Review and fix contract migration/normalization
3. Address dataset extraction/inference

### Phase 4: E2E Tests (Lower Priority)
1. Ensure all services are running
2. Fix service connectivity issues
3. Address timing/race conditions
4. Review workflow logic

---

## Testing Commands

### Run specific test categories:
```bash
# GraphQL tests
pytest hub/apps/graphql/tests/ -v

# E2E tests
pytest tests/e2e/ -v

# Marketplace integration tests
pytest hub/apps/marketplace/tests/test_integration_order_flow.py -v

# Individual failures
pytest hub/apps/assets/tests/test_serializers.py::AssetSerializerTest::test_asset_update_serializer -v
```

### Run all failing tests:
```bash
pytest --tb=short -q 2>&1 | grep FAILED
```

---

## Notes
- Many individual failures may be quick fixes (validation, assertions, etc.)
- E2E tests may resolve after fixing other issues
- GraphQL authentication requires deeper investigation into Strawberry's architecture
- Marketplace integration tests may need business logic review

