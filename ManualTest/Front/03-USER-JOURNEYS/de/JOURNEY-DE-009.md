# JOURNEY-DE-009: Set Up Data Virtualization

**Journey ID**: JOURNEY-DE-009  
**Title**: Set Up Data Virtualization  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-009-set-up-data-virtualization-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Virtualization capability enabled
- [ ] At least one data source

---

## What You Will Do

Define virtual dataset. Configure sources. Set up query mapping. Test queries.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to virtualization | Go to **Virtualization** (sidebar). | Virtualization page | ☐ |
| 2 | Create virtual dataset | Click **Create Virtual Dataset**. | Create form | ☐ |
| 3 | Configure sources | Add source systems (tables, APIs). | Sources configured | ☐ |
| 4 | Set query mapping | Define joins, mappings. | Mapping configured | ☐ |
| 5 | Test query | Run sample query. | Results returned | ☐ |
| 6 | Deploy | Save. | Virtual dataset active | ☐ |

---

## Success Criteria

- Virtual dataset created
- Sources configured
- Query works

---

## Note

If virtualization is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-009.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
