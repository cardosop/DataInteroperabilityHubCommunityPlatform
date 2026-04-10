# JOURNEY-AUTH-004: Unauthenticated Access

**Persona:** Any (anonymous visitor)
**Use Cases:** UC-AUTH-006, UC-DC-001

## Overview

An anonymous visitor browses publicly visible Meshant marketplace
listings without authenticating. They can view asset summaries, quality
badges, and pricing information. When they attempt a privileged action
such as purchasing an asset or downloading data, the platform redirects
them to the authentication wall.

## Journey Steps

1. **Visit public URL** — The visitor navigates to the public
   marketplace URL (e.g., `meshant-internal.example.com` or a tenant-branded
   subdomain). No login is required. The page renders with the public
   header and a search bar.

2. **Browse listings** — The visitor sees a paginated grid of
   [marketplace listings](../concepts/marketplace-listings.md) that have
   been explicitly marked as publicly browsable by their owners. Each
   card shows the asset name, domain tag, quality score badge, and
   pricing tier.

3. **View asset summary** — The visitor clicks a listing card to open
   the detail page. The public detail view displays the asset
   description, schema overview (column names and types), data quality
   score, compliance badge (e.g., "GDPR Compliant"), and the pricing
   model. Sample data previews are visible if the owner enabled them.

4. **Apply search and filters** — The visitor uses full-text
   [search](../concepts/search.md) and faceted filters (domain, data
   format, quality score range, pricing model) to narrow listings.
   Search results respect public visibility rules; private or
   tenant-internal assets never appear.

5. **Hit auth wall on purchase** — When the visitor clicks "Purchase",
   "Download Sample", or "Request Access" the platform intercepts the
   action and redirects to the login page with a `redirect_uri`
   parameter pointing back to the listing. A banner explains that
   authentication is required to complete the action.

6. **Redirect after login** — After authenticating (see
   [JOURNEY-AUTH-002](JOURNEY-AUTH-002.md)) or registering (see
   [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md)) the platform redirects the
   user back to the original listing so they can continue with the
   purchase flow.

## Success Criteria

- All publicly browsable listings are visible without authentication.
- No private or tenant-internal assets leak into public search results.
- Privileged actions (purchase, download, API access) are blocked with
  a clear auth prompt rather than a raw 401 error.
- The `redirect_uri` survives the login/register flow so the user
  returns to the intended page.
- No session tokens or cookies are issued during anonymous browsing.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md), [Search](../concepts/search.md), [Assets](../concepts/assets.md)
- How-To: [Data Consumer Quickstart](../personas/data-consumer/quickstart.md)
- Journeys: [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md) (Register), [JOURNEY-AUTH-002](JOURNEY-AUTH-002.md) (Login), [JOURNEY-DC-001](JOURNEY-DC-001.md) (Discover and Purchase)
