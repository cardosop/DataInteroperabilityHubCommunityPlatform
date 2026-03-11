# JOURNEY-PA-006: Monitor Marketplace Health

**Journey ID**: JOURNEY-PA-006  
**Title**: Monitor Marketplace Health  
**Persona**: Platform Admin  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)

---

## What You Will Do

View marketplace health dashboard. Listings, orders, errors.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace health | Go to **Admin** → **Marketplace** → **Health**. | Health page | ☐ |
| 2 | View metrics | Check listings, orders, errors. | Metrics displayed | ☐ |
| 3 | Drill down | Open error or order detail if needed. | Detail accessible | ☐ |

---

## Success Criteria

- Health dashboard accessible
- Metrics visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
