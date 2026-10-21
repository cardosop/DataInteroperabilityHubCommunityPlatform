# JOURNEY-DB-007: Request a UC DDL Change

## Overview

A data engineer requests a Unity Catalog DDL change (CREATE for the supported securables, DROP for the flag-gated destructive family) against a registered workspace. The request carries a TRUTHFUL DDL preview — the exact REST method/path/body the 2.3 executor will send, or the identifier-quoted SQL statement for the SQL-fallback types — derived locally, zero network. The 2.4 guards run at the boundary: the denylist refuses destructive DDL on a flag-off tenant, the identifier regex rejects malformed identifiers.

## Journey Steps

1. **Request** — The engineer POSTs `/api/v1/databricks/workspaces/{id}/uc/changes/` with the change type, securable type, and the payload-shaped definition (identifiers + options).
2. **Review the preview** — The response carries the DRAFT with the truthful preview (kind/method/path/body or kind/statement); an unknown vocabulary marks it unsupported instead of crashing.
3. **Submit** — The requester POSTs `/submit/`; the request moves to `PENDING_APPROVAL` (or straight to `APPROVED` when approval is skipped), the step approvers are notified in-app, and the `databricks.uc_change.submitted` webhook fires.

## Success Criteria

- The draft persists tenant-scoped with the preview and lists paginated under the workspace registry.
- A destructive request on a flag-off tenant is refused with `DATABRICKS_DDL_DENYLISTED` and zero network calls.
- The approver inbox surfaces the pending request to exactly the step-authorized users.

## Related

- Use cases: [UC-DB-007](../use-cases/UC-DB-007.md)
- Journeys: [JOURNEY-DB-008](JOURNEY-DB-008.md) (Approve or Reject a DDL Change)
