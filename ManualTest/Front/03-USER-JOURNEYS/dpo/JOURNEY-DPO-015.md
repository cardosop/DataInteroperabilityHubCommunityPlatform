# JOURNEY-DPO-015: Create ODPS Product (Product-First Flow)

**Journey ID**: JOURNEY-DPO-015  
**Title**: Create ODPS Product (Product-First Flow)  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-015-create-odps-product-product-first-flow-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] Support material: `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json`

---

## What You Will Do

Create an ODPS product with an embedded ODCS contract using the product-first flow. The system will parse the ODPS document, extract the ODCS from `product.contract.spec`, create both contracts, and link them bidirectionally.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to ODPS upload | Go to **ODPS** (sidebar) → **Create ODPS Product**, or **Contracts** → **Create Contract** (redirects to ODPS upload). | Page at `/odps/upload` with ODPS content textarea and file upload | ☐ |
| 2 | Provide ODPS document | Copy content from `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json` and paste into the textarea. Or use **Select File** to upload. Ensure **Format** = JSON. | Content loaded; format JSON | ☐ |
| 3 | Optional: Link to asset | Use **AssetPicker** (searchable dropdown) to select target asset. Search by name/key or browse assets. | Asset selected and displayed | ☐ |
| 4 | Submit | Click **Create ODPS Product**. | Workflow starts; progress bar/status shown | ☐ |
| 5 | Wait for completion | Workflow runs: parse ODPS → validate → extract ODCS → create ODCS contract → create ODPS contract → link. | Status = COMPLETED; success message | ☐ |
| 6 | Verify ODPS contract | Redirect to ODPS detail page. Verify: product details, schema, marketplace section. | ODPS contract displayed | ☐ |
| 7 | Verify ODCS contract | From workflow result or ODPS detail, open the linked ODCS contract. Verify: schema fields, owners, normalization status. | ODCS contract displayed; link bidirectional | ☐ |

---

## Success Criteria

- ODPS document uploaded and parsed successfully
- ODCS contract extracted from `product.contract.spec`
- ODCS contract created
- ODPS contract created
- ODPS ↔ ODCS link established (both directions)
- Redirect to ODPS or contract detail

---

## ODPS Document Requirements

The ODPS document must include:

- `schema`: `https://opendataproducts.org/schema/v4.1`
- `version`: `4.1`
- `product.details.en`: productID, name, description
- `product.contract.spec`: Inline ODCS contract with `apiVersion`, `kind`, `id`, `name`, `schema.fields`

---

## Traceability

- **Use Case**: UC-ODPS-001 (Product-first flow)
- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-015.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
