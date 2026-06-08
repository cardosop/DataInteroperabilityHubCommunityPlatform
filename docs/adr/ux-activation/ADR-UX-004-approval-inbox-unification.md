# ADR-UX-004 — Approval Inbox Unification (Single Inbox vs Per-Type)

- **Status**: accepted
- **Date**: 2026-05-13
- **Deciders**: Frontend team, Governance product owner
- **Stakeholders**: DPO, Compliance Officer, Platform Admin (approval-heavy personas)

## Context

Phase 278.I.1 required a consolidated "waiting on me" inbox. Before Phase 278, approvals were siloed: access requests lived on `/governance/access-requests`, DSARs on `/gdpr/dsar`, breach incidents on `/gdpr/breaches`, and DPIAs on `/compliance/dpias`. Approvers with cross-cutting responsibilities had to check 4+ pages to clear their queue.

Two architectures were evaluated:
1. **Unified inbox:** Single view aggregating all approval types with per-item type badges and priority indicators.
2. **Per-type inboxes with notification aggregation:** Keep existing per-type pages; add a notification-bell badge that links to the oldest pending item.

## Decision

**Unified inbox (`MyApprovalsInbox`)** — a single view that aggregates PENDING and PENDING_NEXT_APPROVER items across access requests, DSARs, breach incidents, DPIAs, and KYB reviews.

Design properties:
- Each item shows a **type badge** (Access/DSAR/Breach/DPIA/KYB) with distinct background color for rapid visual scanning.
- **Priority color coding** via left border: red (high), amber (medium), gray (low).
- **Inline action buttons** (Approve/Reject) on each row — no full-page navigation required.
- **Bulk operations** via select-all checkbox + bulk approve/reject with shared reason input.
- **Count badge** in the header shows total pending items as a red pill.
- **Footer link** "View all governance items →" for drill-down into per-type detail pages.

The unified inbox supplements, not replaces, the per-type detail pages. Approvers who need full context (document review, compliance run results) click through to the detail page; approvers who can act on the summary information (standard access requests, low-risk DPIAs) act directly from the inbox.

Rejected alternative — per-type inboxes with notification badges: lower implementation cost but fails the "single glance" requirement. A Platform Admin with 3 pending access requests, 1 DSAR, and 2 breach reviews still visits 3 pages.

## Consequences

- **Positive:** Single-page approval clearance for the common case (standard access requests).
- **Positive:** Type badges and priority borders enable rapid visual triage.
- **Positive:** Bulk operations reduce click count for batch approvals.
- **Negative:** Initial implementation only aggregates access requests (PENDING/PENDING_NEXT_APPROVER). DSAR, breach, DPIA, and KYB items are represented in the type badge system but data fetching for those types is deferred pending their respective API endpoints exposing the required status filters.
- **Negative:** Per-type detail pages must still be maintained for deep-dive review; the inbox adds a surface without removing any.

## Cross-references

- Implementation: `frontend/src/features/governance/components/MyApprovalsInbox.tsx`, `.css`
- Backend: `useAccessRequests`, `useApproveAccessRequest`, `useRejectAccessRequest` hooks (from `useGovernance`)
- Bulk operations: `frontend/src/shared/hooks/useBulkSelect.ts`, `frontend/src/shared/components/BulkActionBar.tsx`
- Related: Phase 278.I.1-I.5 (approval inbox tasks), Phase 272.6 (delegation), Phase 223.3.4 (bulk operations)
