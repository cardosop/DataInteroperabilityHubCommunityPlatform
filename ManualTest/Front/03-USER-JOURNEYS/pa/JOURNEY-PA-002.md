# JOURNEY-PA-002: Manage Tenant Lifecycle

**Journey ID**: JOURNEY-PA-002  
**Title**: Manage Tenant Lifecycle  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] At least one tenant

---

## What You Will Do

View tenants. Change tenant status (active, suspended). Manage lifecycle.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to tenants | Go to **Admin** → **Tenants**. | Tenant list | ☐ |
| 2 | View tenant | Click a tenant. | Tenant detail | ☐ |
| 3 | Change status | Suspend or activate tenant. | Status changed | ☐ |
| 4 | Verify | Tenant status reflects in list. | Status persisted | ☐ |

---

## Success Criteria

- Tenants visible
- Status change works
- Lifecycle manageable

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
