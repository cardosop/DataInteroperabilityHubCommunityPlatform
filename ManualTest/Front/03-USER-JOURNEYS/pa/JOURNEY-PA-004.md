# JOURNEY-PA-004: Review Platform Analytics

**Journey ID**: JOURNEY-PA-004  
**Title**: Review Platform Analytics  
**Persona**: Platform Admin  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)

---

## What You Will Do

View platform-wide analytics. Tenants, usage, marketplace metrics.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to analytics | Go to **Admin** → **Analytics**. | Analytics page | ☐ |
| 2 | View dashboard | Check tenant count, usage, marketplace. | Metrics displayed | ☐ |
| 3 | Filter | Change date range or filter. | Filter works | ☐ |

---

## Success Criteria

- Analytics accessible
- Metrics displayed

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
