# JOURNEY-TA-004: Review Tenant Analytics

**Journey ID**: JOURNEY-TA-004  
**Title**: Review Tenant Analytics  
**Persona**: Tenant Admin  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)

---

## What You Will Do

View tenant analytics dashboard. Review usage, assets, users.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to analytics | Go to **Admin** → **Analytics** or **Observability**. | Analytics page | ☐ |
| 2 | View dashboard | Check usage, asset count, user count. | Metrics displayed | ☐ |
| 3 | Filter/date range | Change date range if available. | Filter works | ☐ |

---

## Success Criteria

- Analytics accessible
- Metrics displayed

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
