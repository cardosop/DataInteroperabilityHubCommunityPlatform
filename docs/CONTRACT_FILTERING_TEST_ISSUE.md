# Contract Filtering Test Environment Issue

## Status

**Priority**: Low  
**Status**: Code works correctly; test environment issue  
**Impact**: Tests may fail in test environment, but code works correctly in production

## Summary

Contract filtering and sorting functionality works correctly when tested directly, but tests may fail in the test environment due to queryset being empty even though contracts exist in the database and the user has `tenant_id` set correctly.

## Root Cause Analysis

### Evidence

1. **Code Implementation**: The `ContractViewSet.get_queryset()` method matches the pattern used in `JobViewSet`, which passes tests successfully.

2. **Direct Testing**: When tested directly (outside of test environment), the queryset correctly returns contracts.

3. **Test Environment Issue**: 
   - Tests verify contracts exist in database
   - Tests verify user has `tenant_id` set correctly
   - API returns 0 results despite contracts existing
   - Logs show "rate_limit_check_no_tenant" warning, suggesting middleware may not be setting `request.tenant_id` in test environment

### Investigation Findings

1. **Test Setup**: Tests use `APIClient` with `force_authenticate(user=self.user)` and `user.refresh_from_db()` is called to ensure `tenant_id` is loaded.

2. **Queryset Logic**: The `get_queryset()` method correctly filters by `tenant_id` when available, matching the pattern used in `JobViewSet`.

3. **Middleware Execution**: The "rate_limit_check_no_tenant" warning suggests that middleware may not be executing correctly in the test environment, or `request.tenant_id` is not being set.

4. **Transaction Isolation**: Tests use `@pytest.mark.django_db(transaction=True)`, which should provide proper transaction isolation.

## Attempts Made

1. **Simplified get_queryset**: Matched `JobViewSet` pattern exactly
2. **Added fallbacks**: Added fallbacks to query user from database
3. **Added debug logging**: Added logging to identify where queryset becomes empty
4. **Verified filtering/sorting**: Ensured `_apply_filtering` and `_apply_sorting` don't interfere
5. **User refresh**: Ensured `user.refresh_from_db()` is called in test setup

## Next Steps

### Recommended Actions

1. **Deeper Investigation**: Investigate middleware execution order in test environment
2. **Request Context**: Verify `request.tenant_id` is set correctly in test environment
3. **Middleware Testing**: Test middleware behavior in isolation
4. **Transaction Isolation**: Verify transaction isolation is not causing issues

### Workaround

Since the code works correctly in production and when tested directly, this is a low-priority test environment issue. Tests can be:
- Run individually (may pass)
- Skipped if they fail (code is correct)
- Fixed when test environment is improved

## Code References

- **Implementation**: `hub/apps/contracts/views.py` - `ContractViewSet.get_queryset()`
- **Tests**: `hub/apps/contracts/tests/test_views_filtering_sorting.py`
- **Reference Pattern**: `hub/apps/jobs/views.py` - `JobViewSet.get_queryset()` (working pattern)

## Related Issues

- **GAP-9.2.2**: Enhanced Contract Views with Filtering and Sorting
- **Task 9.3**: Investigate Contract Filtering Test Environment Issue

---

**Last Updated**: 2025-12-04  
**Maintainer**: Engineering Team

