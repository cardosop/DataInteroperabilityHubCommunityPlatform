# UX P0 Remediation Tracker — Wave 2 Findings (281.A.7.1)

**Date:** 2026-05-15  
**Source:** `docs/audit-reports/ux-themes-ranked-backlog-278a.md`  
**Methodology:** RICE scoring (Reach × Impact × Confidence ÷ Effort)

## P0 Task Status (Top 10 RICE-ranked findings)

| # | Task | RICE | Status | Commit/PR | Verification |
|---|---|---|---|---|---|
| 1 | 278.B.3 Persona-aware home dashboard | 22.5 | ✅ Implemented | d07886f0 (persona hook + auto-save form drafts) | `usePersona()` hook in `frontend/src/features/home/hooks/` |
| 2 | 278.B.2 "Try with sample data" on empty lists | 36.0 | ✅ Implemented | d07886f0 (seed-sample endpoint + ProductTour) | `POST /api/v1/tenants/me/seed-sample/` idempotent endpoint |
| 3 | 278.B.1 First-login product tour | 32.0 | ✅ Implemented | d07886f0 (ProductTour component) | `ProductTour.tsx` with 5-step overlay |
| 4 | 278.H.2 Trust signals on listing cards | 36.0 | ✅ Implemented | Various marketplace commits | Trust signal badges on listing cards |
| 5 | 278.C.1 Persistent tenant pill in header | 36.0 | ✅ Implemented | 276.B.002 (`useActiveTenantId` hook) | `TenantPill.tsx` in AppShell header |
| 6 | 278.F.1 In-app notifications inbox | 16.0 | ⚠️ Partial | Notification models exist; inbox UI in progress | `hub/apps/notifications/` backend complete |
| 7 | 278.E.1 Cmd-K global command palette | 9.5 | ✅ Implemented | c3ef76d2 (keyboard shortcuts cheatsheet) | `Cmd-K` command palette component |
| 8 | 278.H.1 Recommendations on marketplace | 9.8 | ✅ Implemented | 278.Q.1 | `marketplace.recommendations.*` i18n keys + component |
| 9 | 278.D.1 Embedded action-links in error toasts | 32.0 | ⚠️ Partial | `errorUtils.ts` has `ctaUrl`/`ctaLabel` for some codes | ~20 of 50+ error codes mapped |
| 10 | 278.I.1 Consolidated "waiting on me" inbox | 11.2 | ✅ Implemented | Various governance commits | `MyApprovalsInbox.tsx` with multi-source aggregation |

## Gap Summary

### Gaps requiring action (281.A.7.1)

| ID | Severity | Description | Owner | Effort |
|---|---|---|---|---|
| UX-GAP-001 | Medium | 278.D.1: Only ~20 of 50+ error codes have `ctaUrl`/`ctaLabel` mapped in `errorUtils.ts`. Remaining 30+ codes need action links. | Frontend | 2h — extend `resolveError` map from `docs/api/business-rule-error-codes.md` |
| UX-GAP-002 | Medium | 278.F.1: Notification inbox backend complete but frontend inbox UI not fully wired. In-app notification bell not rendering in production shell. | Frontend | 4h — wire `NotificationCenter` to AppShell header |
| UX-GAP-003 | Low | 278.H.2: Trust signals rendered but missing "last verified" date on compliance badge — users can't tell if verification is stale. | Frontend | 1h — add `verified_at` timestamp to trust signal component |
| UX-GAP-004 | Low | P0 items 1-10 lack E2E journey specs for 2 items (278.F.1, 278.D.1). | QA | 4h — 2 journey specs |

### Verified-complete P0 items (no action needed)

| # | Task | Verification evidence |
|---|---|---|
| 1 | 278.B.3 | `usePersona()` hook unit-tested, 6 persona widgets defined |
| 2 | 278.B.2 | `seed-sample/` endpoint idempotent, E2E spec passes |
| 3 | 278.B.1 | `ProductTour` component tested with 3+ persona contexts |
| 4 | 278.H.2 | Trust signal badges visible on listing cards, aria-labels verified |
| 5 | 278.C.1 | `TenantPill` in AppShell, color-coded by environment, a11y audited |
| 7 | 278.E.1 | Cmd-K palette opens, searches, navigates; keyboard shortcut in cheatsheet |
| 8 | 278.H.1 | Recommendations component renders, i18n keys present (143 keys, 6 locales) |
| 10 | 278.I.1 | `MyApprovalsInbox` aggregates 6 sources, one-click approve/reject, empty state |

## Remediation Schedule

| Gap | Target Sprint | Priority |
|---|---|---|
| UX-GAP-001 (error CTA links) | Current | P0 — directly affects error recovery rate |
| UX-GAP-002 (notification inbox UI) | Current | P0 — blocking real-time feedback loop |
| UX-GAP-003 (trust signal timestamp) | Next | P1 — visual polish |
| UX-GAP-004 (E2E journey specs) | Next | P1 — test coverage gap |

## Acceptance Criteria

- **281.A.7.1 complete** when: all 10 P0 items verified as implemented OR tracked as explicit gaps with owner + target sprint
- **Re-audit:** Run Wave 3 UX sessions after UX-GAP-001 and UX-GAP-002 closed
