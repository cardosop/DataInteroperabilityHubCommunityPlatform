# JOURNEY-TA-002: Manage User Roles

**Journey ID**: JOURNEY-TA-002  
**Title**: Manage User Roles  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)
- [ ] At least one user in tenant (besides self)

---

## What You Will Do

View users, change roles, and verify role updates.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to users | Go to **Admin** → **Users** (or equivalent). | User list loads | ☐ |
| 2 | Select user | Click a user to edit or open role dropdown. | User detail or edit form | ☐ |
| 3 | Change role | Add/remove role (e.g. DATA_PROVIDER, DATA_CONSUMER). Save. | Role updated; success message | ☐ |
| 4 | Verify | Refresh or re-open user. | New role reflected | ☐ |

---

## Success Criteria

- User list accessible
- Role change succeeds
- Updated role visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
