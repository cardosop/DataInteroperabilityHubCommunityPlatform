# JOURNEY-DC-010: Query Virtual Dataset

**Journey ID**: JOURNEY-DC-010  
**Title**: Query Virtual Dataset  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-010-query-virtual-dataset-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Virtualization capability enabled
- [ ] At least one virtual dataset

---

## What You Will Do

Select virtual dataset. Build query. Execute. Export results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to virtualization | Go to **Virtualization** (sidebar). | Virtualization page | ☐ |
| 2 | Select virtual dataset | Choose a virtual dataset. | Dataset selected | ☐ |
| 3 | Build query | Use SQL editor or visual builder. | Query built | ☐ |
| 4 | Execute | Run query. | Results returned | ☐ |
| 5 | Export | Export results (CSV, JSON). | File downloaded | ☐ |

---

## Success Criteria

- Virtual dataset selectable
- Query executes
- Results displayed and exportable

---

## Note

If virtualization is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-010.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
