# JOURNEY-DC-012: Preview Data Before Purchase

**Journey ID**: JOURNEY-DC-012  
**Title**: Preview Data Before Purchase  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-012-preview-data-before-purchase-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Marketplace listing with preview enabled

---

## What You Will Do

Request data preview on listing. Review sample data. Decide to purchase.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to listing | Go to **Marketplace** → select listing. | Listing detail | ☐ |
| 2 | Request preview | Click **Preview** or **Sample Data**. | Preview requested | ☐ |
| 3 | View sample | Review sample rows/columns. | Sample data displayed | ☐ |
| 4 | Purchase (optional) | Purchase if satisfied. | Purchase works | ☐ |

---

## Success Criteria

- Preview accessible
- Sample data visible
- Purchase decision supported

---

## Note

If preview is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-012.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
