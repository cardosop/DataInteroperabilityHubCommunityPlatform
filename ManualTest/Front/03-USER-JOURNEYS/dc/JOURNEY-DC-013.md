# JOURNEY-DC-013: Use Asset Recommendations

**Journey ID**: JOURNEY-DC-013  
**Title**: Use Asset Recommendations  
**Persona**: Data Consumer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-013-use-asset-recommendations-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Recommendation engine enabled

---

## What You Will Do

View recommended assets. Browse recommendations. Click through to asset.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace/home | Go to **Marketplace** or **Home**. | Page loads | ☐ |
| 2 | View recommendations | Find "Recommended for you" or similar section. | Recommendations displayed | ☐ |
| 3 | Browse | Scroll through recommendations. | List visible | ☐ |
| 4 | Click asset | Open recommended asset. | Asset detail loads | ☐ |

---

## Success Criteria

- Recommendations visible
- Relevant to user/context
- Click-through works

---

## Note

If recommendations are not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-013.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
