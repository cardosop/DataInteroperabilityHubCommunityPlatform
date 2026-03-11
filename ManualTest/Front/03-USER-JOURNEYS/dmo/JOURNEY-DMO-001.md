# JOURNEY-DMO-001: Create Data Mesh Domain

**Journey ID**: JOURNEY-DMO-001  
**Title**: Create Data Mesh Domain  
**Persona**: Data Mesh Domain Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dmo-001-create-data-mesh-domain)

---

## Prerequisites

- [ ] Logged in as **Data Mesh Domain Owner** (e2e_dmo@example.com / TestPass123)
- [ ] Data mesh capability enabled
- [ ] TENANT_ADMIN or DATA_MESH_DOMAIN_OWNER role

---

## What You Will Do

Create a new data mesh domain. Configure name, boundaries, and ownership.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to mesh | Go to **Mesh** or **Data Mesh** (sidebar). | Mesh page loads | ☐ |
| 2 | Create domain | Click **Create Domain** or **Add Domain**. | Create form | ☐ |
| 3 | Enter details | Name (e.g. "Sales Domain"), description, boundaries. | Form accepts input | ☐ |
| 4 | Assign owner | Set domain owner (self or other user). | Owner assigned | ☐ |
| 5 | Save | Submit. | Domain created | ☐ |
| 6 | Verify | Domain appears in list/topology. | Domain visible | ☐ |

---

## Success Criteria

- Domain created
- Owner assigned
- Domain visible in mesh

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dmo/JOURNEY-DMO-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
