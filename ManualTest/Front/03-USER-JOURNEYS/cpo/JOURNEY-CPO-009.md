# JOURNEY-CPO-009: Configure Automated Retention Policies

**Journey ID**: JOURNEY-CPO-009  
**Title**: Configure Automated Retention Policies  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-009-configure-automated-retention-policies-new)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] Retention automation capability enabled

---

## What You Will Do

Define retention rules. Configure automation. Set scheduling. Test and deploy.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to retention | Go to **Governance** → **Retention**. | Retention page | ☐ |
| 2 | Define rules | Create retention rules (period, scope). Use **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading) to assign scope. | Rules defined | ☐ |
| 3 | Configure automation | Enable automated retention. | Automation configured | ☐ |
| 4 | Set scheduling | Configure run schedule. | Schedule set | ☐ |
| 5 | Test | Run test. | Test passes | ☐ |
| 6 | Deploy | Activate. | Retention operational | ☐ |

---

## Success Criteria

- Rules defined
- Automation configured
- Test passes

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-009.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
