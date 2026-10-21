# JOURNEY-DE-001: Programmatic Contract-First Onboarding

**Journey ID**: JOURNEY-DE-001  
**Title**: Programmatic Contract-First Onboarding  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-001-programmatic-contract-first-onboarding)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Support material: `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json`

---

## What You Will Do

Onboard an asset via contract-first flow: create contract (ODPS) first, then attach dataset and create/activate asset. Uses UI (ODPS upload) or API.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Create contract | Go to **Contracts** → **Create Contract** (→ ODPS upload). Paste `odps-with-embedded-odcs.json` or upload file. Click **Create ODPS Product**. | ODPS + ODCS contracts created; workflow completes | ☐ |
| 2 | Verify contract | Open contract detail. Check normalization (NORMALIZED_OK), validation (VALID). | Contract valid and normalized | ☐ |
| 3 | Create asset | Go to **Assets** → **Create Asset**. Fill key, name, description. Submit. | Asset created (DRAFT) | ☐ |
| 4 | Link contract to asset | From contract detail or asset detail, link the contract to the asset. Or create ODPS with Asset ID in upload form. | Contract linked to asset | ☐ |
| 5 | Attach dataset | Create dataset from file (`05-SUPPORT-MATERIAL/data/sample-upload.csv`) and link to asset. | Dataset linked; schema aligned with contract | ☐ |
| 6 | Activate asset | Change asset status from DRAFT to ACTIVE. | Asset status = ACTIVE | ☐ |

---

## Success Criteria

- Contract created and validated
- Asset created
- Contract linked to asset
- Dataset attached
- Asset activated

---

## API Alternative

Use `POST /api/v1/contracts/products/` with ODPS JSON, then `POST /api/v1/assets/`, link via asset_id in contract creation or update.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
