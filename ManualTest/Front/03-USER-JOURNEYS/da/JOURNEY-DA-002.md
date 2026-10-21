# JOURNEY-DA-002: Wrangle Data Interactively

**Journey ID**: JOURNEY-DA-002  
**Title**: Wrangle Data Interactively  
**Persona**: Data Analyst  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-da-002-wrangle-data-interactively)

---

## Prerequisites

- [ ] Logged in as **Data Analyst** (e2e_consumer@example.com / TestPass123)
- [ ] Data wrangling/virtualization capability enabled
- [ ] At least one dataset or virtual dataset

---

## What You Will Do

Interactively explore and transform data using the wrangling UI (if available).

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to data | Go to **Virtualization** or **Data** (sidebar). | Data/virtualization page | ☐ |
| 2 | Select dataset | Choose a dataset or virtual dataset. | Dataset loaded | ☐ |
| 3 | Explore schema | View columns, types, sample. | Schema visible | ☐ |
| 4 | Apply transforms (if available) | Filter, rename, derive columns. | Transforms applied | ☐ |
| 5 | Preview result | View transformed output. | Preview displayed | ☐ |

---

## Success Criteria

- Data exploration accessible
- Transforms work (if available)
- Preview updates

---

## Note

If wrangling UI is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/da/JOURNEY-DA-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
