# UC-DB-008: Approve UC DDL Change

**Persona:** [Platform Admin](../personas/platform-admin/index.md), [Data Protection Officer](../personas/dpo/index.md)
**MVP Tier:** :white_check_mark:
**Phase P2 Test:** `hub/apps/databricks_admin/tests/test_uc_change_journeys.py::TestJOURNEYDB008ApproveDdlChange::test_approve_or_reject_ddl_change`

## Description

Approve or reject a pending UC DDL change with full context: the approver inbox (requests whose CURRENT approval step authorizes them — the workflow's own step logic, never a copied check), the diff-style DDL preview, the requester, the comment thread, and the status timeline. Multi-step chains and time-windowed delegation reuse the governance approval machinery (272.4/272.6).

## Preconditions

- A submitted request (`PENDING_APPROVAL` / `PENDING_NEXT_APPROVER`).
- The approver is ACTIVE, tenant-scoped, and authorized for the current step (directly or via an active delegation).

## Steps

1. Approver GETs `/api/v1/databricks/uc/changes/pending-approvals/` (the inbox, paginated, with previews).
2. Approver reviews the detail (`/uc/changes/{id}/` — preview + timeline) and the comments (`/uc/changes/{id}/comments/`).
3. Approver POSTs `/uc/changes/{id}/approve/` (or `/reject/` with a required reason); the REAL workflow validates the step and transitions the request.
4. The requester is notified in-app; `databricks.uc_change.approved` / `.rejected` webhooks fire; the approval metrics refresh.

## Expected Outcome

- Final-step approval → `APPROVED` (ready for execution); intermediate steps → `PENDING_NEXT_APPROVER`.
- The requester receives an in-app notification; subscribers receive the webhook event.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Unauthorized approver | `400` (the service's `uc_change_approver_unauthorized`) |
| Invalid state (double-approve) | `400` (the service's stage codes) |
| Blank rejection reason | `400` |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-008 -- Approve or Reject a DDL Change](../journeys/JOURNEY-DB-008.md)
- Personas: [Platform Admin](../personas/platform-admin/index.md)
