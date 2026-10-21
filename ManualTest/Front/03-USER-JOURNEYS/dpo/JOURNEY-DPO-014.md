# JOURNEY-DPO-014: Monitor Asset Reliability Score

**Journey ID**: JOURNEY-DPO-014  
**Title**: Monitor Asset Reliability Score  
**Persona**: Data Product Owner  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-014-monitor-asset-reliability-score-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one asset with reliability metrics

---

## What You Will Do

View reliability score dashboard. Review score breakdown (quality, freshness, compliance). Identify issues.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select asset. | Asset detail | ☐ |
| 2 | Open reliability dashboard | Find **Reliability** or **Reliability Score** section. | Dashboard visible | ☐ |
| 3 | View score | Check overall reliability score. | Score displayed | ☐ |
| 4 | View breakdown | Check quality, freshness, compliance components. | Breakdown visible | ☐ |
| 5 | Identify issues | Review any issues affecting score. | Issues listed | ☐ |

---

## Success Criteria

- Reliability score displayed
- Score breakdown visible
- Issues identifiable

---

## Note

If reliability score is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-014.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
