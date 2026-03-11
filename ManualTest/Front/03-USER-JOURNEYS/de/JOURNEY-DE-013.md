# JOURNEY-DE-013: Configure Data Mesh Domain

**Journey ID**: JOURNEY-DE-013  
**Title**: Configure Data Mesh Domain  
**Persona**: Data Engineer  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-013-configure-data-mesh-domain-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Data mesh capability enabled

---

## What You Will Do

Create domain. Configure infrastructure. Set up self-serve. Configure governance.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to mesh | Go to **Mesh** or **Data Mesh**. | Mesh page | ☐ |
| 2 | Create domain | Create new domain. | Domain created | ☐ |
| 3 | Configure infrastructure | Set domain infrastructure. | Config saved | ☐ |
| 4 | Set self-serve | Enable self-serve capabilities. | Self-serve enabled | ☐ |
| 5 | Configure governance | Set governance rules. | Governance configured | ☐ |

---

## Success Criteria

- Domain created
- Infrastructure configured
- Governance set

---

## Note

If data mesh is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-013.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
