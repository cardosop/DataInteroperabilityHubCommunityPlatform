# API Key Scope Taxonomy

**Status**: Authoritative — all API key scopes defined here.
**Phase**: 278.T.3
**Owners**: Security Team, Developer Experience

## Why this exists

When API key scope enforcement is added to the BaaS surface, each endpoint
MUST declare the scope(s) required to access it. Without a documented taxonomy,
endpoints would be unprotectable — an operator adding scope enforcement later
would have no reference for which endpoint needs which scope. This document
provides that reference.

**Enforcement status (updated 2026-10-15, W11.2)**: scope enforcement IS
active. API keys are ALWAYS scope-checked (no enforcement flag bypass) on the
HasScope surfaces — `ml` (write actions `ml:write`, else `ml:read`), `assets`
writes (`assets:write`; reads are IsAuthenticated-only), `integrations`
marketplace connections + sync jobs + mappings (`integrations:write` plus
role gates), `transformation` (reads `transformation:read`, writes
`transformation:write`), `mesh` writes, `virtualization` writes, and the two
worker-internal surfaces (`scheduled_ingestion:internal` /
`scheduled_export:internal`). Minting is role-bounded (`disallowed_mint_scopes`;
`"*"` PLATFORM_ADMIN-only; worker-internal scopes unmintable; the allowlist
for key-authenticated callers derives from the OWNER's live roles). Endpoints
WITHOUT a scope gate (files, marketplace, jobs, users, search, audit,
billing, governance, compliance, consent, datasets, warehouses, contracts…)
still authenticate API keys as the owner — the recorded OPEN-THREATS class
owned by W11.3. The authoritative cell-by-cell matrix is
`docs/security/adversarial-matrices/w112-auth-session-matrix.md`, verified
by `scripts/tests/test_w112_matrix_veracity.py`.

## Scope naming convention

Scopes follow the pattern `<resource>:<action>`:

| Component | Description | Examples |
|---|---|---|
| `resource` | The API resource area (lowercase, singular) | `assets`, `marketplace`, `ai` |
| `action` | The access level | `read` (GET/HEAD/OPTIONS), `write` (POST/PUT/PATCH/DELETE) |

The wildcard `*` grants unrestricted access and is reserved for
`PLATFORM_ADMIN` and internal service accounts.

## Resource categories

### `ai` — AI / ML inference

| Scope | Endpoints | Phase |
|---|---|---|
| `ai:read` | `GET /api/v1/ai/recommendations/` — list recommendations | 278.H.1 |
| `ai:read` | `GET /api/v1/ai/recommendations/model/` — model metadata | 278.H.1 |
| `ai:read` | `POST /api/v1/ai/recommendations/feedback/` — user feedback (*) | 278.H.1 |

(*) Feedback submission is classified as `read` rather than `write` because
the endpoint records user sentiment without mutating the recommendation model
or its training data.

### `assets` — Data assets

| Scope | Endpoints |
|---|---|
| `assets:read` | `GET /api/v1/assets/`, `GET /api/v1/assets/{id}/` |
| `assets:write` | `POST /api/v1/assets/`, `PUT /api/v1/assets/{id}/`, `DELETE /api/v1/assets/{id}/` |

### `audit` — Audit events

| Scope | Endpoints |
|---|---|
| `audit:read` | `GET /api/v1/audit/audit-events/`, `GET /api/v1/audit/audit-events/{id}/` |

### `billing` — Billing and subscriptions

| Scope | Endpoints |
|---|---|
| `billing:read` | `GET /api/v1/billing/*` |
| `billing:write` | `POST /api/v1/billing/*`, `PUT /api/v1/billing/*` |

### `compliance` — Compliance scans and runs

| Scope | Endpoints |
|---|---|
| `compliance:read` | `GET /api/v1/compliance/*` |
| `compliance:write` | `POST /api/v1/compliance/*` |

### `contracts` — Data contracts (ODPS/ODCS)

| Scope | Endpoints |
|---|---|
| `contracts:read` | `GET /api/v1/contracts/*` |
| `contracts:write` | `POST /api/v1/contracts/*`, `PUT /api/v1/contracts/*` |

### `core` — Cross-cutting infrastructure

| Scope | Endpoints | Phase |
|---|---|---|
| `core:write` | `GET /api/v1/drafts/` — retrieve draft | 278.B.4 |
| `core:write` | `PUT /api/v1/drafts/save/` — upsert draft | 278.B.4 |
| `core:write` | `DELETE /api/v1/drafts/delete/` — delete draft | 278.B.4 |

All draft endpoints are classified as `write` because drafts accept
arbitrary JSON payloads via the PUT upsert path. Even the GET endpoint
is classified as `write` because draft data is user-owned content, not
shared resources.

### `datasets` — Structured datasets

| Scope | Endpoints |
|---|---|
| `datasets:read` | `GET /api/v1/datasets/*` |
| `datasets:write` | `POST /api/v1/datasets/*` |

### `files` — Raw file storage

| Scope | Endpoints |
|---|---|
| `files:read` | `GET /api/v1/files/*` |
| `files:write` | `POST /api/v1/files/*` |

### `governance` — Access requests, retention, DPIA, DSAR

| Scope | Endpoints |
|---|---|
| `governance:read` | `GET /api/v1/governance/*` |
| `governance:write` | `POST /api/v1/governance/*`, `PUT /api/v1/governance/*` |

### `integrations` — Third-party integrations

| Scope | Endpoints |
|---|---|
| `integrations:read` | `GET /api/v1/integrations/*` |
| `integrations:write` | `POST /api/v1/integrations/*` |

### `jobs` — Async job tracking

| Scope | Endpoints |
|---|---|
| `jobs:read` | `GET /api/v1/jobs/*` |
| `jobs:write` | `POST /api/v1/jobs/*` |

### `marketplace` — Marketplace listings and orders

| Scope | Endpoints | Phase |
|---|---|---|
| `marketplace:read` | `GET /api/v1/marketplace/listings/` — browse catalog | — |
| `marketplace:read` | `GET /api/v1/marketplace/listings/{id}/` — listing detail | — |
| `marketplace:read` | `GET /api/v1/marketplace/listings/{id}/preview/` — quick preview | 278.H.5 |
| `marketplace:read` | `GET /api/v1/marketplace/saved-searches/` — list saved searches | 278.H.4 |
| `marketplace:write` | `POST /api/v1/marketplace/saved-searches/` — create saved search | 278.H.4 |
| `marketplace:write` | `PUT /api/v1/marketplace/saved-searches/{id}/` — update saved search | 278.H.4 |
| `marketplace:write` | `DELETE /api/v1/marketplace/saved-searches/{id}/` — delete saved search | 278.H.4 |
| `marketplace:write` | `POST /api/v1/marketplace/orders/` — place order | — |
| `marketplace:read` | `GET /api/v1/marketplace/orders/` — list orders | — |

### `mesh` — Mesh domain management

| Scope | Endpoints |
|---|---|
| `mesh:read` | `GET /api/v1/mesh/*` |
| `mesh:write` | `POST /api/v1/mesh/*`, `PUT /api/v1/mesh/*` |

### `ml` — ML model training and inference

| Scope | Endpoints |
|---|---|
| `ml:read` | `GET /api/v1/ml/*` |
| `ml:write` | `POST /api/v1/ml/*` |

### `transformation` — Data transformation pipelines

| Scope | Endpoints |
|---|---|
| `transformation:read` | `GET /api/v1/transformations/*` |
| `transformation:write` | `POST /api/v1/transformations/*` |

### `users` — User management

| Scope | Endpoints |
|---|---|
| `users:read` | `GET /api/v1/users/*` |
| `users:write` | `POST /api/v1/users/*` |

## Role-to-scope mapping (current)

This is the authoritative mapping from `ROLE_SCOPE_MAP` in
`hub/apps/auth/permissions.py`. API key scopes are a subset of
these role scopes — a key cannot grant more access than the
user's role already permits.

| Role | Scopes |
|---|---|
| `PLATFORM_ADMIN` | `*` (wildcard — all scopes) |
| `TENANT_ADMIN` | `assets:rw`, `contracts:rw`, `datasets:rw`, `compliance:rw`, `governance:rw`, `users:rw`, `billing:rw`, `audit:r`, `files:rw`, `jobs:rw`, `marketplace:rw`, `mesh:rw`, `integrations:rw`, `ml:rw`, `transformation:rw` |
| `DATA_PROVIDER` | `assets:rw`, `contracts:rw`, `datasets:rw`, `files:rw`, `jobs:rw`, `marketplace:rw`, `mesh:rw`, `integrations:rw`, `transformation:rw` |
| `DATA_CONSUMER` | `assets:r`, `datasets:r`, `marketplace:r`, `jobs:r` |
| `AUDITOR` | `audit:r`, `compliance:r`, `governance:r`, `assets:r` |
| `DEVELOPER` | `assets:r`, `datasets:r`, `marketplace:r` |

Key: `r` = `:read`, `rw` = `:read` + `:write`.

## Phase 278 endpoint scope summary

| Endpoint group | Scope | ViewSet / Module |
|---|---|---|
| Recommendations (`/ai/recommendations/`) | `ai:read` | `hub.apps.ai.views.RecommendationsViewSet` |
| Saved searches (`/marketplace/saved-searches/`) | `marketplace:read` (list), `marketplace:write` (create/update/delete) | `hub.apps.marketplace.views.SavedSearchViewSet` |
| Form drafts (`/drafts/`) | `core:write` | `hub.apps.core.draft_views` |
| Quick preview (`/marketplace/listings/{id}/preview/`) | `marketplace:read` | `hub.apps.marketplace.views` (listing detail) |

## Enforcement state and remaining work

Enforcement is ACTIVE on the surfaces listed above (points 1 and 4 landed:
the permission class is `HasScope("domain:action")` / `HasAnyScope(...)` from
`hub/apps/auth/permissions.py`, and `ROLE_SCOPE_MAP` in
`hub/apps/auth/scopes.py` is the minting upper bound — a key cannot grant
scopes beyond the owner's role). Out-of-scope requests return `403
FORBIDDEN` with the standard envelope (`AUTH_FORBIDDEN` / `permission_denied`)
— the planned dedicated `API_KEY_SCOPE_INSUFFICIENT` code is NOT implemented.
Point 2 (the BaaS mint UI checkboxes) remains open. Extending scope gates to
the un-gated endpoint class is owned by W11.3 (access-control matrix).

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-05-14
- **Next review**: When scope enforcement code is implemented
