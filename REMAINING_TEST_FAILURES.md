# Remaining Test Failures Analysis

## Current Status
- **Total tests:** 493
- **Passing:** 460 (93.3%)
- **Failing:** 26 (5.3%)
- **Skipped:** 7 (1.4%)

## Failure Categories

### 1. GraphQL Tests (4 failures)
- `test_me_query` - Authentication/tenant context
- `test_assets_query` - Tenant context
- `test_asset_query` - Tenant context  
- `test_jobs_query` - Tenant context

**Root Cause:** GraphQL context not properly inheriting user/tenant from Django request
**Status:** Partially fixed (context error resolved, but authentication still failing)

### 2. E2E Tests (3 failures)
- `test_data_consumer_journey` - Complex integration test
- `test_data_provider_journey` - Complex integration test
- `test_complete_marketplace_purchase_journey` - Complex integration test

**Root Cause:** Complex integration tests that may depend on external services or other fixes
**Status:** Needs investigation

### 3. Marketplace Integration Tests (3 failures)
- `test_free_listing_auto_approval_flow`
- `test_order_rejection_flow`
- `test_request_approval_listing_manual_approval_flow`

**Root Cause:** Likely related to order flow logic or service integration
**Status:** Needs investigation

### 4. Individual Test Failures (16 failures)

#### Asset Tests (1)
- `AssetSerializerTest::test_asset_update_serializer`

#### Audit Tests (2)
- `AuditEventQueryingTest::test_filter_by_time_range`
- `AuditUtilsTest::test_redact_string`

#### Compliance Tests (1)
- `FailClosedBehaviorTest::test_fail_closed_blocks_asset_activation`

#### Contract Tests (3)
- `MigrationTest::test_can_migrate`
- `MigrationTest::test_needs_migration`
- `NormalizationTest::test_normalize_datacontract_com_to_hubcontract`

#### Dataset Tests (2)
- `SampleDataExtractionTest::test_extract_sample_data_json_array`
- `SchemaInferenceTest::test_infer_schema_from_json_array`

#### DQ Tests (1)
- `DQServiceClientTest::test_run_dq_with_failures`

#### File Tests (2)
- `ChunkedUploadTest::test_init_chunk_upload`
- `FileUploadDownloadTest::test_init_file_upload_simple`

#### Marketplace Tests (1)
- `EntitlementLifecycleTest::test_entitlement_created_on_order_approval`

#### Observability Tests (1)
- `MetricsTest::test_metrics_endpoint`

#### Semantic Tests (1)
- `URIGenerationTest::test_uri_uses_hub_domain_setting`

#### User Tests (1)
- `UserDeletionTest::test_cannot_delete_self`

## Recommended Fix Order

### Priority 1: GraphQL Authentication (4 failures)
- Fix user/tenant context in GraphQL views
- Ensure authentication middleware runs for GraphQL requests

### Priority 2: Marketplace Integration (3 failures)
- Review order flow logic
- Check service integration points

### Priority 3: Individual Failures (16 failures)
- Address one by one based on impact
- Start with most common patterns

### Priority 4: E2E Tests (3 failures)
- Address after core functionality is fixed
- May resolve automatically with other fixes

## Next Steps
1. Continue fixing GraphQL authentication
2. Investigate marketplace integration test failures
3. Address individual test failures systematically
4. Review E2E tests after other fixes

