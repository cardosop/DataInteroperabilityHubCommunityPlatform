# JOURNEY-DC-003: Search and Filter Assets

**Journey ID**: JOURNEY-DC-003  
**Title**: Search and Filter Assets  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] At least one asset in catalog (run DPO-001 or use existing)

---

## What You Will Do

Use search and filters to find relevant assets in the catalog or marketplace.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to catalog | Go to **Marketplace** or **Assets** (sidebar). | List page loads | ☐ |
| 2 | Enter search term | Type in search box (e.g. asset name, domain, tag). | Results update or search executes | ☐ |
| 3 | Apply filters | Use filters (domain, status, tags, etc.) if available. | Filtered results displayed | ☐ |
| 4 | Clear filters | Reset or clear filters. | Full list restored | ☐ |

---

## Success Criteria

- Search returns relevant results
- Filters work correctly
- Results update as expected

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
