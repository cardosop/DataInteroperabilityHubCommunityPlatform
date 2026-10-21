# UC-DS-EDIT: Edit Dataset and Link to Asset

**Use Case ID**: UC-DS-EDIT  
**Title**: Edit Dataset and Link to Asset  
**Persona**: Data Product Owner, Data Engineer  
**Priority**: High  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-ds-edit-edit-dataset-and-link-to-asset)

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. Have at least one dataset (create via Files → Create Dataset or asset upload)
3. Have at least one asset (create via Assets → Create Asset)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** or **Data Engineer**
- [ ] Dataset exists
- [ ] Asset exists (when linking)

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to **Datasets** | Dataset list loads | ☐ |
| 2 | Click a dataset row (or open dataset detail) | Dataset detail page loads | ☐ |
| 3 | Click **Edit** or **Link to Asset** | Edit form opens with AssetPicker | ☐ |
| 4 | Select asset via AssetPicker (search or Browse assets link) | Asset selected and displayed | ☐ |
| 5 | Click **Save** | Success toast; dataset shows linked asset | ☐ |
| 6 | Verify dataset detail | Shows asset_id and asset_name | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Unlink | Click clear (×) on AssetPicker, then Save | Dataset no longer linked to asset | ☐ |

---

## Traceability

- **Journey**: [JOURNEY-DPO-018](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-018.md)
- **E2E Spec**: `frontend/e2e/use-cases/ux/dataset-edit.spec.ts`
- **API**: `PATCH /api/v1/datasets/{id}/` with `asset` (UUID or null)
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md)
