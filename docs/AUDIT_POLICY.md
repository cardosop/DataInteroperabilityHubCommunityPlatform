# Audit Policy

**Last Updated**: 2026-01-29

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

### 1.10 Files and datasets

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
