# JOURNEY-DPO-009: Manage Asset Ratings and Reviews

**Journey ID**: JOURNEY-DPO-009  
**Title**: Manage Asset Ratings and Reviews  
**Persona**: Data Product Owner  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-009-manage-asset-ratings-and-reviews-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one asset with ratings/reviews (or social feature enabled)

---

## What You Will Do

View ratings and reviews for owned assets. Respond to reviews, moderate if permitted.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select owned asset. | Asset detail | ☐ |
| 2 | Open ratings section | Find **Ratings** or **Reviews** section. | Ratings and reviews displayed | ☐ |
| 3 | View ratings | Check star rating (1-5). | Rating visible | ☐ |
| 4 | Read reviews | Browse review text. | Reviews visible | ☐ |
| 5 | Respond (if available) | Reply to a review. | Response posted | ☐ |
| 6 | Moderate (if permitted) | Approve/reject or moderate review. | Moderation works | ☐ |

---

## Success Criteria

- Ratings and reviews visible
- Response works (if available)
- Moderation works (if permitted)

---

## Note

If social/ratings feature is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-009.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
