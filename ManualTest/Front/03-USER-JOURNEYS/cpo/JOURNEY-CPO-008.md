# JOURNEY-CPO-008: Manage Consent Tracking

**Journey ID**: JOURNEY-CPO-008  
**Title**: Manage Consent Tracking  
**Persona**: Compliance Officer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-008-manage-consent-tracking-new)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] Consent tracking capability enabled

---

## What You Will Do

Configure consent rules. Set up tracking. Monitor consent status. Generate reports.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to consent | Go to **Governance** → **Consent** or **Compliance** → **Consent**. | Consent page | ☐ |
| 2 | Configure rules | Define consent rules. | Rules configured | ☐ |
| 3 | Set up tracking | Enable consent tracking. | Tracking enabled | ☐ |
| 4 | Monitor status | View consent status by user/asset. | Status visible | ☐ |
| 5 | Generate report | Export consent report. | Report generated | ☐ |

---

## Success Criteria

- Rules configured
- Tracking enabled
- Reports generated

---

## Note

If consent tracking is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-008.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
