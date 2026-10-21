# UC-AUTH-004: Unauthenticated Access

**Persona:** [Data Consumer (DC) -- visitor](../personas/data-consumer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_public_listings_no_auth`

## Description

An unauthenticated visitor browses the public marketplace listings,
views asset summaries, and reads community reviews without creating an
account or logging in. This flow is critical for discoverability and
top-of-funnel conversion -- visitors must be able to evaluate the
catalog before committing to registration.

## Preconditions

- At least one asset has been published to the marketplace with
  `visibility = PUBLIC` (see [UC-AM-002](UC-AM-002.md)).
- The public marketplace API endpoints are not behind an authentication
  gate.

## Steps

1. Visitor opens the Meshant marketplace home page or calls
   `GET /api/v1/marketplace/listings?visibility=public` without an
   `Authorization` header.
2. The API returns a paginated list of public listings including title,
   description, tags, quality score, and pricing summary.
3. Visitor clicks a listing to view its detail page, which calls
   `GET /api/v1/marketplace/listings/{listing_id}`.
4. The detail response includes the full description, schema preview,
   sample-data availability flag, provider name, and aggregate rating.
5. Visitor navigates to the reviews tab, which calls
   `GET /api/v1/marketplace/listings/{listing_id}/reviews`.
6. The API returns paginated reviews (author display name, rating,
   comment, date).
7. Visitor attempts an authenticated action (e.g., "Purchase" or "Request
   Access"). The UI redirects to the login/register page, preserving the
   return URL.

## Expected Outcome

- The visitor can browse, search, filter, and view public listing
  details without authentication.
- No JWT is required for the public endpoints; the API responds with
  full listing metadata.
- Authenticated-only actions (purchase, subscribe, review, download)
  are gated and redirect to login.
- No `AUDIT_USER_*` events are recorded for anonymous browsing (only
  anonymized analytics are captured).

## Security Considerations

- Public endpoints enforce rate limiting (100 req/min per IP) to
  prevent scraping.
- Sensitive fields (owner email, internal asset IDs, raw data URLs) are
  stripped from public responses.
- The `sample_data` endpoint requires authentication even when the
  listing is public.

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Assets](../../concepts/assets.md)
- Journeys: [JOURNEY-AUTH-004 -- Unauthenticated Access](../journeys/JOURNEY-AUTH-004.md), [JOURNEY-DC-001 -- Discover and Purchase Asset](../journeys/JOURNEY-DC-001.md)
- Personas: [Data Consumer](../personas/data-consumer/index.md)
