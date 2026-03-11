# JOURNEY-DPO-005: Configure Data Contracts

**Journey ID**: JOURNEY-DPO-005  
**Title**: Configure Data Contracts  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-005-configure-data-contracts)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] Support material: `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json`, `odcs-minimal.json`, `odps-invalid-missing-schema.json`

---

## What You Will Do

Create contracts via ODPS upload (product-first flow). The UI uses **Contracts → Create Contract** which navigates to **ODPS Upload**. You will create valid contracts (JSON and optionally YAML) and verify error handling with an invalid contract.

---

## Steps

### Part A: Create Valid Contract (ODPS with Embedded ODCS)

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Open contract creation | Go to **Contracts** (sidebar) → click **Create Contract**. | Navigate to `/odps/upload` (Create ODPS Product page) | ☐ |
| 2 | Paste ODPS content | Copy content from `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json` and paste into the **ODPS Content** textarea. Or use **Select File** to upload the file. | Content appears in textarea; Format = JSON | ☐ |
| 3 | Submit | Click **Create ODPS Product**. | Workflow runs; progress shown. On success: ODPS and ODCS contracts created, redirect to ODPS or contract detail | ☐ |
| 4 | Verify contract | On contract/ODPS detail page, verify: normalization status (NORMALIZED_OK), validation status (VALID), schema fields visible. | Contract details displayed correctly | ☐ |

### Part B: Create Contract with YAML (Optional)

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 5 | Use YAML | Create an ODPS document in YAML format (or use a sample from `tests/fixtures/odps/`). Set Format to **YAML**. Paste/upload and submit. | Contract created; format stored as YAML | ☐ |

### Part C: Error Handling (Invalid Contract)

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 6 | Submit invalid contract | Use `05-SUPPORT-MATERIAL/contracts/odps-invalid-missing-schema.json`. Paste or upload. This ODPS has `product.contract.spec` without `schema.fields`. | Error displayed (400 Bad Request or validation error). No contract created | ☐ |

---

## Success Criteria

- Valid ODPS contract (with embedded ODCS) created successfully
- Normalization status = NORMALIZED_OK
- Validation status = VALID
- Invalid input produces clear error message

---

## Contract Types to Test

| Contract Type | File | Purpose |
|---------------|------|---------|
| ODPS + embedded ODCS | `odps-with-embedded-odcs.json` | Product-first flow; creates ODPS + ODCS |
| ODCS minimal (JSON) | `odcs-minimal.json` | Use inside ODPS `product.contract.spec` if testing ODCS-only |
| Invalid ODPS | `odps-invalid-missing-schema.json` | Error handling (UI) |

**Note**: The UI creates contracts via ODPS upload. Use ODPS documents (with `product.contract.spec`) for both valid and invalid tests.

---

## Traceability

- **Use Case**: UC-DPO-005 (Contract configuration)
- **E2E Spec**: `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
