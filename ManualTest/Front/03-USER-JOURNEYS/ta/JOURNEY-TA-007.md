# JOURNEY-TA-007: Monitor Cost Tracking

**Journey ID**: JOURNEY-TA-007  
**Title**: Monitor Cost Tracking  
**Persona**: Tenant Admin  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ta-007-monitor-cost-tracking-new)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)
- [ ] Cost tracking capability enabled

---

## What You Will Do

View cost dashboard. Analyze costs by asset/domain. Review recommendations.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to cost | Go to **Settings** (user menu) → **Cost tracking** or visit `/settings/cost`. | Cost page | ☐ |
| 2 | View dashboard | Check cost breakdown. | Costs displayed | ☐ |
| 3 | Analyze by asset | Filter by asset or domain. | Breakdown visible | ☐ |
| 4 | Review recommendations | Check optimization recommendations. | Recommendations shown | ☐ |

---

## Success Criteria

- Costs displayed
- Breakdown visible
- Recommendations (if available)

---

## Note

Cost tracking is implemented (Phase 18). Route: `/settings/cost`. Requires TENANT_ADMIN or PLATFORM_ADMIN.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-007.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
