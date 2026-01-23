# Transformation Removal Deployment Guide

**Date**: 2026-01-16
**Purpose**: Step-by-step guide for deploying transformation feature removal

---

## Overview

This guide provides detailed instructions for deploying the transformation feature removal to test/staging and production environments.

---

## Pre-Deployment Checklist

### Code Verification
- [x] Transformation app directory removed
- [x] All transformation imports removed
- [x] URL routing updated
- [x] Integration points cleaned up
- [x] Migrations created
- [x] Monitoring configured
- [x] Documentation updated

### Backup
- [ ] Backup created for test/staging environment
- [ ] Backup created for production environment
- [ ] Backup location documented
- [ ] Backup verification completed

### Environment Preparation
- [ ] Test/staging environment accessible
- [ ] Production environment accessible
- [ ] Database access verified
- [ ] Monitoring systems ready
- [ ] Team notified of deployment

---

## Deployment Steps

### Step 1: Pre-Deployment Verification

Run the verification script to ensure everything is ready:

```bash
./scripts/verify_transformation_removal.sh staging
```

**Expected Output**: All code verifications should pass.

### Step 2: Create Backup

**IMPORTANT**: Always create a backup before deployment.

```bash
# For staging
./scripts/create_backup.sh staging

# For production
./scripts/create_backup.sh production
```

**Verify Backup**:
- Check backup directory exists
- Verify backup files are not empty
- Document backup location

### Step 3: Deploy to Test/Staging

Use the deployment script:

```bash
./scripts/deploy_transformation_removal.sh staging
```

**What the script does**:
1. Pre-deployment checks
2. Creates backup (unless SKIP_BACKUP=true)
3. Runs migrations
4. Restarts services
5. Verifies deployment
6. Sets up monitoring

**Manual alternative** (if script not available):

```bash
# 1. Run migrations
docker compose -f docker-compose.staging.yml exec api python3 hub/manage.py migrate

# 2. Verify tables are removed
docker compose -f docker-compose.staging.yml exec postgres psql -U postgres hub -c "
    SELECT tablename
    FROM pg_tables
    WHERE tablename LIKE '%transformation%'
       OR tablename LIKE '%preview%'
       OR tablename LIKE '%wrangling%';
"

# 3. Restart services
docker compose -f docker-compose.staging.yml restart api worker

# 4. Verify endpoints return 404
curl http://staging-api:8000/api/v1/transformation/pipelines/
# Expected: 404
```

### Step 4: Monitor for 48 Hours

**Active Monitoring** (first 24 hours):
- Check Prometheus alerts every hour
- Review Grafana dashboard every 2 hours
- Monitor application logs continuously
- Check for import errors
- Monitor API access logs

**Passive Monitoring** (24-48 hours):
- Review alerts twice daily
- Check dashboard once daily
- Review logs for any issues
- Verify no external consumers

**Monitoring Resources**:
- **Alerts**: `monitoring/prometheus/alerts/removal-monitoring.yml`
- **Dashboard**: `monitoring/grafana/dashboards/transformation-removal-monitoring.json`
- **Guide**: `docs/TRANSFORMATION_REMOVAL_MONITORING.md`

### Step 5: Verify Runtime Success Criteria

After 48 hours, run comprehensive verification:

```bash
./scripts/verify_transformation_removal.sh staging
```

**Check**:
- [ ] No import errors in logs
- [ ] No database query errors
- [ ] All endpoints return 404
- [ ] No external consumers detected
- [ ] No cache keys remaining
- [ ] All alerts in OK state

### Step 6: Deploy to Production

**Only after successful 48-hour monitoring period in staging!**

```bash
# 1. Final verification in staging
./scripts/verify_transformation_removal.sh staging

# 2. Create production backup
./scripts/create_backup.sh production

# 3. Deploy to production
./scripts/deploy_transformation_removal.sh production

# 4. Monitor production closely for first 24 hours
```

**Production Deployment Checklist**:
- [ ] Staging verification successful
- [ ] Production backup created
- [ ] Deployment window scheduled
- [ ] Team notified
- [ ] Rollback plan ready
- [ ] Monitoring active
- [ ] On-call engineer available

---

## Post-Deployment Tasks

### Immediate (0-1 hour)
- [ ] Verify services are running
- [ ] Check for import errors
- [ ] Verify endpoints return 404
- [ ] Confirm monitoring is active
- [ ] Document deployment time

### Short-term (1-24 hours)
- [ ] Monitor alerts continuously
- [ ] Review dashboard every 2 hours
- [ ] Check logs for errors
- [ ] Verify no external consumers
- [ ] Document any issues

### Medium-term (24-48 hours)
- [ ] Continue monitoring
- [ ] Review alerts twice daily
- [ ] Check for any recurring issues
- [ ] Verify success criteria
- [ ] Prepare production deployment (if staging)

### Long-term (48+ hours)
- [ ] Final verification
- [ ] Document lessons learned
- [ ] Update runbooks if needed
- [ ] Consider removing monitoring after 1 month

---

## Troubleshooting

### Issue: Migration Fails

**Symptoms**: Migration errors during deployment

**Solution**:
1. Check migration status: `python manage.py showmigrations`
2. Review migration logs
3. Check database connectivity
4. Verify migration files exist
5. See `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` for rollback procedures

### Issue: Import Errors After Deployment

**Symptoms**: `ModuleNotFoundError: No module named 'hub.apps.transformation'`

**Solution**:
1. Find the code path causing the import
2. Remove or fix the import statement
3. Redeploy
4. See `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` for details

### Issue: Endpoints Not Returning 404

**Symptoms**: Transformation endpoints return 200 or other status codes

**Solution**:
1. **CRITICAL**: This should not happen
2. Verify URL routing is correct
3. Check for misconfiguration
4. Review `hub/apps/api/urls.py`
5. Fix immediately and redeploy

### Issue: High 404 Rate

**Symptoms**: Many 404 responses for transformation endpoints

**Solution**:
1. Check access logs for source IPs
2. Identify external consumers
3. Notify consumers of endpoint removal
4. Provide migration guidance
5. Consider temporary stub endpoints if needed

### Issue: Database Query Errors

**Symptoms**: Errors querying removed transformation tables

**Solution**:
1. Identify the query causing the error
2. Find the code path executing the query
3. Remove or fix the database reference
4. Redeploy
5. See `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` for details

---

## Rollback Procedures

If rollback is necessary, see:
- `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` - Complete rollback procedures
- `scripts/rollback.sh` - Automated rollback script

**Important**: Rollback should only be performed if absolutely necessary, as the transformation feature was incomplete and problematic.

---

## Success Indicators

### Healthy Deployment
- ✅ No import errors
- ✅ All endpoints return 404
- ✅ No database query errors
- ✅ No external consumers detected
- ✅ All alerts in OK state
- ✅ Services running normally

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

## Monitoring Schedule

### Hour 0-1 (Immediate)
- Check services are running
- Verify no import errors
- Confirm endpoints return 404
- Check monitoring is active

### Hour 1-6 (Active)
- Monitor alerts every 30 minutes
- Review dashboard every hour
- Check logs continuously
- Verify no errors

### Hour 6-24 (Active)
- Monitor alerts every hour
- Review dashboard every 2 hours
- Check logs for patterns
- Document any issues

### Hour 24-48 (Passive)
- Review alerts twice daily
- Check dashboard once daily
- Review logs for issues
- Prepare verification

### After 48 Hours
- Run comprehensive verification
- Document results
- Proceed with production deployment (if staging)
- Continue monitoring for 1 month

---

## Related Documentation

- `docs/TRANSFORMATION_REMOVAL.md` - Complete removal documentation
- `docs/TRANSFORMATION_REMOVAL_MONITORING.md` - Monitoring procedures
- `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` - Rollback procedures
- `docs/TRANSFORMATION_REMOVAL_SUCCESS_CRITERIA.md` - Success criteria
- `docs/TRANSFORMATION_REMOVAL_BACKUP_IMPACT.md` - Backup impact

---

## Deployment Scripts

- `scripts/deploy_transformation_removal.sh` - Automated deployment script
- `scripts/verify_transformation_removal.sh` - Verification script
- `scripts/create_backup.sh` - Backup script
- `scripts/rollback.sh` - Rollback script

---

## Contact

For deployment issues or questions:
- **Engineering Team**: [Contact Information]
- **On-Call Engineer**: [Contact Information]
- **Database Administrator**: [Contact Information]

---

## Notes

- **Always backup before deployment**
- **Monitor closely for first 48 hours**
- **Document any issues immediately**
- **Follow rollback procedures if needed**
- **Keep team informed of deployment status**
