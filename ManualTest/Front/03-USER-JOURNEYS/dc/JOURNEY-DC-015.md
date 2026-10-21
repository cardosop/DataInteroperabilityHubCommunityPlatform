# JOURNEY-DC-015: Purchase ODPS Product (Marketplace)

**Journey ID**: JOURNEY-DC-015  
**Title**: Purchase ODPS Product (Marketplace)  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-015-purchase-odps-product-marketplace-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] ODPS product published to marketplace (from DPO flows)

---

## What You Will Do

Discover ODPS product in marketplace. View details. Purchase. Access data.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to marketplace | Go to **Marketplace**. | Marketplace page | ☐ |
| 2 | Find ODPS product | Search or browse for ODPS product. | ODPS product found | ☐ |
| 3 | View details | Open product. Check schema, pricing, contract. | Details visible | ☐ |
| 4 | Purchase | Click **Purchase** or **Subscribe**. Complete checkout. | Purchase completed | ☐ |
| 5 | Access | Access entitlement. Download or query. | Data accessible | ☐ |

---

## Success Criteria

- ODPS product discoverable
- Purchase completed
- Data accessible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-015.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
