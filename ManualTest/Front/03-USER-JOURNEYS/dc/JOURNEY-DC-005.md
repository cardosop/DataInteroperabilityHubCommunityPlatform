# JOURNEY-DC-005: Download Data

**Journey ID**: JOURNEY-DC-005  
**Title**: Download Data  
**Persona**: Data Consumer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Entitlement to asset with download access

---

## What You Will Do

Download data from purchased asset. Select format. Verify download.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Entitlements** → select asset. Or **Marketplace** → purchased asset. | Asset/entitlement detail | ☐ |
| 2 | Click Download | Find **Download** button. Click it. | Download options or file | ☐ |
| 3 | Select format | Choose format (CSV, JSON, etc.) if offered. | Format selected | ☐ |
| 4 | Download | File downloads. | File received | ☐ |
| 5 | Verify | Open file. Verify content. | Content valid | ☐ |

---

## Success Criteria

- Download works
- File received
- Content valid

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
