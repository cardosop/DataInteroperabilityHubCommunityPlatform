# JOURNEY-DA-003: Query Virtual Dataset

**Journey ID**: JOURNEY-DA-003  
**Title**: Query Virtual Dataset  
**Persona**: Data Analyst  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-da-003-query-virtual-dataset)

---

## Prerequisites

- [ ] Logged in as **Data Analyst** (e2e_consumer@example.com / TestPass123)
- [ ] Virtualization capability enabled
- [ ] At least one virtual dataset

---

## What You Will Do

Select a virtual dataset, build/execute a query, and review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to virtualization | Go to **Virtualization** (sidebar). | Virtualization page | ☐ |
| 2 | Select virtual dataset | Choose a virtual dataset from list. | Dataset selected | ☐ |
| 3 | Build query | Use SQL editor or visual builder. Enter query. | Query built | ☐ |
| 4 | Execute | Run query. | Results returned | ☐ |
| 5 | Export (if available) | Export results to CSV/JSON. | File downloaded | ☐ |

---

## Success Criteria

- Virtual dataset selectable
- Query executes
- Results displayed

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/da/JOURNEY-DA-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
