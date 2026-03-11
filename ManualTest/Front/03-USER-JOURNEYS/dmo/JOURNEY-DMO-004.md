# JOURNEY-DMO-004: Transfer Asset Ownership

**Journey ID**: JOURNEY-DMO-004  
**Title**: Transfer Asset Ownership  
**Persona**: Data Mesh Domain Owner  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dmo-004-transfer-asset-ownership)

---

## Prerequisites

- [ ] Logged in as **Data Mesh Domain Owner** (e2e_dmo@example.com / TestPass123)
- [ ] At least one asset in domain
- [ ] Transfer permission

---

## What You Will Do

Transfer asset ownership to another user or domain. Verify transfer.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select asset in domain. | Asset detail | ☐ |
| 2 | Open ownership | Find **Transfer Ownership** or **Ownership**. | Transfer UI | ☐ |
| 3 | Select new owner | Choose user or domain. | New owner selected | ☐ |
| 4 | Transfer | Confirm transfer. | Ownership transferred | ☐ |
| 5 | Verify | New owner has asset. | Transfer complete | ☐ |

---

## Success Criteria

- Transfer works
- Ownership updated
- New owner has access

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dmo/JOURNEY-DMO-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
