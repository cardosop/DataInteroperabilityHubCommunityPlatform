# JOURNEY-DMO-003: Manage Domain Topology

**Journey ID**: JOURNEY-DMO-003  
**Title**: Manage Domain Topology  
**Persona**: Data Mesh Domain Owner  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dmo-003-manage-domain-topology)

---

## Prerequisites

- [ ] Logged in as **Data Mesh Domain Owner** (e2e_dmo@example.com / TestPass123)
- [ ] At least one domain

---

## What You Will Do

View domain topology. Add/remove domains. Update relationships.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to topology | Go to **Mesh** → **Topology**. | Topology view | ☐ |
| 2 | View topology | See domain graph/relationships. | Topology displayed | ☐ |
| 3 | Add domain | Create or link domain. | Domain added | ☐ |
| 4 | Update relationship | Modify domain relationship. | Relationship updated | ☐ |

---

## Success Criteria

- Topology visible
- Domains manageable
- Relationships editable

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dmo/JOURNEY-DMO-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
