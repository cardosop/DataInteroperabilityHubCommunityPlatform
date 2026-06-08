# JOURNEY-CPO-016: Report and Resolve Data Breach

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-BREACH-001
**Phase:** 284 (GA Promotion — Pre-Existing Bug Fixes)
**Status:** Implemented (284.F.4)
**E2E:** `breach-report-flow.spec.ts`
**Routes:** `/governance/breach/report`, `/governance/breach/{id}`, `/governance/breach`

**Note:** JOURNEY-CPO-011 (Approval Inbox) already exists. This breach reporting journey is numbered CPO-016 to avoid collision.

## Overview

A Compliance & Privacy Officer identifies a personal data breach, creates an incident record in Meshant, tracks the statutory notification clock across multiple regulatory regimes (GDPR Art. 33, LGPD Art. 48, CCPA § 1798.82), sends supervisory authority notifications, and drives the incident to resolution (CONTAINED → NOTIFIED → CLOSED). The breach dashboard provides SLA deadline tracking and open-incident counts so the CPO can prioritize the most urgent regulatory deadlines.

## Journey Steps

1. **Report a breach** — From the governance sidebar, the CPO navigates to `/governance/breach/report` and fills the report form:
   - **Title** — brief incident title (required)
   - **Summary** — narrative description (no PII in the summary)
   - **Regimes** — comma-separated list of applicable regulations (GDPR, LGPD, CCPA)
   - **Discovered at** — auto-populated to current UTC timestamp
   - POSTs to `POST /api/v1/governance/breach-incidents/` → redirects to `/governance/breach/{id}`

2. **View breach detail with SLA clock** — The detail page at `/governance/breach/{id}` renders:
   - Incident title, summary, status badge
   - `statutory_authority_deadline_utc` — the tightest deadline across all regimes
   - SLA countdown timer (recalculates every 30s via `setInterval`)
   - Notification list with per-regime status: `PENDING`, `SENT`, `ACKNOWLEDGED`
   - Status transition buttons: Mark CONTAINED, Mark NOTIFIED, Close

3. **Mark notification sent** — The CPO clicks "Mark sent" on a notification row, enters an outbound reference (DPA portal case ID), and POSTs to `POST /api/v1/governance/breach-notifications/{id}/mark-sent/`.

4. **Transition status** — The CPO progresses the incident through:
   - CONTAINED — breach scope is understood and contained
   - NOTIFIED — supervisory authorities have been notified
   - CLOSED — incident resolved, post-mortem complete
   Each transition calls `PATCH /api/v1/governance/breach-incidents/{id}/status/`.

5. **Dashboard monitoring** — The CPO opens `/governance/breach` to see:
   - Open incidents count with red badge
   - Pending notifications count
   - Incident list with deadline countdown and hours-remaining indicators
   Source: `GET /api/v1/governance/breach-dashboard/`.

## Error Handling

- **Form validation** — Title is required; empty title shows inline validation error.
- **API failure on create** — Backend 4xx/5xx renders via `<ErrorDisplay>` with the specific error code (e.g., `BREACH_VALIDATION_FAILED`).
- **Status transition conflict** — If the incident was already transitioned by another user, backend returns 409; the page refreshes to show current state.
- **Network failure** — Mutation shows retryable error toast; SLA clock continues ticking locally.
- **Dashboard load failure** — `<ErrorDisplay>` with retry button; empty state is distinguishable from error state.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `BREACH_INCIDENT_CREATED` | New breach incident record | 90 days |
| `BREACH_NOTIFICATION_SENT` | Notification marked as sent | 90 days |
| `BREACH_STATUS_CHANGED` | Incident status transition | 90 days |
| `BREACH_DASHBOARD_LOADED` | Dashboard page view | 30 days |

## Success Criteria

- CPO can report a breach in under 2 minutes from form open to redirect.
- SLA clock renders with correct deadline and countdown; updates every 30s.
- Status transitions CONTAINED → NOTIFIED → CLOSED complete without page crash.
- Dashboard shows open incidents and pending notifications with correct counts.
- Every mutation emits the corresponding audit event.

## Related

- Concepts: [Breach Notification](../concepts/), [Compliance Runs](../concepts/compliance-runs.md), [Audit Events](../concepts/audit-events.md)
- E2E: `frontend/e2e/journeys/breach-report-flow.spec.ts` (284.F.4)
- Runbook: [RB-COMP-004-breach.md](../../runbooks/RB-COMP-004-breach.md)
- Components: `ReportBreachPage`, `BreachDetailPage`, `BreachDashboardPage`
- Phase: 232.3 (Breach Notification), 284.F.4 (E2E gap closure)
