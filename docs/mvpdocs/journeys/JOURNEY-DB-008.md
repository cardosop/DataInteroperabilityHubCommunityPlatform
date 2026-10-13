# JOURNEY-DB-008: Approve or Reject a DDL Change

## Overview

An approver reviews pending Unity Catalog DDL changes in an approval inbox, decides with full context (diff-style DDL preview, requester, comments), and triggers execution or rejection. Multi-step approval chains and time-windowed delegation reuse the governance approval machinery (Phase 272.4/272.6). The inbox shows exactly the requests whose CURRENT step authorizes the user — the workflow's own step logic, never a copied check.

## Journey Steps

1. **Discover** — The approver GETs `/api/v1/databricks/uc/changes/pending-approvals/` (paginated, previews included).
2. **Review** — The approver inspects the diff-style preview, the object's current state, and the comment thread (`/uc/changes/{id}/` + `/comments/` + `/timeline/`).
3. **Decide** — The approver POSTs `/approve/` (final step → `APPROVED`, intermediate → `PENDING_NEXT_APPROVER`) or `/reject/` with a required reason (`REJECTED`).
4. **Side effects** — The requester is notified in-app; the `databricks.uc_change.approved` / `.rejected` webhooks fire for subscribers; the approval-pipeline metrics (backlog gauge, oldest-pending gauge, approval latency) refresh.

## Success Criteria

- An unauthorized user cannot approve (the service's step authorization).
- The requester receives the in-app notification; subscribers receive the webhook event.
- The inbox empties once the request leaves the approvable states.

## Related

- Use cases: [UC-DB-008](../use-cases/UC-DB-008.md)
- Journeys: [JOURNEY-DB-007](JOURNEY-DB-007.md) (Request a UC DDL Change)
