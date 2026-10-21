# JOURNEY-DC-004: Access Entitlement

**Journey ID**: JOURNEY-DC-004  
**Title**: Access Entitlement  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] At least one purchased entitlement (from JOURNEY-DC-001 or DC-015)

---

## What You Will Do

View entitlements. Access purchased asset. Download or query data.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to entitlements | Go to **Entitlements** or **My Data** or **Orders**. | Entitlements list | ☐ |
| 2 | View entitlement | Click an entitlement. | Entitlement detail: asset, access type | ☐ |
| 3 | Access data | Click **Access** or **Download** or open asset. | Data accessible | ☐ |
| 4 | Verify access | Confirm data or API access works. | Access works | ☐ |

---

## Success Criteria

- Entitlements visible
- Data accessible
- Access type correct

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
