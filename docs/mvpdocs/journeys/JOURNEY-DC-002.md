# JOURNEY-DC-002: Marketplace Discovery Flow

**Persona:** [Data Consumer](../personas/data-consumer/)
**Use Cases:** UC-MKT-ADV-002, UC-DC-002
**Phase:** 278 (UX Activation)
**Status:** Implemented (278.H.2, 278.H.3, 278.H.5, 278.V.6, 278.V.8)
**E2E:** `trust-signals-listing-card.spec.ts`, `comparison-side-by-side.spec.ts`

## Overview

A Data Consumer browses the Meshant marketplace to discover data products
relevant to their domain. They use semantic search, domain and pricing-model
filters, quick-preview, and side-by-side comparison to evaluate listings.
They save promising searches with notification preferences, use bulk-select
to compare listings, and rely on trust signals (KYC status, compliance grade,
average rating) displayed at a glance on every listing card. The flow
culminates in either direct purchase (Free / Free Auto-Approve) or an access
request (Request Approval).

## Journey Steps

1. **Browse marketplace with recommendations** — From the home dashboard or
   primary navigation, the DC navigates to `/marketplace`. The page renders
   three sections:

   - **"You might also like"** — personalized recommendations powered by
     `POST /api/v1/ai/recommendations/`, scoped to the DC's domain activity and
     prior purchase history (Phase 278.H.1).
   - **"Trending in your domain"** — popular listings among tenants in the
     same industry vertical.
   - **Full catalog** — all published listings with pagination, rendered via
     `MarketplaceRecommendations` and the unified listing card component
     (Phase 278.H.1).

   Each listing card displays trust signals at a glance (Phase 278.H.2):
   KYC-verified badge, compliance grade (PASS / WARN / FAIL), average star
   rating, last-updated timestamp, and sample-availability indicator.

2. **Search and filter** — The DC uses the search bar with debounced
   keyword search (`GET /api/v1/marketplace/listings/?q=...`, Phase 278.G.4
   `SearchablePicker` component). Refinement controls:

   - Domain filter (e.g., "healthcare", "financial-services") — multi-select
     picker.
   - Pricing model: Free, Free Auto-Approve, Request Approval.
   - Product category: Data, ML Model, API.
   - Status: Published only (default).
   - Sort: relevance, price (asc/desc), rating, most recent.

   Filters are applied client-side with 300 ms debounce. The active filter
   state is reflected in the URL query string so pages are bookmarkable.

3. **Save a search with alerts** — The DC clicks "Save search" (`SavedSearchButton`)
   to persist their current filter configuration (Phase 278.H.4). A modal
   prompts for a name and optional notification preferences:

   - **Instant** — push notification (in-app) on every new matching listing.
   - **Daily digest** — email summary at 09:00 tenant-local time.
   - **Weekly digest** — email summary every Monday.
   - **None** — manual check only.

   Saved searches are persisted via `POST /api/v1/marketplace/saved-searches/`
   and surfaced under "My Saved Searches" in the sidebar. The saved view is
   also reachable via `?saved=<name>` for URL sharing (Phase 278.E.3).

4. **Quick-preview a listing** — The DC clicks "Preview" on a listing card
   (Phase 278.H.5). `QuickPreviewModal` opens as a focused overlay showing:

   - Schema summary: column names, types, sample values (first 5 rows).
   - Pricing: model type, unit price if applicable, billing cadence.
   - Compliance badge: PASS / WARN / FAIL with last scan date.
   - Average rating and review count.
   - Data quality score (0–100) from the most recent DQ run.

   The modal fetches `GET /api/v1/marketplace/listings/{id}/preview/`
   without full-page navigation. It is keyboard-dismissible (Escape) and
   trap-focused (`role=dialog`, `aria-modal=true`).

5. **Compare listings side-by-side** — The DC selects 2–5 listings using
   row checkboxes powered by `useBulkSelect` (Phase 278.E.2) and clicks
   "Compare" from the `BulkActionBar`. `ComparisonView` (Phase 278.H.3)
   renders a horizontal table with columns per listing and rows for:

   - Pricing model and unit price.
   - Compliance grade + last scan date.
   - Data quality score.
   - Schema metrics: column count, row count, nullability %.
   - Last updated timestamp.
   - Sample available (yes/no).
   - Average rating.

   The comparison view supports keyboard navigation (arrow keys between
   cells) and includes an "Export comparison" button (CSV download).

6. **View listing detail** — The DC clicks through to
   `/marketplace/listings/{id}` for full detail: complete data contract,
   lineage graph, all DQ/compliance run history, terms of use, and the
   order/access-request flow entry point.

7. **Purchase or request access** — Depending on pricing model:

   - **Free** → "Get Access" creates an entitlement immediately via
     `POST /api/v1/marketplace/orders/`. The asset is available instantly
     in the DC's tenant.
   - **Free Auto-Approve** → Same flow, with a form collecting intended
     use and data-retention period.
   - **Request Approval** → Submits an `AccessRequest` via
     `POST /api/v1/governance/access-requests/`. The DC sees a confirmation
     with expected approval SLA. The request appears in the CPO's unified
     approval inbox (JOURNEY-CPO-011).

## Error Handling

- **Empty search results** — The marketplace page renders an illustrated empty
  state ("No listings match your search") with suggested actions: broaden
  filters, clear all filters, browse full catalog by domain.
- **Preview load failure** — `QuickPreviewModal` displays a retryable error
  state with "Try again" button; does not block navigation to the full detail
  page.
- **Comparison limit exceeded** — Selecting >5 listings disables additional
  checkboxes and shows a tooltip: "You can compare up to 5 listings at once."
- **Saved-search save failure** — `SavedSearchButton` shows an inline error
  toast; the dialog stays open so the DC does not lose their name/notification
  configuration.
- **Order failure** — Checkout shows a specific error (insufficient
  permissions, billing required, listing unpublished since page load) and
  suggests remediation.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `MARKETPLACE_LISTINGS_SEARCHED` | Every keyword/filter search | 30 days |
| `MARKETPLACE_LISTING_PREVIEWED` | Quick-preview modal opened | 30 days |
| `MARKETPLACE_LISTINGS_COMPARED` | Comparison view rendered | 30 days |
| `SEARCH_SAVED` | Saved search created/updated | 90 days |
| `ORDER_CREATED` | Free / Free Auto-Approve purchase | 90 days |
| `ACCESS_REQUEST_CREATED` | Request Approval submission | 90 days |

## Success Criteria

- The DC finds at least one relevant listing via search or recommendations
  within 30 seconds of landing on `/marketplace`.
- The DC uses at least one filter to narrow results; filter state is reflected
  in the URL query string.
- The DC previews or compares at least one listing before viewing detail.
- A saved search persists across sessions and triggers the configured
  notification (instant, daily, or weekly).
- The listing detail page shows compliance status, pricing, and data contract
  information.
- Quick preview renders within 1 second of click (client-side cached after
  first fetch).
- Comparison view handles 2–5 listings without horizontal scroll on viewports
  ≥ 1024 px wide.
- `MARKETPLACE_LISTING_PREVIEWED` and `MARKETPLACE_LISTINGS_COMPARED` audit
  events are emitted within the transaction boundary of the corresponding API
  calls.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md),
  [Compliance Badge](../concepts/compliance-runs.md),
  [Audit Events](../concepts/audit-events.md)
- Use Cases: [UC-MKT-ADV-002](../use-cases/UC-MKT-ADV-002.md) (Preview Data
  Before Purchase)
- Journeys: [JOURNEY-DC-001](JOURNEY-DC-001.md) (Discover and Purchase Asset),
  [JOURNEY-CPO-011](JOURNEY-CPO-011.md) (Approval Inbox Flow)
- Components: `MarketplaceRecommendations`, `ComparisonView`,
  `QuickPreviewModal`, `SavedSearchButton`, `SearchablePicker`, `BulkActionBar`
- Phase 278 tasks:
  - 278.H.1 — Recommendations surface on `/marketplace`
  - 278.H.2 — Trust signals at-a-glance on every listing card
  - 278.H.3 — ComparisonView side-by-side (2–5 listings)
  - 278.H.4 — Saved searches + alerts with notification preferences
  - 278.H.5 — Preview-before-buy as primary CTA
  - 278.E.2 — Bulk multi-select hook + BulkActionBar
  - 278.E.3 — Saved filters/views per user
  - 278.G.4 — SearchablePicker component
