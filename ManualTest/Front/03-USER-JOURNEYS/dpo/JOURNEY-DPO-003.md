# JOURNEY-DPO-003: Manage Asset Lifecycle

**Journey ID**: JOURNEY-DPO-003  
**Title**: Manage Asset Lifecycle  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-003-manage-asset-lifecycle)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one asset exists (from JOURNEY-DPO-001 or existing)

---

## What You Will Do

Change asset status through the lifecycle (DRAFT → ACTIVE → DEPRECATED → RETIRED). Verify status changes and transitions.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select an asset. | Asset detail page | ☐ |
| 1a | Attach contract/dataset (optional) | Use **ContractPicker** and **DatasetPicker** in Attach sections to link contract and dataset to asset. | Contract/dataset attached | ☐ |
| 2 | View current status | Check status badge. | Status displayed (DRAFT, ACTIVE, etc.) | ☐ |
| 3 | Change status (if DRAFT) | Use status dropdown or **Activate** button. Set to ACTIVE. | Status = ACTIVE | ☐ |
| 4 | Change to DEPRECATED (if available) | If asset is ACTIVE, set to DEPRECATED. | Status = DEPRECATED | ☐ |
| 5 | Change to RETIRED (if available) | Set to RETIRED. | Status = RETIRED | ☐ |
| 6 | Verify transitions | Confirm status changes reflect in list and detail. | Status persisted | ☐ |

---

## Success Criteria

- Asset status can be changed
- Transitions follow allowed lifecycle (DRAFT→ACTIVE, ACTIVE→DEPRECATED, etc.)
- Status persists and visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
