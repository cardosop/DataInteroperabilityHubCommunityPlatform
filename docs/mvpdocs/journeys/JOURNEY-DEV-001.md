# JOURNEY-DEV-001: External Developer Marketplace Browsing

**Persona:** [External Developer](../personas/external-developer/)
**Use Cases:** UC-DEV-001, UC-DEV-009
**Phase:** 278 (UX Activation)
**Status:** Implemented (278.H.5, 278.G.5, 278.V.6, 278.V.8)
**E2E:** `trust-signals-listing-card.spec.ts`, `comparison-side-by-side.spec.ts`, `saved-search-crud.spec.ts`
**Status:** Implemented
**Routes:** `/developer`, `/marketplace`

## Overview

An External Developer discovers Meshant's data products through the public
marketplace, evaluates listings via preview and comparison, accesses the
developer portal for SDK documentation and API reference, creates scoped API
keys, and integrates data into their application. Unlike a Data Consumer
(tenant member), the External Developer may browse the marketplace before
belonging to a tenant, registers a service account to obtain API access, and
uses the BaaS (Backend-as-a-Service) surface to programmatically consume data.

## Prerequisites

- The developer must have a Meshant account (self-registration via
  [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md)).
- Programmatic access requires a service account within a tenant or a
  developer-tier tenant provisioned at sign-up.
- API key scoping uses the standard RBAC model (`DEVELOPER` role with
  `read` and `write` scopes configurable per key).

## Journey Steps

1. **Access the developer portal** — From the home dashboard or primary
   navigation, the DEV navigates to `/developer`. The portal surfaces:

   - **SDK documentation** — auto-generated from the OpenAPI spec, rendered
     as interactive API reference with code snippets in Python, JavaScript,
     and cURL.
   - **Plugin listings** — available integrations and connectors (Phase
     278.D reference).
   - **Getting-started guide** — step-by-step walkthrough: register, create
     API key, make first API call.
   - **Authentication patterns** — documentation covering API key headers
     (`Authorization: Bearer msh_...`), JWT exchange, and key rotation.

   The portal content is statically generated from the OpenAPI spec at build
   time and served via the frontend bundle; real-time availability of
   endpoints is reflected via a health-check badge per module.

2. **Browse the marketplace** — The DEV navigates to `/marketplace` to
   discover available data products. The marketplace page shows:

   - **Trust signals** (Phase 278.H.2) on every listing card: KYC-verified
     badge, compliance grade (PASS / WARN / FAIL), average rating,
     last-updated timestamp, sample-availability indicator.
   - **Recommendations** (Phase 278.H.1) — "Popular with developers" and
     "Recently added" sections.
   - **Pricing at a glance** — Free, Free Auto-Approve, Request Approval,
     or Paid with per-unit pricing.

   The DEV can filter by product category (Data, ML Model, API), domain,
   and pricing model. Search uses `SearchablePicker` (Phase 278.G.4) with
   debounced keyword matching across listing title, description, and tags.

3. **Evaluate a listing** — The DEV uses two evaluation surfaces:

   - **Quick preview** (Phase 278.H.5) — `QuickPreviewModal` shows schema
     summary (column names, types, sample values), pricing details,
     compliance badge, data quality score, and average rating — without
     navigating away from the listing list.
   - **Side-by-side comparison** (Phase 278.H.3) — `ComparisonView`
     supports up to 5 listings with rows for pricing, compliance, DQ score,
     schema metrics, last updated, and sample availability. Selection via
     `useBulkSelect` (Phase 278.E.2) checkboxes + `BulkActionBar`.

4. **Save a search for new listings** — The DEV saves a marketplace search
   for their domain of interest (e.g., "financial datasets with SQL
   access") via `SavedSearchButton` (Phase 278.H.4). They configure a daily
   digest notification to receive email alerts when new matching listings
   appear. The saved search is persisted via
   `POST /api/v1/marketplace/saved-searches/` and reachable via
   `?saved=<name>` (Phase 278.E.3).

5. **Access SDK documentation** — From the developer portal, the DEV
   selects their language (Python, JavaScript, or cURL) and reads:

   - **Authentication** — how to include the API key in requests, token
     refresh flow, key rotation procedure.
   - **Error handling** — standard error response format, retry guidance
     (exponential backoff, 429 rate-limit handling), common error codes.
   - **Code examples** — copy-pasteable snippets for every API module:
     assets, marketplace, search, semantic/SPARQL, governance, and billing.
   - **Rate limits** — per-endpoint quota documentation, tenant-level vs
     key-level limits, how to check remaining quota via response headers
     (`X-RateLimit-Remaining`).

   SDK docs are rendered from the OpenAPI spec with language-specific
   syntax highlighting. Each endpoint shows the request schema, response
   schema, and a live "Try it" button (gated on having an active API key).

6. **Generate an API key** — The DEV navigates to the BaaS API key
   management page (`/developer/keys`). The key creation form collects:

   - **Key name** — human-readable label (e.g., "production-pipeline").
   - **Scopes** — `read` (list/get/search), `write` (create/update/delete),
     or both. Scopes are per-module (assets, marketplace, governance, etc.).
   - **Expiry** — configurable from 30 to 365 days; default 90 days per
     [users-and-roles](../concepts/users-and-roles.md). Keys can be set to
     never expire with an explicit confirmation.
   - **Usage tier** — maps to rate-limit quota (free-tier: 100 req/min;
     standard: 1000 req/min; enterprise: custom).

   On creation (`POST /api/v1/baas/api-keys/`), the full key is displayed
   **exactly once** with a prominent copy button and a warning: "Copy this
   key now. You won't be able to see it again." The key is prefixed `msh_`
   for easy identification in logs.

   The DEV can rotate a key via `POST /api/v1/baas/api-keys/{id}/rotate/`,
   which creates a new key with a 24-hour overlap window before the old key
   is revoked. Rotation emits `API_KEY_ROTATED`.

7. **Integrate into application** — The DEV copies code examples from the
   SDK docs into their application:

   ```python
   from meshant_sdk import MeshantClient

   client = MeshantClient(
       base_url="https://api.stagingmeshant-internal.example.com",
       api_key="msh_...",
   )
   assets = client.assets.list(limit=20)
   ```

   They configure the API base URL (`api.stagingmeshant-internal.example.com` for
   staging, `apimeshant-internal.example.com` for production) and make their first
   API call to `GET /api/v1/assets/`. The response includes pagination
   metadata, rate-limit headers, and the asset list.

   The DEV monitors their API usage via `GET /api/v1/baas/usage/` and
   receives quota-exhaustion warnings when usage reaches 80% of the
   tier limit.

8. **Monitor and manage** — The DEV returns to `/developer/keys` to:
   - View all active keys with masked values (`msh_...abc123`).
   - Revoke a key (`DELETE /api/v1/baas/api-keys/{id}/`).
   - Rotate a key before expiry.
   - View usage per key (requests, errors, latency p50/p99).

   Key lifecycle events (`created`, `rotated`, `revoked`, `expired`) are
   recorded in the audit log with 90-day retention.

## Error Handling

- **API key creation failure** — If the DEV lacks the `DEVELOPER` role or
  the tenant has reached its key limit, the form shows an inline error with
  the specific cause and remediation.
- **Key not copied** — The one-time display of the full key is backed by a
  session flag. If the DEV navigates away before copying, they must rotate
  (or delete and re-create) the key.
- **Expired key** — API responses return 401 `API_KEY_EXPIRED`. The SDK
  surfaces this as a typed error with a link to the key management page.
- **Rate limit exceeded** — API returns 429 with `Retry-After` header. The
  SDK's built-in retry handler applies exponential backoff (1s, 2s, 4s,
  max 30s). The DEV sees `X-RateLimit-Remaining` approaching zero as an
  early warning.
- **Marketplace listing unavailable** — If a listing was unpublished
  between preview and access request, the detail page shows a 404 with
  "This listing is no longer available."
- **SDK doc generation failure** — A stale-docs banner appears at the top
  of `/developer` with "Documentation may be out of date — last generated
  YYYY-MM-DD."

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `API_KEY_CREATED` | New API key generated | 90 days |
| `API_KEY_ROTATED` | Key rotation (new key issued, old key has 24h overlap) | 90 days |
| `API_KEY_REVOKED` | Key explicitly revoked | 90 days |
| `API_KEY_EXPIRED` | Key past its expiry date | 30 days |
| `DEVELOPER_PORTAL_ACCESSED` | `/developer` page load | 30 days |
| `SDK_DOCS_VIEWED` | SDK documentation page viewed (module + language) | 30 days |
| `MARKETPLACE_LISTING_PREVIEWED` | Quick-preview modal opened | 30 days |
| `MARKETPLACE_LISTINGS_COMPARED` | Comparison view rendered | 30 days |
| `SEARCH_SAVED` | Saved search created/updated | 90 days |
| `API_CALL_MADE` | Every BaaS API request (sampled 1%) | 30 days |

## Success Criteria

- The DEV finds at least one marketplace listing in their domain within
  60 seconds of landing on `/marketplace`.
- The DEV saves a search with notification preferences configured.
- The DEV accesses SDK documentation for their preferred language and
  copies at least one code example.
- The DEV creates an API key with appropriate scopes and copies the key
  before navigating away.
- The DEV makes a successful API call using the SDK within 10 minutes of
  key creation.
- API key rotation works: new key is active immediately, old key remains
  valid during the 24-hour overlap window, then is revoked.
- Rate-limit headers (`X-RateLimit-Remaining`, `X-RateLimit-Reset`) are
  present on every API response.
- `API_KEY_CREATED` and `DEVELOPER_PORTAL_ACCESSED` audit events are
  emitted within the transaction boundary.

## Related

- Concepts: [Marketplace](../concepts/marketplace-listings.md),
  [Users and Roles](../concepts/users-and-roles.md),
  [Audit Events](../concepts/audit-events.md),
  [Feature Availability](../concepts/feature-availability.md)
- Use Cases: [UC-DEV-001](../use-cases/UC-DEV-001.md) (Install Plugin),
  [UC-DEV-009](../use-cases/UC-DEV-009.md) (Developer Portal)
- Journeys: [JOURNEY-DC-002](JOURNEY-DC-002.md) (Marketplace Discovery —
  same marketplace surface, different end-goal),
  [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md) (Registration)
- SDK: `meshant-sdk` (Python, JavaScript) — authentication, error handling,
  rate-limit retry
- Components: `MarketplaceRecommendations`, `QuickPreviewModal`,
  `ComparisonView`, `SavedSearchButton`, `SearchablePicker`, `BulkActionBar`,
  DevPortal SDK docs renderer
- Phase 278 tasks:
  - 278.H.1 — Recommendations surface on `/marketplace`
  - 278.H.2 — Trust signals at-a-glance on every listing card
  - 278.H.3 — ComparisonView side-by-side (2–5 listings)
  - 278.H.4 — Saved searches + alerts with notification preferences
  - 278.H.5 — Preview-before-buy as primary CTA
  - 278.E.2 — Bulk multi-select hook + BulkActionBar
  - 278.E.3 — Saved filters/views per user
  - 278.G.2 — Inline validation hook (API key creation form)
  - 278.G.4 — SearchablePicker component
  - 278.B.1 — ProductTour (first-time developer onboarding)
