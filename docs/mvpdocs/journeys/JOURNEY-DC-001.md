# JOURNEY-DC-001: Discover and Purchase Asset

**Persona:** [Data Consumer](../personas/data-consumer/)
**Use Cases:** UC-DC-001, UC-DC-002, UC-MKT-003

## Overview

A Data Consumer searches the Meshant marketplace for a dataset that
meets their business needs, evaluates quality and compliance trust
indicators, previews sample data, completes a purchase, and accesses
the asset via download or API. This journey represents the core
marketplace buying experience.

## Journey Steps

1. **Search marketplace** — The authenticated consumer navigates to
   the marketplace and enters a search query in the full-text
   [search](../concepts/search.md) bar. The search indexes asset
   names, descriptions, tags, column names, and semantic annotations.
   Results are ranked by relevance with quality score as a secondary
   sort factor.

2. **Filter by domain and quality** — The consumer uses faceted
   filters to narrow results:

   - **Domain:** Finance, Healthcare, Marketing, IoT, etc.
   - **Data format:** CSV, Parquet, JSON, API.
   - **Quality score:** Minimum threshold (e.g., >= 80/100).
   - **Compliance badge:** GDPR Compliant, PCI-DSS, HIPAA.
   - **Pricing model:** One-off, Subscription, Usage-based.
   - **Freshness:** Updated within last 7/30/90 days.

3. **Preview sample data** — On the listing detail page the consumer
   views a sample data preview (first 100 rows, configurable by the
   asset owner). The preview shows column names, data types, and
   representative values. For API-based assets the consumer sees
   example request/response payloads.

4. **Evaluate trust badges** — The consumer reviews the asset's trust
   indicators displayed prominently on the listing:

   - **Quality score:** Overall DQ score from the latest
     [DQ run](../concepts/dq-runs.md) (e.g., 94/100).
   - **Compliance badge:** Result of the latest
     [compliance scan](../concepts/compliance-runs.md) (e.g., "LOW
     risk — GDPR Compliant").
   - **Contract status:** Whether a [data contract](../concepts/contracts.md)
     is bound and its validation status.
   - **Freshness:** Time since the last data update.
   - **Consumer rating:** Average star rating from other purchasers.

5. **Checkout** — The consumer clicks "Purchase" and selects the
   desired pricing tier. The checkout flow collects payment
   information (or references an existing billing profile), displays
   the license terms, and requires explicit acceptance. On
   confirmation the platform processes the payment and records a
   `marketplace.purchase` [audit event](../concepts/audit-events.md).

6. **Access asset** — After purchase the consumer accesses the asset
   through their preferred method:

   - **Download:** Direct download of the data file (CSV, Parquet)
     from the "My Purchases" dashboard.
   - **API access:** An API key or OAuth token scoped to the
     purchased asset, with endpoint documentation and SDK examples.
   - **Query access:** For virtualized assets, direct SQL or SPARQL
     query access via the platform's query interface.

   Access permissions are enforced by the platform based on the
   purchase license terms and expiry.

## Success Criteria

- Search returns relevant results within 2 seconds.
- Filters correctly narrow results (no false inclusions).
- Sample data preview renders accurately.
- Trust badges reflect the latest DQ and compliance run results.
- Checkout processes payment and grants access within 30 seconds.
- The purchased asset is accessible via the consumer's chosen method.
- All purchase and access events are recorded in the audit trail.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md), [Search](../concepts/search.md), [DQ Runs](../concepts/dq-runs.md), [Billing](../concepts/billing.md)
- How-To: [DC How-To Guides](../personas/data-consumer/how-to/)
- Journeys: [JOURNEY-AUTH-004](JOURNEY-AUTH-004.md) (Unauthenticated Access), [JOURNEY-DPO-002](JOURNEY-DPO-002.md) (Publish Asset)
