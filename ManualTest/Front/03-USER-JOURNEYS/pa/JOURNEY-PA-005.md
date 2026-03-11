# JOURNEY-PA-005: Manage Marketplace Configuration

**Journey ID**: JOURNEY-PA-005  
**Title**: Manage Marketplace Configuration  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)

---

## What You Will Do

Configure marketplace settings. Set defaults, fees, approval workflow.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace admin | Go to **Admin** → **Marketplace**. | Marketplace config | ☐ |
| 2 | View config | Browse marketplace settings. | Config displayed | ☐ |
| 3 | Edit | Change fee, approval flow, etc. Save. | Change saved | ☐ |
| 4 | Verify | Config persisted. | Persisted | ☐ |

---

## Success Criteria

- Config accessible
- Edit works
- Changes persist

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
