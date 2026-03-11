# JOURNEY-AUD-006: Review Social Feature Activity

**Journey ID**: JOURNEY-AUD-006  
**Title**: Review Social Feature Activity  
**Persona**: Auditor  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-aud-006-review-social-feature-activity-new)

---

## Prerequisites

- [ ] Logged in as **Auditor** (e2e_auditor@example.com / TestPass123)
- [ ] Social features enabled (ratings, reviews, communities)

---

## What You Will Do

View audit of social feature activity. Ratings, reviews, community actions.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to social audit | Go to **Audit** → **Social** or **Social** → **Audit**. | Social audit page | ☐ |
| 2 | View activity | Browse ratings, reviews, community actions. | Activity displayed | ☐ |
| 3 | Filter | Filter by user, asset, date. | Filter works | ☐ |

---

## Success Criteria

- Social audit accessible
- Activity visible

---

## Note

If social audit is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/aud/JOURNEY-AUD-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
