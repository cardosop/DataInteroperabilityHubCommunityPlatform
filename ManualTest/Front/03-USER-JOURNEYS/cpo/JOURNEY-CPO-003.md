# JOURNEY-CPO-003: Review Access Request

**Journey ID**: JOURNEY-CPO-003  
**Title**: Review Access Request  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] At least one access request (from Data Consumer or governance flow)

---

## What You Will Do

View access requests. Approve or reject. Verify workflow.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to governance | Go to **Governance** → **Access Requests**. | Access requests list | ☐ |
| 2 | View request | Click a request. | Request detail: requester, asset, justification | ☐ |
| 3 | Approve or reject | Click **Approve** or **Reject**. Add comment if needed. | Decision recorded | ☐ |
| 4 | Verify | Requester receives notification. Access granted if approved. | Workflow complete | ☐ |

---

## Success Criteria

- Requests visible
- Approve/reject works
- Workflow completes

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
