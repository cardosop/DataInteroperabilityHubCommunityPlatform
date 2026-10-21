# JOURNEY-DPO-010: Publish Asset with Usage-Based Pricing

**Journey ID**: JOURNEY-DPO-010  
**Title**: Publish Asset with Usage-Based Pricing  
**Persona**: Data Product Owner  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-010-publish-asset-with-usage-based-pricing-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] ACTIVE asset to publish
- [ ] Usage-based pricing capability enabled

---

## What You Will Do

Publish asset with usage-based pricing (per-query, per-GB). Configure tiers and rates.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to publish | Go to **Marketplace** → **Publish**. Select asset. | Publish form | ☐ |
| 2 | Select usage-based pricing | Choose pricing model: **Usage-based**. | Model selected | ☐ |
| 3 | Configure tiers | Set per-query or per-GB rates. | Tiers configured | ☐ |
| 4 | Set billing | Configure billing period, limits. | Billing configured | ☐ |
| 5 | Create listing | Submit. | Listing created with usage-based pricing | ☐ |

---

## Success Criteria

- Usage-based pricing selectable
- Tiers configured
- Listing published

---

## Note

If usage-based pricing is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-010.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
