# JOURNEY-DC-014: Discover ODPS Products (Semantic Search)

**Journey ID**: JOURNEY-DC-014  
**Title**: Discover ODPS Products (Semantic Search)  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-014-discover-odps-products-semantic-search-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Semantic search capability enabled
- [ ] ODPS products in catalog

---

## What You Will Do

Use semantic search to discover ODPS products. Enter query. Review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to search | Go to **Search** or **Semantic Search**. | Search page | ☐ |
| 2 | Enter semantic query | Type conceptual query (e.g. "customer analytics"). | Query accepted | ☐ |
| 3 | Execute | Submit. | ODPS products returned | ☐ |
| 4 | Review results | Browse results. Check relevance. | Results relevant | ☐ |
| 5 | Open product | Click ODPS product. | Product detail | ☐ |

---

## Success Criteria

- Semantic search works
- ODPS products returned
- Results relevant

---

## Note

If semantic search is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-014.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
