# JOURNEY-DPO-018: Edit Dataset and Link to Asset

**Journey ID**: JOURNEY-DPO-018  
**Title**: Edit Dataset and Link to Asset  
**Persona**: Data Product Owner, Data Engineer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-018-edit-dataset-and-link-to-asset-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** or **Data Engineer** (e2e_test@example.com / TestPass123)
- [ ] At least one dataset exists
- [ ] At least one asset exists

---

## What You Will Do

Link an existing dataset to an asset (or unlink) via the dataset edit form.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to Datasets | Go to **Datasets** (sidebar). | Dataset list loads | ☐ |
| 2 | Open dataset | Click a dataset row. | Dataset detail page loads | ☐ |
| 3 | Open edit | Click **Edit** or **Link to Asset**. | Edit form with AssetPicker | ☐ |
| 4 | Select asset | Use AssetPicker to search and select an asset. | Asset selected and displayed | ☐ |
| 5 | Save | Click **Save**. | Success toast; dataset shows linked asset | ☐ |
| 6 | Verify | Check dataset detail. | asset_id and asset_name displayed | ☐ |

---

## Success Criteria

- Dataset linked to asset
- Unlink works (clear AssetPicker, then Save; asset: null)

---

## Traceability

- **Use Case**: [UC-DS-EDIT](../../02-USE-CASES/UC-DS-EDIT.md)
- **E2E Spec**: `frontend/e2e/use-cases/ux/dataset-edit.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
