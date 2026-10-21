# JOURNEY-PA-003: Configure Platform Settings

**Journey ID**: JOURNEY-PA-003  
**Title**: Configure Platform Settings  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)

---

## What You Will Do

View and update platform-wide settings. Configure defaults, features, limits.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to platform settings | Go to **Admin** → **Platform Settings**. | Settings page | ☐ |
| 2 | View settings | Browse platform config. | Settings displayed | ☐ |
| 3 | Edit | Change a setting. Save. | Change saved | ☐ |
| 4 | Verify | Refresh. Confirm persisted. | Persisted | ☐ |

---

## Success Criteria

- Settings accessible
- Edit works
- Changes persist

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
