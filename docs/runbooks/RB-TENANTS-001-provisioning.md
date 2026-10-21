# RB-TENANTS-001 — Tenant Provisioning & Configuration

**Date:** 2026-05-20
**Feature flags:** 35 GA + 1 CANARY + 0 DRAFT (see CLAUDE.md § Feature Flag State)
**Audit event:** `TENANT_CREATED`, `TENANT_CONFIG_CHANGED`, `TENANT_FEATURE_FLAG_CHANGED`, `TENANT_DEACTIVATED`

## 1. Overview

Operational procedure for tenant lifecycle — provisioning, configuration,
feature flag management, plan assignment, and deactivation. Covers the
tenant provisioning pipeline (Phase 271), feature flag audit trail
(Phase 235.1 two-person rule), and tenant offboarding.

## 2. When This Runbook Fires

- **New tenant provisioning request** — sales or self-serve signup.
- **Prometheus alert `TenantProvisioningFailed`** — provisioning pipeline fails.
- **Feature flag change** — any `TENANT_FEATURE_FLAG_CHANGED` audit event
  for a sensitive flag.
- **Plan change request** — tenant requests upgrade/downgrade.
- **Tenant deactivation** — offboarding or suspension.

## 3. Scope

1. **Provisioning** — tenant creation with default plan, licensed regulations,
   feature flags, initial admin user, and Stripe customer.
2. **Feature flag management** — 35 GA flags (17 default-on, 18 opt-in), 1 CANARY.
   Sensitive flags require two-person approval (Phase 235.1).
3. **Plan assignment** — FREE/STARTER/GROWTH/PRO/SCALE/ENTERPRISE tiers;
   ML_AI plans are independent. Plan changes >$1,000/mo require two-person
   approval (285.13.9.3).
4. **Configuration** — `Tenant.settings_json`, rate limits, webhook config,
   licensed regulation keys.
5. **Deactivation** — tenant offboarding with data export window and
   retention-gated deletion.
6. **Feature flag runbook references** — every GA flag has a runbook reference
   at `docs/runbooks/RB-FLAG-NNN-<slug>.md` or a cross-reference in its
   parent system runbook.

## 4. Provisioning Procedure

### 4.1 — Manual provisioning

```bash
python manage.py provision_tenant \
  --name "Acme Corp" \
  --slug "acme-corp" \
  --admin-email "admin@acme.com" \
  --plan "starter" \
  --regulations "GDPR,UK_GDPR"
```

### 4.2 — Verify provisioning

```sql
SELECT id, name, slug, status, plan_id,
       licensed_regulation_keys, created_at
FROM tenants_tenant
WHERE slug = 'acme-corp';
```

### 4.3 — Post-provisioning checklist

- [ ] Tenant status is ACTIVE
- [ ] Default feature flags are set (17 default-on GA flags active)
- [ ] Licensed regulations match the plan's `includes_regulations`
- [ ] Stripe customer created (for paid plans)
- [ ] Initial admin user can log in
- [ ] Tenant appears in admin tenant list

## 5. Feature Flag Operations

### 5.1 — List all flags for a tenant

```
GET /api/v1/admin/tenants/{id}/feature-flags/
```

### 5.2 — Change a non-sensitive flag

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/feature-flags/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"semantic_search_enabled": true, "reason": "Tenant request per CS ticket #1234"}'
```

### 5.3 — Change a sensitive flag (two-person rule)

Sensitive flags: `compliance_fail_closed_enabled`,
`allow_intake_on_compliance_degraded`, `compliance_audit_full_sampling`,
`compliance_intake_gate_enabled`.

1. First PLATFORM_ADMIN creates a flip request:
   `POST /api/v1/admin/feature-flag-approvals/`
2. Second PLATFORM_ADMIN approves:
   `POST /api/v1/admin/feature-flag-approvals/{id}/approve/`

### 5.4 — Verify flag state

```sql
SELECT tenant_id, is_enabled, updated_at, updated_by
FROM feature_flag_approval
WHERE flag_name = '<flag-name>'
ORDER BY updated_at DESC LIMIT 5;
```

## 6. Plan Assignment

### 6.1 — Assign a plan

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"plan_id": "<new-plan-uuid>"}'
```

### 6.2 — Validate plan limits

```bash
python manage.py validate_plan_config --tenant <tenant-slug>
```

## 7. Deactivation Procedure

### 7.1 — Pre-deactivation checklist

- [ ] Notify tenant 30 days in advance
- [ ] Export tenant data if requested
- [ ] Cancel active Stripe subscriptions
- [ ] Revoke API keys
- [ ] Unschedule all ingestions/exports

### 7.2 — Deactivate

```bash
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/deactivate/ \
  -H "Authorization: Bearer $TOKEN"
```

### 7.3 — Post-deactivation

- [ ] Tenant status is INACTIVE
- [ ] All subscriptions cancelled
- [ ] API keys revoked
- [ ] Webhooks disabled
- [ ] Data retained per retention policy

## 8. Forensic Queries

```python
# python manage.py shell
from hub.apps.tenants.models import Tenant, TenantStatus

# Active tenants by plan tier
from django.db.models import Count
by_tier = Tenant.objects.filter(
    status=TenantStatus.ACTIVE,
).values("plan__tier").annotate(count=Count("id"))
for row in by_tier:
    print(f"{row['plan__tier']}: {row['count']}")

# Recent provisioning failures (last 7d)
from hub.apps.audit.models import AuditEvent
recent = AuditEvent.objects.filter(
    action="TENANT_PROVISIONING_FAILED",
    timestamp__gte=timezone.now() - timedelta(days=7),
).count()
print(f"Provisioning failures (7d): {recent}")
```

## 9. Feature Flag Runbook Cross-References

Every GA flag has a runbook reference:

| Flag | Runbook |
|---|---|
| `asset_creation_enabled` | `RB-ASSETS-001`, `asset-creation.md` |
| `data_quality_enabled` / `_advanced` | `RB-DQ-001`, `RB-FLAG-005-data-quality.md` |
| `compliance_fail_closed_enabled` | `RB-COMP-001-compliance-fail-closed.md` |
| `compliance_consent_enabled` | `RB-COMP-002-consent.md` |
| `compliance_dsar_enabled` | `RB-GDPR-001-data-request-failure.md` |
| `compliance_ropa_enabled` | `phase232-ropa.md` |
| `compliance_breach_enabled` | `phase232-breach.md` |
| `datasets_enabled` | `RB-DATASETS-001` |
| `files_enabled` | `RB-FILES-001-file-upload-failure.md` |
| `trust_signals_enabled` | `RB-FLAG-001-trust-signals.md` |
| `versioning_enabled` | `RB-FLAG-006-versioning.md` |
| `workflows_enabled` | `RB-FLAG-002-workflows.md` |
| `compliance_dpia_enabled` | `RB-COMP-005-dpia.md` |
| `compliance_processor_agreements_enabled` | `RB-FLAG-007-processor-agreements.md` |
| `compliance_retention_enforcer_enabled` | `RB-FLAG-008-retention-enforcer.md` |
| `compliance_audit_full_sampling` | `RB-FLAG-003-audit-full-sampling.md` |
| `federated_import_enabled` | `RB-COMP-006-federated-import.md` |
| `semantic_search_enabled` | `RB-SEM-001-graphql-ld.md` |
| `ml_enabled` | `RB-ML-001-odh-connectivity-failure.md` |
| `transformation_enabled` | `RB-TRANS-001-dbt-execution-failure.md` |
| `data_mesh_enabled` | `RB-MESH-001-domain-conflict.md` |

## 10. Related

- **Spec**: `openspec/changes/preprod01/specs/tenants/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 271 (Tenants)
- **Code**:
  - `hub/apps/tenants/models.py` — `Tenant`, `TenantPlan`, `FeatureFlagApproval`
  - `hub/apps/tenants/views.py` — admin ViewSets
  - `hub/apps/tenants/management/commands/provision_tenant.py`
- **Alerts**: `monitoring/prometheus/alerts.yml`
- **Dashboard**: `monitoring/grafana/dashboards/auth-tenancy.json`
- **Cross-runbook**:
  - [`RB-AUTH-001-rls-kill-switch.md`](RB-AUTH-001-rls-kill-switch.md)
  - [`tenant-offboarding.md`](tenant-offboarding.md)
  - [`admin-tenant-deactivation.md`](admin-tenant-deactivation.md)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
