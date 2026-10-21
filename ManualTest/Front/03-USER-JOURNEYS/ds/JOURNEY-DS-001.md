# JOURNEY-DS-001: Use Natural Language Search

**Journey ID**: JOURNEY-DS-001  
**Title**: Use Natural Language Search  
**Persona**: Data Scientist  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ds-001-use-natural-language-search)

---

## Prerequisites

- [ ] Logged in as **Data Scientist** (e2e_test@example.com or e2e_consumer@example.com / TestPass123)
- [ ] Natural language search capability enabled (if deployment supports it)

---

## What You Will Do

Enter a natural language query to discover data. Review interpretation and results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to search | Go to **Search** or **AI Search** (if available). | Search page loads | ☐ |
| 2 | Enter NL query | Type e.g. "customer data from last quarter" or "sales by region". | Query accepted | ☐ |
| 3 | Execute | Submit or run query. | Interpretation and/or results shown | ☐ |
| 4 | Review results | Check returned assets or data. | Relevant results | ☐ |

---

## Success Criteria

- NL search accessible
- Query executed
- Results returned (or clear message if capability disabled)

---

## Note

If NL search is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ds/JOURNEY-DS-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
