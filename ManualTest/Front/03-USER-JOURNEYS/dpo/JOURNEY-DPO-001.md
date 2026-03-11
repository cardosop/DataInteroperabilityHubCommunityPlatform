# JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Journey ID**: JOURNEY-DPO-001  
**Title**: Onboard New Asset via Data-First Flow  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 20 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-001-onboard-new-asset-via-data-first-flow)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] Test stack running (frontend http://localhost:3010, API http://localhost:8001)
- [ ] Support material ready: `05-SUPPORT-MATERIAL/data/sample-upload.csv`, `05-SUPPORT-MATERIAL/contracts/odcs-minimal.json`

---

## What You Will Do

Turn a data file into a validated, quality-checked, compliant data product. You will create an asset, upload a file, create a dataset (schema inference), run compliance and DQ checks, create a contract, and activate the asset.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Create asset (draft) | Go to **Assets** (sidebar) → **Create Asset**. Fill: Key `manual-test-asset-001`, Name `Manual Test Asset`, Description `Data-first flow test`. Submit. | Asset created, status **DRAFT**, redirect to asset detail page | ☐ |
| 2 | Upload file | Go to **Datasets** → **Create Dataset**. Click **Select File** and choose `05-SUPPORT-MATERIAL/data/sample-upload.csv`. Optionally use **AssetPicker** (Link to Asset) to select asset from step 1. | File uploaded; success message shows file name and size | ☐ |
| 3 | Create dataset | Click **Create Dataset** button. | Dataset created; redirect to dataset detail page. Schema inferred (id, name, value, created_at) | ☐ |
| 4 | Run compliance check | From asset detail (or dataset), navigate to **Compliance** section. Start a compliance run if available. | Compliance run starts; result shows pass/fail | ☐ |
| 5 | Run DQ check | Navigate to **DQ** (Data Quality) section. Start a DQ run if available. | DQ run starts; result shows pass/fail | ☐ |
| 6 | Create contract | Go to **Contracts** → **Create Contract** (navigates to ODPS upload). Paste content from `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json` into the textarea, or upload the file. Ensure **Format** is JSON. Click **Create ODPS Product**. | Workflow runs; ODPS and ODCS contracts created and linked. Redirect to ODPS detail or contract detail | ☐ |
| 7 | Link contract to asset | If contract is not auto-linked, go to contract detail → **Link ODPS** or **Link asset** and associate with the asset from step 1. | Contract linked to asset | ☐ |
| 8 | Activate asset | Go to asset detail. Change status from DRAFT to **ACTIVE** (via status dropdown or Activate button if available). | Asset status = **ACTIVE** | ☐ |

---

## Success Criteria

- Asset created in DRAFT status
- File uploaded successfully
- Schema inferred from file (id, name, value, created_at)
- Compliance check runs (pass or fail logged)
- DQ check runs (pass or fail logged)
- Contract created and linked
- Asset activated (status = ACTIVE)

---

## Alternative: Data-First Flow (Create Asset & Dataset in One Step)

- **Path A**: Datasets → Create Dataset → Flow selector "Create new asset and link" → Upload file → Enter asset key/name → Create Asset & Dataset.
- **Path B**: Assets → Create Asset → "I have data to upload" → redirects to Dataset Create with create_new mode → same flow as Path A.
- **API**: `POST /api/v1/assets/data-first/` with `file_id`, `key`, `name`.
- **E2E**: `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` (Dataset Create flow); `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` (Asset Create "I have data" redirect).
- **Runbook**: [docs/runbooks/DATA_FIRST_ASSET_CREATION.md](../../../../docs/runbooks/DATA_FIRST_ASSET_CREATION.md).

## Notes

- **Compliance/DQ**: If the UI does not expose compliance or DQ runs from asset/dataset, these steps may be available via API or a different route. Document any deviations.
- **Contract creation**: The UI uses ODPS upload. Use `odps-with-embedded-odcs.json` which contains `product.contract.spec` with inline ODCS.
- **Schema alignment**: `sample-upload.csv` columns (id, name, value, created_at) align with `odcs-minimal.json` schema (id, name, value).

---

## Traceability

- **Use Case**: UC-AM-001 (Create Asset via Data-First Flow)
- **E2E Specs**: `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts`, `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts`, `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
