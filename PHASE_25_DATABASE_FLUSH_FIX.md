# Phase 25 Database Flush Fix

## Date: 2026-02-04

## Issue Identified

**Error**: `psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint`
**Detail**: `Table "ingestion_templates" references "users".`
**Hint**: `Truncate table "ingestion_templates" at the same time, or use TRUNCATE ... CASCADE.`

**Location**: Test teardown when Django tries to flush the database

## Root Cause

When running tests with `manage.py test`, Django's `TransactionTestCase` attempts to flush the database during teardown. The flush operation fails because PostgreSQL doesn't allow truncating tables with foreign key constraints without CASCADE.

The `ingestion_templates` table has a foreign key to `users` via the `created_by` field:
- `created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, ...)`

## Solution Applied

### Database Flush Patch

Added a patch to all Phase 25 test files that modifies Django's `sql_flush` method to always use `CASCADE` when truncating tables.

**Files Modified**:
1. ✅ `hub/apps/tenants/tests/test_plan_limit_enforcement_comprehensive.py`
2. ✅ `hub/apps/billing/tests/test_subscription_integration.py`
3. ✅ `hub/apps/gdpr/tests/test_erasure_integration.py`

**Patch Code**:
```python
# CRITICAL: Patch sql_flush to use CASCADE for foreign key constraints
# This is needed when running tests with manage.py test (not pytest)
# Fixes: psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
try:
    import django.db.backends.postgresql.operations as pg_operations

    if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
        _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

        def _patched_sql_flush(
            self, style, tables, *, reset_sequences=False, allow_cascade=False
        ):
            """
            Patched sql_flush that always uses CASCADE to handle foreign key constraints.

            ROOT CAUSE: During test teardown, Django tries to truncate tables but fails
            when tables have foreign key constraints. PostgreSQL requires CASCADE to truncate
            tables with foreign key references.

            SOLUTION: Always use allow_cascade=True when truncating tables during teardown.
            """
            return _original_sql_flush(
                self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
            )

        _patched_sql_flush._patched_for_cascade = True
        pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
except Exception:
    # Patch failed, but tests should still run
    pass
```

## How It Works

1. **Patch Application**: The patch is applied at module import time, before Django's test runner initializes
2. **CASCADE Truncation**: When Django calls `sql_flush`, the patched version always passes `allow_cascade=True`
3. **Foreign Key Handling**: PostgreSQL's `TRUNCATE ... CASCADE` automatically truncates dependent tables
4. **Idempotent**: The patch checks if it's already applied to avoid double-patching

## Verification

### Test Status

- ✅ **API Versioning Tests**: PASSED (2 tests, 0.268s)
- ⏳ **Plan Limit Enforcement Tests**: Patch applied, awaiting full test run
- ⏳ **Subscription Integration Tests**: Patch applied, awaiting full test run
- ⏳ **Erasure Integration Tests**: Patch applied, awaiting full test run

### Expected Results

With the patch in place:
1. Database flush should complete successfully during test teardown
2. Tests should run without `Database couldn't be flushed` errors
3. Test isolation should be restored
4. All Phase 25 tests should execute properly

## Related Files

- `tests/conftest.py` - Contains pytest version of the same patch (lines 326-360)
- `hub/apps/scheduled_ingestion/tests/test_scheduled_ingestion_comprehensive_validation.py` - Example of patch usage (lines 25-54)
- `hub/apps/integrations/tests/ROOT_CAUSE_FIX_DATABASE_FLUSH.md` - Previous documentation of the issue

## Next Steps

1. **Run Full Test Suite**: Execute all Phase 25 tests to verify the patch works
2. **Monitor Test Execution**: Check for any remaining database flush errors
3. **Verify Test Logic**: Once database issues are resolved, verify all test assertions pass

## Notes

- The patch is applied at module level, so it affects all tests in the file
- The patch is idempotent - it won't apply twice if already patched
- If the patch fails to apply, tests will still run (exception is caught)
- This is a known issue in Django when using PostgreSQL with foreign key constraints
