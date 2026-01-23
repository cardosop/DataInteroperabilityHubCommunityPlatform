# Transformation Removal Deployment Checklist

**Date**: 2026-01-16
**Environment**: [ ] Staging [ ] Production

---

## Pre-Deployment

### Code Verification
- [ ] Run `./scripts/verify_transformation_removal.sh staging`
- [ ] All code verifications pass
- [ ] No transformation imports found
- [ ] Transformation app directory removed
- [ ] URL routing updated

### Backup
- [ ] Backup created: `./scripts/create_backup.sh [environment]`
- [ ] Backup location documented: _______________________
- [ ] Backup verified (files exist and not empty)
- [ ] Backup timestamp: _______________________

### Environment Preparation
- [ ] Environment accessible
- [ ] Database accessible
- [ ] Monitoring systems ready
- [ ] Team notified
- [ ] Deployment window scheduled: _______________________

---

## Deployment

### Step 1: Deploy Code
- [ ] Code deployed to environment
- [ ] Services restarted
- [ ] Health checks passing

### Step 2: Run Migrations
- [ ] Migrations executed: `python manage.py migrate`
- [ ] Migration status verified: `python manage.py showmigrations`
- [ ] No migration errors
- [ ] Transformation tables verified as removed

### Step 3: Verify Deployment
- [ ] Transformation endpoints return 404
  - [ ] `/api/v1/transformation/pipelines/` → 404
  - [ ] `/api/v1/transformation/executions/` → 404
  - [ ] `/api/v1/transformation/previews/` → 404
  - [ ] `/api/v1/transformation/wrangling/` → 404
- [ ] No import errors in logs
- [ ] Services running normally
- [ ] Monitoring active

---

## Post-Deployment Monitoring

### Hour 0-1 (Immediate)
- [ ] Services running
- [ ] No import errors
- [ ] Endpoints return 404
- [ ] Monitoring active
- [ ] Initial verification complete

### Hour 1-6 (Active Monitoring)
- [ ] Alerts checked every 30 minutes
- [ ] Dashboard reviewed every hour
- [ ] Logs monitored continuously
- [ ] No errors detected
- [ ] Time: _______________________

### Hour 6-24 (Active Monitoring)
- [ ] Alerts checked every hour
- [ ] Dashboard reviewed every 2 hours
- [ ] Logs checked for patterns
- [ ] Any issues documented
- [ ] Time: _______________________

### Hour 24-48 (Passive Monitoring)
- [ ] Alerts reviewed twice daily
- [ ] Dashboard checked once daily
- [ ] Logs reviewed for issues
- [ ] Verification prepared
- [ ] Time: _______________________

---

## Verification (After 48 Hours)

### Code Verification
- [ ] No transformation imports
- [ ] No transformation files
- [ ] No linting errors

### Database Verification
- [ ] No transformation tables
- [ ] No foreign keys to transformation tables
- [ ] No pending/running transformation jobs
- [ ] Migrations successful

### API Verification
- [ ] All endpoints return 404
- [ ] No external consumers detected
- [ ] OpenAPI schema cleaned (if server available)

### Log Verification
- [ ] No import errors for 48 hours
- [ ] No transformation-related errors
- [ ] No database query errors

### Monitoring Verification
- [ ] All alerts in OK state
- [ ] Dashboard showing healthy metrics
- [ ] No critical issues detected

### Cache Verification
- [ ] No transformation cache keys (if Redis accessible)
- [ ] Cache cleanup completed

---

## Production Deployment (After Staging Success)

### Pre-Production
- [ ] Staging verification successful (48 hours)
- [ ] Production backup created
- [ ] Deployment window scheduled
- [ ] Team notified
- [ ] Rollback plan ready
- [ ] On-call engineer available

### Production Deployment
- [ ] Code deployed
- [ ] Migrations executed
- [ ] Services restarted
- [ ] Initial verification complete

### Production Monitoring
- [ ] Monitor closely for first 24 hours
- [ ] Alerts checked every hour
- [ ] Dashboard reviewed every 2 hours
- [ ] Logs monitored continuously

---

## Issues & Actions

### Issues Encountered
| Time | Issue | Action Taken | Resolved |
|------|-------|--------------|----------|
|      |       |              |          |
|      |       |              |          |

### Notes
_______________________________________________________________________
_______________________________________________________________________
_______________________________________________________________________

---

## Sign-off

**Deployed By**: _______________________
**Date**: _______________________
**Time**: _______________________
**Environment**: [ ] Staging [ ] Production
**Status**: [ ] Success [ ] Issues Encountered
**Next Steps**: _______________________

---

## Related Documentation

- `docs/TRANSFORMATION_REMOVAL_DEPLOYMENT_GUIDE.md` - Detailed deployment guide
- `docs/TRANSFORMATION_REMOVAL_MONITORING.md` - Monitoring procedures
- `docs/TRANSFORMATION_REMOVAL_ROLLBACK.md` - Rollback procedures
- `docs/TRANSFORMATION_REMOVAL_SUCCESS_CRITERIA.md` - Success criteria
