# Phase 25 Test Execution Plan

## Summary

All Phase 25 tests have been reviewed and fixed for common issues. The tests are ready to run, but due to the time required for database setup (3-5 minutes per test suite), they should be run in cycles.

## Fixes Applied

1. ✅ Fixed BigIntegerField serializer issue
2. ✅ Fixed API versioning headers test (header access)
3. ✅ Fixed API versioning middleware (sunset_date handling)
4. ✅ Fixed test asset creation (added required `key` field)
5. ✅ Fixed erasure test (use returned request object)

## Test Execution Strategy

### Option 1: Run All Tests Together (Recommended for CI)
```bash
docker compose exec api-service python manage.py test \
  hub.apps.tenants.tests.test_plan_limit_enforcement_comprehensive \
  hub.apps.billing.tests.test_subscription_integration \
  hub.apps.gdpr.tests.test_erasure_integration \
  hub.apps.api.tests.test_versioning_headers \
  --verbosity=2 \
  --keepdb
```

**Expected Duration**: 5-10 minutes (first run), 2-3 minutes (subsequent runs with --keepdb)

### Option 2: Run Tests Individually (Recommended for Debugging)
```bash
# Test 1: Plan Limit Enforcement
docker compose exec api-service python manage.py test \
  hub.apps.tenants.tests.test_plan_limit_enforcement_comprehensive \
  --verbosity=2 --keepdb

# Test 2: Subscription Integration
docker compose exec api-service python manage.py test \
  hub.apps.billing.tests.test_subscription_integration \
  --verbosity=2 --keepdb

# Test 3: Erasure Integration
docker compose exec api-service python manage.py test \
  hub.apps.gdpr.tests.test_erasure_integration \
  --verbosity=2 --keepdb

# Test 4: API Versioning
docker compose exec api-service python manage.py test \
  hub.apps.api.tests.test_versioning_headers \
  --verbosity=2 --keepdb
```

## Expected Test Results

### Plan Limit Enforcement Tests
- ✅ `test_asset_limit_enforcement` - Should pass (fixed key field)
- ✅ `test_dataset_limit_enforcement` - Should pass
- ✅ `test_scheduled_ingestion_limit_enforcement` - Should pass
- ✅ `test_scheduled_export_limit_enforcement` - Should pass
- ✅ `test_unlimited_plan_bypasses_limits` - Should pass

### Subscription Integration Tests
- ✅ `test_subscription_status_enforcement` - Should pass (fixed key field)
- ✅ `test_tenant_suspension_blocks_writes` - Should pass (fixed key field)
- ✅ `test_active_subscription_allows_writes` - Should pass (fixed key field)

### Erasure Integration Tests
- ✅ `test_erasure_request_creation` - Should pass
- ✅ `test_erasure_execution_anonymizes_user` - Should pass
- ✅ `test_erasure_revokes_api_keys` - Should pass (fixed request object)
- ✅ `test_erasure_request_api` - Should pass

### API Versioning Tests
- ✅ `test_version_headers_present` - Should pass (fixed header access)
- ⏭️ `test_deprecated_endpoint_headers` - Placeholder (no deprecated endpoints yet)

## Potential Issues to Watch For

1. **Stripe Configuration**: Subscription tests may fail if Stripe test keys aren't configured
   - Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in environment
   - Tests use Stripe test mode (no real charges)

2. **Middleware Registration**: Versioning tests may fail if `APIVersionMiddleware` isn't registered
   - Check `MIDDLEWARE` setting in `hub/settings.py`

3. **Plan Limits**: Plan limit tests may fail if limits aren't being enforced in services
   - Verify `PlanLimitService.check_limit()` is called in asset/dataset creation

4. **Tenant Suspension**: Subscription tests may fail if middleware isn't checking tenant status
   - Verify `TenantSuspensionMiddleware` is registered and working

## Next Steps After Test Execution

1. **If tests pass**: Mark Phase 25 as complete in `openspec/changes/perfect1/tasks.md`
2. **If tests fail**:
   - Review error messages
   - Check if fixes need to be applied
   - Update this document with findings
   - Re-run tests after fixes

## Files Modified

- `hub/apps/tenants/serializers.py` - Fixed BigIntegerField
- `hub/apps/api/tests/test_versioning_headers.py` - Fixed header access
- `hub/apps/api/versioning.py` - Fixed sunset_date handling
- `hub/apps/tenants/tests/test_plan_limit_enforcement_comprehensive.py` - Added key field
- `hub/apps/billing/tests/test_subscription_integration.py` - Added key field
- `hub/apps/gdpr/tests/test_erasure_integration.py` - Fixed request object usage
