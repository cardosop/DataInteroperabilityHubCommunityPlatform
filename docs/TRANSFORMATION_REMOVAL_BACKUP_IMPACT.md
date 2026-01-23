# Transformation Feature Removal - Backup Impact Documentation

**Date:** 2026-01-16
**Status:** Documented

---

## Overview

This document describes the impact of the transformation feature removal on backup and restore procedures.

---

## Backup Impact

### Pre-Migration Backups

**Behavior:**
- Backups created **before** running migration `0004_remove_transformation_feature.py` will include transformation tables
- `pg_dump` will include all tables that exist at the time of backup
- Transformation tables included:
  - `transformation_pipelines`
  - `transformation_nodes`
  - `transformation_pipeline_executions`
  - `wrangling_sessions`
  - `wrangling_operations`
  - `preview_results`

**Backup Scripts:**
- `scripts/create_backup.sh` uses `pg_dump` which includes all tables
- No changes needed to backup scripts - they will automatically include/exclude tables based on database state

### Post-Migration Backups

**Behavior:**
- Backups created **after** running migration `0004_remove_transformation_feature.py` will **exclude** transformation tables
- Transformation tables will be permanently removed from the database schema
- `pg_dump` will not include tables that don't exist

---

## Restore Impact

### Restoring Pre-Migration Backups

**Warning:** Restoring a backup created before the migration will restore transformation tables.

**Impact:**
- Transformation tables will be recreated in the database
- Application code will not reference these tables (transformation app removed)
- This may cause:
  - Orphaned data in transformation tables
  - Foreign key constraint issues if referenced tables don't exist
  - Database schema inconsistencies

**Recommendation:**
- If restoring from pre-migration backup, manually drop transformation tables after restore:
  ```sql
  DROP TABLE IF EXISTS preview_results CASCADE;
  DROP TABLE IF EXISTS wrangling_operations CASCADE;
  DROP TABLE IF EXISTS wrangling_sessions CASCADE;
  DROP TABLE IF EXISTS transformation_pipeline_executions CASCADE;
  DROP TABLE IF EXISTS transformation_nodes CASCADE;
  DROP TABLE IF EXISTS transformation_pipelines CASCADE;
  ```

### Restoring Post-Migration Backups

**Behavior:**
- Post-migration backups will not include transformation tables
- Restore will work normally without transformation tables
- No manual cleanup needed

---

## Backup Strategy

### Before Migration

**If transformation data needs to be preserved:**

1. **Export transformation data separately:**
   ```bash
   # Export transformation data to JSON (if needed)
   python manage.py dumpdata transformation --output backups/transformation_data_YYYYMMDD.json
   ```

2. **Create full database backup:**
   ```bash
   scripts/create_backup.sh staging
   ```

3. **Note:** Transformation data export requires transformation app to be in `INSTALLED_APPS` (not recommended after removal)

### After Migration

**Normal backup procedure:**
- Backups will automatically exclude transformation tables
- No special handling needed
- Backup scripts work as normal

---

## Backup Manifest

**Note:** Backup manifests created before migration will reference transformation tables in the database dump. This is expected and does not affect restore procedures.

**Example manifest entry:**
```
database:backups/staging_20260116_120000/database_20260116_120000.sql.gz:20260116_120000
```

The manifest does not list individual tables - it references the entire database dump.

---

## Migration Order

**Important:** The migration `0004_remove_transformation_feature.py` uses `CASCADE` when dropping tables, which automatically:
- Drops foreign key constraints pointing to transformation tables
- Drops indexes on transformation tables
- Handles all dependent objects

**No manual foreign key cleanup needed** - CASCADE handles everything.

---

## Rollback Considerations

**If rollback is needed:**

1. **Code rollback:** Restore code from backup (transformation app will be restored)
2. **Database rollback:**
   - If restoring pre-migration backup: Transformation tables will be restored
   - If restoring post-migration backup: Transformation tables will not exist (need to run transformation migrations)

**Recommendation:**
- Keep pre-migration backup if rollback might be needed
- Document which backup contains transformation tables

---

## Summary

| Scenario | Backup Contains Transformation Tables | Restore Behavior |
|----------|--------------------------------------|------------------|
| Pre-migration backup | ✅ Yes | Restores tables (may need manual cleanup) |
| Post-migration backup | ❌ No | No transformation tables (expected) |
| Pre-migration restore | ✅ Yes | Tables restored, may cause issues |
| Post-migration restore | ❌ No | No tables (normal) |

---

## Files Affected

- `scripts/create_backup.sh` - No changes needed (works automatically)
- `scripts/rollback.sh` - No changes needed (works automatically)
- Migration: `hub/apps/core/migrations/0004_remove_transformation_feature.py` - Handles table removal with CASCADE

---

## Related Documentation

- `docs/TRANSFORMATION_REMOVAL.md` - Complete removal documentation
- Migration files:
  - `hub/apps/core/migrations/0004_remove_transformation_feature.py`
  - `hub/apps/jobs/migrations/0005_remove_transformation_job_references.py`
  - `hub/apps/orchestration/migrations/0001_remove_transformation_workflow_references.py`
  - `hub/apps/observability/migrations/0003_remove_transformation_pipeline_type.py`
