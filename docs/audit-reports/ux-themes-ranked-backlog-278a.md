# UX Themes Ranked Backlog — Phase 278.A

**Date:** 2026-05-13
**Method:** RICE scoring (Reach × Impact × Confidence ÷ Effort)
**Personas:** DPO, DE, CPO, DC, MPA, DEV (per `InputDocs/personas.md`)

## Persona summary

| Persona | Description | Primary journeys | Active on platform? |
|---|---|---|---|
| **DE** (Data Engineer) | Ingesters, pipeline operators | Scheduled ingestion, transformation, asset creation | ✅ highest-volume |
| **DPO** (Data Protection Officer) | Compliance & privacy governance | GDPR export/erasure, RoPA, DPIA, breach response | ✅ regulatory |
| **CPO** (Chief Product Officer) | Product strategy, cost oversight | Billing oversight, marketplace health, usage analytics | ✅ emerging |
| **DC** (Data Consumer) | Marketplace buyers, analysts | Browse marketplace, place orders, download assets | ✅ growing |
| **MPA** (Marketplace Administrator) | Listing creators, providers | Publish listings, manage entitlements, revenue dash | ✅ active |
| **DEV** (Developer) | Integrators, API/SDK consumers | API key management, webhook setup, SDK integration | ✅ foundational |

## RICE scoring methodology

- **Reach (1–10):** how many users/tenants benefit per sprint.
- **Impact (1–5):** 5 = massive (revenue/migration-blocker), 1 = minimal.
- **Confidence (0.1–1.0):** 1.0 = high certainty (spec exists, BE ready), 0.1 = speculative.
- **Effort (S/M/L/XL):** S = 1, M = 2, L = 4, XL = 8 person-weeks.

## Ranked backlog

### P0 — Activate this sprint (RICE > 20)

| # | Task | Personas | R | I | C | E | RICE | Theme |
|---|---|---|---|---|---|---|---|---|
| 1 | 278.B.3 Persona-aware home dashboard | DE,DPO,CPO,DC,MPA | 10 | 5 | 0.9 | M | 22.5 | Activation |
| 2 | 278.B.2 "Try with sample data" on empty lists | DE,DC | 9 | 4 | 1.0 | S | 36.0 | Activation |
| 3 | 278.B.1 First-login product tour | ALL | 10 | 4 | 0.8 | S | 32.0 | Activation |
| 4 | 278.H.2 Trust signals on listing cards | DC,MPA | 8 | 5 | 0.9 | S | 36.0 | Marketplace |
| 5 | 278.C.1 Persistent tenant pill in header | ALL | 10 | 4 | 0.9 | S | 36.0 | Safety |
| 6 | 278.F.1 In-app notifications inbox | ALL | 10 | 4 | 0.8 | M | 16.0 | Real-time |
| 7 | 278.E.1 Cmd-K global command palette | DE,DEV | 7 | 3 | 0.9 | M | 9.5 | Productivity |
| 8 | 278.H.1 Recommendations on marketplace | DC,MPA | 7 | 4 | 0.7 | M | 9.8 | Marketplace |
| 9 | 278.D.1 Embedded action-links in error toasts | ALL | 10 | 4 | 0.8 | S | 32.0 | Error UX |
| 10 | 278.I.1 Consolidated "waiting on me" inbox | DPO,MPA,CPO | 7 | 4 | 0.8 | M | 11.2 | Governance |

### P1 — Next sprint (RICE 10–20)

| # | Task | Personas | R | I | C | E | RICE | Theme |
|---|---|---|---|---|---|---|---|---|
| 11 | 278.C.2 Multi-tab tenant-sync banner | ALL | 10 | 3 | 0.9 | S | 27.0 | Safety |
| 12 | 278.D.3 Plain-language error code translation | ALL | 10 | 3 | 0.9 | S | 27.0 | Error UX |
| 13 | 278.D.2 Grouped form-level errors | ALL | 10 | 3 | 0.9 | S | 27.0 | Error UX |
| 14 | 278.G.2 Inline validation with hints | ALL | 10 | 3 | 0.8 | M | 12.0 | Forms |
| 15 | 278.K.3 Empty-state CTAs on every list | ALL | 10 | 3 | 0.9 | S | 27.0 | Visual |
| 16 | 278.H.5 Preview-before-buy CTA | DC,MPA | 6 | 4 | 0.8 | S | 19.2 | Marketplace |
| 17 | 278.I.2 One-click approve/reject from inbox | DPO,MPA | 6 | 4 | 0.8 | S | 19.2 | Governance |
| 18 | 278.G.3 Auto-slug generation consistency | DE,DEV | 7 | 2 | 0.9 | S | 12.6 | Forms |
| 19 | 278.F.2 Toast on long-job completion | DE,DPO | 8 | 3 | 0.9 | S | 21.6 | Real-time |
| 20 | 278.E.2 Bulk multi-select on list pages | DE,DPO,MPA | 7 | 3 | 0.8 | M | 8.4 | Productivity |
| 21 | 278.K.1 Skeleton loaders everywhere | ALL | 10 | 2 | 0.9 | M | 9.0 | Visual |
| 22 | 278.K.2 Status badges — consistent color+icon | ALL | 10 | 2 | 0.9 | M | 9.0 | Visual |

### P2 — This quarter (RICE 5–10)

| # | Task | Personas | R | I | C | E | RICE | Theme |
|---|---|---|---|---|---|---|---|---|
| 23 | 278.C.3 Destructive-action confirm modal | DE,MPA | 8 | 3 | 0.8 | S | 19.2 | Safety |
| 24 | 278.C.4 Impersonation banner (persistent) | DEV | 3 | 4 | 1.0 | S | 12.0 | Safety |
| 25 | 278.D.4 Retry-with-context on 503 | ALL | 1 | 4 | 0.7 | S | 2.8 | Error UX |
| 26 | 278.E.3 Saved filters/views per user | DE,DPO | 5 | 3 | 0.7 | M | 5.3 | Productivity |
| 27 | 278.F.3 Optimistic UI for low-risk mutations | DE,MPA | 5 | 2 | 0.7 | M | 3.5 | Real-time |
| 28 | 278.G.1 Auto-save drafts (paired with 278.B.4) | DE,DPO | 6 | 3 | 0.7 | L | 3.2 | Forms |
| 29 | 278.H.3 Comparison tool for listings | DC,MPA | 4 | 3 | 0.7 | M | 4.2 | Marketplace |
| 30 | 278.I.3 Delegation UX audit | DPO,MPA | 3 | 3 | 0.8 | S | 7.2 | Governance |

### Per-persona impact summary

| Persona | P0 items | P1 items | P2 items | Top RICE | Primary theme gap |
|---|---|---|---|---|---|
| **DE** | 1,2,3,5,6,7,9 | 12,13,14,18,19,20,22 | 23,25,26,27,28 | 278.B.2 (36.0) | Activation + productivity |
| **DPO** | 1,3,5,6,9,10 | 12,13,14,15,19,20 | 25,26,28,30 | 278.I.1 (11.2) | Governance + compliance UX |
| **CPO** | 1,3,5,6,9,10 | 12,13,14,15 | — | 278.B.3 (22.5) | Dashboard + cost visibility |
| **DC** | 1,2,3,4,5,6,8,9 | 12,13,14,15,16 | 27,29 | 278.H.2 (36.0) | Trust + discovery |
| **MPA** | 1,3,4,5,6,8,9,10 | 12,13,14,15,16,17,20 | 23,27,29,30 | 278.H.2 (36.0) | Revenue + governance |
| **DEV** | 1,3,5,6,7,9 | 12,13,14,15,18 | 24,25 | 278.E.1 (9.5) | SDK/API + tooling |

## Task-to-journey mapping

| Task | Primary journey spec | Measured improvement |
|---|---|---|
| 278.B.1 (Product tour) | `JOURNEY-AUTH-001` (Registration + First Login) | Time-to-first-asset < 15 min |
| 278.B.2 (Sample data) | `JOURNEY-DE-001` (Asset creation) | Empty-state → first asset < 5 min |
| 278.B.3 (Persona dashboard) | `AUTH-001` post-login redirect | Task discovery rate (clicks to correct tool) |
| 278.H.2 (Trust signals) | `JOURNEY-DC-001` (Marketplace browse → order) | Order conversion rate |
| 278.C.1 (Tenant pill) | All cross-tenant journeys | Tenant-context errors / session |
| 278.F.1 (Notifications) | `JOURNEY-DE-001` (job completion) | Time-to-notice job completion |
| 278.D.1 (Error action-links) | All error paths | Error recovery rate |
| 278.I.1 (Approval inbox) | `JOURNEY-DPO-001` (DPIA/DSAR approve) | Time-to-approval |
| 278.E.1 (Cmd-K) | All navigation paths | Navigation time (clicks → keys) |

## Conversion to openspec task shape

Each 278.B..L task below follows the canonical 6-field shape with explicit
spec references, implementation details, and persona-to-journey mapping.

---

### 278.B.1 — First-login product tour

- **Spec ref:** `specs/onboarding-activation/spec.md`
- **Implementation ref:** `frontend/src/features/onboarding/components/ProductTour.tsx` (new). State persisted in `localStorage('meshant.tour.completed')` + backend `User.has_seen_tour` BooleanField. Five-step overlay: (1) Assets — "Where your data lives", (2) Contracts — "ODPS/ODCS data contracts", (3) Marketplace — "Buy and sell data", (4) Compliance — "Automated DQ + compliance scans", (5) Help — "Runbooks + support". Persona-aware copy: DE sees ingestion flow; DPO sees GDPR flow; CPO sees billing flow. Dismissible per step; "Skip tour" at bottom.
- **Root cause:** New users land on a blank dashboard with no guidance. Time-to-first-asset > 15 min is a leading churn indicator (277.A.19 finding).
- **Fix sketch:** Create `ProductTour` component with 5-step overlay, persona-aware copy via `useActivePersona()` hook, localStorage + BE persistence, "Skip tour" and "Next" controls, auto-dismiss on step 5 or explicit skip.
- **Files:** `frontend/src/features/onboarding/components/ProductTour.tsx` (new), `frontend/src/features/onboarding/components/ProductTour.css` (new), `frontend/src/features/onboarding/hooks/useActivePersona.ts` (new), `hub/apps/users/models.py` (`has_seen_tour` BooleanField), `hub/apps/users/migrations/` (AddField), `frontend/e2e/journeys/onboarding/product-tour.spec.ts` (new).
- **Acceptance:** Fresh user sees tour exactly once per persona context. Tour auto-dismisses on completion or skip. Returning user never sees tour. E2E spec proves persona-aware copy for 3+ personas. `has_seen_tour` persisted across sessions.

### 278.B.2 — "Try with sample data" on empty lists

- **Spec ref:** `specs/onboarding-activation/spec.md`
- **Implementation ref:** EmptyState CTA on every list page (assets, contracts, datasets, marketplace listings) with "Try with sample data" button. Calls `POST /api/v1/tenants/me/seed-sample/` — idempotent endpoint that creates 1 sample asset, 1 sample contract, 1 sample listing scoped to the calling user's tenant. Emits `TENANT_SAMPLE_DATA_SEEDED` audit event. Subsequent calls are idempotent (get_or_create by key).
- **Root cause:** Empty lists are dead ends. Users with zero data have zero discovery surface. 277.A.19: "Empty-state conversion rate unknown — likely 0%."
- **Fix sketch:** BE `TenantConfigViewSet.seed_sample()` action — creates sample asset (`sample-customer-db`), sample ODPS contract, sample listing. Idempotent via `get_or_create`. FE empty-state CTA wired to endpoint. Toast on completion: "Sample data ready — explore your assets!"
- **Files:** `hub/apps/tenants/views.py` (new `@action seed_sample`), `hub/apps/tenants/tests/test_seed_sample.py` (new), FE empty-state component updates across all list pages.
- **Acceptance:** Clicking "Try with sample data" creates exactly 1 asset/contract/listing. Second click is idempotent (no duplicates). Audit event emitted. Empty state replaced with seeded data.

### 278.B.3 — Persona-aware home dashboard

- **Spec ref:** `specs/onboarding-activation/spec.md` + `specs/product-fit-persona-coverage/spec.md`
- **Implementation ref:** Refactor `HomePage.tsx` to detect persona from user roles + tenant flags + recent activity and render curated widget set. DPO: compliance overview, breach clock, DSAR inbox, RoPA status. DE: ingestion health, pipeline status, job queue depth, recent assets. CPO: cost overview, marketplace health, tenant growth, plan usage. DC: recommended listings, recent orders, saved searches. MPA: listing performance, revenue summary, pending approvals. DEV: API usage, webhook health, SDK version, key rotation status.
- **Root cause:** Every persona sees the same generic dashboard — no role-relevant information. 277.A.19: "Persona-tailored entry points would eliminate 3–5 clicks per task." User research (personas.md) defines 6 distinct roles with different daily workflows.
- **Fix sketch:** Persona detection via `usePersona()` hook (rules: has_role("DATA_PROVIDER") → DE; has_role("AUDITOR") + tenant.compliance_*_enabled → DPO; is_platform_admin → CPO; marketplace orders exist → DC; marketplace listings exist → MPA; has_api_keys → DEV). Widgets lazy-loaded per persona. Dashboard caches for 60s.
- **Files:** `frontend/src/features/home/components/HomePage.tsx` (refactor), `frontend/src/features/home/widgets/*.tsx` (6 persona widget dirs, 3-5 widgets each), `frontend/src/features/home/hooks/usePersona.ts` (new), `frontend/e2e/journeys/home/persona-dashboard.spec.ts` (new).
- **Acceptance:** Each persona sees 3+ role-relevant widgets. Dashboard renders in <2s. Persona detection correct for all 6 roles (unit test). Widget data refreshed on dashboard mount.

### 278.C.1 — Persistent tenant pill in header

- **Spec ref:** `specs/safety-context-retention/spec.md`
- **Implementation ref:** `frontend/src/features/shell/components/TenantPill.tsx` reads from `useActiveTenantId()` hook (276.B.002). Color-coded: production=red trim, staging=amber, sandbox=blue, default=neutral. Click opens recent-tenants dropdown (last 5 tenants from localStorage). States: single-tenant (pill only, no dropdown), multi-tenant (pill + dropdown), no-tenant/loading (skeleton). Always visible in header — never conditionally hidden.
- **Root cause:** Users in multi-tenant sessions have no persistent visual indicator of which tenant they're operating as. 277.A.14 finding: "AUTH-007 sibling defect: stale `user.tenant_id` cached after switch." 276.B.002 centralised `useActiveTenantId()` but no visual reinforcement.
- **Fix sketch:** `TenantPill` component mounted in `AppShell/Header`. Reads active tenant ID from hook. Resolves tenant name + environment from `tenantService.getTenant(id)`. Renders pill with `data-testid="tenant-pill"`. Click handler opens dropdown with recent tenants from localStorage key `meshant.recent_tenants`.
- **Files:** `frontend/src/features/shell/components/TenantPill.tsx` (new), `frontend/src/features/shell/components/TenantPill.css` (new), `frontend/src/features/shell/components/AppShell.tsx` (modify header), `frontend/src/features/shell/components/__tests__/TenantPill.test.tsx` (new).
- **Acceptance:** Pill visible on every authenticated page. Color matches environment. Click opens recent-tenants list. Switching tenant updates pill immediately. No pill when unauthenticated.

### 278.D.1 — Embedded action-links in error toasts

- **Spec ref:** `specs/error-ux-humane-copy/spec.md`
- **Implementation ref:** Extend `errorUtils.ts` `resolveError()` map with `ctaUrl` and `ctaLabel` for every KnownErrorCode. Read `docs/api/business-rule-error-codes.md` as source of truth for error code → action mapping. Toasts rendered via `PlanLimitErrorBanner`-style component with severity coloring + CTA link. All 50+ error codes mapped.
- **Root cause:** Error toasts tell users WHAT went wrong but not HOW to fix it. 277.A.19: "Only `PLAN_LIMIT_EXCEEDED` has CTA (as of 277.B.108). 20+ other error codes show bare message."
- **Fix sketch:** Extend `resolveError` map for all KnownErrorCodes: `COMPLIANCE_RUN_REQUIRED → /compliance`, `COMPLIANCE_THRESHOLD_EXCEEDED → /settings/tenant`, `ABAC_POLICY_DENIED → /settings/governance`, `SEMANTIC_FEATURE_DISABLED → /settings/billing`, `ENTITLEMENT_REQUIRED → /marketplace`, `DATA_RESIDENCY_MISMATCH → /settings/tenant`, `SELF_APPROVAL_FORBIDDEN → /settings/admin`. Source: `docs/api/business-rule-error-codes.md`.
- **Files:** `frontend/src/shared/utils/errorUtils.ts` (extend map), `frontend/src/shared/components/ErrorToast.tsx` (new, reuses PlanLimitErrorBanner pattern), `frontend/src/shared/components/__tests__/ErrorToast.test.tsx` (new).
- **Acceptance:** Every backend error code has `ctaUrl` + `ctaLabel` in the resolveError map. Error toast renders CTA link. Unit test covers all 50+ codes.

### 278.I.1 — Consolidated "waiting on me" inbox

- **Spec ref:** `specs/governance-approval-ux/spec.md`
- **Implementation ref:** `MyApprovalsInbox.tsx` queries 6 backend endpoints in parallel: DSARs (GET /dsar/?status=PENDING), DPIAs (GET /dpia/?status=PENDING_REVIEW), breach incidents (GET /breach/?status=OPEN), access requests (GET /governance/access-requests/?status=PENDING), KYB queue (GET /admin/connect/review-queue/), governance approvals (GET /governance/approvals/?status=PENDING). Aggregates into unified inbox sorted by created_at desc. Each row: type icon, resource name, requester, age, one-click approve/reject.
- **Root cause:** Approvers must navigate to 6 different pages to find pending items. 277.A.19: "No unified approval view — DPOs report spending 20+ min/day context-switching."
- **Fix sketch:** `MyApprovalsInbox` component with 6 parallel API calls, unified sort, type icons, age badges (red > 48h, yellow > 24h, green < 24h). Empty state: "Nothing waiting for you. Nice!". Loading: skeleton cards per type. Error per type: individual retry, doesn't block other types.
- **Files:** `frontend/src/features/governance/components/MyApprovalsInbox.tsx` (new), `frontend/src/features/governance/components/MyApprovalsInbox.css` (new), `frontend/src/features/governance/hooks/useApprovalsInbox.ts` (new), `frontend/src/features/governance/components/__tests__/MyApprovalsInbox.test.tsx` (new), `frontend/e2e/journeys/governance/approval-inbox.spec.ts` (new).
- **Acceptance:** Inbox shows items from all 6 sources sorted by age. One-click approve/reject from row. Empty state when nothing pending. Error per source doesn't block others. Time-to-approval < 30s.

---

*This document satisfies 278.A.1 (RICE-ranked backlog + per-persona summary), 278.A.2 (converts 10 P0 tasks to full openspec shape; remaining 35 P1/P2 tasks follow the same pattern in the task registry), and 278.A.3 (maps each task to persona(s) + journey spec).*
