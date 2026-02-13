# Phase 25 Test Verification Guide

## Date: 2026-02-04

## Quick Verification Commands

### 1. Check Database Flush Errors
```bash
grep -c "Database.*couldn't be flushed\|cannot truncate" /tmp/phase25_final_run.log
# Expected: 0 ✅
```

### 2. Run API Versioning Tests (Fast - ~0.3s)
```bash
docker compose exec api-service python manage.py test \
  hub.apps.api.tests.test_versioning_headers \
  --keepdb --verbosity=1
# Expected: Ran 2 tests - OK ✅
```

### 3. Run Plan Limit Enforcement Tests
```bash
docker compose exec api-service python manage.py test \
  hub.apps.tenants.tests.test_plan_limit_enforcement_comprehensive \
  --keepdb --verbosity=1
# Expected: Ran 5 tests - OK
```

### 4. Run Subscription Integration Tests
```bash
docker compose exec api-service python manage.py test \
  hub.apps.billing.tests.test_subscription_integration \
  --keepdb --verbosity=1
# Expected: Ran 3 tests - OK
```

### 5. Run Erasure Integration Tests
```bash
docker compose exec api-service python manage.py test \
  hub.apps.gdpr.tests.test_erasure_integration \
  --keepdb --verbosity=1
# Expected: Ran 4 tests - OK
```

### 6. Run Full Suite
```bash
docker compose exec api-service python manage.py test \
  hub.apps.tenants.tests.test_plan_limit_enforcement_comprehensive \
  hub.apps.billing.tests.test_subscription_integration \
  hub.apps.gdpr.tests.test_erasure_integration \
  hub.apps.api.tests.test_versioning_headers \
  --verbosity=2 --keepdb
# Expected: Ran 14 tests - OK
```

## Current Status

### ✅ Verified Working
- **Database Flush**: 0 errors detected ✅
- **API Versioning**: 2/2 tests passing ✅
- **Test Execution**: Tests running successfully ✅

### ⏳ Awaiting Full Completion
- **Plan Limit Enforcement**: Tests running (migrations taking time)
- **Subscription Integration**: Tests running (migrations taking time)
- **Erasure Integration**: Tests running (migrations taking time)

## Expected Results

Once all tests complete, you should see:
```
Ran 14 tests in X.XXXs

OK
```

Or if there are failures:
```
Ran 14 tests in X.XXXs

FAILED (failures=N, errors=M)
```

## Troubleshooting

### If Tests Still Show Database Flush Errors
1. Verify patch is applied: Check test files have the CASCADE patch
2. Check patch execution: Verify patch runs before Django initialization
3. Review foreign keys: Check `ingestion_templates` table relationships

### If Tests Fail
1. Check error messages: Review specific failure details
2. Verify fixes: Ensure all fixes are applied correctly
3. Check dependencies: Verify all services are running
4. Review logs: Check test output for detailed errors

## Success Criteria

✅ **All Phase 25 tests pass**:
- No database flush errors
- All 14 tests execute successfully
- All assertions pass

✅ **Fixes verified**:
- Database flush patch working
- Test logic fixes applied
- Code fixes applied

## Notes

- Tests may take 10-15 minutes due to migrations on first run
- Subsequent runs with `--keepdb` are much faster (2-3 minutes)
- Database flush errors should be completely eliminated
- All fixes follow engineering best practices
