# Transformation Removal Rollback Procedures

**Date**: 2026-01-16
**Purpose**: Document rollback procedures for transformation feature removal

---

## Overview

This document describes rollback procedures for various scenarios that may occur after transformation feature removal. Rollback should only be performed if absolutely necessary, as the transformation feature was incomplete and problematic.

---

## Rollback Scenarios

### 1. Critical Import Errors

**Scenario**: Code is still trying to import transformation modules, causing application failures.

**Symptoms**:
- `ModuleNotFoundError: No module named 'hub.apps.transformation'`
- Application startup failures
- Service crashes

**Rollback Procedure**:
1. **Immediate**: Identify and fix import statements (preferred)
   ```bash
   # Find all transformation imports
   grep -r "from hub.apps.transformation" hub/
   grep -r "import.*transformation" hub/

   # Remove or fix imports
   # Deploy fix
   ```

2. **If fix not possible immediately**: Rollback code deployment
   ```bash
   # Find backup with transformation code
   LATEST_BACKUP=$(ls -td backups/staging_* | head -1)

   # Restore code from backup
   git checkout <backup-commit-hash>

   # Restart services
   docker compose restart
   ```

3. **Verify**: Check that import errors are resolved
   ```bash
   # Monitor logs
   tail -f logs/application.log | grep -i "ModuleNotFoundError"
   ```

---

### 2. Database Migration Failures

**Scenario**: Migrations fail to run, causing database schema issues.

**Symptoms**:
- Migration errors: `relation "transformation_pipelines" does not exist`
- Database constraint errors
- Application database errors

**Rollback Procedure**:

#### Option A: Rollback Migrations (If Not Applied)
```bash
# Check migration status
python manage.py showmigrations

# Rollback specific migration
python manage.py migrate core 0003_create_bug_prevention_models

# Verify rollback
python manage.py showmigrations core
```

#### Option B: Restore Database from Backup (If Migrations Applied)
```bash
# Find pre-migration backup
LATEST_BACKUP=$(ls -td backups/staging_* | head -1)
DB_BACKUP=$(find "$LATEST_BACKUP" -name "database_*.sql.gz" | head -1)

# Restore database
gunzip -c "$DB_BACKUP" | docker compose exec -T postgres psql -U postgres hub

# Note: This will restore transformation tables
# Manual cleanup may be needed if code is rolled back
```

#### Option C: Manual Database Fix
```sql
-- If transformation tables were partially dropped
-- Recreate tables from backup migration files (NOT RECOMMENDED)
-- Better to restore from backup
```

**Verification**:
```bash
# Check database schema
python manage.py dbshell
\dt transformation*
```

---

### 3. External API Consumer Breakage

**Scenario**: External systems are still calling transformation endpoints, causing integration failures.

**Symptoms**:
- High 404 rate for transformation endpoints
- External system errors
- Integration failures

**Rollback Procedure**:

#### Option A: Notify and Migrate (Preferred)
1. **Identify consumers**:
   ```bash
   # Find external IPs accessing transformation endpoints
   grep "/api/v1/transformation/" logs/access.log | awk '{print $1}' | sort | uniq
   ```

2. **Notify consumers**:
   - Send notification about endpoint removal
   - Provide migration timeline
   - Offer support for migration

3. **Temporary workaround** (if needed):
   - Create stub endpoints that return 410 Gone
   - Add deprecation headers
   - Log all requests for analysis

#### Option B: Restore Endpoints (Not Recommended)
```python
# Add to hub/apps/api/urls.py (TEMPORARY)
path('transformation/', include('hub.apps.transformation.urls')),

# Restore transformation app code from backup
# This is NOT recommended as feature was incomplete
```

**Verification**:
```bash
# Monitor endpoint access
grep "/api/v1/transformation/" logs/access.log | tail -20
```

---

### 4. Feature Restoration (Full Rollback)

**Scenario**: Need to completely restore transformation feature.

**Warning**: This is NOT recommended as the feature was incomplete and problematic. Only perform if absolutely necessary.

**Rollback Procedure**:

1. **Restore Code**:
   ```bash
   # Find backup with transformation code
   LATEST_BACKUP=$(ls -td backups/staging_* | head -1)

   # Restore from backup
   git checkout <backup-commit-hash>

   # Or restore from transformation backup
   cp -r backups/transformation_backup_20260116/hub/apps/transformation hub/apps/
   ```

2. **Restore Database**:
   ```bash
   # Restore from pre-migration backup
   DB_BACKUP=$(find "$LATEST_BACKUP" -name "database_*.sql.gz" | head -1)
   gunzip -c "$DB_BACKUP" | docker compose exec -T postgres psql -U postgres hub
   ```

3. **Update Settings**:
   ```python
   # Add to hub/settings.py
   INSTALLED_APPS = [
       # ...
       'hub.apps.transformation',
   ]
   ```

4. **Run Migrations**:
   ```bash
   python manage.py migrate transformation
   ```

5. **Restart Services**:
   ```bash
   docker compose restart
   ```

6. **Verify**:
   ```bash
   # Check transformation endpoints
   curl http://localhost:8000/api/v1/transformation/pipelines/

   # Check database tables
   python manage.py dbshell
   \dt transformation*
   ```

---

## Rollback Decision Matrix

| Scenario | Severity | Rollback Type | Time to Fix |
|----------|----------|---------------|-------------|
| Import Errors | High | Code Fix (preferred) or Code Rollback | 1-2 hours |
| Migration Failures | Critical | Migration Rollback or DB Restore | 2-4 hours |
| External Consumer Breakage | Medium | Notify Consumers (preferred) | 1-3 days |
| Feature Restoration | N/A | Full Rollback (NOT RECOMMENDED) | 4-8 hours |

---

## Prevention Measures

### Before Rollback
1. **Assess Impact**: Determine if rollback is necessary
2. **Check Alternatives**: Can the issue be fixed without rollback?
3. **Notify Team**: Inform team of rollback decision
4. **Document Issue**: Record the problem and rollback reason

### During Rollback
1. **Backup Current State**: Create backup before rollback
2. **Follow Procedure**: Use documented rollback steps
3. **Monitor Closely**: Watch for issues during rollback
4. **Verify Success**: Confirm rollback resolved the issue

### After Rollback
1. **Root Cause Analysis**: Identify why rollback was needed
2. **Fix Root Cause**: Address the underlying issue
3. **Update Documentation**: Document lessons learned
4. **Plan Re-removal**: If re-removing, plan more carefully

---

## Rollback Checklist

### Pre-Rollback
- [ ] Issue severity assessed
- [ ] Alternatives considered
- [ ] Team notified
- [ ] Rollback procedure reviewed
- [ ] Backup of current state created
- [ ] Rollback window scheduled

### During Rollback
- [ ] Code restored (if needed)
- [ ] Database restored (if needed)
- [ ] Settings updated (if needed)
- [ ] Migrations run (if needed)
- [ ] Services restarted
- [ ] Health checks passed

### Post-Rollback
- [ ] Issue resolved
- [ ] System stable
- [ ] Monitoring active
- [ ] Root cause identified
- [ ] Fix planned
- [ ] Documentation updated

---

## Emergency Contacts

- **Engineering Team**: [Contact Information]
- **On-Call Engineer**: [Contact Information]
- **Database Administrator**: [Contact Information]

---

## Related Documentation

- `docs/TRANSFORMATION_REMOVAL.md` - Complete removal documentation
- `docs/TRANSFORMATION_REMOVAL_BACKUP_IMPACT.md` - Backup/restore impact
- `docs/TRANSFORMATION_REMOVAL_MONITORING.md` - Monitoring procedures
- `scripts/rollback.sh` - Automated rollback script

---

## Notes

- **Rollback is NOT recommended** - The transformation feature was incomplete and problematic
- **Prefer fixes over rollback** - Most issues can be fixed without full rollback
- **Document everything** - Keep detailed records of any rollback procedures
- **Learn from issues** - Use rollback experiences to improve future removals
