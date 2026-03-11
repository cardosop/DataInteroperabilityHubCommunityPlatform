# JOURNEY-DC-002: Browse Catalog

**Journey ID**: JOURNEY-DC-002  
**Title**: Browse Catalog  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)

---

## What You Will Do

Browse the data catalog or marketplace to discover available assets.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to catalog/marketplace | Go to **Marketplace** or **Catalog** (sidebar). | Catalog/marketplace page loads | ☐ |
| 2 | Browse listings | Scroll or paginate through listings. | Listings displayed with name, description, status | ☐ |
| 3 | View listing detail | Click a listing. | Detail page with schema, pricing, metadata | ☐ |
| 4 | Return to list | Navigate back. | List view restored | ☐ |

---

## Success Criteria

- Catalog/marketplace accessible
- Listings displayed
- Detail view works

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
