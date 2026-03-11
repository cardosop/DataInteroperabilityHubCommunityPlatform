# JOURNEY-PA-009: Manage Federated Assets

**Journey ID**: JOURNEY-PA-009  
**Title**: Manage Federated Assets  
**Persona**: Platform Admin  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] Federated assets capability

---

## What You Will Do

View federated assets. Manage federation topology. Configure sync.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to federated assets | Go to **Admin** → **Federated Assets** or **Marketplace** → **Federated**. | Federated assets page | ☐ |
| 2 | View assets | Browse federated assets. | Assets displayed | ☐ |
| 3 | Manage topology | Configure federation topology. | Topology configured | ☐ |
| 4 | Sync | Trigger or configure sync. | Sync works | ☐ |

---

## Success Criteria

- Federated assets visible
- Topology manageable
- Sync works

---

## Note

If federated assets is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-009.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
