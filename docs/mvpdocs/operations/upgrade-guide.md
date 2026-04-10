# Upgrade Guide

Procedures for upgrading the Meshant platform to a new version.

## Pre-Upgrade Checklist

1. **Review the changelog** for the target version. Note any breaking
   changes, new environment variables, or required migrations.
2. **Back up the database** using the procedures in
   [Backup & Restore](backup-restore.md).
3. **Notify stakeholders** of the maintenance window.
4. **Verify staging** -- deploy the target version to staging first
   and run smoke tests. See [Staging Deploy](staging-deploy.md).

## Upgrade Steps

### 1. Pull the New Release

```bash
git fetch origin
git checkout <release-tag>
```

### 2. Review Migration Files

Check for new Django migrations:

```bash
python manage.py showmigrations --plan | grep '\[ \]'
```

### 3. Deploy to Staging

Push to the `staging` branch and let CI/CD deploy. Verify:

- Health checks pass: `/health/`, `/health/ready/`
- Key workflows function (asset creation, marketplace browsing)
- No error spikes in monitoring dashboards

### 4. Deploy to Production

Follow the [Production Deploy](production-deploy.md) procedure:

- Apply Helm upgrade with the new image tag.
- Migrations run automatically via the init container.
- Monitor the rollout: `kubectl rollout status deployment/meshant`.

### 5. Post-Upgrade Verification

- Confirm all pods are running and healthy.
- Check `/health/ready/` returns 200.
- Verify database migration state: `python manage.py showmigrations`.
- Monitor error rates for 30 minutes post-deploy.

## Rollback

If issues are detected after upgrade:

1. Roll back Helm: `helm rollback meshant <previous-revision>`.
2. If migrations need reverting, run
   `python manage.py migrate <app> <previous-migration>`.
3. See [RUNBOOKS.md -- Deployment and rollback](../../RUNBOOKS.md#deployment-and-rollback).

## Related

- [Production Deploy](production-deploy.md) -- deployment procedures
- [Backup & Restore](backup-restore.md) -- pre-upgrade backups
- [Monitoring](monitoring.md) -- post-upgrade monitoring
