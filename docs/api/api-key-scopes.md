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

**Important**: No scope enforcement code is active as of 2026-05-14. This
document is a forward-looking taxonomy. Endpoints are NOT currently gated on
API key scopes (authentication is role-based via JWT/cookie).

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

## Future enforcement

When scope enforcement is activated:

1. Each ViewSet or view function will declare `required_scope` on its
   permission class (e.g., `permission_classes = [IsAuthenticated,
   RequireScope("ai:read")]`).
2. The BaaS API key creation UI will display available scopes as checkboxes
   per resource category.
3. API responses for out-of-scope requests will return `403 FORBIDDEN`
   with error code `API_KEY_SCOPE_INSUFFICIENT`.
4. The `ROLE_SCOPE_MAP` in `hub/apps/auth/permissions.py` will be the
   upper bound — an API key cannot grant scopes beyond the user's role.

Until enforcement is active, this taxonomy serves as the design reference
for scope-aware endpoint categorization.

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-05-14
- **Next review**: When scope enforcement code is implemented
