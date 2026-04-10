# Operator Documentation

Deploy, configure, monitor, and maintain the Meshant platform.

## Deployment & Configuration

- [Production Deploy](production-deploy.md) -- pre-flight, blue-green, canary, rollback
- [Staging Deploy](staging-deploy.md) -- staging environment setup
- [Destroy Staging](../../runbooks/destroy-staging.md) -- full teardown, sweep, verification
- [Configuration Reference](configuration-reference.md) -- all env vars and Helm keys
- [Local Development](local-dev.md) -- dev environment setup

## Operations & Maintenance

- [Backup & Restore](backup-restore.md) -- database snapshots, S3 sync, restore drills
- [Secrets Management](secrets-management.md) -- rotation, audit, access control
- [Monitoring](monitoring.md) -- dashboards, alerts, metrics
- [Health Checks](health-checks.md) -- endpoint monitoring

## Incident Management

- [Incident Response](incident-response.md) -- runbook for incidents
- [Disaster Recovery](disaster-recovery.md) -- RTO/RPO, failover procedures

## Planning

- [Capacity Planning](capacity-planning.md) -- scaling guidelines
- [Upgrade Guide](upgrade-guide.md) -- version upgrade procedures

## Existing Runbooks

See [RUNBOOKS.md](../../RUNBOOKS.md) for the full 37-section operator reference.
Sections marked `[Post-MVP]` are for post-launch features.

### MVP Runbook Sections

- [Data-first asset creation](../../RUNBOOKS.md#data-first-asset-creation)
- [Frontend UX troubleshooting](../../RUNBOOKS.md#frontend-ux-troubleshooting)
- [Resource Picker troubleshooting](../../RUNBOOKS.md#resource-picker-troubleshooting)
- [Tenant switch failures](../../RUNBOOKS.md#tenant-switch-failures)
- [Brand Name Change](../../RUNBOOKS.md#brand-name-change)
- [Subscription plan change failures](../../RUNBOOKS.md#subscription-plan-change-failures)
- [Personal tenant creation failures](../../RUNBOOKS.md#personal-tenant-creation-failures)
- [Compliance Service — Policy and Risk Config](../../RUNBOOKS.md#compliance-service-policy-and-risk-config)
- [Compliance Run Stuck PENDING](../../RUNBOOKS.md#compliance-run-stuck-pending)
- [Marketplace orders and entitlements — KYC required](../../RUNBOOKS.md#marketplace-orders-and-entitlements-kyc-required)
- [Full test suite (Phase 12A-style)](../../RUNBOOKS.md#full-test-suite-phase-12a-style)
- [Batch execution (Phase 12A path-based batches)](../../RUNBOOKS.md#batch-execution-phase-12a-path-based-batches)
- [Gap remediation validation](../../RUNBOOKS.md#gap-remediation-validation)
- [Security suite (Phase 12A.3)](../../RUNBOOKS.md#security-suite-phase-12a3)
- [Chaos tests (manual only)](../../RUNBOOKS.md#chaos-tests-manual-only)
- [Dependency and vulnerability scans](../../RUNBOOKS.md#dependency-and-vulnerability-scans)
- [Deployment and rollback](../../RUNBOOKS.md#deployment-and-rollback)
- [Normalization Failures](../../RUNBOOKS.md#normalization-failures)
- [Lineage Issues](../../RUNBOOKS.md#lineage-issues)
- [Search Service Issues](../../RUNBOOKS.md#search-service-issues)
- [Observability Service Issues](../../RUNBOOKS.md#observability-service-issues)
- [Webhook Service Issues](../../RUNBOOKS.md#webhook-service-issues)
- [Marketplace Connector Pattern Violations](../../RUNBOOKS.md#marketplace-connector-pattern-violations)
- [Disaster Recovery](../../RUNBOOKS.md#disaster-recovery)
- [Backup and Recovery](../../RUNBOOKS.md#backup-and-recovery)
- [CKAN Connector Issues](../../RUNBOOKS.md#ckan-connector-issues)
- [ODH Integration Troubleshooting](../../RUNBOOKS.md#odh-integration-troubleshooting)
- [Frontend / SPA](../../RUNBOOKS.md#frontend--spa)

### Post-MVP Runbook Sections

- [ODBC Virtualization Issues [Post-MVP]](../../RUNBOOKS.md#odbc-virtualization-issues-post-mvp)
- [Real Scheduled Ingestion/Export E2E [Post-MVP]](../../RUNBOOKS.md#real-scheduled-ingestionexport-e2e-post-mvp)
- [KYC provider integration [Post-MVP]](../../RUNBOOKS.md#kyc-provider-integration-post-mvp)
- [BaaS Infrastructure (dedicated instances) [Post-MVP]](../../RUNBOOKS.md#baas-infrastructure-dedicated-instances-post-mvp)
- [Scheduled Ingestion Failures [Post-MVP]](../../RUNBOOKS.md#scheduled-ingestion-failures-post-mvp)
- [Prefect Server Issues [Post-MVP]](../../RUNBOOKS.md#prefect-server-issues-post-mvp)
- [Prefect Workers Issues [Post-MVP]](../../RUNBOOKS.md#prefect-workers-issues-post-mvp)
- [BaaS Platform Troubleshooting [Post-MVP]](../../RUNBOOKS.md#baas-platform-troubleshooting-post-mvp)
