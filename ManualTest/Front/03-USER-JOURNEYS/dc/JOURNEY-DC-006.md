# JOURNEY-DC-006: Use Natural Language Search

**Journey ID**: JOURNEY-DC-006  
**Title**: Use Natural Language Search  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-006-use-natural-language-search-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Natural language search capability enabled

---

## What You Will Do

Enter natural language query. Review interpretation. Execute. Refine if needed.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to search | Go to **Search** or **AI Search**. | Search page | ☐ |
| 2 | Enter NL query | Type e.g. "customer data from last quarter". | Query accepted | ☐ |
| 3 | Execute | Submit. | Interpretation and/or results shown | ☐ |
| 4 | Review results | Check returned assets. | Relevant results | ☐ |
| 5 | Refine | Modify query if needed. | Refinement works | ☐ |

---

## Success Criteria

- NL search works
- Results returned
- Refinement works

---

## Note

If NL search is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
