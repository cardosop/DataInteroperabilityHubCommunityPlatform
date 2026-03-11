# JOURNEY-DC-001: Discover and Purchase Marketplace Asset

**Journey ID**: JOURNEY-DC-001  
**Title**: Discover and Purchase Marketplace Asset  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-001-discover-and-purchase-marketplace-asset)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] At least one asset published to marketplace (run DPO-001 + DPO-002 first, or use existing listing)

---

## What You Will Do

Discover a data asset in the marketplace, view details, review pricing, and complete a purchase. Then access or download the data.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace | Go to **Marketplace** (sidebar). | Marketplace page loads; listings visible | ☐ |
| 2 | Search or browse | Use search bar or browse listings. Optionally use natural language search if available. | Listings displayed; search works | ☐ |
| 3 | View asset details | Click a listing. | Listing detail page: description, schema, pricing | ☐ |
| 4 | Preview data (if available) | Click "Preview" or "Sample data" if shown. | Sample data or preview displayed | ☐ |
| 5 | Review pricing | Check pricing model (free, subscription, one-time). | Pricing visible and clear | ☐ |
| 6 | Purchase asset | Click **Purchase** or **Subscribe**. Complete any checkout flow. | Purchase completed; entitlement created | ☐ |
| 7 | Access data | Navigate to **Entitlements** or **My Data**; open the purchased asset. | Data accessible (download or API) | ☐ |

---

## Success Criteria

- Asset discovered in marketplace
- Asset details and pricing visible
- Purchase completed
- Data accessible after purchase

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| No listings | Empty state or message | ☐ |
| Purchase fails (e.g. no subscription) | Clear error message | ☐ |
| Already purchased | Message or redirect to access | ☐ |

---

## Traceability

- **Use Case**: UC-DC-001
- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
