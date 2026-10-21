# JOURNEY-DPO-004: Monitor Asset Quality

**Journey ID**: JOURNEY-DPO-004  
**Title**: Monitor Asset Quality  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one asset with DQ runs (run JOURNEY-DPO-001 or DQ first)

---

## What You Will Do

View data quality runs, metrics, and results for asset(s). Monitor quality trends.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to DQ | Go to **DQ** or **Data Quality** (sidebar). | DQ page loads | ☐ |
| 2 | View runs list | Browse DQ runs. Filter by asset if available. | Runs displayed | ☐ |
| 3 | Open run detail | Click a run. | Run detail: status, metrics, pass/fail | ☐ |
| 4 | View from asset | Go to asset detail → **Quality** or **DQ** section. | DQ metrics/runs visible | ☐ |
| 5 | Start new run (if available) | Trigger DQ run from asset or DQ page. | Run starts | ☐ |

---

## Success Criteria

- DQ runs visible
- Run details accessible
- New run can be triggered (if UI supports)

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
