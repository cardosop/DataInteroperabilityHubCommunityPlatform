# E2E Full Coverage Plan

**Last Updated**: 2026-03-06
**Status**: 📋 **Planning Phase** (Phase 13 in progress)

## Overview

This document provides a comprehensive test matrix and mapping for Phase 10 — Full E2E Coverage (Playwright). The plan covers all journeys, personas, use cases, and features with test dimensions including happy paths, failure scenarios, and edge cases.

**Coverage Targets**:

- ✅ **Journey Coverage**: All 101 journey IDs (4 auth + 90 role-based + 7 marketplace)
- ✅ **Persona Coverage**: All 13 personas (Visitor/Prospect + 12 role-based)
- ✅ **Use Case Coverage**: All ~109 use cases (68+ with dedicated sections)
- ✅ **Feature Coverage**: All 28 feature areas
- ✅ **Test Dimensions**: Happy paths, failure scenarios, edge cases
- ✅ **Real Backend Only**: No mocks/stubs

---

## Test Organization Structure

### Directory Structure

```
frontend/e2e/
├── personas/
│   ├── visitor.spec.ts              # Visitor/Prospect persona (4 auth journeys)
│   ├── data-product-owner.spec.ts   # Data Product Owner (17 journeys)
│   ├── data-engineer.spec.ts        # Data Engineer (14 journeys)
│   ├── compliance-officer.spec.ts   # Compliance Officer (10 journeys)
│   ├── data-consumer.spec.ts        # Data Consumer (15 journeys)
│   ├── tenant-admin.spec.ts         # Tenant Admin (8 journeys)
│   ├── platform-admin.spec.ts       # Platform Admin (10 journeys)
│   ├── external-developer.spec.ts   # External Developer (9 journeys)
│   ├── auditor.spec.ts              # Auditor (6 journeys)
│   ├── data-scientist.spec.ts       # Data Scientist (5 journeys)
│   ├── data-analyst.spec.ts         # Data Analyst (4 journeys)
│   ├── community-manager.spec.ts    # Community Manager (4 journeys)
│   └── data-mesh-domain-owner.spec.ts # Data Mesh Domain Owner (5 journeys)
├── journeys/
│   ├── auth/
│   │   ├── JOURNEY-AUTH-001.spec.ts # First-Time Visitor Registers
│   │   ├── JOURNEY-AUTH-002.spec.ts # User Logs In
│   │   ├── JOURNEY-AUTH-003.spec.ts # User Resets Password
│   │   └── JOURNEY-AUTH-004.spec.ts # Unauthenticated User Accesses Public Resources
│   ├── marketplace/
│   │   ├── JOURNEY-MP-001.spec.ts   # Connect to External Marketplace
│   │   ├── JOURNEY-MP-002.spec.ts   # Publish Asset to Marketplace
│   │   ├── JOURNEY-MP-003.spec.ts   # Import Dataset from Marketplace
│   │   ├── JOURNEY-MP-004.spec.ts   # Sync Assets Bidirectionally
│   │   ├── JOURNEY-MP-005.spec.ts   # Schedule Automatic Sync
│   │   ├── JOURNEY-MP-006.spec.ts   # Manage Marketplace Mappings
│   │   └── JOURNEY-MP-007.spec.ts   # Monitor Sync Jobs
│   └── [other journey files organized by persona prefix]
├── use-cases/
│   ├── auth/           # UC-AUTH-001–004, accept-invitation
│   ├── assets/         # UC-AM-001 (Phase 29.4.1)
│   ├── contracts/      # UC-CM-001, UC-CM-002 (Phase 29.4.1)
│   ├── marketplace/    # UC-MKT-001–004 (Phase 29.4.1)
│   ├── dq/             # UC-DQ-001 (Phase 29.4.1)
│   ├── compliance/     # UC-COMP-001 (Phase 29.4.1)
│   ├── odps/           # UC-ODPS-001–003 (Phase 29.4.2)
│   ├── integrations/   # UC-INT-001, UC-INT-002 (Phase 29.4.2)
│   └── webhooks/       # UC-WH-001 (Phase 29.4.2)
├── design-system/                  # Phase 29.0 — Meshant design system
│   ├── meshant-brand.spec.ts       # APP_NAME in Header, Landing, Login, document title
│   ├── meshant-layout.spec.ts      # .app-main max-width, sidebar 240px, content centered
│   └── meshant-typography.spec.ts  # body font Inter, headings use tokens
├── features/
│   ├── auth.spec.ts                 # Auth feature coverage
│   ├── contracts.spec.ts            # Contracts feature coverage
│   ├── assets.spec.ts               # Assets feature coverage
│   ├── datasets.spec.ts             # Datasets feature coverage
│   ├── data-quality.spec.ts         # Data Quality feature coverage
│   ├── compliance.spec.ts           # Compliance feature coverage
│   ├── marketplace.spec.ts          # Marketplace feature coverage
│   ├── governance.spec.ts           # Governance feature coverage
│   ├── search.spec.ts               # Search feature coverage
│   ├── observability.spec.ts       # Observability feature coverage
│   ├── workflows.spec.ts           # Workflows feature coverage
│   ├── lineage.spec.ts             # Lineage feature coverage
│   ├── versioning.spec.ts           # Versioning feature coverage
│   ├── baas.spec.ts                 # BaaS feature coverage
│   ├── integrations.spec.ts         # Integrations feature coverage
│   ├── jobs.spec.ts                 # Jobs feature coverage
│   ├── files.spec.ts                # Files feature coverage
│   ├── semantic.spec.ts             # Semantic feature coverage
│   ├── ai.spec.ts                   # AI feature coverage
│   ├── ml.spec.ts                   # ML feature coverage
│   ├── social.spec.ts               # Social feature coverage
│   ├── data-mesh.spec.ts            # Data Mesh feature coverage
│   ├── virtualization.spec.ts       # Virtualization feature coverage
│   ├── scheduled-ingestion.spec.ts  # Scheduled Ingestion feature coverage
│   ├── webhooks.spec.ts             # Webhooks feature coverage
│   ├── audit.spec.ts                # Audit feature coverage
│   └── health.spec.ts               # Health feature coverage
├── cross-cutting/
│   ├── failure-scenarios-tests.spec.ts  # Phase 29.4.3: ≥7 real tests (session expiry, invalid JSON, 404, 403, API error, network error, 429)
│   └── edge-cases-tests.spec.ts          # Phase 29.4.4: ≥5 real tests (empty submit, max length, special chars, pagination, unicode)
└── dimensions/
    ├── happy-paths.spec.ts          # Phase 29.4.5: Aggregator; imports use-cases + journeys
    ├── failure-scenarios.spec.ts   # Failure scenarios (imports cross-cutting/failure-scenarios-tests)
    ├── edge-cases.spec.ts          # Edge cases (imports cross-cutting/edge-cases-tests)
    ├── network-failures.spec.ts    # Cross-cutting: offline, connection refused, timeout (Phase 8.7.1)
    ├── timeout-handling.spec.ts    # Cross-cutting: long-running ops, retry behavior (Phase 8.7.2)
    ├── rate-limit.spec.ts          # Cross-cutting: 429 handling, backoff (Phase 8.7.3)
    └── concurrent-operations.spec.ts # Cross-cutting: race conditions, optimistic locking (Phase 8.7.4)
```

---

## Route → Journey → Use Case Mapping

Every route in `frontend/src/app/routes/routes.tsx` SHALL have at least one success E2E; where applicable, failure/edge coverage. Backend-unavailable or capability-gated routes: mark with skip or assert `/unavailable` / "not available" (see [Backend-not-implemented handling](#backend-not-implemented-handling)).

| Route                                                                                                      | Journey(s)                                       | Use Case(s)   | Success E2E                                        | Failure/Edge                             | Notes                                                        |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------- | -------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------ |
| `/login`                                                                                                   | JOURNEY-AUTH-002                                 | UC-AUTH-002   | ✅ JOURNEY-AUTH-002                                | ✅ invalid/empty credentials, rate limit |                                                              |
| `/public`                                                                                                  | JOURNEY-AUTH-004                                 | UC-AUTH-004   | ✅ auth-visitor                                    | —                                        | Public resources                                             |
| `/register`                                                                                                | JOURNEY-AUTH-001                                 | UC-AUTH-001   | ✅ auth-visitor                                    | Registration disabled, duplicate email   |                                                              |
| `/password-reset`, `/password-reset/confirm`, `/auth/password-reset/confirm`                               | JOURNEY-AUTH-003                                 | UC-AUTH-003   | ✅ auth-visitor (when MailHog)                     | Reset disabled                           |                                                              |
| `/accept-invitation`, `/auth/accept-invitation`                                                            | JOURNEY-TA-001                                   | —             | ✅ use-cases/auth/accept-invitation.spec.ts       | ✅ invalid/expired token, no token, edge |                                                              |
| `/unavailable`                                                                                             | —                                                | —             | Assert redirect or message                         | —                                        | Backend-not-implemented flows show this                      |
| `/403`                                                                                                     | —                                                | —             | ⏳                                                 | —                                        | Forbidden page                                               |
| `/` (home)                                                                                                 | —                                                | —             | ✅ login-app-shell                                 | —                                        |                                                              |
| `/assets`, `/assets/create`, `/assets/:id`                                                                 | JOURNEY-DPO-001                                  | UC-AM-001     | ✅ phase2 → JOURNEY-DPO-001                        | ⏳                                       |                                                              |
| `/datasets`, `/datasets/create`, `/datasets/:id`, `:id/versions`                                           | JOURNEY-DPO-001                                  | UC-AM-001     | ✅ phase2 → JOURNEY-DPO-001                        | ⏳                                       |                                                              |
| `/files`                                                                                                   | JOURNEY-DPO-001                                  | —             | ✅ features/files.spec.ts                         | ✅ 403 unauthenticated, empty state       |                                                              |
| `/contracts`, `/:id`, `/:id/edit`, `/:id/link-odps`                                                        | JOURNEY-DPO-001, JOURNEY-DE-001, JOURNEY-DPO-016 | UC-CM-\*      | ✅ contracts-odps-routes                           | ✅ non-existent id, link-odps edge       | Phase 13 — 15.3                                              |
| `/marketplace`, `/listings/:id`, `/publish`, `/orders`, `/entitlements`                                    | JOURNEY-DPO-002, JOURNEY-DC-001, JOURNEY-DC-015  | UC-MKT-\*     | ✅ marketplace-dc-routes                           | ✅ non-existent listing, governance/403  | Phase 13 — 15.4                                              |
| `/integrations/connections`, `/sync-jobs`, `/mappings`                                                     | JOURNEY-MP-001, JOURNEY-TA-008                   | UC-INT-\*     | ✅ integrations-jobs-webhooks                      | —                                        | Phase 13 — 15.7                                              |
| `/odps`, `/odps/upload`, `/odps/:id`                                                                       | JOURNEY-DPO-015, JOURNEY-DPO-016, JOURNEY-DE-014 | UC-ODPS-\*    | ✅ contracts-odps-routes                           | ✅ non-existent id                       | Phase 13 — 15.3                                              |
| `/dq`, `/dq/runs/:id`                                                                                      | JOURNEY-DPO-001, JOURNEY-DE-003                  | UC-DQ-\*      | ✅ dq-compliance-governance                        | ✅ non-existent run id                   | Phase 13 — 15.5                                              |
| `/compliance`, `/compliance/runs/:id`                                                                      | JOURNEY-CPO-001                                  | UC-COMP-\*    | ✅ dq-compliance-governance                        | ✅ non-existent run id                   | Phase 13 — 15.5                                              |
| `/mesh`, `/mesh/topology`, `/mesh/create`, `/mesh/:id`                                                     | JOURNEY-DMO-001, JOURNEY-DMO-003, JOURNEY-TA-005 | UC-MESH-\*    | ✅ mesh-search-ai-routes                           | Skip or /unavailable if backend limited  | Phase 13 — 15.6                                              |
| `/virtualization`, `/virtualization/create`, `/:id`, `/:id/edit`                                           | JOURNEY-DE-009, JOURNEY-DA-003, JOURNEY-DC-010   | UC-VIRT-\*    | ✅ mesh-search-ai-routes, phase6-mesh-virtualization (ODBC 26.8, 28.4.2) | —                                        | Phase 13 — 15.6; ODBC create/execute (API + UI) in phase6     |
| `/search`                                                                                                  | JOURNEY-DC-006, JOURNEY-DS-001                   | UC-AI-\*      | ✅ mesh-search-ai-routes                           | —                                        | Phase 13 — 15.6                                              |
| `/semantic`                                                                                                | JOURNEY-DC-014                                   | UC-SEM-\*     | ✅ features/semantic.spec.ts                      | ✅ /unavailable when capability-gated     | Capability: semantic.sparql                                  |
| `/ai/search`                                                                                               | JOURNEY-DC-006, JOURNEY-DS-001                   | UC-AI-\*      | ✅ mesh-search-ai-routes                           | Assert /unavailable if gated             | Phase 13 — 15.6; Capability: ai.natural-language-search      |
| `/ai/schema-matching`                                                                                      | JOURNEY-DPO-007                                  | UC-AI-\*      | ✅ mesh-search-ai-routes                           | Assert /unavailable if gated             | Phase 13 — 15.6; Capability: ai.schema-matching              |
| `/communities` (Phase 27.2; `/social` redirects)                                                            | JOURNEY-DC-008, JOURNEY-DPO-009                  | UC-SOCIAL-\*  | ✅ admin-audit-settings-routes, social.spec.ts      | Load or /unavailable                     | Phase 13 — 15.8; Capability: social.communities; **Note**: `/social` redirects to `/communities` (Phase 27.2) |
| `/assets/:id` (Community section, Phase 27.1)                                                               | JOURNEY-DC-008, JOURNEY-DPO-009                  | UC-SOCIAL-001, UC-SOCIAL-002 | ✅ social.spec.ts, JOURNEY-DC-008, JOURNEY-DPO-009 | Rate/review on asset page (27.3.2)       | Phase 27.1; **Asset social section**: ratings, reviews, Community on asset detail page; social.ratings, social.reviews |
| `/developer`                                                                                               | JOURNEY-DEV-001, JOURNEY-DEV-009                 | UC-DEV-\*     | ✅ admin-audit-settings-routes                     | Load or /unavailable                     | Phase 13 — 15.8; Capability: developer.plugins               |
| `/baas`                                                                                                    | —                                                | UC-BAAS-\*    | ✅ admin-audit-settings-routes                     | Load or /unavailable                     | Phase 13 — 15.8; Capability: baas.api-keys                   |
| `/ml`                                                                                                      | JOURNEY-DS-003                                   | —             | ✅ admin-audit-settings-routes                     | Load or /unavailable                     | Phase 13 — 15.8; Capability: ml.models                       |
| `/observability`                                                                                           | —                                                | UC-OBS-ADV-\* | ✅ admin-audit-settings-routes                     | —                                        | Phase 13 — 15.8                                              |
| `/jobs`, `/jobs/:id`                                                                                       | JOURNEY-DE-006                                   | —             | ✅ integrations-jobs-webhooks                      | ✅ non-existent job id                   | Phase 13 — 15.7                                              |
| `/webhooks` (list, create, :id, :id/edit)                                                                  | —                                                | UC-WH-\*      | ✅ integrations-jobs-webhooks                      | —                                        | Phase 13 — 15.7                                              |
| `/governance`, `/governance/access-requests/*`                                                             | JOURNEY-TA-006                                   | UC-GOV-\*     | ✅ marketplace-dc-routes, dq-compliance-governance | 403 or content                           | Phase 13 — 15.4, 15.5; Role: TENANT_ADMIN, PLATFORM_ADMIN    |
| `/governance/retention`, `/governance/retention/new`, `/governance/retention/:id`, `/governance/retention/:id/edit` | JOURNEY-CPO-003, JOURNEY-CPO-009                  | UC-GOV-\*     | ✅ governance-retention-crud                       | Role/redirect                           | Phase 15.5.3; Role: TENANT_ADMIN, PLATFORM_ADMIN             |
| `/audit`, `/audit/:id`                                                                                     | JOURNEY-AUD-001                                  | UC-AUDIT-\*   | ✅ admin-audit-settings-routes                     | 403 or content                           | Phase 13 — 15.8; Role: AUDITOR, TENANT_ADMIN, PLATFORM_ADMIN |
| `/scheduled-ingestions/*`                                                                                  | JOURNEY-DE-006                                   | UC-SI-\*      | ✅ integrations-jobs-webhooks                      | Role/redirect                            | Phase 13 — 15.7; Role: DATA_PROVIDER, etc.                   |
| `/scheduled-exports`, `/scheduled-exports/create`, `/scheduled-exports/:id`, `/scheduled-exports/:id/edit` | JOURNEY-EXPORT-001, JOURNEY-EXPORT-002           | UC-SE-\*      | ✅ scheduled-export-journey                        | Role/redirect, Prefect unavailable       | Phase 22; Role: DATA_PROVIDER, TENANT_ADMIN, PLATFORM_ADMIN  |
| `/admin`                                                                                                   | JOURNEY-PA-_, JOURNEY-MPA-_                      | —             | ✅ admin-audit-settings-routes                     | 403 or content                           | Phase 13 — 15.8; Role: TENANT_ADMIN, PLATFORM_ADMIN          |
| `/settings/sessions`, `/settings/api-keys`                                                                 | —                                                | —             | ✅ admin-audit-settings-routes                     | —                                        | Phase 13 — 15.8                                              |

### Backend-not-implemented handling

For use cases listed as **Not implemented (Backend)** in `docs/USE_CASES.md` (e.g. UC-CM-004, UC-CPO-006, UC-CPO-007, UC-CPO-008, UC-CPO-010, UC-DE-011, UC-DEV-002, UC-TA-007, UC-SOCIAL-005), E2E SHALL either:

- **Skip** the test with `test.skip()` and a comment referencing the UC ID, or
- **Assert** that the app shows `/unavailable` or a clear "not available" message when the user attempts the flow.

Do not mock missing endpoints.

---

## Route Spec → Journey Mapping (Phase 6.11.6)

This section documents **which route specs cover which journeys** for traceability. Route specs provide broader route coverage (Success/Failure/Edge); dedicated journey specs provide end-to-end user-flow traceability per `docs/USER_JOURNEYS.md`.

| Route Spec File | Routes Covered | Journeys Covered | Notes |
| --------------- | -------------- | ---------------- | ----- |
| `journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` | `/mesh`, `/virtualization`, `/search`, `/ai/search`, `/ai/schema-matching` | DMO-001, DMO-002, DMO-003, DMO-004, DMO-005, DPO-007, DPO-013, DE-009, DA-003, DA-004, DC-006, DC-010, DS-001, DS-002, TA-005 | Mesh domains, virtualization, NL search, AI schema matching; capability-gated |
| `phase6-mesh-virtualization.spec.ts` | `/virtualization/create` (ODBC source), `/virtualization/:id` (execute) | DE-009, DA-003, DC-010 | ODBC create via API (Phase 26.8), ODBC create via UI form (Phase 28.4.2); real backend only |
| `journeys/contracts-odps/contracts-odps-routes.spec.ts` | `/contracts`, `/contracts/:id/edit`, `/contracts/:id/link-odps`, `/odps`, `/odps/upload`, `/odps/:id` | DPO-001, DPO-015, DPO-016, DPO-017, DE-001, DE-002, DE-014 | Contract-first, ODPS product-first, link-odps flows |
| `journeys/marketplace-dc/marketplace-dc-routes.spec.ts` | `/marketplace`, `/marketplace/listings/:id`, `/marketplace/orders`, `/marketplace/entitlements`, `/governance` | DPO-002, DC-001, DC-002, DC-003, DC-004, DC-005, DC-011, DC-012, DC-014, DC-015, TA-006, CPO-004 | Discover, purchase, entitlements; governance access-requests |
| `journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` | `/admin`, `/audit`, `/audit/:id`, `/settings/sessions`, `/settings/api-keys`, `/developer`, `/baas`, `/ml`, `/communities`, `/observability` | PA-001–PA-010, MPA-001–MPA-009, AUD-001, DEV-001, DEV-009, DS-003, DC-008, DPO-009, TA-* (admin), CM-* | Role-gated; capability-gated for developer, baas, ml, communities |
| `features/social.spec.ts` | `/communities`, `/social` (redirects to `/communities`), `/assets/:id` (Community section) | DC-008, DPO-009 | Phase 27.1–27.3; /social → /communities; asset social section (ratings, reviews); rate/review E2E |
| `journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` | `/integrations/connections`, `/integrations/sync-jobs`, `/integrations/mappings`, `/jobs`, `/jobs/:id`, `/webhooks`, `/scheduled-ingestions` | DE-006, DE-010, TA-008, MP-001, MP-002, MP-003, MP-004, MP-005, MP-006, MP-007 | Integrations, sync jobs, mappings, jobs, webhooks, scheduled ingestion |
| `journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` | `/dq`, `/dq/runs/:id`, `/compliance`, `/compliance/runs/:id`, `/governance` | DPO-001, DPO-004, DE-003, DE-004, CPO-001, CPO-002, TA-006 | DQ runs, compliance runs, access requests |
| `journeys/governance-retention/governance-retention-crud.spec.ts` | `/governance/retention`, `/governance/retention/new`, `/governance/retention/:id`, `/governance/retention/:id/edit` | CPO-003, CPO-009, TA-006 | Retention policy CRUD; role-gated (TENANT_ADMIN, PLATFORM_ADMIN) |
| `journeys/scheduled-export/scheduled-export-journey.spec.ts` | `/scheduled-exports`, `/scheduled-exports/create`, `/scheduled-exports/:id`, `/scheduled-exports/:id/edit` | EXPORT-001, EXPORT-002 | Journey spec (not route-only); full flow coverage |
| `design-system/meshant-brand.spec.ts`, `meshant-layout.spec.ts`, `meshant-typography.spec.ts` | `/`, `/login` (brand, layout, typography) | Phase 28.7 Meshant design system | Phase 29.0; design tokens, brand, layout, typography |

### Route Spec vs Journey Spec Strategy (6.11.6.2)

**Confirmed preference**:

- **Dedicated journey specs** (`JOURNEY-*.spec.ts`): Provide **traceability** to `docs/USER_JOURNEYS.md`. Each journey has a spec file with Success/Failure/Edge dimensions. Persona aggregators import these for persona-level runs.
- **Route specs** (`*-routes.spec.ts`): Provide **broader route coverage**. They verify that routes load (or show 403/unavailable when gated) without duplicating full journey flows. Route specs are the primary source for "every route has at least one E2E" (see [Route → Journey → Use Case Mapping](#route--journey--use-case-mapping)).
- **Both coexist**: Journey specs = user-flow traceability; route specs = route reachability and failure/edge coverage at the route level. No duplication of journey flows in route specs; route specs focus on route load, 404, 403, capability-gate behavior.

---

## Journey Coverage Matrix

> **Source of truth**: Journey titles and IDs in this document SHALL match `docs/USER_JOURNEYS.md`. When in doubt, refer to USER_JOURNEYS.md as the authoritative source.

### Authentication Journeys (4)

| Journey ID       | Title                                          | Test File                                | Status                                                                              |
| ---------------- | ---------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------- |
| JOURNEY-AUTH-001 | First-Time Visitor Registers                   | `journeys/auth/JOURNEY-AUTH-001.spec.ts` | ✅ Success/Failure (empty, duplicate email)/Edge (empty submit, display name)       |
| JOURNEY-AUTH-002 | User Logs In                                   | `journeys/auth/JOURNEY-AUTH-002.spec.ts` | ✅ Success/Failure (invalid, empty)/Edge (rate limit, special chars)                |
| JOURNEY-AUTH-003 | User Resets Password                           | `journeys/auth/JOURNEY-AUTH-003.spec.ts` | ✅ Success/Failure (unknown email, invalid token)/Edge; MailHog; skip when SMTP off |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | `journeys/auth/JOURNEY-AUTH-004.spec.ts` | ✅ Implemented (Success/Failure/Edge)                                               |
| —                | /unavailable, /403                             | `journeys/auth/unavailable-403.spec.ts`  | ✅ Phase 13 — 15.1.5                                                                |
| —                | Cross-cutting: 404, 403, session               | `cross-cutting/404-403-session.spec.ts`  | ✅ Phase 13 — 15.9.2                                                                |

### Data Product Owner Journeys (17)

| Journey ID      | Title                                             | Test File                              | Status                                |
| --------------- | ------------------------------------------------- | -------------------------------------- | ------------------------------------- |
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow             | `journeys/dpo/JOURNEY-DPO-001.spec.ts` | ✅ Implemented (migrated from phase2) |
| JOURNEY-DPO-002 | Publish Asset to Marketplace                      | `journeys/dpo/JOURNEY-DPO-002.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-003 | Manage Asset Lifecycle                            | `journeys/dpo/JOURNEY-DPO-003.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-004 | Monitor Asset Quality                             | `journeys/dpo/JOURNEY-DPO-004.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-005 | Configure Data Contracts                          | `journeys/dpo/JOURNEY-DPO-005.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-006 | Manage Marketplace Listings                       | `journeys/dpo/JOURNEY-DPO-006.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-007 | Use AI Schema Matching for Asset Creation         | `journeys/dpo/JOURNEY-DPO-007.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-008 | Create Transformation Pipeline for Asset          | `journeys/dpo/JOURNEY-DPO-008.spec.ts` | ⏸️ Deferred (see [E2E_TEST_SKIP_DOCUMENTATION.md](E2E_TEST_SKIP_DOCUMENTATION.md)) |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews                  | `journeys/dpo/JOURNEY-DPO-009.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-010 | Publish Asset with Usage-Based Pricing            | `journeys/dpo/JOURNEY-DPO-010.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-011 | Assign Data Stewards                              | `journeys/dpo/JOURNEY-DPO-011.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-012 | Join Data Community                               | `journeys/dpo/JOURNEY-DPO-012.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-013 | Configure Data Mesh Domain                        | `journeys/dpo/JOURNEY-DPO-013.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-014 | Monitor Asset Reliability Score                   | `journeys/dpo/JOURNEY-DPO-014.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-015 | Create ODPS Product (Product-First Flow)          | `journeys/dpo/JOURNEY-DPO-015.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-016 | Link ODPS to ODCS Contract (Technical-First Flow) | `journeys/dpo/JOURNEY-DPO-016.spec.ts` | ⏳ Pending                            |
| JOURNEY-DPO-017 | Export ODPS Product                               | `journeys/dpo/JOURNEY-DPO-017.spec.ts` | ⏳ Pending                            |

### Data Engineer Journeys (14)

Aligned with `docs/USER_JOURNEYS.md`.

| Journey ID     | Title                                  | Test File                            | Status     |
| -------------- | -------------------------------------- | ------------------------------------ | ---------- |
| JOURNEY-DE-001 | Programmatic Contract-First Onboarding | `journeys/de/JOURNEY-DE-001.spec.ts` | ⏳ Pending |
| JOURNEY-DE-002 | Set Up Scheduled Ingestion (if applicable) | `journeys/de/JOURNEY-DE-002.spec.ts` | ⏳ Pending |
| JOURNEY-DE-003 | Configure Data Quality Checks          | `journeys/de/JOURNEY-DE-003.spec.ts` | ⏳ Pending |
| JOURNEY-DE-004 | Set Up Compliance Scanning             | `journeys/de/JOURNEY-DE-004.spec.ts` | ⏳ Pending |
| JOURNEY-DE-005 | Integrate External Data Source         | `journeys/de/JOURNEY-DE-005.spec.ts` | ⏳ Pending |
| JOURNEY-DE-006 | Monitor Data Pipeline Health           | `journeys/de/JOURNEY-DE-006.spec.ts` | ⏳ Pending |
| JOURNEY-DE-007 | Create Transformation Pipeline         | `journeys/de/JOURNEY-DE-007.spec.ts` | ⏸️ Deferred (see [E2E_TEST_SKIP_DOCUMENTATION.md](E2E_TEST_SKIP_DOCUMENTATION.md)) |
| JOURNEY-DE-008 | Integrate AI Schema Matching into Workflow | `journeys/de/JOURNEY-DE-008.spec.ts` | ⏳ Pending |
| JOURNEY-DE-009 | Set Up Data Virtualization             | `journeys/de/JOURNEY-DE-009.spec.ts` | ⏳ Pending |
| JOURNEY-DE-010 | Configure Connector for Data Source    | `journeys/de/JOURNEY-DE-010.spec.ts` | ⏳ Pending |
| JOURNEY-DE-011 | Set Up Reverse ETL                     | `journeys/de/JOURNEY-DE-011.spec.ts` | ⏳ Pending |
| JOURNEY-DE-012 | Create Custom Plugin                   | `journeys/de/JOURNEY-DE-012.spec.ts` | ⏳ Pending |
| JOURNEY-DE-013 | Configure Data Mesh Domain             | `journeys/de/JOURNEY-DE-013.spec.ts` | ⏳ Pending |
| JOURNEY-DE-014 | Create ODPS via API                    | `journeys/de/JOURNEY-DE-014.spec.ts` | ⏳ Pending |

### Compliance Officer Journeys (10)

**Persona**: Compliance Officer. Journey IDs use **CPO** (Compliance Officer) per `docs/USER_JOURNEYS.md`. Do not use "CO". CPO-002 through CPO-005 added for backend alignment (FRONTEND_BACKEND_GAP_REMEDIATION_PLAN).

| Journey ID      | Title                                  | Test File                              | Status     |
| --------------- | -------------------------------------- | -------------------------------------- | ---------- |
| JOURNEY-CPO-001 | Review Compliance for Asset            | `journeys/cpo/JOURNEY-CPO-001.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-002 | Generate Compliance Report             | `journeys/cpo/JOURNEY-CPO-002.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-003 | Configure Retention Policies           | `journeys/cpo/JOURNEY-CPO-003.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-004 | Review Access Requests                 | `journeys/cpo/JOURNEY-CPO-004.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-005 | Audit Access Logs                      | `journeys/cpo/JOURNEY-CPO-005.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-006 | Configure Automated Compliance         | `journeys/cpo/JOURNEY-CPO-006.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-007 | Set Up GDPR Right to be Forgotten      | `journeys/cpo/JOURNEY-CPO-007.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-008 | Manage Consent Tracking                | `journeys/cpo/JOURNEY-CPO-008.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-009 | Configure Automated Retention Policies | `journeys/cpo/JOURNEY-CPO-009.spec.ts` | ⏳ Pending |
| JOURNEY-CPO-010 | Review AI Auto-Classification Results  | `journeys/cpo/JOURNEY-CPO-010.spec.ts` | ⏳ Pending |

### Data Consumer Journeys (15)

Aligned with `docs/USER_JOURNEYS.md`. DC-002 through DC-005 are implementation slices of the DC-001 flow (search → view details → purchase → access).

| Journey ID     | Title                                    | Test File                            | Status     |
| -------------- | ---------------------------------------- | ------------------------------------ | ---------- |
| JOURNEY-DC-001 | Discover and Purchase Marketplace Asset  | `journeys/dc/JOURNEY-DC-001.spec.ts` | ⏳ Pending |
| JOURNEY-DC-002 | Search Marketplace                       | `journeys/dc/JOURNEY-DC-002.spec.ts` | ⏳ Pending |
| JOURNEY-DC-003 | View Asset Details                       | `journeys/dc/JOURNEY-DC-003.spec.ts` | ⏳ Pending |
| JOURNEY-DC-004 | Purchase Asset                           | `journeys/dc/JOURNEY-DC-004.spec.ts` | ⏳ Pending |
| JOURNEY-DC-005 | Access Purchased Asset                   | `journeys/dc/JOURNEY-DC-005.spec.ts` | ⏳ Pending |
| JOURNEY-DC-006 | Use Natural Language Search              | `journeys/dc/JOURNEY-DC-006.spec.ts` | ⏳ Pending |
| JOURNEY-DC-007 | Create Transformation Pipeline for Data  | `journeys/dc/JOURNEY-DC-007.spec.ts` | ⏳ Pending |
| JOURNEY-DC-008 | Rate and Review Asset                    | `journeys/dc/JOURNEY-DC-008.spec.ts` | ⏳ Pending |
| JOURNEY-DC-009 | Join Data Community                      | `journeys/dc/JOURNEY-DC-009.spec.ts` | ⏳ Pending |
| JOURNEY-DC-010 | Query Virtual Dataset                    | `journeys/dc/JOURNEY-DC-010.spec.ts` | ⏳ Pending |
| JOURNEY-DC-011 | Purchase Asset with Usage-Based Pricing  | `journeys/dc/JOURNEY-DC-011.spec.ts` | ⏳ Pending |
| JOURNEY-DC-012 | Preview Data Before Purchase             | `journeys/dc/JOURNEY-DC-012.spec.ts` | ⏳ Pending |
| JOURNEY-DC-013 | Use Asset Recommendations                | `journeys/dc/JOURNEY-DC-013.spec.ts` | ⏳ Pending |
| JOURNEY-DC-014 | Discover ODPS Products (Semantic Search) | `journeys/dc/JOURNEY-DC-014.spec.ts` | ⏳ Pending |
| JOURNEY-DC-015 | Purchase ODPS Product (Marketplace)      | `journeys/dc/JOURNEY-DC-015.spec.ts` | ⏳ Pending |

### Other Persona Journeys

Aligned with `docs/USER_JOURNEYS.md`. Journey ID prefixes: TA (Tenant Admin), PA/MPA (Platform Admin), DEV (External Developer), AUD (Auditor), DS (Data Scientist), DA (Data Analyst), CM (Community Manager), DMO (Data Mesh Domain Owner).

**Tenant Admin (8 journeys)**: JOURNEY-TA-001 to JOURNEY-TA-008 — `journeys/ta/` (TA-002 through TA-004 added for backend alignment)
**Platform Admin (10 journeys)**: JOURNEY-PA-001, JOURNEY-MPA-001 to JOURNEY-MPA-009, JOURNEY-PA-010 — `journeys/pa/` (MPA-001 through MPA-004 added for backend alignment)
**External Developer (9 journeys)**: JOURNEY-DEV-001 to JOURNEY-DEV-009 — `journeys/dev/`
**Auditor (6 journeys)**: JOURNEY-AUD-001 to JOURNEY-AUD-006 — `journeys/aud/`
**Data Scientist (5 journeys)**: JOURNEY-DS-001 to JOURNEY-DS-005 — `journeys/ds/`
**Data Analyst (4 journeys)**: JOURNEY-DA-001 to JOURNEY-DA-004 — `journeys/da/`
**Community Manager (4 journeys)**: JOURNEY-CM-001 to JOURNEY-CM-004 — `journeys/cm/`
**Data Mesh Domain Owner (5 journeys)**: JOURNEY-DMO-001 to JOURNEY-DMO-005 — `journeys/dmo/`

### Marketplace Journeys (7)

Marketplace journeys (MP-001–MP-007) are imported by the Data Product Owner persona per Phase 6.11.5 design (`personas/data-product-owner.spec.ts`). Per `docs/MARKETPLACE_USER_JOURNEYS.md`, MP-001 persona is DPO+Tenant Admin; MP-001 is also imported by `personas/tenant-admin.spec.ts`.

| Journey ID     | Title                           | Test File                                     | Status     |
| -------------- | ------------------------------- | --------------------------------------------- | ---------- |
| JOURNEY-MP-001 | Connect to External Marketplace | `journeys/marketplace/JOURNEY-MP-001.spec.ts` | ⏳ Pending |
| JOURNEY-MP-002 | Publish Asset to Marketplace    | `journeys/marketplace/JOURNEY-MP-002.spec.ts` | ⏳ Pending |
| JOURNEY-MP-003 | Import Dataset from Marketplace | `journeys/marketplace/JOURNEY-MP-003.spec.ts` | ⏳ Pending |
| JOURNEY-MP-004 | Sync Assets Bidirectionally     | `journeys/marketplace/JOURNEY-MP-004.spec.ts` | ⏳ Pending |
| JOURNEY-MP-005 | Schedule Automatic Sync         | `journeys/marketplace/JOURNEY-MP-005.spec.ts` | ⏳ Pending |
| JOURNEY-MP-006 | Manage Marketplace Mappings     | `journeys/marketplace/JOURNEY-MP-006.spec.ts` | ⏳ Pending |
| JOURNEY-MP-007 | Monitor Sync Jobs               | `journeys/marketplace/JOURNEY-MP-007.spec.ts` | ⏳ Pending |

### Scheduled Export Journeys (2)

| Journey ID         | Title                                | Test File                                                    | Status         |
| ------------------ | ------------------------------------ | ------------------------------------------------------------ | -------------- |
| JOURNEY-EXPORT-001 | Create and Run Scheduled Export      | `journeys/scheduled-export/scheduled-export-journey.spec.ts` | ✅ Implemented |
| JOURNEY-EXPORT-002 | Monitor and Troubleshoot Export Runs | `journeys/scheduled-export/scheduled-export-journey.spec.ts` | ✅ Implemented |

**Total**: 103 journeys (4 auth + 90 role-based + 7 marketplace + 2 scheduled export)

---

## Persona Coverage Matrix

| Persona                | Test File                                 | Journeys                 | Status         |
| ---------------------- | ----------------------------------------- | ------------------------ | -------------- |
| Visitor / Prospect     | `personas/visitor.spec.ts`                | 4 (AUTH-001 to AUTH-004) | ✅ Implemented |
| Data Product Owner     | `personas/data-product-owner.spec.ts`     | 24 (17 DPO + 7 MP)       | ⏳ Pending     |
| Data Engineer          | `personas/data-engineer.spec.ts`          | 14                       | ⏳ Pending     |
| Compliance Officer     | `personas/compliance-officer.spec.ts`     | 10                       | ⏳ Pending     |
| Data Consumer          | `personas/data-consumer.spec.ts`          | 15                       | ⏳ Pending     |
| Tenant Admin           | `personas/tenant-admin.spec.ts`           | 9 (8 TA + MP-001)        | ⏳ Pending     |
| Platform Admin         | `personas/platform-admin.spec.ts`         | 10                       | ⏳ Pending     |
| External Developer     | `personas/external-developer.spec.ts`     | 9                        | ⏳ Pending     |
| Auditor                | `personas/auditor.spec.ts`                | 6                        | ⏳ Pending     |
| Data Scientist         | `personas/data-scientist.spec.ts`         | 5                        | ⏳ Pending     |
| Data Analyst           | `personas/data-analyst.spec.ts`           | 4                        | ⏳ Pending     |
| Community Manager      | `personas/community-manager.spec.ts`      | 4                        | ⏳ Pending     |
| Data Mesh Domain Owner | `personas/data-mesh-domain-owner.spec.ts` | 5                        | ⏳ Pending     |

**Total**: 13 personas

---

## Use Case Coverage Matrix

### Authentication & Access Use Cases (4)

| Use Case ID | Title                                          | Test File                            | Status         |
| ----------- | ---------------------------------------------- | ------------------------------------ | -------------- |
| UC-AUTH-001 | User Registers (Self-Service Sign-Up)          | `use-cases/auth/UC-AUTH-001.spec.ts` | ✅ Implemented |
| UC-AUTH-002 | User Logs In                                   | `use-cases/auth/UC-AUTH-002.spec.ts` | ✅ Implemented |
| UC-AUTH-003 | User Resets Password                           | `use-cases/auth/UC-AUTH-003.spec.ts` | ✅ Implemented |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | `use-cases/auth/UC-AUTH-004.spec.ts` | ✅ Implemented |

### Other Use Case Categories

**Asset Management (~8 use cases)**: UC-AM-001 to UC-AM-008
**Contract Management (~6 use cases)**: UC-CM-001 to UC-CM-006
**Data Quality (~6 use cases)**: UC-DQ-001 to UC-DQ-006
**Compliance (~6 use cases)**: UC-COMP-001 to UC-COMP-006
**Marketplace (~8 use cases)**: UC-MKT-001 to UC-MKT-008
**AI/ML (~10 use cases)**: UC-AI-001 to UC-AI-010
**Social Features (~6 use cases)**: UC-SOCIAL-001 to UC-SOCIAL-006
**Data Mesh (~5 use cases)**: UC-MESH-001 to UC-MESH-005
**Virtualization (~4 use cases)**: UC-VIRT-001 to UC-VIRT-004
**Advanced Marketplace (~5 use cases)**: UC-MKT-ADV-001 to UC-MKT-ADV-005
**Advanced Governance (~4 use cases)**: UC-GOV-ADV-001 to UC-GOV-ADV-004
**Advanced Observability (~4 use cases)**: UC-OBS-ADV-001 to UC-OBS-ADV-004
**Integration Ecosystem (~5 use cases)**: UC-INT-001 to UC-INT-005
**Developer Experience (~4 use cases)**: UC-DEV-001 to UC-DEV-004
**Transformation (~8 use cases)**: UC-TRANS-001 to UC-TRANS-008
**Lineage (~4 use cases)**: UC-LINEAGE-001 to UC-LINEAGE-004
**Versioning (~3 use cases)**: UC-VER-001 to UC-VER-003
**BaaS (~4 use cases)**: UC-BAAS-001 to UC-BAAS-004
**ODH Integration (~4 use cases)**: UC-ODH-001 to UC-ODH-004
**ODPS (~6 use cases)**: UC-ODPS-001 to UC-ODPS-006
**Semantic (~4 use cases)**: UC-SEM-001 to UC-SEM-004
**Scheduled Ingestion (~3 use cases)**: UC-SI-001 to UC-SI-003
**Webhooks (~3 use cases)**: UC-WH-001 to UC-WH-003
**Audit (~3 use cases)**: UC-AUDIT-001 to UC-AUDIT-003

**Total**: ~109 use cases

---

## Feature Coverage Matrix

| Feature             | Test File                              | Use Cases                        | Status         |
| ------------------- | -------------------------------------- | -------------------------------- | -------------- |
| Auth                | `features/auth.spec.ts`                | UC-AUTH-001 to UC-AUTH-004       | ✅ Implemented |
| Contracts           | `features/contracts.spec.ts`           | UC-CM-001 to UC-CM-006           | ⏳ Pending     |
| ODPS                | `features/odps.spec.ts`                | UC-ODPS-001 to UC-ODPS-006       | ⏳ Pending     |
| Assets              | `features/assets.spec.ts`              | UC-AM-001 to UC-AM-008           | ⏳ Pending     |
| Datasets            | `features/datasets.spec.ts`            | Related use cases                | ⏳ Pending     |
| Data Quality        | `features/data-quality.spec.ts`        | UC-DQ-001 to UC-DQ-006           | ⏳ Pending     |
| Compliance          | `features/compliance.spec.ts`          | UC-COMP-001 to UC-COMP-006       | ⏳ Pending     |
| Marketplace         | `features/marketplace.spec.ts`         | UC-MKT-001 to UC-MKT-008         | ⏳ Pending     |
| Governance          | `features/governance.spec.ts`          | UC-GOV-ADV-001 to UC-GOV-ADV-004 | ⏳ Pending     |
| Search              | `features/search.spec.ts`              | Related use cases                | ⏳ Pending     |
| Observability       | `features/observability.spec.ts`       | UC-OBS-ADV-001 to UC-OBS-ADV-004 | ⏳ Pending     |
| Workflows           | `features/workflows.spec.ts`           | Related use cases                | ⏳ Pending     |
| Lineage             | `features/lineage.spec.ts`             | UC-LINEAGE-001 to UC-LINEAGE-004 | ⏳ Pending     |
| Versioning          | `features/versioning.spec.ts`          | UC-VER-001 to UC-VER-003         | ⏳ Pending     |
| BaaS                | `features/baas.spec.ts`                | UC-BAAS-001 to UC-BAAS-004       | ⏳ Pending     |
| Integrations        | `features/integrations.spec.ts`        | UC-INT-001 to UC-INT-005         | ⏳ Pending     |
| Jobs                | `features/jobs.spec.ts`                | Related use cases                | ⏳ Pending     |
| Files               | `features/files.spec.ts`               | Related use cases                | ⏳ Pending     |
| Semantic            | `features/semantic.spec.ts`            | UC-SEM-001 to UC-SEM-004         | ⏳ Pending     |
| AI                  | `features/ai.spec.ts`                  | UC-AI-001 to UC-AI-010           | ⏳ Pending     |
| ML                  | `features/ml.spec.ts`                  | Related use cases                | ⏳ Pending     |
| Communities (Phase 27.2) | `features/social.spec.ts`              | UC-SOCIAL-001 to UC-SOCIAL-006   | ⏳ Pending     |
| Data Mesh           | `features/data-mesh.spec.ts`           | UC-MESH-001 to UC-MESH-005       | ⏳ Pending     |
| Virtualization      | `features/virtualization.spec.ts`      | UC-VIRT-001 to UC-VIRT-004       | ⏳ Pending     |
| Scheduled Ingestion | `features/scheduled-ingestion.spec.ts` | UC-SI-001 to UC-SI-003           | ⏳ Pending     |
| Webhooks            | `features/webhooks.spec.ts`            | UC-WH-001 to UC-WH-003           | ⏳ Pending     |
| Audit               | `features/audit.spec.ts`               | UC-AUDIT-001 to UC-AUDIT-003     | ⏳ Pending     |
| Health              | `features/health.spec.ts`              | Health check endpoints           | ⏳ Pending     |

**Total**: 28 feature areas

---

## Test Dimensions

### 1. Happy Paths

**File**: `dimensions/happy-paths.spec.ts`

Tests that verify the primary success scenario for each journey/use case:

- All steps complete successfully
- Expected outcomes are achieved
- No errors occur
- Performance targets are met

### 2. Failure Scenarios

**File**: `dimensions/failure-scenarios.spec.ts`

Tests that verify error handling:

- Invalid input validation
- API error responses (400, 401, 403, 404, 429, 500, 503)
- Network failures
- Timeout handling
- Error messages are user-friendly and don't expose sensitive data

### 3. Edge Cases

**File**: `dimensions/edge-cases.spec.ts`

Tests that verify boundary conditions:

- Empty/null values
- Maximum/minimum values
- Concurrent operations
- Race conditions
- Large payloads
- Special characters and encoding
- Timezone handling
- Pagination boundaries

### 4. Cross-cutting failure specs (Phase 8.7)

Dedicated dimension specs for cross-cutting failure behavior; runnable with real backend (network/timeout tests use Playwright route to simulate transport failure only; no backend response mocks).

| File | Scope | Run |
|------|--------|-----|
| `dimensions/network-failures.spec.ts` | Offline, connection refused, request abort handling | `npm run test:e2e -- e2e/dimensions/network-failures.spec.ts` |
| `dimensions/timeout-handling.spec.ts` | Long-running operations, retry behavior, slow API | `npm run test:e2e -- e2e/dimensions/timeout-handling.spec.ts` |
| `dimensions/rate-limit.spec.ts` | 429 handling, backoff, rate limit message in UI | `npm run test:e2e -- e2e/dimensions/rate-limit.spec.ts` |
| `dimensions/concurrent-operations.spec.ts` | Race conditions, optimistic locking, double-submit | `npm run test:e2e -- e2e/dimensions/concurrent-operations.spec.ts` |
| `design-system/meshant-*.spec.ts` (Phase 29.0) | Meshant brand, layout, typography | `npm run test:e2e -- e2e/design-system/ --project=chromium` or `./scripts/run_meshant_tests.sh` |

---

## Implementation Strategy

### Phase 1: Foundation (Current)

- ✅ Authentication journeys (4)
- ✅ Basic E2E pipeline setup
- ✅ Test fixtures and helpers

### Phase 2: Core Journeys (Next)

- ⏳ Data Product Owner journeys (17)
- ⏳ Data Engineer journeys (14)
- ⏳ Data Consumer journeys (15)

### Phase 3: Extended Coverage

- ⏳ Remaining persona journeys
- ⏳ Marketplace journeys (7)
- ⏳ Use case coverage

### Phase 4: Feature Coverage

- ⏳ Feature-specific tests
- ⏳ Cross-feature integration tests

### Phase 5: Test Dimensions

- ⏳ Failure scenarios
- ⏳ Edge cases
- ⏳ Performance tests

---

## E2E Execution Order and Batching (CI)

E2E tests are split into batches for CI and iterate-and-fix cycles. Run order matters: auth/setup first, then routes, then persona journeys.

| Batch | Scope | Run Command | ~Tests |
|-------|-------|--------------|--------|
| 1 | Auth, setup, cross-cutting, a11y | `npm run test:e2e:batch1` | ~79 |
| 2 | Routes (contracts, marketplace, dq, mesh, integrations, admin) | `npm run test:e2e:batch2` | ~121 |
| 3 | DPO journeys | `npm run test:e2e:batch3` | ~253 |
| 4 | Auth, DC, DE journeys | `npm run test:e2e:batch4` | ~376 |
| 5 | TA, PA, Dev, Aud journeys | `npm run test:e2e:batch5` | ~352 |
| 6 | CPO, DS, DMO, DA, CM, Marketplace journeys | `npm run test:e2e:batch6` | ~364 |
| 7 | Features, phase specs, governance, scheduled | `npm run test:e2e:batch7` | ~400 |

**Full suite**: `npm run test:e2e` (runs all batches via `e2e-detect-api.sh`).

**Faster iteration**: `E2E_PROJECT=chromium npm run test:e2e:batch1` (single project, ~27 tests).

**List batches**: `npm run test:e2e:batches:list`.

---

## Test Execution Strategy

### Parallel Execution

- Tests organized by persona can run in parallel (different users/tenants)
- Tests within a persona run sequentially to avoid conflicts
- Use `--workers=1` per persona, but run personas in parallel

### Test Data Management

- Each test creates its own test data (no shared state)
- Cleanup after each test
- Use unique identifiers (timestamps, UUIDs) to avoid conflicts

### Real Backend Requirements

- All tests use real backend API (no mocks/stubs)
- Backend services must be running (api-service, postgres, redis-cache)
- Optional services (mailhog, worker-service) for specific tests

---

## Coverage Metrics

### Current Coverage

- **Journeys**: 4/101 (4%)
- **Personas**: 1/13 (8%)
- **Use Cases**: 4/~109 (4%)
- **Features**: 1/28 (4%)

### Target Coverage

- **Journeys**: 101/101 (100%)
- **Personas**: 13/13 (100%)
- **Use Cases**: ~109/~109 (100%)
- **Features**: 28/28 (100%)

---

## References

- **[User Journeys](docs/USER_JOURNEYS.md)** - Complete journey documentation
- **[User Personas](docs/USER_PERSONAS.md)** - Persona profiles and capabilities
- **[Use Cases](docs/USE_CASES.md)** - Complete use case catalog
- **[Features](docs/FEATURES.md)** - Feature documentation
- **[Marketplace User Journeys](docs/MARKETPLACE_USER_JOURNEYS.md)** - Marketplace integration journeys
- **[E2E Pipeline Documentation](./E2E_PIPELINE_DOCUMENTATION.md)** - E2E test infrastructure

---

**Last Updated**: 2026-02-17
**Status**: 📋 **Planning Phase** - Ready for implementation
