# JOURNEY-DS-005: Review Auto-Classification Results

**Journey ID**: JOURNEY-DS-005  
**Title**: Review Auto-Classification Results  
**Persona**: Data Scientist  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ds-005-review-auto-classification-results)

---

## Prerequisites

- [ ] Logged in as **Data Scientist** (e2e_test@example.com or e2e_consumer@example.com / TestPass123)
- [ ] Auto-classification runs exist

---

## What You Will Do

View auto-classification results. Review confidence. Approve/reject. Update rules.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to classification | Go to **AI** → **Classification** or **Compliance** → **Classification**. | Classification page | ☐ |
| 2 | View results | Browse classification results. | Results displayed | ☐ |
| 3 | Review confidence | Check confidence scores. | Scores visible | ☐ |
| 4 | Approve/reject | Approve or reject classifications. | Decisions recorded | ☐ |
| 5 | Update rules | Modify rules if needed. | Rules updated | ☐ |

---

## Success Criteria

- Results visible
- Approve/reject works
- Rules updatable

---

## Note

If auto-classification is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ds/JOURNEY-DS-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
