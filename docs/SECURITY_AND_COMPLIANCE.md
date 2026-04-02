# Security & Compliance

> Security policy, tenant isolation, GDPR, data residency, and audit
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

# Security

**Last Updated**: 2026-03-22

This document covers production security requirements: secrets, CORS, and related configuration.

---

## 1. Secrets in production and staging

### Requirements

- **Production and staging MUST set** `SECRET_KEY` and `JWT_SECRET_KEY` via environment (or a secret manager). They MUST NOT use the development default values.
- **Never commit** production or staging secrets to the repository.
- Use a secret manager (e.g. HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager) or CI/CD–injected environment variables for production/staging.

### Enforcement

- When `ENVIRONMENT=production`, Django startup fails with `ImproperlyConfigured` if:
  - `SECRET_KEY` is unset or equals the dev default (`dev-secret-key-not-for-production`), or
  - `JWT_SECRET_KEY` is unset or equals the dev default (`dev-jwt-secret-key-not-for-production`).
- Integration tests in `tests/security/test_production_secrets.py` assert that production rejects dev-default secrets and accepts non-default values (no mocks).

### How to set

- **Docker Compose**: Set in `.env` (never commit production `.env`) or pass via `environment:` in compose.
- **Kubernetes**: Use `Secret` resources and reference via `envFrom` or `valueFrom.secretKeyRef`.
- **CI/CD**: Inject from your secret store into the runtime environment; do not log or echo secrets.

### References

- `hub/settings.py`: `ENVIRONMENT`, `SECRET_KEY`, `JWT_SECRET_KEY`, and production validation block.
- `docs/DEVELOPMENT_GUIDE.md`: Production deployment and secrets overview.

### HashiCorp Vault Integration (Phase 2)

- **Authentication**: AppRole auth (CI/Docker) and Kubernetes auth (in-cluster). Vault agent sidecar renders secrets as env files.
- **KV v2 secrets**: All production secrets stored at `secret/hub/production/{django,postgres,redis,minio,email}`.
- **Transit encryption**: AES256-GCM96 key (`hub-encryption-key`) with auto-rotation every 720h for field-level encryption. Wired into the application via `hub/apps/integrations/encryption.py` — `encrypt_json_field()` tries Vault Transit first; if unavailable or on error, falls back to Fernet (see below). Ciphertext prefix `vault:v1:...` routes decryption to Transit; base64 strings route to Fernet.
- **Dynamic database credentials**: PostgreSQL `hub-api` role with 1h TTL via Vault Database engine. Credentials rotate automatically.
- **Vault loader**: `hub/vault_loader.py` injects secrets into `os.environ` at Django startup (before any secret consumption). Retry 3x exponential on transient errors.

### Credentials Encrypted at Rest (Phase 121G)

All credential-bearing JSONFields are encrypted before storage using Vault Transit (primary) or Fernet symmetric encryption (fallback via `ENCRYPTION_KEY`). The model `save()` method encrypts on write; a `get_*()` accessor decrypts on read. Serializers call the accessor and mask sensitive fields (password, api_key, token, connection_string, etc.) before returning to the API.

| # | App | Model | Field | Encryption Format | Migration |
|---|-----|-------|-------|-------------------|-----------|
| 1 | webhooks | `Webhook` | `secret` | `vault:v1:...` or `v1:<fernet>` | Phase 11.4 (existing) |
| 2 | integrations | `MarketplaceConnection` | `credentials` | `vault:v1:...` or base64 Fernet | Phase 11.4 (existing) |
| 3 | scheduled_ingestion | `ScheduledIngestion` | `source_config` | `{"_encrypted": "..."}` | `0009_encrypt_source_config` |
| 4 | scheduled_export | `ScheduledExport` | `destination_config` | `{"_encrypted": "..."}` | `0005_encrypt_destination_config` |
| 5 | tenants | `TenantConfig` | `sso_config` | `{"_encrypted": "..."}` | `0021_encrypt_sso_config` |
| 6 | dq | `DQAlertingRule` | `channel_config` | `{"_encrypted": "..."}` | `0005_encrypt_channel_config` |
| 7 | virtualization | `VirtualDataset` | `sources` | `{"_encrypted": "..."}` (list wrapped as `{"_items": [...]}`) | `0006_encrypt_sources` |
| 8 | transformation | `TransformationPipeline` | `pipeline_definition` | `{"_encrypted": "..."}` | `0002_encrypt_pipeline_definition` |
| 9 | transformation | `TransformationNode` | `node_config` | `{"_encrypted": "..."}` | `0003_encrypt_node_config` |

**Key rotation**: See `docs/DEPLOYMENT_AND_OPERATIONS.md` § "Rotating ENCRYPTION_KEY".

**Backup/restore**: The `ENCRYPTION_KEY` (or Vault Transit key) used at encryption time **must** be available at restore time. If a database backup is restored and the encryption key has been rotated or lost, all encrypted fields become unrecoverable. Always back up `ENCRYPTION_KEY` alongside database backups (see `docs/DEPLOYMENT_AND_OPERATIONS.md` § "Database Backup / Restore").

### Content Security Policy & Source Maps

- **CSP headers**: Enforced via Traefik middleware. `script-src 'self'`; no inline scripts in production.
- **Source maps**: Disabled by default in production (`GENERATE_SOURCEMAPS=true` required to enable). Controlled in `frontend/vite.config.ts`.

### CORS Hardening

- **Traefik CORS**: `routes.yml.tmpl` uses `${ALLOWED_ORIGINS_REGEX}` — no wildcard in production. Dev defaults to localhost only.
- **Django CORS**: `CORS_ALLOWED_ORIGINS` must list explicit origins. `CORS_ALLOW_CREDENTIALS=True` requires non-wildcard.

### Container & Supply Chain Security

- **Image signing**: Cosign signs all container images in CI. Admission webhook rejects unsigned images in production clusters.
- **Pod Security Standards**: `restricted` PSS enforced via Kubernetes namespace labels. `readOnlyRootFilesystem: true` on all pods with emptyDir mounts for temp/cache.
- **Non-root containers**: All containers run as non-root UIDs (api: 1000, frontend/nginx: 101, pgbouncer: 70).

### Network Policies

- 15+ NetworkPolicy resources enforce pod-to-pod communication rules. Default deny-all ingress/egress per namespace.
- API pod: ingress from Traefik only; egress to PostgreSQL, Redis, MinIO, external services.
- Worker pod: no ingress; egress to PostgreSQL, Redis, MinIO.
- Frontend pod: ingress from Traefik only; no backend egress.

### TLS on Internal Services

- PostgreSQL: `sslmode=require` enforced in production (`PGBOUNCER_ENABLED` sets `CONN_MAX_AGE=0`).
- Redis: All 5 core Redis URLs must contain auth credentials (`@` + non-empty password) in production.
- Vault: TLS with minimum TLS 1.2 on listener. Raft backend uses TLS for peer communication.

### Production Environment Guards

- `ENCRYPTION_KEY`: Must be set and not equal dev default when `ENVIRONMENT=production`.
- `SECRET_KEY`, `JWT_SECRET_KEY`: Must not be dev defaults.
- Redis URLs: Validated for auth credentials at startup.
- PostgreSQL: SSL mode enforced, BaaS database also requires SSL.

---

## 2. CORS in production and staging

### Requirements

- In **production and staging**, CORS MUST use **explicit allowed origins**, not `*`.
- **Django**: `CORS_ALLOWED_ORIGINS` must list the exact origins (e.g. `https://app.example.com`, `https://hub.example.com`). Do not use `CORS_ALLOWED_ORIGINS=*` or allow-all when credentials (cookies, authorization headers) are used.
- **Traefik**: In `infrastructure/traefik/dynamic/routes.yml`, the CORS middleware `accessControlAllowOriginList` must not be `*` in production; replace with explicit origins (see file comments and deployment docs).

### How to set (Django)

- Set `CORS_ALLOWED_ORIGINS` as a comma-separated list or JSON array of origins, e.g.:
  ```bash
  CORS_ALLOWED_ORIGINS=https://app.example.com,https://hub.example.com
  ```
- For staging, use staging frontend/origin URLs only.
- See `hub/settings.py` for the default (development) list; production must override with explicit origins.

### How to set (Traefik)

- The file `infrastructure/traefik/dynamic/routes.yml` contains a CORS middleware with a placeholder `*` and a comment that production must replace it with explicit origins.
- For env-driven or deployment-specific CORS, generate this file from a template (e.g. CI/CD or ConfigMap) that injects the allowed origins for the environment.
- Traefik v3 file provider does not support env var substitution inside YAML; use a pre-processing step or separate generated file per environment.

### Validation

- **Checklist**: Before deploying to production/staging, confirm that `CORS_ALLOWED_ORIGINS` (Django) and Traefik CORS config do not use `*` when credentials are used.
- **CI**: Run `python scripts/check_production_cors.py --production` (or with `ENVIRONMENT=production`). It exits 1 if Traefik uses `accessControlAllowOriginList: ["*"]` or if Django `CORS_ALLOWED_ORIGINS` contains `*` when `ENVIRONMENT=production`. Add this to CI for production/staging builds.

---

## 3. AllowAny (public) endpoints

All views that use `AllowAny` are listed and reviewed in **`docs/AUDIT_POLICY.md`** (Section 3). For each endpoint we state whether it is intentional and what data is exposed. Public endpoints must **not** expose sensitive data (PII, tenant internals, secrets). Tests in `tests/security/test_allowany_public_endpoints.py` assert that unauthenticated access returns only intended public data.

---

## 3.5. Application Security Hardening (Phase 117A–117B)

### B1: Billing Middleware Fail-Closed

The `SubscriptionStatusMiddleware` returns **HTTP 503** for all mutation requests (POST/PUT/PATCH/DELETE) when a `DatabaseError` or `OperationalError` occurs during subscription/tenant lookup. GET/HEAD/OPTIONS pass through before any DB access. This ensures billing enforcement never silently fails open during database outages.

- **Implementation**: `hub/apps/billing/middleware.py` — catches `(DatabaseError, OperationalError)` → 503 with `service_unavailable` code and `retry_after: 30`.
- **Non-DB errors**: Also return 503 (fail-closed for mutations).

### M3: Cross-Tenant Entitlement Enforcement

All cross-tenant resource access (dataset retrieve, file download, virtual dataset query) is gated by `require_entitlement()` from `hub/apps/marketplace/entitlement_check.py`. Raises `PermissionDenied` with error codes:

- `ENTITLEMENT_REQUIRED` — no entitlement exists
- `ENTITLEMENT_EXPIRED` — entitlement expired
- `ENTITLEMENT_REVOKED` — entitlement revoked

Same-tenant access is always allowed (fast path). See section 5 below for details.

### G1: ABAC Cache Invalidation via Signals

AccessPolicy changes trigger cache invalidation via Django `post_save`/`post_delete` signals. The `abac_cache_version_{tenant_id}` counter is incremented in cache, causing all cached ABAC evaluations for the tenant to be re-evaluated.

- **Implementation**: `hub/apps/governance/signals.py` — `invalidate_policy_cache_on_save/delete`.

### ML-7: Cross-Tenant ML Training Guard

ML training jobs that reference datasets from other tenants require an active marketplace entitlement for the source dataset's asset. The `ODHIntegrationAPI` validates entitlements before submitting cross-tenant training jobs.

### Stripe Circuit Breaker

All Stripe API calls are gated by `StripeCircuitBreaker` (failure_threshold=5, timeout=60s). When OPEN, calls fast-fail with `CircuitBreakerError` without touching Stripe. Prevents cascading failures during Stripe outages.

- **Implementation**: `hub/apps/billing/services.py` — `_stripe_call_with_retry()` wraps via `_get_stripe_circuit_breaker().call()`.

---

## 4. Summary

| Item | Development | Production / Staging |
|------|-------------|----------------------|
| `SECRET_KEY` | Default allowed | MUST set via env; MUST NOT be dev default |
| `JWT_SECRET_KEY` | Default allowed | MUST set via env; MUST NOT be dev default |
| CORS (Django) | Default list or `*` for local | Explicit origins only |
| CORS (Traefik) | `*` acceptable for local | Explicit origins only |
| AllowAny endpoints | See `docs/AUDIT_POLICY.md` | Must not expose sensitive data; tests in `tests/security/test_allowany_public_endpoints.py` |

---

# Security Findings & Risk Acceptance Tracker

> **Single source of truth** for pen-test scope, findings, and risk acceptance.
> Updated: 2026-03-21 | Phase 112.J.1

## Pen Test Scope

Defined in: `InputDocs/Security_Review_and_Pentest_Plan.md`

### In-Scope Components

| Component | Type | Status |
|-----------|------|--------|
| REST API (`/api/v1/`) | API security | CI automated (Bandit SAST) |
| Authentication (JWT, sessions, API keys) | Auth | CI automated + manual tests |
| Multi-tenant isolation | Tenant | Automated tests (`test_integration_isolation.py`) |
| ODPS $ref resolver | Input validation | Pen-test suite (`penetration_test_odps_ref_resolver.py`) |
| File upload (S3/MinIO) | Storage | Automated tests (`test_storage.py`) |
| Webhook delivery (SSRF) | Network | SSRF guard tests (`test_delivery_validators.py`) |
| Frontend (XSS, CSRF) | Client | DOMPurify audit (Phase 112.D.1) |

### Out of Scope

- Internal admin tools (Django admin disabled in production)
- Third-party SaaS integrations (Stripe, AWS, GCP — vendor responsibility)

## Remediation SLAs

| Severity | SLA | Escalation |
|----------|-----|------------|
| Critical | 7 days or block launch | CTO + security lead |
| High | 30 days | Engineering lead |
| Medium | 90 days or risk acceptance | Product owner |
| Low | Normal backlog | Sprint planning |

## CI/CD Security Controls

| Control | Workflow | Status |
|---------|----------|--------|
| Dependency scanning (pip-audit + Safety) | `security-scan.yml` → `dependency-scan` | Active |
| SAST (Bandit) | `security-scan.yml` → `code-scan` | Active |
| Container scanning (Trivy) | `security-scan.yml` → `container-scan` | Active |
| Secret scanning (Gitleaks) | `ci.yml` → `secret-scan` | Active |
| ODPS security scanning | `ci.yml` → `scan-odps-security` | Active |

## Current Findings

| ID | Severity | Component | Finding | Status | Date |
|----|----------|-----------|---------|--------|------|
| — | — | — | No open findings | — | 2026-03-21 |

> All automated scans passing as of 2026-03-21.
> Manual penetration test scheduled per `Security_Review_and_Pentest_Plan.md`
> (annual or on major architectural changes).

## Risk Acceptance Register

| ID | Risk | Accepted By | Date | Review Date | Notes |
|----|------|-------------|------|-------------|-------|
| RA-001 | JWT tokens stored in localStorage (not httpOnly cookies) | Engineering | 2026-03-21 | 2026-06-21 | Standard SPA pattern; refresh token rotation mitigates theft; httpOnly cookies require backend proxy changes |
| RA-002 | pip-audit CI step uses `continue-on-error: true` | Engineering | 2026-03-21 | 2026-06-21 | Non-blocking to avoid CI failures from upstream CVE database lag; findings reviewed weekly |

---

# Tenant isolation (Phase 16)

**Last Updated**: 2026-03-22

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

## 4.5. ABAC Policy Engine (Phase 117C)

### G1: Cache Invalidation via Django Signals

The ABAC policy evaluation cache is invalidated when any `AccessPolicy` object is saved or deleted. Django `post_save` and `post_delete` signals on `AccessPolicy` increment a per-tenant version counter (`abac_cache_version_{tenant_id}`) in the cache backend. All cached ABAC evaluations for that tenant become stale and are re-evaluated on the next request.

- **Signal handler**: `hub/apps/governance/signals.py` — `invalidate_policy_cache_on_save`, `invalidate_policy_cache_on_delete`
- **Cache key pattern**: `abac_eval:{tenant_id}:{policy_version}:{resource_type}:{resource_id}:{user_id}`
- **Invalidation scope**: All policies for the affected tenant (not just the changed policy)

### G2: Field-Level Audit

When data masking is applied (e.g., PII redaction in responses), a `FIELD_MASKING_APPLIED` audit event is emitted. This provides a tamper-evident record of which fields were masked, for which user, and at what time.

- **Audit event**: `resource_type=DATA_MASKING`, `action=FIELD_MASKING_APPLIED`
- **Details**: `{fields_masked: [...], masking_policy: "...", reason: "..."}`

### G3: Access Request Expiration

Access requests have an `expires_at` field (default: 90 days from approval). The `revoke_expired_access` management command revokes expired access requests and their associated entitlements.

- **Model field**: `GovernanceAccessRequest.expires_at` (DateTimeField, nullable)
- **Default**: 90 days from approval timestamp
- **Management command**: `python manage.py revoke_expired_access`
- **SDK methods**: `get_access_request_expiration(request_id)`, `set_access_request_expiration(request_id, expires_at)`

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

## 5.6. Cross-Tenant Entitlement Enforcement (Phase 117B)

### Overview

Cross-tenant resource access is gated by marketplace entitlements. When a user in tenant B attempts to access a resource owned by tenant A, the system checks for an ACTIVE entitlement linking tenant B to the resource's asset via a fulfilled marketplace order.

### Enforcement Points

| Endpoint | View | Guard |
|----------|------|-------|
| `GET /api/v1/datasets/{id}/` | `DatasetViewSet.retrieve()` | `_get_via_entitlement()` fallback on 404 — fetches dataset without tenant filter, calls `require_entitlement()` |
| `GET /api/v1/files/{id}/download/` | `FileViewSet.download()` | `_get_file_via_entitlement()` fallback on 404 — resolves asset via `get_asset_id_from_file()`, calls `require_entitlement()` |
| `POST /api/v1/virtualization/datasets/{id}/queries/` | `VirtualDatasetViewSet.execute_query()` | Cross-tenant fallback checks `get_dataset_for_cross_tenant_check()` + `require_entitlement()` |
| Scheduled ingestion cross-tenant source | N/A | Not yet implemented — ingestion uses external sources (S3/HTTP), not cross-tenant asset references |

### `require_entitlement()` Function

**Location**: `hub/apps/marketplace/entitlement_check.py` (re-exports from `access_utils.py`)

```python
require_entitlement(
    consumer_tenant_id: str,
    asset_id: str,
    provider_tenant_id: Optional[str] = None,
) -> Optional[Entitlement]
```

- **Same-tenant fast path**: If `consumer_tenant_id == provider_tenant_id`, returns `None` (no check needed).
- **Cross-tenant check**: Queries `Entitlement.objects.filter(tenant_id=consumer_tenant_id, asset_id=asset_id)`.
- **Raises `PermissionDenied`** with structured error codes:
  - `ENTITLEMENT_REQUIRED` — no entitlement found
  - `ENTITLEMENT_EXPIRED` — entitlement exists but expired (auto-expires via `is_active()` check)
  - `ENTITLEMENT_REVOKED` — entitlement was explicitly revoked

### Entitlement Lifecycle

1. **Consumer creates order** for a published listing → `OrderStatus.REQUESTED`
2. **FREE_AUTO_APPROVE**: Automatically transitions `REQUESTED → APPROVED → FULFILLED` with entitlement creation
3. **REQUEST_APPROVAL**: Provider manually approves → `approve_order()` creates entitlement + transitions to `FULFILLED`
4. **Entitlement grants access**: `require_entitlement()` succeeds for the consumer tenant + asset combination
5. **Revocation**: Provider can revoke via `EntitlementViewSet.revoke()` → sets `REVOKED` status
6. **Expiration**: Entitlements with `expires_at` in the past auto-expire on next `is_active()` check

### Security Guarantees

- **No entitlement = no access**: Cross-tenant requests without entitlement receive 403.
- **Revocation is immediate**: Revoking an entitlement takes effect on the next request (no cache).
- **Same-tenant is always allowed**: The fast path ensures no performance impact on same-tenant operations.
- **Platform admins bypass**: Admin users (`is_platform_admin=True`) see all resources via the queryset, bypassing entitlement checks.

---

## 6. References

- **Helper**: `hub.apps.tenants.request_tenant.get_request_tenant_id`, `get_request_tenant`
- **Middleware**: `hub.apps.auth.middleware.TenantScopingMiddleware` (sets request.tenant_id / request.tenant)
- **Suspension Middleware**: `hub.apps.tenants.middleware.TenantSuspensionMiddleware` (enforces suspension)
- **Plan Limits**: `hub.apps.tenants.services.PlanLimitService` (enforces plan limits)
- **Tests**: `tests/integration/test_tenant_isolation.py` (no mocks; real DB and auth)
- **Onboarding**: `docs/ONBOARDING.md` (self-service tenant creation)
- **Billing**: `docs/BILLING.md` (plans, limits, subscriptions)

---

# GDPR Erasure (Right to be Forgotten)

**Last Updated**: 2026-03-22

This document describes the data erasure feature (GDPR Article 17 - Right to be Forgotten).

---

## Overview

Users can request deletion or anonymization of their personal data. The platform provides an erasure workflow that handles PII deletion/anonymization while respecting legal and compliance retention requirements.

---

## Requesting Erasure

### User Self-Service

**POST** `/api/v1/users/me/request-erasure/`

Creates an erasure request for the authenticated user.

**Authentication**: Required (user must be authenticated)

**Response**:
```json
{
  "request_id": "uuid",
  "status": "COMPLETED",
  "requested_at": "2026-02-03T12:00:00Z",
  "completed_at": "2026-02-03T12:00:01Z"
}
```

### Platform Admin

**POST** `/api/v1/platform/users/{user_id}/request-erasure/`

Platform admins can create erasure requests for any user.

**Authentication**: Required (platform admin)

---

## Erasure Process

### 1. Request Creation

- Erasure request created with status `PENDING`
- Audit event logged: `ERASURE_REQUESTED`

### 2. Execution

Erasure is executed immediately (or queued for async processing):

1. **User Profile Anonymization**:
   - Email: Anonymized to `deleted-{user_id}@deleted.local`
   - Display name: Set to "Deleted User"
   - Other PII fields: Anonymized or removed

2. **Session Revocation**:
   - All user sessions revoked and deleted
   - User logged out from all devices

3. **API Key Revocation**:
   - All API keys deactivated
   - API access revoked

4. **Audit Event Anonymization**:
   - Actor references anonymized in audit events
   - Email addresses in event details anonymized

### 3. Completion

- Request status set to `COMPLETED`
- Completion timestamp recorded
- Audit event logged: `ERASURE_COMPLETED`

---

## What is Deleted vs Anonymized

### Deleted

- **Sessions**: All user sessions deleted
- **API Keys**: API keys deactivated (soft delete)

### Anonymized

- **User Profile**: Email and display name anonymized
- **Audit Events**: Actor references and email addresses anonymized

### Retained (Retention Exceptions)

Some data may be retained for legal/compliance reasons:

- **Audit Events**: Audit events retained (with anonymized references)
- **Compliance Records**: Compliance-related records may be retained
- **Legal Holds**: Data subject to legal holds retained

**Note**: Retention exceptions are documented in the erasure request record.

---

## Erasure Request Status

Erasure requests can have the following statuses:

- **PENDING**: Request created, waiting to be processed
- **PROCESSING**: Erasure is being executed
- **COMPLETED**: Erasure completed successfully
- **FAILED**: Erasure failed, error message available

---

## Checking Request Status

### User Self-Service

**GET** `/api/v1/users/me/erasure-requests/{request_id}/`

Returns erasure request status and details.

### Platform Admin

**GET** `/api/v1/platform/users/{user_id}/erasure-requests/`

Returns all erasure requests for a user.

---

## Erasure Details

Completed erasure requests include:

- **anonymized_fields**: List of fields that were anonymized
- **deleted_resources**: List of resource types that were deleted
- **retention_exceptions**: List of resources retained due to legal/compliance requirements

**Example Response**:
```json
{
  "request_id": "uuid",
  "status": "COMPLETED",
  "anonymized_fields": ["email", "display_name"],
  "deleted_resources": ["sessions", "api_keys"],
  "retention_exceptions": ["audit_events"],
  "requested_at": "2026-02-03T12:00:00Z",
  "completed_at": "2026-02-03T12:00:01Z"
}
```

---

## Retention Policy

### Audit Events

- **Retention**: Audit events retained for compliance
- **Anonymization**: Actor references anonymized
- **Purpose**: Legal compliance and audit trail

### Compliance Records

- **Retention**: Compliance-related records may be retained
- **Purpose**: Regulatory compliance requirements

### Legal Holds

- **Retention**: Data subject to legal holds retained
- **Purpose**: Legal proceedings and investigations

---

## Timeline

### Request Processing

- **Immediate**: Erasure executed immediately upon request
- **Async option**: In production, erasure may be queued for async processing
- **Completion**: Typically completes within seconds

### Data Removal

- **Immediate**: User profile anonymized immediately
- **Sessions**: Sessions revoked immediately
- **API Keys**: API keys deactivated immediately
- **Audit**: Audit events anonymized immediately

---

## Limitations

### Partial Erasure

- **Tenant data**: User data within tenant context is erased
- **Cross-tenant**: Data shared across tenants may not be fully erased
- **Aggregated data**: Aggregated or derived data may not be erased

### Retention Exceptions

- **Legal requirements**: Data retained for legal compliance
- **Audit trail**: Audit events retained (anonymized)
- **Compliance**: Compliance records may be retained

---

## Privacy and Security

### Access Control

- **User-only**: Users can only request erasure for themselves
- **Platform admin**: Platform admins can request erasure for any user
- **Authenticated**: Authentication required for all erasure operations

### Audit Trail

- **Request logged**: Erasure request logged in audit trail
- **Completion logged**: Erasure completion logged in audit trail
- **Anonymized references**: Audit events use anonymized user references

### Data Protection

- **Secure deletion**: Deleted data securely removed from database
- **Anonymization**: PII anonymized rather than deleted where retention required
- **Encryption**: Data encrypted at rest and in transit

---

## Use Cases

### GDPR Compliance

- **Right to be forgotten**: Users can request deletion of their data
- **Data minimization**: Supports data minimization principles
- **User control**: Users have control over their personal data

### Account Deletion

- **Account closure**: Users can delete their accounts
- **Data cleanup**: Automatic cleanup of user data
- **Privacy**: Ensures user privacy after account deletion

---

## Related Documentation

- `docs/DATA_PORTABILITY.md` - Right to data portability
- `docs/TENANT_ISOLATION.md` - Tenant isolation and data scoping
- GDPR compliance documentation

---

# Data Portability

**Last Updated**: 2026-03-22

This document describes the data portability feature (GDPR Article 20 - Right to Data Portability).

---

## Overview

Users can request a copy of their personal data in a machine-readable format. The platform provides a data export feature that collects user data and provides it as a downloadable archive.

---

## Requesting Data Export

### API Endpoint

**POST** `/api/v1/users/me/export-data/`

Creates a data export job and returns job information.

**Authentication**: Required (user must be authenticated)

**Response**:
```json
{
  "job_id": "uuid",
  "status": "COMPLETED",
  "download_url": "https://...",
  "download_url_expires_at": "2026-02-04T12:00:00Z",
  "created_at": "2026-02-03T12:00:00Z"
}
```

### Job Status

Data export jobs can have the following statuses:

- **PENDING**: Job created, waiting to be processed
- **PROCESSING**: Job is being processed
- **COMPLETED**: Job completed, download URL available
- **FAILED**: Job failed, error message available

### Checking Job Status

**GET** `/api/v1/users/me/export-jobs/{job_id}/`

Returns job status and download URL if completed.

---

## Export Contents

The export archive (ZIP file) contains:

### user_data.json

Main data file containing:

- **user_profile**: User account information (email, display name, status, timestamps)
- **audit_events**: Recent audit events (last 1000) where user was the actor
- **assets**: Assets created by user (metadata only)
- **datasets**: Datasets created by user (metadata only)
- **contracts**: Contracts created by user (metadata only)

### README.txt

Information about the export contents and format.

---

## Data Included

### User Profile

- User ID
- Email address
- Display name
- Account status
- Created/updated timestamps

### Audit Events

- Event ID
- Resource type and ID
- Action performed
- Event details
- Timestamp

### Resources (Metadata Only)

- Asset metadata (name, description, status)
- Dataset metadata (name, description, status)
- Contract metadata (name, status)

**Note**: Actual file contents are not included in the export for privacy and storage reasons. Contact support if you need file contents.

---

## Download URL

### Expiry

Download URLs expire after **24 hours** from generation.

### Access

Download URLs are:
- **Signed**: Cryptographically signed for security
- **Short-lived**: Expire after 24 hours
- **Single-use**: Not intended for multiple downloads (though not enforced)

### Regeneration

If download URL expires, request a new export:

**POST** `/api/v1/users/me/export-data/`

---

## Rate Limiting

- **One export per user**: Only one export job can be in progress at a time
- **Rate limit**: Additional rate limiting may apply (check rate limit headers)

---

## Privacy and Security

### Data Access

- **User-only**: Users can only export their own data
- **Tenant-scoped**: Export only includes data from user's tenant
- **Authenticated**: Authentication required for all export operations

### Data Storage

- **Temporary**: Export archives stored temporarily in S3/MinIO
- **Automatic cleanup**: Old exports may be automatically deleted (retention policy)
- **Secure storage**: Exports stored in private S3 buckets with access controls

### Download Security

- **Signed URLs**: Download URLs are cryptographically signed
- **Expiry**: URLs expire after 24 hours
- **HTTPS**: Downloads use HTTPS (in production)

---

## Limitations

### Metadata Only

- **No file contents**: Actual file contents are not included
- **No sensitive data**: Sensitive data (passwords, API keys) are never included
- **Aggregated data**: Some aggregated or derived data may not be included

### Retention

- **Audit events**: Limited to recent 1000 events
- **Historical data**: Very old data may not be included

### Format

- **JSON format**: Data provided as JSON
- **ZIP archive**: Multiple files packaged as ZIP
- **Machine-readable**: Structured format for easy processing

---

## Use Cases

### GDPR Compliance

- **Right to data portability**: Users can obtain their data in a portable format
- **Data migration**: Users can migrate data to another service
- **Data backup**: Users can create backups of their data

### Data Analysis

- **Personal analytics**: Users can analyze their own usage patterns
- **Data processing**: Users can process their data with external tools

---

## Related Documentation

- `docs/GDPR_ERASURE.md` - Right to be Forgotten (data erasure)
- `docs/TENANT_ISOLATION.md` - Tenant isolation and data scoping
- GDPR compliance documentation

---

# Data Residency

**Last Updated**: 2026-03-22

This document describes the current data residency behavior and roadmap for multi-region support.

---

## Current Behavior

### Single Region Deployment

The platform currently operates in a **single region** deployment model:

- All tenant data is stored in the same cloud region
- The `Tenant.region` field is **informational only** and does not affect data storage location
- All services (API, database, storage, compute) run in the same region
- No cross-region data replication or failover is currently implemented

### Tenant Region Field

The `Tenant.region` field in the Tenant model:

- **Purpose**: Informational field for tracking tenant preferences or compliance requirements
- **Current behavior**: Does not affect where data is stored or processed
- **Future use**: Will be used to determine data storage location in multi-region deployments

**Example**:
```python
tenant = Tenant.objects.create(
    name="EU Customer",
    slug="eu-customer",
    region="eu-west-1"  # Informational only
)
```

---

## Roadmap: Multi-Region Support

### Phase 1: Multi-Region Data Storage (Planned)

**Goal**: Store tenant data in the region specified by `Tenant.region`

**Requirements**:
- Database sharding or replication by region
- S3-compatible storage buckets per region
- Region-aware service routing
- Cross-region data synchronization for federated assets

**Implementation considerations**:
- Tenant region cannot be changed after creation (data migration complexity)
- Platform admin operations may require cross-region access
- Audit logs and compliance data must respect regional requirements

### Phase 2: Regional Failover (Future)

**Goal**: Automatic failover to backup region in case of primary region failure

**Requirements**:
- Cross-region data replication
- Health monitoring and automatic failover
- DNS-based region routing
- Data consistency guarantees

---

## Job Queue Fairness

### Current Implementation

Job queues (django-rq) operate with tenant-aware fairness:

- **Reserved slots**: Each tenant can reserve a minimum number of concurrent job slots
- **Shared slots**: Additional slots are shared across tenants based on demand
- **Per-tenant limits**: Maximum concurrent jobs per tenant enforced via `TenantConfig.max_job_concurrency`

### Configuration

Job queue fairness is configured via:

1. **TenantConfig.max_job_concurrency**: Maximum concurrent running jobs for the tenant
2. **TenantConfig.max_queued_jobs**: Maximum queued jobs for the tenant
3. **Platform defaults**: Applied when tenant-specific config is not set

### Fairness Algorithm

1. Check tenant's reserved slots availability
2. If reserved slots available, allocate job immediately
3. If reserved slots full, check shared pool availability
4. If shared pool available and tenant hasn't exceeded max_job_concurrency, allocate job
5. Otherwise, queue job (up to max_queued_jobs limit)

### Per-Tenant Limits

Per-tenant limits are enforced at:

- **Job creation**: `hub.apps.jobs.utils.check_tenant_job_limits()`
- **Service layer**: `GovernanceService.check_tenant_resource_limits()`
- **Business rules**: Job creation workflows validate limits before queuing

**See also**:
- `docs/SERVICES_ARCHITECTURE.md` - Service architecture and job processing
- `docs/RUNBOOKS.md` - Operational runbooks including job queue management

---

## Compliance Considerations

### GDPR

- **Data location**: Currently all data stored in single region (may not meet GDPR requirements for EU data)
- **Data transfer**: Cross-region data transfers may require additional compliance measures
- **Right to erasure**: Must be implemented per-region when multi-region is deployed

### Regional Compliance

Different regions may have specific compliance requirements:

- **EU**: GDPR requires data to remain in EU
- **US**: Some states require data to remain in-state
- **China**: Data localization requirements

**Current limitation**: Single-region deployment may not meet all regional compliance requirements.

---

## Migration Path

When multi-region support is implemented:

1. **Existing tenants**: Will remain in default region unless explicitly migrated
2. **New tenants**: Can specify region at creation time
3. **Region migration**: Will require data migration and downtime (to be documented separately)

---

## Related Documentation

- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy
- `docs/SERVICES_ARCHITECTURE.md` - Service architecture including job queues
- `docs/RUNBOOKS.md` - Operational runbooks

---

# Data Residency and Retention

This document describes where platform data is stored and the retention/delete policy for audit events, dead letter queue (DLQ), and job history. It supports compliance and operational planning.

## Where data is stored

| Data | Storage | Location / table |
|------|---------|-------------------|
| **Audit events** | PostgreSQL | `audit_events` (hub audit app) |
| **Event bus events** | PostgreSQL | `events` (core app); Redis for pub/sub (ephemeral) |
| **Dead letter queue (event bus)** | PostgreSQL | `dead_letter_queue` (core app) |
| **Scheduled ingestion DLQ** | PostgreSQL | `scheduled_ingestion_dlq` (scheduled_ingestion app) |
| **Webhook delivery status** | PostgreSQL | Webhook app models (e.g. delivery records) |
| **Job records** | PostgreSQL | `jobs_job` (jobs app) — job metadata and status |
| **RQ job payloads / results** | Redis | RQ queues (configurable TTL; see Redis configuration) |
| **Workflow execution state** | PostgreSQL | Orchestration app models |
| **File objects** | MinIO (S3-compatible) | Buckets per tenant/use case |
| **Cache** | Redis | Separate instances for cache, queue, events, channels |

**Region / residency**: Storage is in the same region as the deployment (e.g. Docker Compose or Kubernetes cluster). For multi-region or sovereign-cloud requirements, configure deployment and backing stores accordingly; no automatic cross-region replication is described here.

## Audit events

- **Storage**: PostgreSQL table `audit_events`.
- **Immutability**: Audit events are append-only; updates and deletes are disallowed in application code.
- **Retention**: Managed by the `archive_old_audit_events` management command (`hub.apps.audit.management.commands.archive_old_audit_events`). It identifies events older than a configurable retention window (e.g. `--retention_years`). In the current MVP implementation, the command does not delete events; it reports what would be archived. Production implementation is expected to move old events to cold storage or mark as archived; actual deletion (if ever required by policy) would be a separate, controlled process.
- **Delete policy**: No routine delete in application. Any purge or export-for-deletion would require an explicit, compliance-approved process (future work).

## Dead letter queue (DLQ)

- **Event bus DLQ**: PostgreSQL table `dead_letter_queue`. Failed events after max retries are stored here. No automatic retention or purge is implemented; entries are resolved manually (e.g. via admin or API) or left for review.
- **Scheduled ingestion DLQ**: PostgreSQL table `scheduled_ingestion_dlq`. Failed file ingestions are tracked here; retry and resolve are supported via API. No automatic retention/delete policy is implemented.
- **Future work**: Define and implement retention and purge policy (e.g. age-based archive or delete after resolution) for both DLQs to meet compliance and operational needs.

## Job history

- **Job records**: PostgreSQL table `jobs_job` stores job metadata and status (resource type, resource id, status, timestamps, etc.). There is no automatic retention or purge; history accumulates.
- **RQ**: Redis holds RQ job payloads and results; retention is governed by Redis and RQ configuration (e.g. result TTL). Not covered in this doc; see Redis/RQ documentation.
- **Future work**: Define and implement retention or archival for old job records (e.g. by age or status) if required by compliance or operations.

## Summary

| Area | Current state | Future work |
|------|----------------|-------------|
| Audit events | Stored in PostgreSQL; immutable; archive command exists (no delete in app) | Define cold storage/archival and any purge process |
| Event bus DLQ | Stored in PostgreSQL; no auto retention | Define retention and purge policy |
| Scheduled ingestion DLQ | Stored in PostgreSQL; no auto retention | Define retention and purge policy |
| Job history | Stored in PostgreSQL; no auto retention | Define retention/archival if required |

For compliance-specific requirements (e.g. right to erasure, maximum retention, or geographic residency), extend this document and implement the corresponding retention, archival, and delete procedures.

---

# Audit Policy

**Last Updated**: 2026-03-22

This document defines which operations MUST emit an audit event and lists all public (AllowAny) endpoints for review. It supports Phase 15 — Governance: Audit policy and AllowAny review.

---

## 1. Audit scope (operations that MUST emit an audit event)

The following resource types and actions **MUST** emit an audit event via `hub.apps.audit.utils.create_audit_event` (or the convenience helpers `log_tenant_operation`, `log_user_operation`, `log_auth_operation`). Implementation lives in `hub.apps.audit` and is used across views, services, and workflows.

### 1.1 Tenant operations

| Action | When | Reference |
|--------|------|-----------|
| Tenant create | New tenant created | `hub.apps.tenants` |
| Tenant update | Tenant config/name/slug changed | `hub.apps.tenants` |
| Tenant delete | Tenant deactivated or removed | `hub.apps.tenants` |

### 1.2 User operations

| Action | When | Reference |
|--------|------|-----------|
| User create | New user or invitation accepted | `hub.apps.users.views`, `hub.apps.auth.views` |
| User update | Profile or status changed | `hub.apps.users.views` |
| User delete | User deactivated or removed | `hub.apps.users.views` |

### 1.3 Authentication

| Action | When | Reference |
|--------|------|-----------|
| Login | Successful or failed login | `hub.apps.auth.views` (log_auth_operation) |
| Logout | Token refresh revoked or logout | `hub.apps.auth.views` |
| Password reset request | Request sent | `hub.apps.auth.views` |
| Password reset confirm | Password changed | `hub.apps.auth.views` |
| Accept invitation | User accepts invite | `hub.apps.auth.views` |
| Register | New user registration | `hub.apps.auth.views` |

### 1.4 Contracts

| Action | When | Reference |
|--------|------|-----------|
| Contract create | New contract created | `hub.apps.contracts.views`, `hub.apps.contracts.services` |
| Contract update | Contract terms/status changed | `hub.apps.contracts.views`, `hub.apps.contracts.services` |
| Contract delete | Contract removed or voided | `hub.apps.contracts.views`, `hub.apps.contracts.services` |

### 1.5 Assets

| Action | When | Reference |
|--------|------|-----------|
| Asset create | New asset created | `hub.apps.assets.views` |
| Asset update | Asset metadata/status changed | `hub.apps.assets.views` |
| Asset delete | Asset removed or deactivated | `hub.apps.assets.views` |
| Asset publish | Asset published to marketplace | `hub.apps.marketplace` |

### 1.6 Compliance and DQ

| Action | When | Reference |
|--------|------|-----------|
| Compliance report create/run | Compliance run started or completed | `hub.apps.compliance.views` |
| DQ run create/update | Data quality run | `hub.apps.dq.views` |

### 1.7 Jobs and workflows

| Action | When | Reference |
|--------|------|-----------|
| Job create/cancel | Job submitted or cancelled | `hub.apps.jobs.views`, `hub.apps.jobs.tasks` |
| Workflow step | Key workflow steps (access request, asset creation, etc.) | `hub.apps.orchestration.workflows` |

### 1.8 Governance

| Action | When | Reference |
|--------|------|-----------|
| Access request create/approve/deny | Access request lifecycle | `hub.apps.governance.access_request_views` |
| Retention policy change | Retention rules updated | `hub.apps.governance.retention_views` |

### 1.9 Marketplace and integrations

| Action | When | Reference |
|--------|------|-----------|
| Listing create/update/delete | Marketplace listing changes | `hub.apps.marketplace.views`, `hub.apps.marketplace.services` |
| Integration sync/mapping | Sync or mapping created/updated | `hub.apps.integrations.services` |

#### 1.9.1 Integrations — Connection, sync job, mapping

All integrations mutations go through `MarketplaceIntegrationService` (`hub.apps.integrations.services`), decomposed into focused mixins: `ConnectionServiceMixin`, `SyncServiceMixin`, `MappingServiceMixin`, `DiscoveryServiceMixin`. Views delegate to the service; the service emits audit events. No direct model mutations from views.

| Resource | Action | View → Service path | Audit event |
|----------|--------|---------------------|-------------|
| **Connection** | Create | `MarketplaceConnectionViewSet.create` → `service.create_connection` | `CONNECTION_CREATED` |
| **Connection** | Update | `MarketplaceConnectionViewSet.update` / `partial_update` → `service.update_connection` | `CONNECTION_UPDATED` |
| **Connection** | Delete | `MarketplaceConnectionViewSet.destroy` → `service.delete_connection` | `CONNECTION_DELETED` |
| **Connection** | Test | `MarketplaceConnectionViewSet.test` → `service.test_connection` | `CONNECTION_TESTED` |
| **Sync job** | Create | `MarketplaceSyncJobViewSet.create` → `service.sync_assets_to_marketplace` / `sync_from_marketplace` | `SYNC_JOB_CREATED` |
| **Sync job** | Cancel | `MarketplaceSyncJobViewSet.cancel` → `service.cancel_sync_job` | `SYNC_JOB_CANCELLED` |
| **Mapping** | Create | Sync operations / tasks → `service.create_mapping` | `MAPPING_CREATED` |
| **Mapping** | Update | Programmatic → `service.update_mapping` | `MAPPING_UPDATED` |
| **Mapping** | Delete | `MarketplaceMappingViewSet.destroy` → `service.delete_mapping` | `MAPPING_DELETED` |
| **Scheduled sync** | Create | Programmatic → `service.schedule_sync` | `SCHEDULED_SYNC_CREATED` |
| **Scheduled sync** | Delete | Programmatic → `service.unschedule_sync` | `SCHEDULED_SYNC_DELETED` |

**Trace confirmation (2026-03-07):** All mutation paths verified. No views perform `instance.save()` or `instance.delete()` directly; all delegate to `MarketplaceIntegrationService` methods that call `create_audit_event` before returning. Tests: `hub.apps.integrations.tests.test_services_integration`, `test_mapping_views`, `test_marketplace_framework`, `test_scheduled_sync` (SCHEDULED_SYNC_CREATED, SCHEDULED_SYNC_DELETED).

### 1.10 Platform admin operations

Platform admin operations (tenant suspend/resume, user erasure) are restricted to users with `is_platform_admin=True`. All mutations go through services that emit audit events. No direct model mutations from views.

#### 1.10.1 Tenant suspend/resume, user erasure

| Resource | Action | View → Service path | Audit event |
|----------|--------|---------------------|-------------|
| **Tenant** | Suspend | `PlatformTenantViewSet.suspend` → `TenantLifecycleService.suspend_tenant` | `TENANT_SUSPENDED` |
| **Tenant** | Resume | `PlatformTenantViewSet.resume` → `TenantLifecycleService.resume_tenant` | `TENANT_REACTIVATED` |
| **Erasure request** | Create (platform-initiated) | `PlatformUserViewSet.request_erasure` → `ErasureService.create_request` | `ERASURE_REQUESTED` |
| **Erasure request** | Execute | `PlatformUserViewSet.request_erasure` → `ErasureService.execute_erasure` | `ERASURE_COMPLETED` |

**Trace confirmation (2026-03-07):** (1) **Tenant suspend/resume** — `PlatformTenantViewSet` delegates to `TenantLifecycleService` (`hub.apps.tenants.services`); service emits `TENANT_SUSPENDED` / `TENANT_REACTIVATED` with `actor_user` = platform admin. API: `POST /api/v1/platform/tenants/{id}/suspend/`, `POST /api/v1/platform/tenants/{id}/resume/`. (2) **User erasure** — `PlatformUserViewSet.request_erasure` calls `ErasureService` (`hub.apps.gdpr.services`)(user_id=request.user.id).create_request(user_id=target.id); actor is platform admin; details include `initiated_by` and `source: "platform_admin"`. `execute_erasure` emits `ERASURE_COMPLETED` with `actor_user=None` (system action). API: `POST /api/v1/platform/users/{id}/request-erasure/`. Tests: `hub.apps.platform.tests.test_views` (test_platform_tenant_suspend_creates_audit_event, test_platform_tenant_resume_creates_audit_event, test_platform_request_erasure_audit_actor_is_platform_admin, test_platform_request_erasure_creates_erasure_completed_audit_event), `tests.integration.test_platform_apis_integration`.

### 1.11 Files and datasets

| Action | When | Reference |
|--------|------|-----------|
| File upload/delete | File created or removed | `hub.apps.files.views` |
| Dataset create/update/delete | Dataset lifecycle | `hub.apps.datasets.views`, `hub.apps.datasets.services` |

---

## 2. Audit coverage checklist (code review)

When adding or changing endpoints that **change sensitive data** (tenant, user, contract, asset, compliance, auth, access request, marketplace listing, file, dataset):

- [ ] The code path calls `create_audit_event` (or `log_tenant_operation` / `log_user_operation` / `log_auth_operation`) with appropriate `resource_type`, `action`, and (where applicable) `actor_user`, `tenant`, `resource_id`.
- [ ] PII in `details` is not required to be pre-redacted; `create_audit_event` redacts via `redact_pii`.
- [ ] Critical paths are covered by integration or E2E tests that assert an audit event is created (see `hub.apps.audit.tests` and `tests/e2e/test_audit_logging.py`, `tests/integration/test_*_audit_logging`).

Optional: add a test that critical paths emit audit events for new resources (no mocks; use real DB and `AuditEvent.objects.filter(...).exists()` or equivalent).

---

## 3. AllowAny endpoints (public endpoints)

All views that use `AllowAny` are listed below. For each, we state whether it is intentional and what data is exposed. These endpoints must **not** expose sensitive data (e.g. PII, tenant internals, secrets).

| Location | Endpoint / View | Intentional | Data exposed |
|----------|-----------------|-------------|--------------|
| `hub.apps.auth.views` | `login` (POST) | Yes | Accepts credentials; returns tokens. No user list or PII in response. |
| `hub.apps.auth.views` | `refresh_token` (POST) | Yes | Accepts refresh token; returns new access token. No user list or PII. |
| `hub.apps.auth.views` | `password_reset_request` (POST) | Yes | Accepts email; sends reset link. No user enumeration in response. |
| `hub.apps.auth.views` | `password_reset_confirm` (POST) | Yes | Accepts token + new password. No sensitive data in response. |
| `hub.apps.auth.views` | `accept_invitation` (POST) | Yes | Accepts invitation token; creates/activates user. Response is token or error. |
| `hub.apps.auth.views` | `register` (POST) | Yes | New user registration. Response is token or validation errors. |
| `hub.apps.auth.sso_views` | SSO callback / entry | Yes | SSO flow; redirects and token exchange. No sensitive data exposed. |
| `hub.apps.api.views` | `api_info` (GET /api/v1/) | Yes | Public API name, version, base_url, documentation URLs, endpoint list (paths only). No secrets or PII. |
| `hub.apps.api.views` | `api_not_found` (all methods) | Yes | 404 handler. Returns "Resource not found". No data. |
| `hub.apps.semantic.views` | `get_ontology` (GET) | Yes | Public ontology in Turtle format for interoperability. No tenant or user data. |
| `hub.apps.semantic.views` | `get_jsonld_context` (GET) | Yes | Public JSON-LD context for hub ontology. No tenant or user data. |
| `hub.apps.developer.views` | `PluginViewSet` (list/retrieve) | Yes | Public plugin list and details (name, description, category, status). No secrets or PII. |
| `hub.apps.developer.views` | `SDKDocumentationViewSet` (list/retrieve) | Yes | Public SDK docs (sdk_name, version, documentation, examples). No secrets or PII. |

### 3.1 Review and hardening

- Developer plugin/SDK and semantic public endpoints must **not** expose sensitive data.
- Tests must assert that unauthenticated access to these endpoints returns only intended public data (no user emails, tenant names, tokens, or internal IDs beyond what is required for the public contract). See Phase 15 tests: `tests/security/test_allowany_public_endpoints.py` (or equivalent in `hub.apps.audit.tests`).

---

## 4. References

- **Audit implementation**: `hub.apps.audit` — `models.AuditEvent`, `utils.create_audit_event`, `utils.redact_pii`
- **Governance**: `docs/RUNBOOKS.md`, `docs/DEVELOPMENT_GUIDE.md`
- **Security**: `docs/SECURITY.md` (secrets, CORS)

---

# Tenant Switch — Production Migration and Rollback

Plan for deploying and operating the tenant switch feature (Phase 29.65). Design: [openspec/changes/useronboardfix/design.md](../openspec/changes/useronboardfix/design.md) D16.

## Overview

Tenant switch allows users with multiple tenants (e.g. personal + org via invitation) to switch active tenant context without re-login. The system uses:

- **UserTenantMembership** model: many-to-many user↔tenant
- **X-Tenant-Id** header: stateless override of active tenant
- **GET /auth/me/tenants/**: list tenants the user has membership in
- **POST /auth/switch-tenant/**: validate membership and return updated me summary

## Prerequisites

- PostgreSQL (existing)
- Migrations `0005_add_user_tenant_membership` and `0006_populate_user_tenant_memberships` applied
- No schema changes required beyond these migrations

## Production Migration

### Step 1: Apply migrations

```bash
# From API service container or host with DB access
python hub/manage.py migrate users
```

Verify:

```bash
python hub/manage.py showmigrations users
# 0005_add_user_tenant_membership [X]
# 0006_populate_user_tenant_memberships [X]
```

### Step 2: Deploy backend and frontend

1. Deploy backend with tenant switch views and middleware (already in codebase).
2. Deploy frontend with tenant switcher in Header (already in codebase).
3. Ensure `FEATURE_TENANT_SWITCH_ENABLED` is **True** (default) or unset.

### Step 3: Verify

1. Log in as a user with multiple tenants (invited to at least one org).
2. Confirm tenant switcher appears in header.
3. Switch tenant and verify assets/listings are scoped to the new tenant.
4. Check audit log for `TENANT_SWITCH` events.

## Rollback

### Option A: Feature flag (recommended)

Disable tenant switch without code rollback:

```bash
# In .env or environment
FEATURE_TENANT_SWITCH_ENABLED=false
```

Effects:

- **GET /auth/me/tenants/** returns 403
- **POST /auth/switch-tenant/** returns 403
- **X-Tenant-Id** header is rejected (403) by middleware
- Frontend hides tenant switcher; shows static tenant name instead

Restart API service after changing the env var.

### Option B: Code rollback

If you must revert to a version without tenant switch:

1. Deploy previous backend version (before tenant switch).
2. Deploy previous frontend version.
3. **Data:** UserTenantMembership table and data remain. No automatic cleanup. This is safe; the old code simply ignores the table.

### Option C: Full data rollback (not recommended)

Removing UserTenantMembership data is **not recommended** because:

- Invitation flow may have added memberships; removing them breaks re-invite semantics.
- Migration is idempotent; re-running is safe.
- No performance impact from leaving the table populated.

If you must remove the table:

```sql
-- Only if absolutely necessary; run during maintenance window
DROP TABLE IF EXISTS users_usertenantmembership CASCADE;
```

Then revert migrations (requires custom reverse migration).

## Feature Flag

| Setting | Default | Effect |
|---------|---------|--------|
| `FEATURE_TENANT_SWITCH_ENABLED` | `True` | When `False`: disables GET /auth/me/tenants/, POST /auth/switch-tenant/, and X-Tenant-Id header |

**Environment variable:** `FEATURE_TENANT_SWITCH_ENABLED=true|false`

**Backend:** `hub/settings.py` — `env.bool("FEATURE_TENANT_SWITCH_ENABLED", default=True)`

**Frontend:** GET /auth/me/ returns `feature_tenant_switch_enabled`; Header hides switcher when false.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 403 on GET /auth/me/tenants/ | Feature disabled or user not authenticated | Set `FEATURE_TENANT_SWITCH_ENABLED=true`; ensure valid JWT/session |
| 403 on POST /auth/switch-tenant/ | Feature disabled or user has no membership in target tenant | Enable feature; verify UserTenantMembership exists for (user, tenant) |
| 403 with X-Tenant-Id header | Feature disabled or invalid membership | Enable feature; ensure user was invited to target tenant |
| Tenant switcher not visible | `feature_tenant_switch_enabled=false` in /auth/me/ | Set `FEATURE_TENANT_SWITCH_ENABLED=true` |
| Empty tenant list | User has no UserTenantMembership rows | Run migration 0006; or invite user to a tenant |

## Runbook

See [docs/runbooks/TENANT_SWITCH.md](runbooks/TENANT_SWITCH.md) for operational procedures and troubleshooting. Index: [RUNBOOKS.md](RUNBOOKS.md).

## References

- Design D16: [openspec/changes/useronboardfix/design.md](../openspec/changes/useronboardfix/design.md)
- Tasks: [openspec/changes/useronboardfix/tasks.md](../openspec/changes/useronboardfix/tasks.md) §29.65
