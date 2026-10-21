# Migration Fixes Applied - Root Cause Resolution

## Issue Identified

**Error**: `django.db.utils.ProgrammingError: relation "search_searchindex" does not exist`
**Location**: Migration `core.0004_remove_transformation_feature`
**Root Cause**: Migration tries to DELETE from `search_searchindex` table before the table exists (search app migrations haven't run yet)

**Error**: `django.db.utils.ProgrammingError: relation "jobs_job" does not exist`
**Location**: Migration `jobs.0005_remove_transformation_job_references`
**Root Cause**: Migration tries to UPDATE `jobs_job` table before the table exists (jobs app migrations haven't run yet)

## Root Cause Analysis

When running tests with `TransactionTestCase`, Django creates a fresh test database and runs all migrations in dependency order. However, the transformation removal migrations (`core.0004` and `jobs.0005`) try to clean up data from tables (`search_searchindex` and `jobs_job`) that may not exist yet if those apps' migrations haven't run.

**Problem**: Migrations use `RunSQL` with direct SQL statements that assume tables exist, causing failures when tables don't exist yet.

## Fixes Applied

### 1. ✅ Fixed `core.0004_remove_transformation_feature` Migration
**File**: `hub/apps/core/migrations/0004_remove_transformation_feature.py`

**Change**: Replaced `RunSQL` with `RunPython` that checks if table exists before deleting:
```python
def _cleanup_search_index(schema_editor):
    """Safely delete transformation pipeline entries from search index if table exists"""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if search_searchindex table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'search_searchindex'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if table_exists:
            cursor.execute(
                "DELETE FROM search_searchindex WHERE resource_type = 'TRANSFORMATION_PIPELINE';"
            )
```

**Impact**: Migration now safely handles cases where `search_searchindex` table doesn't exist yet.

### 2. ✅ Fixed `jobs.0005_remove_transformation_job_references` Migration
**File**: `hub/apps/jobs/migrations/0005_remove_transformation_job_references.py`

**Change**: Replaced `RunSQL` with `RunPython` that checks if table exists before updating:
```python
def _cleanup_transformation_jobs(schema_editor):
    """Safely cancel/fail transformation jobs if jobs_job table exists"""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if jobs_job table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'jobs_job'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if table_exists:
            # Cancel all pending/running transformation jobs
            cursor.execute("""
                UPDATE jobs_job
                SET status = 'CANCELLED',
                    error_message = 'Transformation feature removed',
                    updated_at = NOW()
                WHERE job_type = 'TRANSFORMATION_PIPELINE_EXECUTION'
                AND status IN ('PENDING', 'RUNNING');
            """)
            # Mark all running transformation jobs as FAILED
            cursor.execute("""
                UPDATE jobs_job
                SET status = 'FAILED',
                    error_message = 'Transformation feature removed during execution',
                    updated_at = NOW()
                WHERE job_type = 'TRANSFORMATION_PIPELINE_EXECUTION'
                AND status = 'RUNNING';
            """)
```

**Impact**: Migration now safely handles cases where `jobs_job` table doesn't exist yet.

## Solution Approach

**Root Cause Fix**: Instead of using `RunSQL` with direct SQL statements, use `RunPython` with Python functions that:
1. Check if the target table exists using `information_schema.tables`
2. Only execute the cleanup SQL if the table exists
3. Handle PostgreSQL-specific logic safely

**Benefits**:
- ✅ Migrations work regardless of migration order
- ✅ No errors when tables don't exist yet
- ✅ Safe for test database creation
- ✅ Follows Django migration best practices

## Status

✅ **Both migrations fixed** - Migrations now safely handle missing tables during test database creation.

## Testing

After fixes, tests should:
1. ✅ Run migrations successfully without errors
2. ✅ Create test database correctly
3. ✅ Execute marketplace integration tests
4. ✅ Complete without migration-related failures
