# UC-GOV-ADV-005: Manage Unified Approval Inbox

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md) / [Tenant Admin](../personas/tenant-admin/)
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.I.1`, `278.I.2`, `278.I.4`

## Description

A Compliance Officer or Tenant Admin manages their approval queue through
a unified inbox that aggregates actionable items across access requests,
DSARs, breach incidents, DPIA reviews, and KYB verifications into a
single "Waiting on me" view. Items are color-coded by priority, display
type badges, and support inline approve/reject without full-page
navigation. Bulk approve handles low-risk batches with partial-failure
semantics.

## Preconditions

- The user holds `TENANT_ADMIN`, `DPO`, `LEGAL_ADMIN`, `SECURITY_ADMIN`,
  or `PLATFORM_ADMIN` role.
- At least one access request, DSAR, or governance item is in `PENDING`
  or `PENDING_NEXT_APPROVER` status.
- The route `/governance/my-approvals` is registered (Phase 278.R.8).

## Steps

1. CPO navigates to `/governance/my-approvals`. The `MyApprovalsInbox`
   renders with a header showing the total pending count as a red badge.
2. Each item row shows: type badge (Access/DSAR/Breach/DPIA/KYB),
   priority tag (HIGH=red border, MEDIUM=amber, LOW=gray), title
   linked to detail page, requester identity and age, and inline
   Approve/Reject buttons.
3. CPO clicks "Approve" on a PENDING access request row. The mutation
   fires immediately, without navigating to the detail page.
4. On success, the item is removed from the inbox with a fade-out
   animation. On failure (ABAC denial, compliance gate), an inline
   error toast shows the specific reason.
5. CPO enters an optional rejection reason in the shared input at the
   top, clicks "Reject" on a row. The rejection fires.
6. CPO selects multiple items via checkboxes, clicks "Approve N" from
   the BulkActionBar. Items are processed with partial-failure
   semantics — succeeded items removed, failed items remain with error.
7. CPO clicks "View all governance items →" to navigate to the full
   governance list page.

## Expected Outcome

- All PENDING / PENDING_NEXT_APPROVER items appear with correct badges.
- Inline approve/reject complete without full-page navigation.
- Bulk approve processes up to 50 items; individual failures don't block
  sibling items.
- `ACCESS_REQUEST_APPROVED`, `ACCESS_REQUEST_REJECTED`, and
  `BULK_APPROVAL_COMPLETED` audit events are emitted.
- `meshant.approval_inbox.item_action` and `.bulk_action` CustomEvents
  fire (Phase 278.T.2 telemetry).
- Mobile-responsive layout at ≤640 px renders items in column layout.

## Error Handling

| Condition | Expected Response |
|---|---|
| ABAC policy denial | `403 ABAC_POLICY_DENIED` with actionable message |
| Compliance gate failure | `409 COMPLIANCE_GATE_FAILED` |
| Item already processed by another user | `409 CONFLICT`, item removed |
| Network failure | Retryable error toast; inbox state preserved |

## Related

- Concepts: [Governance](../../concepts/governance.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-CPO-011](../journeys/JOURNEY-CPO-011.md) (Approval Inbox Flow)
- Components: `MyApprovalsInbox`, `BulkActionBar`
- Phase 278 tasks: `278.I.1` (Unified inbox), `278.I.2` (Inline actions), `278.I.4` (Bulk), `278.R.8` (Route)
- Phase 272: ABAC evaluation, compliance gate, multi-step approval chain
- E2E: `approval-inbox-unified.spec.ts` (278.V.3)
