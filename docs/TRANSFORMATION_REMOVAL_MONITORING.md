# Transformation Removal Monitoring Guide

**Date**: 2026-01-16
**Purpose**: Monitor the system after transformation feature removal to detect any issues or remaining references

---

## Overview

This document describes monitoring procedures and alerts configured to detect issues related to the transformation feature removal. Monitoring should be active for at least 48 hours after deployment to ensure no problems arise.

---

## Prometheus Alerts

### Alert Configuration
**File**: `monitoring/prometheus/alerts/removal-monitoring.yml`

### Configured Alerts

#### 1. TransformationImportError
- **Severity**: Warning
- **Trigger**: ModuleNotFoundError for transformation module detected
- **Duration**: 1 minute
- **Action**: Investigate code still trying to import transformation module

#### 2. TransformationEndpoint404Spike
- **Severity**: Warning
- **Trigger**: 404 rate > 10 requests/second for transformation endpoints
- **Duration**: 5 minutes
- **Action**: Check for external API consumers still accessing removed endpoints

#### 3. TransformationTableQueryError
- **Severity**: Critical
- **Trigger**: Database queries attempting to access removed transformation tables
- **Duration**: 1 minute
- **Action**: Investigate code or external systems referencing removed tables

#### 4. TransformationExternalConsumerDetected
- **Severity**: Critical
- **Trigger**: Non-404 responses for transformation endpoints (should not be possible)
- **Duration**: 1 minute
- **Action**: Investigate immediately - endpoints should not be accessible

#### 5. TransformationMigrationFailure
- **Severity**: Critical
- **Trigger**: Migration errors related to transformation removal
- **Duration**: 1 minute
- **Action**: Check migration status and fix migration issues

#### 6. TransformationCacheKeysDetected
- **Severity**: Warning
- **Trigger**: Redis cache keys matching 'transformation:*' pattern still present
- **Duration**: 5 minutes
- **Action**: Clean up remaining cache keys

---

## Grafana Dashboard

### Dashboard Configuration
**File**: `monitoring/grafana/dashboards/transformation-removal-monitoring.json`

### Dashboard Panels

1. **Import Errors**: Count of ModuleNotFoundError exceptions for transformation
2. **404 Responses**: Rate of 404 responses for transformation endpoints
3. **Database Query Errors**: Count of database errors for removed tables
4. **External Consumer Detection**: Rate of non-404 requests to transformation endpoints
5. **Transformation Cache Keys**: Count of remaining cache keys
6. **Migration Status**: Count of migration errors

### Access
- **URL**: `http://grafana:3000/d/transformation-removal-monitoring`
- **Refresh**: 30 seconds
- **Tags**: `transformation`, `removal`, `monitoring`

---

## Log Monitoring

### Manual Log Monitoring Commands

#### 1. Monitor Transformation-Related Errors
```bash
tail -f logs/application.log | grep -i transformation
```

#### 2. Monitor Import Errors
```bash
grep -i "ModuleNotFoundError.*transformation" logs/application.log
```

#### 3. Monitor 404 Responses
```bash
grep "/api/v1/transformation/" logs/access.log | grep "404"
```

#### 4. Monitor Database Errors
```bash
grep -i "transformation\|preview_results\|wrangling" logs/application.log | grep -i "error\|exception"
```

#### 5. Monitor PostgreSQL Logs
```bash
# If PostgreSQL logging is enabled
grep -i "transformation\|preview_results\|wrangling" /var/log/postgresql/postgresql.log
```

### Automated Log Monitoring

Set up log aggregation (e.g., ELK stack, Loki) to automatically monitor for:
- Transformation-related errors
- Import errors
- 404 spikes
- Database query errors

---

## API Monitoring

### Track 404 Responses
```bash
# Count 404 responses for transformation endpoints
grep "404" logs/access.log | grep "/api/v1/transformation/" | wc -l

# Rate of 404 responses
grep "404" logs/access.log | grep "/api/v1/transformation/" | awk '{print $1}' | uniq -c
```

### Check for External API Consumers
```bash
# Find non-404 responses (should be empty)
grep "/api/v1/transformation/" logs/access.log | grep -v "404"

# Find external IPs accessing transformation endpoints
grep "/api/v1/transformation/" logs/access.log | awk '{print $1}' | sort | uniq
```

### Expected Behavior
- All requests to `/api/v1/transformation/*` should return 404
- No successful (200, 201, etc.) responses should occur
- High 404 rate may indicate external consumers need notification

---

## Database Monitoring

### Enable Query Logging

#### PostgreSQL Configuration
```sql
-- Enable query logging for transformation table references
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 0;
SELECT pg_reload_conf();
```

### Monitor for Transformation Table Queries
```bash
# Check PostgreSQL logs for transformation table queries
grep -i "transformation\|preview_results\|wrangling" /var/log/postgresql/postgresql.log

# Check for foreign key constraint errors
grep -i "foreign key\|constraint" /var/log/postgresql/postgresql.log | grep -i "transformation"
```

### Verify Tables Are Removed
```sql
-- Check if transformation tables exist (should return 0 rows)
SELECT tablename
FROM pg_tables
WHERE tablename LIKE '%transformation%'
   OR tablename LIKE '%preview%'
   OR tablename LIKE '%wrangling%';
```

---

## Monitoring Schedule

### Immediate (0-24 hours)
- Monitor Prometheus alerts continuously
- Check Grafana dashboard every hour
- Review logs for any errors
- Verify no external consumers detected

### Short-term (24-48 hours)
- Continue monitoring alerts
- Check dashboard twice daily
- Review API access logs for patterns
- Verify database queries are clean

### Long-term (48+ hours)
- Review monitoring weekly
- Check for any recurring issues
- Document any findings
- Consider removing monitoring after 1 month if no issues

---

## Alert Response Procedures

### ImportError Alert
1. Identify the code path causing the import
2. Remove or fix the import statement
3. Deploy fix
4. Verify alert clears

### 404 Spike Alert
1. Check access logs for source IPs
2. Identify external consumers
3. Notify consumers of endpoint removal
4. Provide migration guidance if needed

### Database Query Error Alert
1. Identify the query causing the error
2. Find the code path executing the query
3. Remove or fix the database reference
4. Deploy fix
5. Verify alert clears

### External Consumer Alert
1. **CRITICAL**: Investigate immediately
2. Check if endpoints are still accessible (should not be)
3. Verify URL routing is correct
4. Check for misconfiguration
5. Fix immediately and redeploy

### Migration Failure Alert
1. Check migration status: `python manage.py showmigrations`
2. Review migration logs
3. Fix migration issues
4. Re-run migrations
5. Verify alert clears

### Cache Keys Alert
1. Connect to Redis
2. List transformation keys: `redis-cli --scan --pattern "transformation:*"`
3. Delete keys: `redis-cli --scan --pattern "transformation:*" | xargs redis-cli del`
4. Verify alert clears

---

## Success Indicators

### Healthy State
- ✅ No import errors for 48+ hours
- ✅ 404 rate for transformation endpoints is low or zero
- ✅ No database query errors
- ✅ No external consumers detected
- ✅ No migration errors
- ✅ No cache keys remaining
- ✅ All alerts in "OK" state

### Warning Signs
- ⚠️ Occasional import errors (may indicate cached code)
- ⚠️ Moderate 404 rate (may indicate external consumers)
- ⚠️ Cache keys present (cleanup needed)

### Critical Issues
- 🚨 Frequent import errors (code still references transformation)
- 🚨 Database query errors (code accessing removed tables)
- 🚨 External consumers detected (endpoints still accessible)
- 🚨 Migration failures (database issues)

---

## Related Documentation

- `docs/TRANSFORMATION_REMOVAL.md` - Complete removal documentation
- `docs/TRANSFORMATION_REMOVAL_BACKUP_IMPACT.md` - Backup/restore impact
- `monitoring/prometheus/alerts/removal-monitoring.yml` - Alert configuration
- `monitoring/grafana/dashboards/transformation-removal-monitoring.json` - Dashboard configuration

---

## Contact

For monitoring issues or questions, contact the engineering team or refer to the project documentation.
