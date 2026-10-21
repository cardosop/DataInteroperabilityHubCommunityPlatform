# JOURNEY-DMO-002: Configure Federated Governance

**Journey ID**: JOURNEY-DMO-002  
**Title**: Configure Federated Governance  
**Persona**: Data Mesh Domain Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dmo-002-configure-federated-governance)

---

## Prerequisites

- [ ] Logged in as **Data Mesh Domain Owner** (e2e_dmo@example.com / TestPass123)
- [ ] Data mesh domain exists (from JOURNEY-DMO-001)
- [ ] Federated governance capability

---

## What You Will Do

Configure federated governance for domain. Set policies. Define boundaries.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to domain | Go to **Mesh** → select domain. | Domain detail | ☐ |
| 2 | Open governance | Find **Governance** or **Federated Governance** section. | Governance config | ☐ |
| 3 | Configure policies | Set governance policies. | Policies configured | ☐ |
| 4 | Define boundaries | Set data boundaries. | Boundaries set | ☐ |
| 5 | Save | Submit. | Governance configured | ☐ |

---

## Success Criteria

- Governance configured
- Policies set
- Boundaries defined

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dmo/JOURNEY-DMO-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
