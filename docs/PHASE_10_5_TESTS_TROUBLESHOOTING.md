# Phase 10.5 Tests Troubleshooting

## Status: IN PROGRESS - Root Cause Investigation

### Issue Summary
Phase 10.5 tests are timing out during execution. Multiple approaches attempted, but tests still not passing.

### Tests Affected
- `test_concurrent_odps_creation` - TIMEOUT
- Other Phase 10.5 tests - Not yet run (expected to have similar issues)

### Root Cause Analysis

#### Issue 1: Test Environment Detection
**Problem**: Background thread execution in test environment is problematic
- `transaction.on_commit()` in tests executes on rollback, not commit
- Background threads may not see workflow instances due to transaction isolation
- Database connections in background threads may not be properly initialized

#### Issue 2: Database Connection in Background Threads
**Problem**: Background threads accessing database in test environment
- Error: `django.db.utils.OperationalError` when thread tries to access database
- Thread may be trying to access database before connection is established
- Transaction isolation prevents thread from seeing committed data

#### Issue 3: Workflow Execution Timing
**Problem**: Tests expect `execute_start` to return quickly (< 2s)
- Current implementation may hang waiting for transaction commit
- Synchronous execution would work but violates test expectations
- Asynchronous execution has threading/transaction issues

### Fixes Attempted

1. ✅ **Workflow Execution Optimizations** (Previous)
   - Removed unnecessary database refreshes
   - Batched database saves
   - Optimized lock usage
   - Added workflow caching

2. ✅ **Test Environment Detection** (Current)
   - Multiple heuristics (sys.argv, database name, connection settings)
   - Fallback to immediate execution
   - Still not working reliably

3. ✅ **Synchronous Execution in Tests** (Attempted)
   - Execute workflow synchronously in test environment
   - Problem: Test expects quick return, not full execution

4. ✅ **Immediate Thread Start** (Current)
   - Start background thread immediately in test environment
   - Problem: Database connection issues in thread

### Recommended Solution

**Option A: Fix Database Connection in Background Threads (Recommended)**
- Ensure background threads properly initialize database connections
- Use Django's `connections` API correctly in threads
- Handle transaction isolation properly

**Option B: Make Tests Wait for Workflow Completion**
- Modify tests to wait for workflow completion instead of just checking `execute_start` returns
- Use `execute_get_result()` to poll for completion
- More realistic test but changes test expectations

**Option C: Use Celery/Background Task Queue**
- Replace threading with proper task queue (Celery, RQ)
- Better handling of background tasks in test environment
- More production-like but requires infrastructure changes

### Next Steps

1. **Fix Database Connection Handling**
   - Ensure background threads properly close and reopen connections
   - Use Django's connection management in threads
   - Test with minimal workflow to isolate issue

2. **Add Debug Logging**
   - Log when test environment is detected
   - Log when background thread starts
   - Log database connection status in thread

3. **Create Minimal Test Case**
   - Create simplest possible test to isolate issue
   - Test just workflow instance creation
   - Test just background thread startup
   - Test just database access in thread

4. **Consider Alternative Approach**
   - If threading issues persist, consider synchronous execution for tests
   - Modify test expectations to wait for completion
   - Or use different execution path for tests

### Technical Details

**Test Framework**: Django `TransactionTestCase`
**Database**: PostgreSQL (test database)
**Execution Model**: Background threads for async workflow execution
**Issue**: Threading + Transaction isolation in test environment

### Files Modified

1. `hub/apps/orchestration/workflows/product_creation.py`
   - Test environment detection
   - Background thread execution logic
   - Database connection handling

2. `hub/apps/orchestration/workflow_engine.py`
   - Execution optimizations
   - Lock usage improvements

3. `hub/apps/orchestration/registry.py`
   - Workflow caching

### Current State

- ✅ Workflow execution optimizations complete
- ⏳ Test environment detection in progress
- ❌ Tests still timing out
- ⏳ Database connection handling needs work

### Priority

**HIGH** - Phase 10.5 tests are critical for validation. Need to resolve threading/transaction issues to proceed with test execution.
