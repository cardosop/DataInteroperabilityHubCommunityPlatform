# JOURNEY-CPO-006: Configure Automated Compliance

**Journey ID**: JOURNEY-CPO-006  
**Title**: Configure Automated Compliance  
**Persona**: Compliance Officer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-006-configure-automated-compliance-new)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] Automated compliance capability enabled

---

## What You Will Do

Define compliance rules. Configure auto-detection. Set enforcement. Test and deploy.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to compliance config | Go to **Compliance** → **Configuration**. | Config page | ☐ |
| 2 | Define rules | Add compliance rules (e.g. PII detection). | Rules defined | ☐ |
| 3 | Configure auto-detection | Enable auto-detection. Set schedule. | Auto-detection configured | ☐ |
| 4 | Set enforcement | Configure actions (alert, block). | Enforcement set | ☐ |
| 5 | Test | Run test. | Test passes | ☐ |

---

## Success Criteria

- Rules defined
- Auto-detection configured
- Test passes

---

## Note

If automated compliance is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
