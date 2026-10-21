# JOURNEY-CPO-007: Set Up GDPR Right to be Forgotten

**Journey ID**: JOURNEY-CPO-007  
**Title**: Set Up GDPR Right to be Forgotten  
**Persona**: Compliance Officer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-007-set-up-gdpr-right-to-be-forgotten-new)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] GDPR deletion workflow capability enabled

---

## What You Will Do

Configure GDPR deletion request workflow. Set up deletion service. Test workflow.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to GDPR config | Go to **Governance** → **GDPR** or **Compliance** → **GDPR**. | GDPR config page | ☐ |
| 2 | Configure deletion workflow | Define deletion request workflow. | Workflow configured | ☐ |
| 3 | Set deletion service | Configure data deletion service. | Service configured | ☐ |
| 4 | Configure verification | Set deletion verification steps. | Verification configured | ☐ |
| 5 | Test | Submit test deletion request. | Workflow runs | ☐ |

---

## Success Criteria

- Workflow configured
- Deletion service set
- Test succeeds

---

## Note

If GDPR workflow is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-007.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
