# JOURNEY-DPO-006: Manage Marketplace Listings

**Journey ID**: JOURNEY-DPO-006  
**Title**: Manage Marketplace Listings  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one published listing (from JOURNEY-DPO-002)

---

## What You Will Do

View, edit, unpublish, or manage marketplace listings for owned assets.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace | Go to **Marketplace** → **Listings** or **My Listings**. | Listings page | ☐ |
| 2 | View listing | Click a listing. | Listing detail: title, description, pricing, status | ☐ |
| 3 | Edit listing | Click **Edit**. Update title, description, or pricing. Save. | Changes saved | ☐ |
| 4 | Unpublish (if available) | Change status from PUBLISHED to DRAFT. | Listing unpublished | ☐ |
| 5 | Re-publish | Set status back to PUBLISHED. | Listing published | ☐ |

---

## Success Criteria

- Listings visible
- Edit works
- Status changes (publish/unpublish) work

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
