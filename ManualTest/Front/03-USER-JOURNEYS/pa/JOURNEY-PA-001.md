# JOURNEY-PA-001: Onboard New Tenant

**Journey ID**: JOURNEY-PA-001  
**Title**: Onboard New Tenant  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 20 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-pa-001-onboard-new-tenant)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] Multi-tenant backend configured
- [ ] Platform admin UI available (`/admin` or equivalent)

---

## What You Will Do

Create a new tenant organization. Configure settings, complete KYC if required, and activate the tenant.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to tenant management | Go to **Admin** → **Tenants** (platform admin section). | Tenant list loads | ☐ |
| 2 | Create tenant | Click **Create Tenant** or **Add Tenant**. | Create form | ☐ |
| 3 | Enter tenant details | Name, slug, contact email, etc. | Form accepts input | ☐ |
| 4 | Configure settings | Set default roles, limits, features if available. | Settings saved | ☐ |
| 5 | KYC/verification (if required) | Complete any verification steps. | Verification recorded | ☐ |
| 6 | Activate tenant | Set status to ACTIVE. Save. | Tenant active | ☐ |

---

## Success Criteria

- Tenant created
- Settings configured
- Tenant activated

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-PA-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
