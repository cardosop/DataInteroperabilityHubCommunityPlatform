# JOURNEY-DE-003: Configure Data Quality Checks

**Journey ID**: JOURNEY-DE-003  
**Title**: Configure Data Quality Checks  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] At least one asset or dataset with schema

---

## What You Will Do

Configure data quality checks for an asset or dataset. Run DQ checks and review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to DQ | Go to **DQ** or **Data Quality** (sidebar). | DQ page loads | ☐ |
| 2 | Select asset/dataset | Use **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading) in create-run modal. | Asset/dataset selected | ☐ |
| 3 | Configure rules | Add or edit quality rules (completeness, validity, etc.) if UI supports. | Rules configured | ☐ |
| 4 | Run DQ check | Start a DQ run. | Run starts; status updates | ☐ |
| 5 | Review results | Open run detail. View pass/fail, metrics. | Results displayed | ☐ |

---

## Success Criteria

- DQ section accessible
- DQ run executes
- Results visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
