# JOURNEY-DPO-006: Manage Marketplace Listings

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-009, UC-MKT-002

## Overview

A Data Product Owner manages their published marketplace listings over
time: updating descriptions and metadata, adjusting pricing, responding
to consumer reviews, and de-listing assets when they are no longer
available. This journey ensures listings remain accurate, competitive,
and responsive to consumer feedback.

## Journey Steps

1. **View listings dashboard** — The DPO navigates to "My Listings"
   from the main navigation. The dashboard shows all
   [marketplace listings](../concepts/marketplace-listings.md) owned
   by the DPO with key metrics: status (`live`, `pending_review`,
   `revision_requested`, `de-listed`), view count, purchase count,
   average rating, and revenue generated.

2. **Update descriptions** — The DPO edits the listing title,
   description, tags, and sample data preview configuration. Rich
   Markdown is supported in descriptions. Changes to a live listing
   take effect immediately without requiring re-approval unless the
   schema or pricing model changes.

3. **Adjust pricing** — The DPO modifies the pricing model or price
   point. Pricing changes on existing subscriptions apply only to new
   billing cycles; existing subscribers are grandfathered until renewal.
   A pricing change triggers a re-review if the adjustment exceeds the
   tenant's auto-approve threshold (e.g., >50% increase).

4. **Respond to reviews** — Consumers can leave star ratings (1-5) and
   text reviews on listings. The DPO sees reviews on the listing detail
   page and can post public replies. Reported reviews are flagged for
   [Marketplace Admin](../personas/marketplace-platform-admin/) review.

5. **Monitor listing analytics** — The DPO views charts showing daily
   views, search impressions, conversion rate (views to purchases),
   and revenue trend. These metrics help the DPO optimize descriptions,
   tags, and pricing for discoverability and conversion.

6. **De-list if needed** — When an asset is retired or data is no
   longer available the DPO clicks "De-list." The listing state changes
   to `de-listed`, removing it from search results. Existing purchasers
   retain access until their license or subscription expires. An
   `asset.unpublished` [webhook](../concepts/webhooks.md) notifies
   downstream systems, and an [audit event](../concepts/audit-events.md)
   is recorded.

## Success Criteria

- The listings dashboard accurately reflects current status and metrics.
- Description and tag edits are live within seconds.
- Pricing changes respect grandfathering rules for existing subscribers.
- Review responses are visible to all consumers viewing the listing.
- De-listing removes the listing from search but preserves existing
  access rights.
- All changes produce audit events.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md), [Assets](../concepts/assets.md), [Webhooks](../concepts/webhooks.md), [Billing](../concepts/billing.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/)
- Journeys: [JOURNEY-DPO-002](JOURNEY-DPO-002.md) (Publish to Marketplace), [JOURNEY-DC-001](JOURNEY-DC-001.md) (Discover and Purchase)
