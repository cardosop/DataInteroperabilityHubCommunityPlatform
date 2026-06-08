# UC-MKT-ADV-005: Receive AI-Powered Listing Recommendations

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md)
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.H.1`

## Description

A Data Consumer views AI-powered marketplace listing recommendations on
the marketplace page. Two sections are rendered: "You might also like"
(cross-sell based on prior purchases and browsing history) and "Trending
in your domain" (popularity-weighted recency in the consumer's industry
vertical). Each recommendation card shows the listing title, domain,
match reasons, and a match score. The consumer can provide thumbs-up or
thumbs-down feedback on each recommendation.

## Preconditions

- The user is authenticated and has visited the marketplace at least once
  (for cross-sell recommendations to have activity data).
- The AI recommendations endpoint (`POST /api/v1/ai/recommendations/`)
  is deployed and healthy.
- At least one published listing exists in the catalog.

## Steps

1. DC navigates to `/marketplace`. The `MarketplaceRecommendations`
   widget renders below the filter bar.
2. DC sees the "Trending in your domain" section with up to 5 listings.
3. DC sees the "You might also like" section with up to 5 cross-sell
   listings.
4. Each card shows the listing title, domain tag, match score bar, and
   recommendation reasons (e.g., "Similar schema", "Same domain").
5. DC clicks a recommendation card to navigate to the listing detail
   page.
6. DC clicks 👍 or 👎 on a card to provide feedback. The feedback is
   submitted via `POST /api/v1/ai/recommendations/feedback/`.
7. If no domain activity exists, only the "Trending" section renders
   (global popularity). If both sections are empty, the widget hides
   entirely.

## Expected Outcome

- At least one recommendation section renders with listing cards.
- Clicking a card navigates to `/marketplace/listings/{id}`.
- Feedback submission returns `200 OK` and the thumbs button briefly
  shows a selected state.
- `meshant.recommendations.impression`, `.click`, and `.feedback`
  CustomEvents fire on window (Phase 278.T.2 telemetry).

## Error Handling

| Condition | Expected Response |
|---|---|
| Recommendations service unavailable | Widget gracefully hides (ErrorBoundary → null) |
| Recommendations endpoint returns 500 | Widget hides; marketplace page renders normally |
| No listings in catalog | Widget shows empty state or hides |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md)
- Use Cases: [UC-MKT-ADV-002](UC-MKT-ADV-002.md) (Preview Data Before Purchase)
- Journeys: [JOURNEY-DC-002](../journeys/JOURNEY-DC-002.md) (Marketplace Discovery Flow)
- Components: `MarketplaceRecommendations`, `ErrorBoundary`
- Phase 278 tasks: `278.H.1` (Recommendations surface), `278.H.2` (Trust signals)
- E2E: `trust-signals-listing-card.spec.ts` (278.V.6)
