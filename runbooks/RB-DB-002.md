# RB-DB-002: Database Migration Rollback

**Runbook ID:** `RB-DB-002`  
**Title:** Database Migration Rollback (Failed Migration)  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers rolling back a failed database migration in production.

**In Scope:**
- Rolling back Django migrations
- Reverting schema changes
- Recovering from failed migration execution

**Out of Scope:**
- Data recovery (see `RB-DR-001`)
- Full database restore (see `RB-DB-003`)
- Forward-fix migrations (covered in deployment runbook)

---

## Prerequisites

**Tools Required:**
- `psql` (PostgreSQL client)
- Django management commands access
- Database admin access

**Access Required:**
- Database superuser or admin access
- Access to migration files
- Access to deployment logs

**Backup Requirements:**
- Database snapshot before migration (if available)
- Migration scripts and version history

---

## Symptoms

**Migration Failure Indicators:**
- Migration command fails with error
- Partial schema changes applied
- Application errors after migration
- Database constraint violations

**Example Errors:**
```
django.db.utils.OperationalError: relation "table_name" already exists
django.db.utils.IntegrityError: constraint violation
django.db.utils.ProgrammingError: column does not exist
```

---

## Detection & Diagnosis

### Step 1: Identify Failed Migration

```bash
# Check migration status
python manage.py showmigrations

# Check which migration failed
python manage.py migrate --plan

# Check Django migration history
python manage.py dbshell
\dt django_migrations
SELECT * FROM django_migrations ORDER BY applied DESC LIMIT 10;
```

### Step 2: Assess Migration State

**Determine if migration partially applied:**
```sql
-- Check if new tables were created
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '%new_table%';

-- Check if columns were added
\d+ table_name  -- In psql

-- Check if indexes were created
SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE '%new_index%';
```

### Step 3: Decision: Rollback vs. Forward Fix

**Rollback is safe if:**
- Migration only adds nullable columns
- Migration only creates new tables (not referenced)
- Migration only creates indexes
- No data transformations occurred

**Forward fix is preferred if:**
- Migration includes data transformations
- Migration partially applied and not easily reversible
- Rollback may cause data loss

---

## Rollback Procedure

### Option A: Using Django Migration Rollback

**If migration has reverse operations:**

```bash
# Rollback to previous migration
python manage.py migrate app_name <previous_migration_number>

# Example: Rollback to 0005 from 0006
python manage.py migrate contracts 0005
```

**Verify rollback:**
```bash
# Check migration status
python manage.py showmigrations

# Verify schema
python manage.py dbshell
\dt  # List tables
\d+ table_name  # Describe table
```

### Option B: Manual SQL Rollback

**1. Identify Executed DDL:**

Review the failed migration file to identify what was executed:
```python
# Example migration file
operations = [
    migrations.CreateModel(...),
    migrations.AddField(...),
    migrations.CreateIndex(...),
]
```

**2. Write Reverse SQL:**

**For CREATE TABLE:**
```sql
DROP TABLE IF EXISTS app_name_table_name CASCADE;
```

**For ADD COLUMN:**
```sql
ALTER TABLE app_name_table_name DROP COLUMN IF EXISTS column_name;
```

**For CREATE INDEX:**
```sql
DROP INDEX IF EXISTS app_name_table_name_column_name_idx;
```

**3. Execute Rollback SQL:**

```bash
# Test in staging first (if possible)
psql -h <staging-db-host> -U <user> -d hub -f rollback.sql

# Execute in production
psql -h <production-db-host> -U <user> -d hub -f rollback.sql
```

**4. Update Django Migration History:**

```sql
-- Remove failed migration from history
DELETE FROM django_migrations 
WHERE app = 'app_name' AND name = '0006_migration_name';
```

---

## Verification

### Step 1: Verify Schema State

```sql
-- Check that removed objects are gone
SELECT tablename FROM pg_tables WHERE tablename = 'removed_table';
-- Should return 0 rows

-- Check that restored objects exist
SELECT tablename FROM pg_tables WHERE tablename = 'restored_table';
-- Should return 1 row
```

### Step 2: Verify Application Compatibility

```bash
# Run Django checks
python manage.py check --database default

# Run schema validation
python manage.py validate_tables

# Run smoke tests
make smoke-test-production
```

### Step 3: Verify Data Integrity

```sql
-- Check foreign key constraints
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f' AND NOT convalidated;

-- Check for orphaned records
SELECT COUNT(*) FROM child_table 
WHERE parent_id NOT IN (SELECT id FROM parent_table);
```

---

## Post-Rollback Actions

### Immediate Actions

1. **Document Rollback:**
   - Record in incident log
   - Note which migration failed
   - Document rollback steps taken

2. **Fix Migration Script:**
   - Identify root cause of failure
   - Fix migration file
   - Test in staging environment

3. **Create Follow-Up Ticket:**
   - Re-test migration in non-production
   - Plan re-deployment with fixed migration
   - Update migration if needed

### Long-Term Improvements

- Review migration testing procedures
- Add migration rollback tests
- Document migration best practices
- Consider migration dry-run mode

---

## Rollback Examples

### Example 1: Rollback CREATE TABLE

**Original Migration:**
```python
operations = [
    migrations.CreateModel(
        name='NewModel',
        fields=[...],
    ),
]
```

**Rollback SQL:**
```sql
DROP TABLE IF EXISTS app_name_newmodel CASCADE;
```

**Django Rollback:**
```bash
python manage.py migrate app_name <previous_migration>
```

### Example 2: Rollback ADD COLUMN

**Original Migration:**
```python
operations = [
    migrations.AddField(
        model_name='ExistingModel',
        name='new_field',
        field=models.CharField(max_length=100),
    ),
]
```

**Rollback SQL:**
```sql
ALTER TABLE app_name_existingmodel DROP COLUMN IF EXISTS new_field;
```

### Example 3: Rollback CREATE INDEX

**Original Migration:**
```python
operations = [
    migrations.AddIndex(
        model_name='Model',
        index=models.Index(fields=['field_name'], name='model_field_idx'),
    ),
]
```

**Rollback SQL:**
```sql
DROP INDEX IF EXISTS app_name_model_field_idx;
```

---

## Related Runbooks

- `RB-DEPLOY-001`: Standard Deployment Procedure
- `RB-DB-001`: Database Outage / Degradation
- `RB-DB-003`: Database Restore from Backup

---

## Appendix

### Migration Rollback Checklist

```markdown
- [ ] Identify failed migration
- [ ] Assess migration state (partial vs. complete)
- [ ] Decide: rollback vs. forward fix
- [ ] Test rollback in staging (if possible)
- [ ] Execute rollback SQL or Django command
- [ ] Update Django migration history
- [ ] Verify schema state
- [ ] Run application checks
- [ ] Run smoke tests
- [ ] Document rollback
- [ ] Create follow-up ticket
```

### Common Migration Failures

**Failure: Table already exists**
- **Cause:** Migration partially applied
- **Rollback:** DROP TABLE, then re-run migration

**Failure: Column does not exist**
- **Cause:** Migration order issue
- **Rollback:** Remove migration from history, fix order

**Failure: Constraint violation**
- **Cause:** Data incompatibility
- **Action:** Forward fix preferred (data transformation needed)

