# Frontend Audit Report — 2026-05-12

## Executive Summary

Static review of `frontend/src/` against backend API surfaces, persona journeys,
UX heuristics, system design, FE↔BE contracts, delivery infra, CI/quality gates,
and docs/DX. **8 P0 findings, 10 P1 findings, 6 P2 findings. 24 total (3 already remediated).**

**Top-10 callouts:**
1. [P0] 4 backend API surfaces lack FE consumers (users, scheduled_ingestion, scheduled_export, ropa)
2. [P0] AUTH-007 tenant-context: `user.tenant_id` read in 40+ FE files without centralized hook
3. [P0] No CSP headers configured for frontend
4. [P0] `dangerouslySetInnerHTML` audit needed — XSS surface
5. [P0] No browser-console capture in e2e harness (✅ remediated: 276.B.001)
6. [P1] 6 persona journeys have gaps in e2e coverage
7. [P1] 3 top-level routes lack ErrorBoundary wrapper
8. [P1] No FE consumer for `/notifications/stream/` SSE endpoint
9. [P1] OpenAPI→FE-types drift guard (✅ remediated: 276.B.006)
10. [P2] No Storybook, dark mode, i18n, or onboarding tour

## Methodology
Sources: `InputDocs/UX_MVP_Flows.md`, `InputDocs/User_Journeys.md`, `InputDocs/personas.md`,
`docs/FRONTEND_GUIDE.md`, `specs/mvp-feature-gating/spec.md`.

---

## Section A — Capability Coverage Matrix (276.A.1)

**26 ✅ exposed with FE consumer.** **4 ❌ exposed, NO FE consumer (P0):**
- Users API (`/users/`) — profile/settings management, no FE page
- Scheduled Ingestion (`/scheduled-ingestions/`) — cron orchestration, no dedicated FE
- Scheduled Export (`/scheduled-exports/`) — export orchestration, no FE consumer
- RoPA (`/ropa/`) — Record of Processing Activities, no FE page

**0 orphan FE folders.** Every `frontend/src/features/*/` has a router entry.

→ Remediations: 276.B.100-103 (P0)

---

## Section B — Per-Persona Journey Audit (276.A.2)

| Persona | Status | Gaps |
|---------|--------|------|
| DPO | 🟡 Partial | RoPA journey missing (matches Section A). Consent dashboard has no e2e spec. |
| DE | 🟡 Partial | Scheduled ingestion/export journeys missing. |
| CPO | 🟡 Partial | Billing journey missing. Governance multi-step approval journey missing. |
| DC | 🟡 Partial | Multi-step approval (PENDING_NEXT_APPROVER) journey not covered. |
| MPA | 🟡 Partial | Compliance threshold gate journey missing. KYB onboarding not tested. |
| DEV | ✅ | Developer API keys + capabilities covered. |

→ Remediations: 276.B.104-109 (P1)

---

## Section C — Cross-Cutting UX Heuristics (276.A.3)

- ✅ Loading: `DetailPageSkeleton`/`ListPageSkeleton` consistent
- ✅ Error: `ErrorDisplay` component with retry
- ✅ Empty: `EmptyState` component with CTA
- ✅ A11y: WCAG 2.1 AA target, axe-core CI, 9 a11y spec files
- ✅ CSS custom properties for design tokens
- 🟡 No centralized `usePermissions()` hook — role checks inline
- 🟡 No "Explain-first for errors" UX — error messages are technical codes
- ❌ No dark mode toggle (P2)
- ❌ No i18n/locale/RTL support (P2)

→ Remediations: 276.B.110 (dark mode), 276.B.111 (i18n)

---

## Section D — System-Design Findings (276.A.4)

- ✅ React Query + Zustand (no Redux) — consistent pattern
- ✅ `React.lazy()` on heavy pages with ErrorBoundary on most routes
- ✅ Memory-only token (Phase 11.1)
- ✅ 0 orphan feature folders
- ❌ No centralized `useActiveTenantId()` — 40+ files read `user.tenant_id` directly (P0)
- ❌ 3 top-level routes lack `<ErrorBoundary>`: `ai`, `social`, `cost` (P1)
- ❌ No `storage` event listener for cross-tab token sync (P0)
- ❌ No FE consumer for `/notifications/stream/` SSE (P1)

→ Remediations: 276.B.002 (AUTH-007 sweep — P0), 276.B.112 (ErrorBoundary — P1), 276.B.113 (SSE — P1)

---

## Section E — FE↔BE Contract Findings (276.A.5)

- ✅ OpenAPI drift spec + CI gate + generate-sdk guard (276.B.006)
- ✅ `normalizeError()` canonicalizes error shapes
- ✅ `Retry-After` on search throttling
- ✅ JWT refresh via `tenantSwitchService.ts`
- ❌ Stale `user.tenant_id` reads in 40+ files without central hook (P0 — 276.B.002)
- 🟡 No global 429 retry pattern (P2)
- 🟡 ABAC denial doesn't render policy_id/remediation URL

→ Remediations: 276.B.002 (P0), 276.B.114 (429 pattern — P2)

---

## Section F — Delivery, Infra, Security & Privacy (276.A.6)

- ✅ Vite content hashing for static assets
- ✅ nginx read-only mount pattern verified
- ✅ `.env` guard added (276.B.003)
- ✅ Login/logout `?next=` same-origin validation
- ✅ Memory-only token storage
- ❌ No CSP headers (P0)
- ❌ `dangerouslySetInnerHTML` found — needs audit (P0)
- ❌ No FE Sentry SDK (P1)
- ❌ No FE UI for GDPR data export/erasure (P1)
- ❌ No cookie consent banner (P2)

→ Remediations: 276.B.004 (Sentry — P1), 276.B.115 (CSP — P0), 276.B.116 (XSS — P0), 276.B.117 (GDPR UI — P1), 276.B.118 (consent — P2)

---

## Section G — CI / Tests / Quality Gates (276.A.7)

- ✅ frontend-ci.yml: lint + type-check + unit + OpenAPI drift + generate-sdk drift
- ✅ Chromatic visual regression
- ✅ Bundle-size budget (30KB/5%)
- ✅ axe-core a11y (9 specs)
- ✅ TypeScript `strict: true`
- 🟡 Vitest coverage warn-only (not hard-gated)
- 🟡 e2e cascade at test 111/173 in e3e-b4 — root cause TBD (276.B.005)
- ❌ Browser-console capture missing (✅ 276.B.001 remediated)

→ Remediations: 276.B.001 (✅ done), 276.B.005 (e2e cascade — P1)

---

## Section H — Docs / DX Findings (276.A.8)

- ✅ `InfoHint` component on detail pages
- ✅ `.env` guard (276.B.003)
- ❌ No Storybook (P2)
- ❌ No onboarding tour (P2)
- ❌ No systematic inline help system
- 🟡 README could reference `.env.example` more prominently

→ Remediation: 276.B.119 (Storybook + onboarding — P2)

---

## Findings Catalog

| ID | Sev | Area | Title | Status |
|----|-----|------|-------|--------|
| 276.B.001 | P0 | CI | Browser-console capture in e2e | ✅ DONE |
| 276.B.002 | P0 | FE↔BE | AUTH-007 tenant-context sweep | OPEN |
| 276.B.003 | P1 | DX | .env pre-commit guard | ✅ DONE |
| 276.B.004 | P1 | Sec | FE Sentry SDK + PII filtering | OPEN |
| 276.B.005 | P1 | CI | Cascade-in-e3e-b4 root cause | OPEN |
| 276.B.006 | P1 | FE↔BE | OpenAPI→FE-types drift guard | ✅ DONE |
| 276.B.100 | P0 | Cov | Users API — no FE consumer | OPEN |
| 276.B.101 | P0 | Cov | Scheduled Ingestion — no FE page | OPEN |
| 276.B.102 | P0 | Cov | Scheduled Export — no FE consumer | OPEN |
| 276.B.103 | P0 | Cov | RoPA — no FE page | OPEN |
| 276.B.104 | P1 | Pers | RoPA journey missing (DPO) | OPEN |
| 276.B.105 | P1 | Pers | Scheduled jobs journeys (DE) | OPEN |
| 276.B.106 | P1 | Pers | Billing journey (CPO) | OPEN |
| 276.B.107 | P1 | Pers | Multi-step approval (DC) | OPEN |
| 276.B.108 | P1 | Pers | Compliance gate journey (MPA) | OPEN |
| 276.B.109 | P1 | Pers | KYB onboarding journey (MPA) | OPEN |
| 276.B.110 | P2 | UX | Dark mode toggle | OPEN |
| 276.B.111 | P2 | UX | i18n / locale support | OPEN |
| 276.B.112 | P1 | Sys | ErrorBoundary on 3 routes | OPEN |
| 276.B.113 | P1 | Sys | SSE consumer for notifications | OPEN |
| 276.B.114 | P2 | FE↔BE | Global 429 retry pattern | OPEN |
| 276.B.115 | P0 | Sec | CSP headers | OPEN |
| 276.B.116 | P0 | Sec | dangerouslySetInnerHTML audit | OPEN |
| 276.B.117 | P1 | Priv | GDPR data export/erasure UI | OPEN |
| 276.B.118 | P2 | Priv | Cookie consent banner | OPEN |
| 276.B.119 | P2 | DX | Storybook + onboarding tour | OPEN |

**Severity counts:** P0=8, P1=10, P2=6. Total: 24 findings (3 remediated, 21 open).
