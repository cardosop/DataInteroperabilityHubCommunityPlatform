# JOURNEY-CPO-011: Approval Inbox Flow

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-GOV-ADV-001, UC-GOV-ADV-002, UC-GOV-ADV-003, UC-GOV-ADV-004
**Phase:** 278 (UX Activation)
**Status:** Implemented (278.I.1, 278.R.8, 278.V.3, 278.V.10)
**E2E:** `approval-inbox-unified.spec.ts`, `bulk-approve-reject.spec.ts`
**Status:** Implemented (route wiring pending — see 278.R.8)
**Routes:** `/governance/my-approvals`, `/governance/delegation`

## Overview

A Compliance & Privacy Officer manages their approval queue through a unified
inbox (`MyApprovalsInbox`) that aggregates actionable items across access
requests, DSARs, breach incidents, DPIA reviews, and KYB verifications into a
single "Waiting on me" view. They can approve or reject items inline without
full-page navigation, delegate approvals during out-of-office periods via
`ApprovalDelegation`, and bulk-process low-risk batches with partial-failure
semantics. The inbox is the primary day-to-day interface for governance
operations and must render priority, type, and requester identity for every
pending item at a glance.

## Journey Steps

1. **Open unified inbox** — From the home dashboard or governance sidebar
   ("My Approvals"), the CPO navigates to `/governance/my-approvals`
   (Phase 278.I.1, route `278.R.8`). The inbox renders:

   - **Header** — total pending count as a red badge (e.g., "12 waiting on
     you"). When zero, renders "No items waiting."
   - **Item rows** — each row shows a type badge (Access, DSAR, Breach,
     DPIA, KYB), a priority tag (HIGH / MEDIUM / LOW), the item title
     (linked to its detail page), a subtitle with requester identity and
     age (e.g., "Requested by alice@acme.com · 3 days ago"), and inline
     action buttons (Approve, Reject).
   - **Priority color coding** (Phase 278.I.1): HIGH = red left border,
     MEDIUM = amber, LOW = gray.
   - **Select-all checkbox** in the header row for bulk operations.
   - **Reject reason input** — a shared text field at the top of the inbox
     for entering a rejection reason before clicking Reject on any row.
   - **Footer** — "View all governance items →" link to the full
     governance list page (`/governance/access-requests`).

   Data source: `GET /api/v1/governance/access-requests/?status=PENDING&status=PENDING_NEXT_APPROVER`
   (tenant-scoped, ordered by priority desc then created_at asc).

2. **Approve an access request inline** — The CPO clicks "Approve" on a
   PENDING row (Phase 278.I.2). The button fires
   `POST /api/v1/governance/access-requests/{id}/approve/` directly from
   the row. On success the item is removed from the inbox with a brief
   fade-out animation. On failure (e.g., ABAC policy denial, compliance
   gate failure, item state changed since page load), an inline error
   toast appears with the specific rejection reason from the backend.

   Backend checks executed during approval (Phase 272):
   - Business-rules validation via `GovernanceBusinessRules`.
   - Compliance gate: queries latest `ComplianceRun` for the resource;
     blocks when `allowed_to_store` is not `True`.
   - ABAC evaluation: `ABACEngine.evaluate_access(action="approve_access_request")`;
     DENY policy → 403 `ABAC_POLICY_DENIED`.
   - Multi-step approval chain check (Phase 272.4): if
     `required_approval_chain` is non-empty, snapshots chain into
     `AccessRequest.approval_workflow`; intermediate approvals set status
     `PENDING_NEXT_APPROVER`; entitlement + order fulfillment fire only on
     the final step.
   - Delegation check (Phase 272.6): `ApprovalDelegation` records
     consulted; delegate may approve during active time window.

3. **Reject with reason** — The CPO enters an optional reason in the shared
   rejection-reason input at the top of the inbox, then clicks "Reject" on
   a row (Phase 278.I.2). The mutation fires
   `POST /api/v1/governance/access-requests/{id}/reject/` with the reason
   in the payload. On success the item fades out. On failure, a specific
   error is shown inline. If the rejection reason is empty, the backend
   accepts the rejection with `reason: null`.

4. **Bulk approve low-risk batches** — The CPO selects multiple items via
   row checkboxes or the select-all header checkbox (Phase 278.E.2
   `useBulkSelect`), then clicks "Approve N" from the `BulkActionBar`
   (Phase 278.I.4). Items are processed with partial-failure semantics:

   - **Succeeded items** — removed from the inbox, each emits
     `ACCESS_REQUEST_APPROVED` audit event.
   - **Failed items** — remain in the inbox with an inline error badge
     (e.g., "Blocked by compliance gate") and a tooltip with the full
     error detail from `POST /api/v1/governance/access-requests/bulk/`.
   - **All failed** — an error toast summarizes: "None of N items could be
     approved. Check each item for details."

   Bulk approval honors the same backend checks as single-item approval
   (business rules, compliance gate, ABAC, multi-step chain).

5. **Delegate during out-of-office** — The CPO navigates to
   `/governance/delegation` (Phase 278.I.3). `DelegationSettingsPage`
   renders a form to create an `ApprovalDelegation`:

   - **Delegate** — email or user-search picker (`SearchablePicker`,
     Phase 278.G.4).
   - **Date range** — start and end date-time pickers with validation
     (start < end, start ≥ now).
   - **Reason** — required free-text field (audited).

   Active delegations are listed below the form with delegate identity,
   date range, reason, and a "Revoke" button (DELETE). Delegation state is
   consulted at approval time — if the original approver is unavailable,
   the delegate can approve on their behalf (Phase 272.6
   `ApprovalDelegation` model).

   The CPO can revoke a delegation early via
   `DELETE /api/v1/governance/delegations/{id}/`. Revocation emits
   `DELEGATION_REVOKED`.

6. **Review completed items** — The CPO clicks "View all governance items →"
   to navigate to the full governance list page
   (`/governance/access-requests`), where all items (including
   already-processed ones) are visible with full filtering by status, date
   range, requester, and resource.

7. **Mobile-responsive use** — On viewports ≤ 640 px (Phase 278.I.5):
   items stack vertically (column layout), action buttons move to the
   bottom with a top-border separator, the row checkbox moves to a top-right
   absolute position, the rejection reason input goes full-width, and bulk
   action buttons stack vertically. The inbox is scrollable and all inline
   actions remain reachable without horizontal scroll.

## Error Handling

- **ABAC policy denial** — Backend returns 403 `ABAC_POLICY_DENIED`. Inline
  error displays: "This approval is blocked by an access policy. Contact a
  Platform Admin."
- **Compliance gate failure** — Backend returns 409 with
  `COMPLIANCE_GATE_FAILED`. Error displays: "The resource failed its most
  recent compliance scan. Review the scan report before approving."
- **Stale item** — Item was approved/rejected by another CPO between page
  load and click. Backend returns 409 `CONFLICT`. The item is removed from
  the inbox with a toast: "This item was already processed by another user."
- **Bulk partial failure** — Items that fail remain in the inbox with an
  error badge; items that succeed are removed. The summary toast shows
  "N of M items approved."
- **Delegation validation** — Creating a delegation with `end_at < start_at`
  or a delegate who lacks the required role shows inline field errors.
- **Network failure** — Each mutation shows a retryable error toast
  ("Network error — try again"). The inbox state is not optimistically
  cleared on network failure.
- **Empty inbox** — Renders "No items waiting for your approval" with a
  link to the full governance list and an illustration.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `ACCESS_REQUEST_APPROVED` | Single or bulk approval (per item) | 90 days |
| `ACCESS_REQUEST_REJECTED` | Single or bulk rejection (per item) | 90 days |
| `ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN` | PLATFORM_ADMIN force-approve bypass | 90 days |
| `ABAC_POLICY_DENIED` | ABAC DENY during approval | 30 days |
| `APPROVAL_DELEGATION_CREATED` | Delegation created | 90 days |
| `APPROVAL_DELEGATION_REVOKED` | Delegation revoked | 90 days |
| `MY_APPROVALS_INBOX_LOADED` | Inbox page load | 30 days |
| `BULK_APPROVAL_COMPLETED` | Bulk operation finishes (succeeded + failed counts) | 30 days |

## Success Criteria

- All PENDING and PENDING_NEXT_APPROVER access requests appear in the
  unified inbox with correct priority color coding and type badges.
- Inline approve and reject complete without full-page navigation; the
  inbox item is removed within 300 ms of a successful response.
- Bulk approve processes up to 50 items in a single operation with
  partial-failure semantics — individual failures do not block sibling
  items.
- Approval delegation CRUD works end-to-end: create, list active, revoke.
  Delegation state is correctly consulted at approval time.
- The inbox renders "No items waiting" when the PENDING queue is empty.
- Mobile-responsive layout is usable at 320 px width without horizontal
  scroll.
- Every approval, rejection, delegation creation, and delegation revocation
  emits a corresponding audit event within the transaction boundary.
- ABAC policy denial and compliance gate failure produce user-facing error
  messages that include actionable remediation.

## Related

- Concepts: [Governance](../concepts/governance.md),
  [Compliance Runs](../concepts/compliance-runs.md),
  [Audit Events](../concepts/audit-events.md),
  [Users and Roles](../concepts/users-and-roles.md)
- Use Cases: [UC-GOV-ADV-001](../use-cases/UC-GOV-ADV-001.md) (Automated
  Compliance), [UC-GOV-ADV-002](../use-cases/UC-GOV-ADV-002.md) (GDPR
  Erasure), [UC-GOV-ADV-003](../use-cases/UC-GOV-ADV-003.md) (Consent
  Tracking), [UC-GOV-ADV-004](../use-cases/UC-GOV-ADV-004.md) (Automated
  Retention)
- Journeys: [JOURNEY-CPO-001](JOURNEY-CPO-001.md) (Run Compliance Scan),
  [JOURNEY-CPO-006](JOURNEY-CPO-006.md) (Configure Automated Compliance),
  [JOURNEY-DC-002](JOURNEY-DC-002.md) (Marketplace Discovery — creates the
  access requests that land in this inbox)
- Components: `MyApprovalsInbox`, `DelegationSettingsPage`, `BulkActionBar`,
  `SearchablePicker`
- Phase 278 tasks:
  - 278.I.1 — Consolidated "waiting on me" inbox (MyApprovalsInbox)
  - 278.I.2 — One-click approve/reject from inbox row
  - 278.I.3 — Delegation UX (DelegationSettingsPage)
  - 278.I.4 — Bulk approve for low-risk batches
  - 278.I.5 — Mobile-responsive approval views
  - 278.E.2 — Bulk multi-select hook + BulkActionBar
  - 278.G.4 — SearchablePicker component (delegate selection)
  - 278.R.8 — Route wiring for `/governance/my-approvals`
- Phase 272 dependencies:
  - 272.2 — Compliance gate check on approval
  - 272.3 — ABAC policy evaluation on approval
  - 272.4 — Multi-step approval chain
  - 272.6 — Approval delegation model + validation
