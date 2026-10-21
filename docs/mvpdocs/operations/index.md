# Operator Documentation

Deploy, configure, monitor, and maintain the Meshant platform.

## Deployment & Configuration

- [Production Deploy](production-deploy.md) -- atomic Helm upgrade, cosign signing, Trivy scanning, rollback
- [Staging Deploy](staging-deploy.md) -- staging environment setup and CI/CD flow
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

---

## Operational Runbooks

Quick-reference runbooks for common operational scenarios. Each section
is self-contained with symptoms, diagnosis steps, and resolution.

### Asset & Data Ingestion

**Data-first asset creation** -- when `POST /api/v1/assets/data-first/` fails.
Prerequisites: file uploaded and ACTIVE, same tenant owns the file.
Test: `./scripts/run_dataset_creation_flow_tests.sh --skip-e2e`.

### Frontend & UX

**Frontend UX troubleshooting** -- toast notifications not showing, breadcrumbs
hidden, ConfirmDialog or EmptyState issues, UUID validation errors. Check
feature flags `VITE_FEATURE_TOAST_ENABLED`, `VITE_FEATURE_BREADCRUMBS_ENABLED`
(default: true). Rebuild after env change.

**Resource Picker troubleshooting** -- picker dropdowns empty or not loading,
list API 403/404, a11y violations, picker shows text input instead of search UI.
Feature flag: `VITE_FEATURE_RESOURCE_PICKERS_ENABLED=true` (default). When
`false`, pickers render text inputs for manual UUID entry.
Test: `./scripts/run_resource_picker_tests.sh`.
Components: `frontend/src/shared/components/pickers/`.

**Frontend / SPA** -- blank page, chunk-load errors, stale assets after deploy.
Hard-reload or clear service worker cache.

### Authentication & Tenants

**Tenant switch failures** -- `GET /auth/me/tenants/` or
`POST /auth/switch-tenant/` returns 403; `X-Tenant-Id` header rejected; tenant
switcher not visible in UI. Feature flag:
`FEATURE_TENANT_SWITCH_ENABLED=true` (default). `X-Tenant-Id` is validated
against UserTenantMembership; 403 if no membership or feature disabled.

**Subscription plan change failures** -- plan change rejected or plan limits
not applied. Verify `TenantConfig.plan` field and `plan_limits` enforcement.

**Personal tenant creation failures** -- auto-creation of personal tenant on
registration fails. Check `AUTO_CREATE_PERSONAL_TENANT` setting and tenant
quota limits.

### Compliance & Governance

**Compliance Service -- Policy and Risk Config** -- adjust
`compliance-service` policy thresholds (`COMPLIANCE_POLICY_*`) and risk level
thresholds (`COMPLIANCE_RISK_THRESHOLD_*`) via environment variables without
code changes.

**Compliance Run Stuck PENDING** -- compliance run shows PENDING indefinitely.
Common root causes:

1. **Wrong queue** -- jobs must be enqueued to `job_critical` (not `default`).
2. **Worker not running** -- verify: `docker compose ps hub-worker`.
3. **Redis misconfigured** -- API and worker must share same `REDIS_QUEUE_URL`.
4. **Compliance service unreachable** -- check `COMPLIANCE_SERVICE_URL`.
5. **Enqueue failure** -- check API logs for "Failed to enqueue" (Redis down).

Quick check:
```bash
docker exec hub-worker python -c "
from django_rq import get_queue
for q in ['job_critical','job_default','job_low']:
    print(q, get_queue(q).count)
"
```

**Marketplace orders and entitlements -- KYC required** -- orders blocked
when KYC status is not `APPROVED`. Check tenant KYC status and approval
workflow.

### Contract Processing

**Normalization Failures** -- contract normalization status is
`NORMALIZATION_FAILED`. Diagnosis:

```python
from hub.apps.contracts.models import Contract
contract = Contract.objects.get(id='<contract-id>')
print(contract.normalization_errors)
print(contract.normalization_warnings)
```

Common issues: large contract JSON (>1MB), missing objects in ODCS structure,
broken lineage links. Resolution: fix source contract, re-normalize.

**Lineage Issues** -- lineage queries timeout, broken links, visualization
fails. Check GIN indexes on lineage JSONB paths, run
`VACUUM ANALYZE contracts_contract`, verify referenced contracts exist.

### Search & Indexing

**Search Service Issues** -- search queries fail, index not updating, results
incorrect. Rebuild index:

```python
from hub.apps.search.tasks import reindex_all_resources
reindex_all_resources.delay()
```

Check tsvector index status and query performance with `EXPLAIN ANALYZE`.

### Webhooks

**Webhook Service Issues** -- webhooks not delivering, retries exhausted.
Check delivery log:

```python
from hub.apps.webhooks.models import WebhookDelivery
deliveries = WebhookDelivery.objects.filter(
    webhook_id='<id>'
).order_by('-created_at')[:10]
for d in deliveries:
    print(f"{d.status}: {d.error_message}")
```

Retry failed deliveries:
```python
from hub.apps.webhooks.tasks import retry_failed_deliveries
retry_failed_deliveries.delay()
```

### Observability

**Observability Service Issues** -- metrics not appearing, tracing gaps.
Check OpenTelemetry collector health and OTLP exporter configuration.

### Marketplace Connectors

**Marketplace Connector Pattern Violations** -- connector sync fails or
mapping errors. Verify connector configuration, check sync job logs.

**CKAN Connector Issues** -- CKAN API errors, dataset sync failures.
Check CKAN endpoint URL and API key configuration.

### Deployment & Rollback

**Deployment and rollback** -- release gate requires green test suite +
sign-off before deploy. Rollback with `helm rollback` or restore previous
Docker Compose image tag. Startup configuration validation:
`python hub/manage.py validate_config` (exit 0 = valid, exit 1 = fix env).

**Disaster Recovery** -- see [Disaster Recovery](disaster-recovery.md).

**Backup and Recovery** -- see [Backup & Restore](backup-restore.md).

### Testing

**Full test suite** -- `./scripts/run_phase_12a_full_suites.sh`. All critical
suites must be green before release.

**Gap remediation validation** -- complete gap remediation checks and obtain
sign-off before release.

**Security suite** -- security-focused test suite for auth, RBAC, CSRF,
injection prevention.

**Dependency and vulnerability scans** -- automated via CI (Trivy, pip-audit).
Review `.trivyignore` for expired CVE exceptions.

### Post-MVP Runbook Sections

The following runbooks apply to post-MVP features and are not active in the
current release:

- ODBC Virtualization Issues
- Real Scheduled Ingestion/Export E2E
- KYC Provider Integration
- BaaS Infrastructure (dedicated instances)
- Scheduled Ingestion Failures
- Prefect Server / Worker Issues
- BaaS Platform Troubleshooting
