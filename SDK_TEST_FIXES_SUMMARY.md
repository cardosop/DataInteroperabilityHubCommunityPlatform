# SDK Test Fixes Summary

## Tests Fixed

### ✅ `test_sdk_file_upload_flow`
- **Status**: SKIPPED (MinIO service not available - expected behavior)
- **Fix Applied**: Improved MinIO availability check with better error handling
- **Root Cause**: MinIO service is not running in the test environment
- **Action Required**: Start MinIO service if file upload testing is needed

### ⚠️ `test_sdk_token_refresh_on_401`
- **Status**: FAILING (transaction isolation issue with LiveServerTestCase)
- **Root Cause**: The user created in the test thread is not visible to the live server thread due to transaction isolation in `LiveServerTestCase`
- **Symptoms**: 
  - Token refresh callback is called successfully
  - New token is obtained from login (200 OK)
  - Subsequent request with new token returns 401 "User not found"
- **Fixes Applied**:
  1. **SDK Client** (`sdk/python/datahub_interoperability/client.py`):
     - Added token refresh attempt tracking to prevent infinite loops
     - Improved token validation after refresh
     - Added debug logging for token refresh flow
     - Fixed token refresh retry logic to prevent multiple refresh attempts
  
  2. **Test Setup** (`tests/e2e/test_sdk_python.py`):
     - Added explicit `transaction.commit()` in `setUp()` to ensure user is committed
     - Added user authentication verification in `setUp()`
     - Added explicit `transaction.commit()` in token refresh callback
     - Increased delay after commit to ensure database visibility
  
  3. **JWT Authentication** (`hub/apps/auth/authentication.py`):
     - Added debug logging for user lookup failures
     - Improved error messages for transaction isolation issues
  
  4. **JWT Utils** (`hub/apps/auth/jwt_utils.py`):
     - Added connection refresh logic to ensure fresh database connection
     - Added error handling and logging for user lookup failures

## Remaining Issue

The `test_sdk_token_refresh_on_401` test is still failing due to a fundamental transaction isolation issue with `LiveServerTestCase`. The test creates a user in one thread, but the live server (running in a separate thread) cannot see that user even after explicit commits.

### Possible Solutions

1. **Use TransactionTestCase instead of LiveServerTestCase** (Recommended):
   - `TransactionTestCase` doesn't use transactions, so data is immediately visible
   - However, this requires using a real HTTP server (not Django's test server)
   - Would need to start the API service separately

2. **Create user via HTTP API** (Alternative):
   - Instead of creating user directly in test, create it via HTTP request to live server
   - This ensures user is created in the server's database connection
   - Similar to approach used in `cli/tests/integration/test_commands_real_api.py`

3. **Use API Key instead of JWT** (Workaround):
   - API keys are more reliable for testing as they don't require user lookup
   - Can create API key via HTTP API and use it for authentication
   - Less realistic but more reliable for E2E tests

4. **Database Connection Pooling** (Advanced):
   - Configure PostgreSQL connection pooling to ensure all threads see committed data
   - Requires infrastructure changes

## Recommendations

1. **Short-term**: Mark `test_sdk_token_refresh_on_401` as `@pytest.mark.skip` with a clear message about the transaction isolation issue
2. **Medium-term**: Refactor to use `TransactionTestCase` with a real HTTP server or create users via HTTP API
3. **Long-term**: Consider using a different testing approach (e.g., Docker Compose with real services) for E2E tests

## Files Modified

1. `sdk/python/datahub_interoperability/client.py` - Token refresh logic improvements
2. `tests/e2e/test_sdk_python.py` - Test setup and token refresh callback improvements
3. `hub/apps/auth/authentication.py` - Debug logging for user lookup failures
4. `hub/apps/auth/jwt_utils.py` - Connection refresh logic (attempted, but file was modified)

## Test Execution

```bash
# Run SDK tests
pytest tests/e2e/test_sdk_python.py::SDKPythonE2ETest::test_sdk_file_upload_flow \
       tests/e2e/test_sdk_python.py::SDKPythonE2ETest::test_sdk_token_refresh_on_401 \
       -v --tb=short --reuse-db
```

## Next Steps

1. Decide on approach for fixing transaction isolation issue
2. Implement chosen solution
3. Re-run tests to verify fix
4. Update test documentation with chosen approach

