# JOURNEY-CPO-002: Configure Retention Policy

**Journey ID**: JOURNEY-CPO-002  
**Title**: Configure Retention Policy  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] Governance/retention capability enabled

---

## What You Will Do

Create or edit retention policy. Define retention period. Assign to assets/datasets.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to retention | Go to **Governance** → **Retention** or **Compliance** → **Retention**. | Retention page | ☐ |
| 2 | Create policy | Click **Create Retention Policy**. | Create form | ☐ |
| 3 | Define rules | Set retention period (e.g. 365 days), scope. | Rules defined | ☐ |
| 4 | Assign to assets | Use **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading: select Asset → DatasetPicker filters; select Dataset → FilePicker filters). | Policy assigned | ☐ |
| 5 | Save | Submit. | Policy created | ☐ |

---

## Success Criteria

- Policy created
- Rules defined
- Policy assigned

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
