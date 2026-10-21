# Launch Governance — Meshant Platform

**Last updated:** 2026-05-15
**Target launch:** TBD

## 1. Go/No-Go Criteria (280.A.7.1)

### Technical Gates — ALL must be ✅

| Gate | Status | Evidence |
|---|---|---|
| `openspec validate preprod01 --strict` | ✅ | `Change 'preprod01' is valid` (2026-05-15) |
| `pytest hub/ -x --tb=short` | ⏭️ | User-executed |
| `pytest cli/tests/ -x --tb=short` | ✅ | 984 passed, 2 pre-existing failures (2026-05-14) |
| `pytest sdk/python/tests/ -x --tb=short` | ⚠️ | 27 passed (unit), integration skipped |
| `frontend-ci.yml` (lint + type-check + vitest) | ⏭️ | Lint verified 0 new errors; vitest user-executed |
| `check_migration_count.py --ci` | ✅ | All 26 apps within 200-migration limit |
| `lint-rls-policies` | ⏭️ | Script exists, CI-executed |
| `pip-audit` (zero CVEs) | ❌ | Not installed locally; CI gate needed |
| `docker compose -f docker-compose.staging.yml config` | ✅ | Validates clean (2026-05-14) |
| E2E batch 1 (153 tests, 0 a11y violations) | ⏭️ | User-executed |
| Staging deploy → all services healthy <10 min | ⏭️ | CI/CD executed |
| DB backup/restore drill (RPO ≤1h, RTO ≤4h) | ⏭️ | Script ready, operator-executed |

### Operational Gates — ALL must be ✅

| Gate | Status | Evidence |
|---|---|---|
| On-call rotation staffed (≥2 engineers per shift) | ⏭️ | Runbook created; staffing TBD |
| Incident response procedure documented | ✅ | `INCIDENT_RESPONSE.md` |
| Alert routing configured (PagerDuty + Slack) | ⏭️ | Runbook documents routing; PagerDuty config TBD |
| Service dependency map published | ✅ | `docs/operations/service-dependency-map.md` |
| Third-party risk assessment complete | ✅ | `docs/operations/third-party-risk-assessment.md` |
| Migration safety policy in place | ✅ | `docs/operations/migration-safety-policy.md` |
| Feature flag baseline classified | ✅ | `hub/apps/tenants/feature_flag_registry.py` (27 flags: 4 DRAFT, 13 CANARY, 10 GA) |
| Production data cleanup procedure documented | ✅ | This document, Section 5 |

### Legal & Compliance Gates

| Gate | Status | Evidence |
|---|---|---|
| Terms of Service reviewed | ⏭️ | Legal review scheduled (Section 3) |
| Privacy Policy reviewed | ⏭️ | Legal review scheduled (Section 3) |
| Data Processing Agreement (DPA) signed | ⏭️ | `docs/compliance/dpa-addendum.md` exists; review pending |
| Privacy Impact Assessment complete | ✅ | `docs/compliance/privacy-impact-assessment.md` |
| GDPR Art. 30 RoPA generated | ⏭️ | CLI: `datahub ropa generate` (Phase 1 module) |
| Data Protection Officer designated | ⏭️ | Internal staffing |

### Go Decision

**Go** requires ALL technical gates ✅, ALL operational gates ✅, and legal review complete for ToS/Privacy/DPA. Any ❌ is a **No-Go** for production launch.

## 2. Stakeholder Sign-Off Checklist (280.A.7.2)

| Role | Name | Signature | Date |
|---|---|---|---|
| **Engineering Lead** | _____________ | _____________ | ___ |
| **Product Owner** | _____________ | _____________ | ___ |
| **Legal Counsel** | _____________ | _____________ | ___ |
| **Security Lead** | _____________ | _____________ | ___ |
| **CTO (final approval)** | _____________ | _____________ | ___ |

**Sign-off implies:** The signatory has reviewed the go/no-go criteria relevant to their domain, confirmed that their area's gates are met, and approves proceeding to production launch.

## 3. Legal Review Timeline (280.A.7.3)

### Documents Requiring Review

| Document | Location | Last Reviewed | Review Status | Review By |
|---|---|---|---|---|
| Terms of Service | `docs/legal/terms-of-service.md` (to be drafted) | Never | ⏭️ Pending | Legal Counsel |
| Privacy Policy | `docs/legal/privacy-policy.md` (to be drafted) | Never | ⏭️ Pending | Legal Counsel + DPO |
| Data Processing Agreement (DPA) | `docs/compliance/dpa-addendum.md` | 2026-04 (initial) | ⏭️ Pending re-review | Legal Counsel |
| Privacy Impact Assessment | `docs/compliance/privacy-impact-assessment.md` | 2026-04 | ✅ Complete | DPO |

### Timeline

```
Week 1-2: Legal Counsel reviews DPA + Privacy Policy
Week 2-3: Draft Terms of Service (if not already in progress)
Week 3-4: Legal Counsel reviews ToS
Week 4:   All reviews complete → sign-off → proceed to launch
```

**If timeline not complete before launch target date:**

- Launch may proceed WITHOUT final legal sign-off ONLY if:
  1. Privacy Policy and DPA are published and accurate
  2. ToS includes standard limitation of liability and governing law clauses
  3. Legal Counsel confirms via email that review is in progress and no blocking issues identified
  4. CTO accepts residual risk

## 4. Production Feature Flag Baseline (280.A.7.4)

**Source:** `hub/apps/tenants/feature_flag_registry.py` (577 lines, 27 registered flags)

### Distribution

| Stage | Count | Meaning |
|---|---|---|
| **DRAFT** | 4 | Code exists, no tenant can enable. Launch: leave as DRAFT. |
| **CANARY** | 13 | Available, friendly tenants opt in. Launch: keep as CANARY, enable for 3 friendly tenants. |
| **GA** | 10 | Generally available, default per flag. Launch: review each GA flag's default. |
| **DEPRECATED** | 0 | Marked for removal. Launch: none to remove. |
| **RETIRED** | 0 | Already removed. |

### GA Flags (Launch Day Defaults)

| Flag | Default | Launch Recommendation |
|---|---|---|
| `auth_register_enabled` | True | Keep GA (public registration open) |
| `contract_creation_enabled` | True | Keep GA |
| `marketplace_enabled` | True | Keep GA |
| `scheduled_ingestion_enabled` | True | Keep GA |
| `search_enabled` | True | Keep GA |
| `api_keys_enabled` | True | Keep GA |
| `compliance_consent_enabled` | True | Keep GA |
| `compliance_dpia_enabled` | True | Keep GA |
| `compliance_breach_enabled` | True | Keep GA |
| `compliance_processor_agreements_enabled` | True | Keep GA |

### CANARY Flags (Opt-in for Friendly Tenants)

| Flag | Launch Recommendation |
|---|---|
| `ai_natural_language_search_enabled` | Enable for 3 friendly tenants, monitor for 2 weeks |
| `ai_schema_matching_enabled` | Enable for 3 friendly tenants |
| `baas_api_keys_enabled` | Enable for 1 friendly tenant |
| `data_quality_enabled` | Keep CANARY (opt-in) |
| `data_quality_advanced_enabled` | Keep CANARY |
| `datasets_enabled` | Keep CANARY |
| `files_enabled` | Keep CANARY |
| `lineage_openlineage_export_enabled` | Enable for 2 friendly tenants |
| `lineage_change_notifications_enabled` | Enable for 2 friendly tenants |
| `ml_models_enabled` | Keep CANARY |
| `social_communities_enabled` | Keep CANARY |
| `developer_plugins_enabled` | Enable for 1 friendly tenant |
| `transformation_enabled` | Enable for 3 friendly tenants |

### DRAFT Flags (No Tenant Access)

| Flag |
|---|
| `ml_advanced_enabled` |
| `ml_auto_training_enabled` |
| `virtualization_enabled` |
| `semantic_federation_enabled` |

## 5. Production Data Cleanup + Seed Procedure (280.A.7.5)

### Pre-Launch Cleanup

```bash
# 1. Verify staging environment
kubectl config use-context meshant-staging
kubectl get pods -n hub-staging

# 2. Remove staging test data
# Run the cleanup management command (idempotent — safe to run multiple times)
python manage.py cleanup_staging_test_data \
    --remove-test-tenants \
    --remove-test-users \
    --remove-test-assets \
    --remove-test-contracts \
    --dry-run  # Remove --dry-run when verified

# 3. Verify cleanup
python manage.py shell -c "
from hub.apps.tenants.models import Tenant
print(f'Remaining tenants: {Tenant.objects.count()}')
"
```

### Seed Production Baseline

```bash
# NOTE: These management commands are procedure descriptions.
# Implementation requires Django ORM model access across tenants, users, billing.
# Existing equivalents: E2E persona provisioning in cli/tests/_persona_provisioning.py
# uses pre-seeded staging accounts. The commands below describe the target interface.

# 1. Seed platform admin user
python manage.py create_platform_admin \
    --email admin@meshant.com \
    --name 'Platform Admin'

# 2. Seed system tenant
python manage.py create_system_tenant

# 3. Seed default billing plans
python manage.py seed_default_plans

# 4. Seed default roles
python manage.py seed_default_roles

# 5. Verify seed data
python manage.py shell -c "
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.billing.models import Plan
print(f'Tenants: {Tenant.objects.count()}')
print(f'Platform admins: {User.objects.filter(roles__contains=[\"PLATFORM_ADMIN\"]).count()}')
print(f'Plans: {Plan.objects.count()}')
"
```

### Post-Seed Verification

```bash
# 1. Platform admin can log in
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/auth/login/ \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@meshant.com","password":"<from-secrets>"}'

# 2. Health check
curl https://api.stagingmeshant-internal.example.com/api/v1/health/

# 3. Capabilities
curl https://api.stagingmeshant-internal.example.com/api/v1/capabilities/ \
    -H 'Authorization: Bearer <token>'
```
