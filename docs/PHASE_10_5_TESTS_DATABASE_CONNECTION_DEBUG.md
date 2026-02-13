# Phase 10.5 Tests - Database Connection Debugging

## Current Status: DEBUGGING IN PROGRESS

### Issue
Tests are timing out. After database setup completes ("Using existing test database..."), the test hangs with no further output.

### Debugging Steps Taken

#### 1. Enhanced Database Connection Handling ✅
- Added proper connection initialization in background threads
- Added connection verification with cursor test
- Added retry logic for workflow instance visibility
- Added comprehensive error handling

#### 2. Enhanced Logging ✅
- Added `[THREAD]` prefix to all background thread logs
- Added logging at key points:
  - Thread start
  - Connection initialization
  - Connection verification
  - Workflow instance lookup
  - Workflow execution start/completion

#### 3. Test Environment Detection ✅
- Multiple heuristics for test detection
- Immediate thread start in test environment
- Fallback to immediate execution if detection fails

### Current Observations

**Test Execution Flow**:
1. ✅ Database migrations complete
2. ✅ Test database ready ("Using existing test database...")
3. ❓ Test hangs - no further output

**Possible Hang Points**:
1. **Test setUp() method** - Creating tenant/users/workflow registration
2. **Workflow registration** - `register_workflow()` might be blocking
3. **Test method execution** - `test_10_concurrent_creations()` might be hanging
4. **execute_start()** - Might be blocking before returning
5. **Background thread** - Thread might be blocking on startup

### Next Debugging Steps

1. **Add logging to test setUp()** - See if it completes
2. **Add logging to test method** - See if it starts
3. **Check workflow registration** - Verify it's not blocking
4. **Verify thread.start()** - Ensure it's non-blocking
5. **Check database locks** - Verify no deadlocks

### Files Modified

1. `hub/apps/orchestration/workflows/product_creation.py`
   - Enhanced `execute_in_background()` with detailed logging
   - Improved database connection handling
   - Added connection verification
   - Increased retry attempts for instance visibility

### Expected Behavior

After fixes:
- `execute_start` should return in < 2 seconds
- Background thread should start immediately
- Database connections should be properly initialized
- Workflow instance should be visible to background thread
- Tests should complete without timeout

### Validation Commands

```bash
# Run test with extended timeout and capture full output
timeout 600 docker compose exec api-service bash -c "cd /app/hub && python manage.py test tests.performance.test_concurrent_odps_creation.TestConcurrentODPSCreation.test_10_concurrent_creations --verbosity=2 --keepdb --no-input" 2>&1 | tee /tmp/test_debug.log

# Check for thread logs
grep "\[THREAD\]" /tmp/test_debug.log

# Check for workflow creation logs
grep "Creating workflow\|Workflow instance" /tmp/test_debug.log

# Check for test execution
grep "test_10\|setUp\|Found.*test" /tmp/test_debug.log
```
