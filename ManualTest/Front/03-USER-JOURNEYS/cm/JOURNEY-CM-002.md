# JOURNEY-CM-002: Moderate Reviews and Ratings

**Journey ID**: JOURNEY-CM-002  
**Title**: Moderate Reviews and Ratings  
**Persona**: Community Manager  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cm-002-moderate-reviews-and-ratings)

---

## Prerequisites

- [ ] Logged in as **Community Manager** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Reviews exist (from Data Consumer)
- [ ] Moderation permission

---

## What You Will Do

View pending reviews. Approve or reject. Publish approved reviews.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to moderation | Go to **Social** → **Moderation** or **Reviews** → **Moderate**. | Moderation page | ☐ |
| 2 | View pending | Browse pending reviews. | Pending listed | ☐ |
| 3 | Approve | Approve a review. | Review published | ☐ |
| 4 | Reject | Reject a review (if applicable). | Review rejected | ☐ |
| 5 | Verify | Approved review visible on asset. | Visibility correct | ☐ |

---

## Success Criteria

- Moderation accessible
- Approve/reject works
- Published correctly

---

## Note

If moderation is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cm/JOURNEY-CM-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
