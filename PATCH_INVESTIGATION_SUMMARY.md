# Patch Investigation Summary

## Problem

All tests fail with `relation "tenants" does not exist` during database setup. The error occurs in Django's `sync_apps` method when it tries to check for existing tables on an empty test database.

## Attempted Solutions

### 1. Patched `sync_apps` Method
- **Status**: ✅ Applied (verified function name is `_patched_sync_apps`)
- **Issue**: ❌ Patch is NOT being called (no debug output appears)
- **Evidence**: Error trace shows `self.sync_apps()` is called, but patch doesn't intercept it

### 2. Patched `__init__` Method
- **Status**: ✅ Applied
- **Issue**: ❌ Still not working - instances may be created before patch

### 3. Patched `handle` Method
- **Status**: ✅ Applied
- **Issue**: ❌ Still not working - patch may not be applied early enough

### 4. Patched `call_command` Function
- **Status**: ✅ Applied
- **Issue**: ❌ Still not working

### 5. Patched Schema Editor Methods
- **Status**: ✅ Applied
- **Issue**: ❌ Error occurs before schema editor is used

## Root Cause Hypothesis

The patch is being applied (verified by checking function name), but it's **NOT being called** when `sync_apps` is invoked. This suggests:

1. **Timing Issue**: Patch is applied after Django has already bound the method
2. **Instance Creation**: Django creates Command instances in a way that bypasses the patch
3. **Method Binding**: Python's method binding may be preventing the patch from working
4. **Import Order**: Django may be importing/using the Command class before our patch is applied

## Evidence

- ✅ Patch is applied: `migrate_module.Command.sync_apps.__name__ == '_patched_sync_apps'`
- ❌ Patch is NOT called: No "[PATCH]" debug output appears
- ❌ Error still occurs: `self.sync_apps(connection, executor.loader.unmigrated_apps)` fails

## Next Steps

1. **Alternative Approach**: Use Django's `MIGRATE: False` and manually run migrations via pytest hook
2. **Different Patch Location**: Patch at the database creation level instead of migrate command level
3. **Django Setting**: Check if there's a Django setting to disable `sync_apps` for test databases
4. **Custom Test Runner**: Create a custom test database setup that runs migrations before sync_apps

## Files Modified

- `tests/conftest.py`: Multiple patch attempts
- `hub/settings.py`: Test database configuration

## Current Status

**487 tests failing** - All tests fail during database setup with the same error.

