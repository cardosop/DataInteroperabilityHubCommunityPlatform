# JOURNEY-DEV-005: Use Natural Language Search API

**Journey ID**: JOURNEY-DEV-005  
**Title**: Use Natural Language Search API  
**Persona**: External Developer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dev-005-use-natural-language-search-api-new)

---

## Prerequisites

- [ ] API credentials
- [ ] Natural language search API enabled

---

## What You Will Do

Call NL search API. Pass query. Verify results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Find API endpoint | Check OpenAPI for NL search endpoint. | Endpoint identified | ☐ |
| 2 | Call API | `POST /api/v1/search/nl/` or equivalent with query. | 200 OK | ☐ |
| 3 | Verify response | Check results. | Results returned | ☐ |

---

## Success Criteria

- API call succeeds
- Results returned

---

## Note

If NL search API is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
