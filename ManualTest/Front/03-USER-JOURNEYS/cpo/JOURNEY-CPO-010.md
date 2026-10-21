# JOURNEY-CPO-010: Review AI Auto-Classification Results

**Journey ID**: JOURNEY-CPO-010  
**Title**: Review AI Auto-Classification Results  
**Persona**: Compliance Officer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-010-review-ai-auto-classification-results-new)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] AI auto-classification capability enabled
- [ ] Classification runs exist

---

## What You Will Do

View classification dashboard. Review results and confidence. Approve/reject. Update rules.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to classification | Go to **Compliance** → **Classification** or **AI Classification**. | Classification dashboard | ☐ |
| 2 | View results | Browse classification results. | Results displayed | ☐ |
| 3 | Review confidence | Check confidence scores. | Scores visible | ☐ |
| 4 | Approve/reject | Approve or reject classifications. | Decisions recorded | ☐ |
| 5 | Update rules | Modify classification rules if needed. | Rules updated | ☐ |

---

## Success Criteria

- Results visible
- Approve/reject works
- Rules updatable

---

## Note

If AI auto-classification is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-010.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
