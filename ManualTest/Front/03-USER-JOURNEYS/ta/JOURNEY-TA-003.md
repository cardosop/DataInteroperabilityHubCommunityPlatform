# JOURNEY-TA-003: Configure Tenant Settings

**Journey ID**: JOURNEY-TA-003  
**Title**: Configure Tenant Settings  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)

---

## What You Will Do

View and update tenant settings. Configure defaults, limits, features.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to settings | Go to **Admin** → **Settings** or **Tenant Settings**. | Settings page | ☐ |
| 2 | View current settings | Browse tenant name, defaults, limits. | Settings displayed | ☐ |
| 3 | Edit setting | Change a setting (e.g. default role, limit). | Change accepted | ☐ |
| 4 | Save | Submit. | Settings saved | ☐ |
| 5 | Verify | Refresh. Confirm change persisted. | Change persisted | ☐ |

---

## Success Criteria

- Settings accessible
- Edit works
- Changes persist

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
