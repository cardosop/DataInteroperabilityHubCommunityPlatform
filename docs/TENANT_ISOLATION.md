# Tenant isolation (Phase 16)

**Last Updated**: 2026-01-29

This document defines the single "current tenant" contract for multi-tenant list/detail APIs and lists endpoints that MUST use it. See Phase 16 — Governance: Tenant isolation in `openspec/changes/workflows1/tasks.md`.

---

## 1. Current tenant contract

All multi-tenant list and detail views **MUST** filter by the current request's tenant. The contract is:

- **Helper**: Use `hub.apps.tenants.request_tenant.get_request_tenant_id(request)` or `get_request_tenant(request)` to obtain the current tenant ID (and optionally the tenant instance).
- **Request attributes**: Middleware (`TenantScopingMiddleware` in `hub.apps.auth.middleware`) sets `request.tenant_id` and `request.tenant` before views run. Views may use these when set, but **must** use the central helper so fallback order is consistent and testable.

### 1.1 Fallback order (standardized)

The helper and middleware use this order:

1. **request.tenant_id** — set by TenantScopingMiddleware from JWT/API key or user
2. **request.tenant.id** — set by TenantScopingMiddleware
3. **request.user from DB** — `User.objects.only('tenant_id').get(id=user.id)` (thread-safe, works in tests)
4. **request.user.tenant_id** — direct field
5. **request.user.tenant.id** — relationship

Views must not implement a different order; use the helper so changing tenant context (e.g. in tests) changes the scope of the response.

### 1.2 Usage

```python
from hub.apps.tenants.request_tenant import get_request_tenant_id, get_request_tenant

# In get_queryset (filter by tenant_id):
tenant_id_str = get_request_tenant_id(self.request)
if tenant_id_str:
    return MyModel.objects.filter(tenant_id=tenant_id_str)
return MyModel.objects.none()

# When you need the Tenant instance:
tenant_id_str, tenant = get_request_tenant(request)
if not tenant:
    return Response({'error': 'User must belong to a tenant'}, status=400)
```

---

## 2. Multi-tenant list/detail endpoints

These ViewSets/views return tenant-scoped list or detail. They MUST use the central helper for filtering.

| App | ViewSet / view | List endpoint | Detail endpoint |
|-----|----------------|---------------|-----------------|
| assets | AssetViewSet | GET /api/v1/assets/ | GET /api/v1/assets/{id}/ |
| contracts | ContractViewSet | GET /api/v1/contracts/ | GET /api/v1/contracts/{id}/ |
| datasets | DatasetViewSet | GET /api/v1/datasets/ | GET /api/v1/datasets/{id}/ |
| files | FileViewSet | GET /api/v1/files/ | GET /api/v1/files/{id}/ |
| jobs | JobViewSet | GET /api/v1/jobs/ | GET /api/v1/jobs/{id}/ |
| mesh | DataMeshDomainViewSet | GET /api/v1/mesh/domains/ | GET /api/v1/mesh/domains/{id}/ |
| virtualization | VirtualDatasetViewSet | GET /api/v1/virtualization/datasets/ | GET /api/v1/virtualization/datasets/{id}/ |
| virtualization | QueryExecutionViewSet | GET /api/v1/virtualization/query-executions/ | GET /api/v1/virtualization/query-executions/{id}/ |
| virtualization | VirtualizationTopologyViewSet | GET /api/v1/virtualization/topology/ | N/A |
| dq | DQRunViewSet | GET /api/v1/dq/runs/ | GET /api/v1/dq/runs/{id}/ |
| compliance | ComplianceRunViewSet | GET /api/v1/compliance/runs/ | GET /api/v1/compliance/runs/{id}/ |
| audit | AuditEventViewSet | GET /api/v1/audit/audit-events/ | GET /api/v1/audit/audit-events/{id}/ |
| semantic | SemanticResourceViewSet | GET /api/v1/semantic/resources/ | GET /api/v1/semantic/resources/{id}/ |
| scheduled_ingestion | ScheduledIngestionViewSet | GET /api/v1/scheduled-ingestions/ | GET /api/v1/scheduled-ingestions/{id}/ |
| scheduled_ingestion | ScheduledIngestionRunViewSet | GET /api/v1/scheduled-ingestions/{id}/runs/ | GET /api/v1/scheduled-ingestions/{id}/runs/{run_id}/ |
| scheduled_export | ScheduledExportViewSet | GET /api/v1/scheduled-exports/ | GET /api/v1/scheduled-exports/{id}/ |
| scheduled_export | ScheduledExportRunViewSet | GET /api/v1/scheduled-exports/runs/ | GET /api/v1/scheduled-exports/runs/{id}/ |
| governance | AccessCertificationViewSet | GET /api/v1/governance/access/certifications/ | GET /api/v1/governance/access/certifications/{id}/ |
| governance | RetentionPolicyViewSet | GET /api/v1/governance/retention-policies/ | GET /api/v1/governance/retention-policies/{id}/ |
| ml | MLModelViewSet | GET /api/v1/ml/models/ | GET /api/v1/ml/models/{id}/ |

**Note**: All ViewSets listed above MUST use `get_request_tenant_id(self.request)` or `get_request_tenant(self.request)` from `hub.apps.tenants.request_tenant` for tenant resolution. This ensures consistent fallback order and testability.

**Apps using central helper** (Phase 24.2): marketplace, integrations, virtualization, webhooks, social, scheduled_export (when implemented). All tenant-scoped views in these apps use the central helper exclusively; no inline `hasattr(request.user, "tenant")` or `request.user.tenant` checks.

Platform admins may see all tenants; regular users see only their tenant. Tests in `tests/integration/test_tenant_isolation.py` assert that user A (tenant 1) cannot see tenant 2's resource by ID (404) and that list returns only tenant 1's resources.

### 2.1 Running the tenant isolation tests

- **First run** (no existing test DB): Session-scoped DB create + migrations run during the first test's setup and can take **~5–8 minutes** in this project. Use a long enough runner timeout (e.g. 10 min) if running in CI.
- **Reruns**: Use `--reuse-db` so pytest reuses the existing test database and skips create/migrate; the suite then completes in **under a minute**.
- Example (Docker):
  `docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/integration/test_tenant_isolation.py -v --tb=short --reuse-db"`

---

---

## 3. Tenant Creation (Phase 25.3)

### 3.1 Self-Service Onboarding

Tenants can be created through self-service onboarding:

**POST** `/api/v1/tenants/onboarding/`

See `docs/ONBOARDING.md` for detailed onboarding documentation.

### 3.2 Platform Admin Creation

Platform admins can create tenants via:

**POST** `/api/v1/tenants/`

Requires platform admin authentication.

---

## 4. Plan Limits (Phase 25.1, 25.2)

### 4.1 Plan-Based Limits

Each tenant is assigned a plan (FREE, PRO, or ENTERPRISE) with specific resource limits:

- **max_assets**: Maximum number of assets
- **max_datasets**: Maximum number of datasets
- **max_scheduled_ingestions**: Maximum number of scheduled ingestion configurations
- **max_scheduled_exports**: Maximum number of scheduled export configurations
- **max_api_calls_per_month**: Maximum API calls per month
- **max_scheduled_runs_per_month**: Maximum scheduled ingestion runs per month
- **max_export_runs_per_month**: Maximum scheduled export runs per month
- **max_storage_gb**: Maximum storage in GB

See `docs/BILLING.md` for plan details and limits.

### 4.2 Limit Enforcement

Plan limits are enforced via `PlanLimitService.check_limit()`:

- **Asset creation**: Checks `max_assets` limit
- **Dataset creation**: Checks `max_datasets` limit
- **Scheduled ingestion creation**: Checks `max_scheduled_ingestions` limit
- **Scheduled export creation**: Checks `max_scheduled_exports` limit
- **Scheduled ingestion runs**: Checks `max_scheduled_runs_per_month` limit
- **Scheduled export runs**: Checks `max_export_runs_per_month` limit

When a limit is exceeded, a `403 Forbidden` response is returned with code `plan_limit_exceeded`.

### 4.3 Usage Monitoring

Tenants can monitor their usage:

**GET** `/api/v1/tenants/me/usage/`

Returns current usage metrics and plan limits.

---

## 5. Tenant Suspension (Phase 25.3)

### 5.1 Suspension Reasons

Tenants can be suspended for:

- **Payment failure**: Subscription past due or unpaid
- **Policy violation**: Violation of terms of service
- **Manual suspension**: Platform admin action

### 5.2 Suspension Behavior

When a tenant is suspended:

- **Status**: Tenant status set to `SUSPENDED`
- **Write operations**: All write operations (POST, PUT, PATCH, DELETE) blocked
- **Read operations**: Read operations (GET, HEAD, OPTIONS) still allowed
- **Error response**: `403 Forbidden` with code `tenant_suspended`

### 5.3 Suspension Enforcement

Suspension is enforced via `TenantSuspensionMiddleware`:

- **Middleware**: Checks tenant status before processing requests
- **Write methods**: Blocks POST, PUT, PATCH, DELETE for suspended tenants
- **Read methods**: Allows GET, HEAD, OPTIONS for suspended tenants

### 5.4 Subscription Status

Subscription status also affects access:

- **PAST_DUE**: Write operations blocked (code `subscription_inactive`)
- **UNPAID**: Write operations blocked (code `subscription_inactive`)
- **ACTIVE**: Full access allowed

### 5.5 Platform Admin Actions

Platform admins can suspend/resume tenants:

**POST** `/api/v1/platform/tenants/{id}/suspend/`
**POST** `/api/v1/platform/tenants/{id}/resume/`

See `docs/BILLING.md` for subscription management details.

---

## 6. References

- **Helper**: `hub.apps.tenants.request_tenant.get_request_tenant_id`, `get_request_tenant`
- **Middleware**: `hub.apps.auth.middleware.TenantScopingMiddleware` (sets request.tenant_id / request.tenant)
- **Suspension Middleware**: `hub.apps.tenants.middleware.TenantSuspensionMiddleware` (enforces suspension)
- **Plan Limits**: `hub.apps.tenants.services.PlanLimitService` (enforces plan limits)
- **Tests**: `tests/integration/test_tenant_isolation.py` (no mocks; real DB and auth)
- **Onboarding**: `docs/ONBOARDING.md` (self-service tenant creation)
- **Billing**: `docs/BILLING.md` (plans, limits, subscriptions)
