# JOURNEY-DPO-002: Publish Asset to Marketplace

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-DPO-004, UC-MKT-001

## Overview

A Data Product Owner takes an active, quality-validated asset and
publishes it to the Meshant marketplace. This involves confirming
quality gates, selecting a pricing model, configuring visibility,
submitting for review, and receiving approval so the asset becomes
discoverable and purchasable by data consumers.

## Journey Steps

1. **Verify DQ passed** — The DPO opens the asset detail page and
   confirms that the latest [DQ run](../concepts/dq-runs.md) shows a
   passing status. The platform enforces that no asset can be submitted
   for publication without at least one passing DQ run and a compliance
   scan with risk level at or below the tenant threshold.

2. **Set pricing model** — The DPO navigates to the "Marketplace"
   tab and selects a pricing model: **one-off** (single payment for
   permanent access), **subscription** (recurring monthly or annual
   fee), or **usage-based** (per-API-call or per-row metering). They
   set the price point and optional free-tier limits.

3. **Configure visibility** — The DPO chooses the listing visibility:
   **public** (discoverable by anyone, including unauthenticated
   visitors), **marketplace** (visible only to authenticated
   marketplace users), or **restricted** (visible only to invited
   tenants). They also toggle whether a data preview is available.

4. **Submit for review** — The DPO clicks "Submit for Review." The
   platform creates a [marketplace listing](../concepts/marketplace-listings.md)
   in `pending_review` state and notifies the
   [Marketplace Admin](../personas/marketplace-platform-admin/) via
   the admin dashboard and email.

5. **Marketplace Admin reviews** — The admin evaluates the listing
   for policy compliance, description quality, and pricing
   reasonableness. They may request changes (returning the listing
   to `revision_requested`) or approve it.

6. **Receive approval** — On approval the listing transitions to
   `live`. The DPO receives an email and in-app notification. The
   asset state changes from `active` to `published`.

7. **Asset goes live** — The listing appears in marketplace search
   results. An `asset.published` [webhook](../concepts/webhooks.md)
   fires, and an [audit event](../concepts/audit-events.md) is
   recorded. Data consumers can now discover, evaluate, and purchase
   the asset.

## Success Criteria

- The marketplace listing is in `live` state.
- The asset state is `published`.
- Pricing and visibility settings are persisted correctly.
- `asset.published` webhook and audit event are recorded.
- The listing appears in search results within 30 seconds of approval.
- Unauthenticated visitors can see the listing if visibility is `public`.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md), [Assets](../concepts/assets.md), [DQ Runs](../concepts/dq-runs.md), [Webhooks](../concepts/webhooks.md)
- How-To: [DPO How-To Guides](../personas/data-product-owner/how-to/)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Onboard Asset), [JOURNEY-DC-001](JOURNEY-DC-001.md) (Discover and Purchase)
