# JOURNEY-DC-011: Purchase Asset with Usage-Based Pricing

**Journey ID**: JOURNEY-DC-011  
**Title**: Purchase Asset with Usage-Based Pricing  
**Persona**: Data Consumer  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-011-purchase-asset-with-usage-based-pricing-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Asset with usage-based pricing in marketplace

---

## What You Will Do

Select asset with usage-based pricing. Review pricing model. Purchase. Use asset. Monitor usage.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Find asset | Browse marketplace for asset with usage-based pricing. | Asset found | ☐ |
| 2 | Review pricing | Check per-query, per-GB rates. | Pricing visible | ☐ |
| 3 | Purchase | Click **Purchase** or **Subscribe**. | Purchase completed | ☐ |
| 4 | Use asset | Run queries or downloads. | Usage tracked | ☐ |
| 5 | Monitor usage | View usage/billing dashboard. | Usage visible | ☐ |

---

## Success Criteria

- Purchase completed
- Usage tracked
- Billing visible

---

## Note

If usage-based pricing is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-011.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
