# JOURNEY-DPO-013: Configure Data Mesh Domain

**Journey ID**: JOURNEY-DPO-013  
**Title**: Configure Data Mesh Domain  
**Persona**: Data Product Owner  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-013-configure-data-mesh-domain-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] Data mesh capability enabled
- [ ] At least one asset to assign to domain

---

## What You Will Do

Create or select data mesh domain. Assign assets to domain. Configure domain boundaries.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to mesh | Go to **Mesh** or **Data Mesh**. | Mesh page | ☐ |
| 2 | Create or select domain | Create new domain or select existing. | Domain selected | ☐ |
| 3 | Define boundaries | Set domain scope, boundaries. | Boundaries configured | ☐ |
| 4 | Assign assets | Link owned assets to domain. | Assets assigned | ☐ |
| 5 | Save | Submit. | Domain configured | ☐ |

---

## Success Criteria

- Domain created/selected
- Boundaries defined
- Assets assigned to domain

---

## Note

If data mesh is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-013.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
