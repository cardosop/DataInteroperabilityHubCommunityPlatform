# UC-MKT-ADV-001: Configure Usage-Based Pricing

**Persona:** [Data Product Owner (DPO)](../personas/data-product-owner/index.md) / [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_marketplace_commands_real_api.py::test_usage_pricing`

## Description

A Data Product Owner or Marketplace Platform Admin configures a
usage-based pricing model for a marketplace listing, allowing consumers
to pay per API request, per row downloaded, or per query executed rather
than a flat subscription fee. The platform meters usage in real time and
reports costs to both producer and consumer.

## Preconditions

- A marketplace listing exists in `DRAFT` or `PUBLISHED` status (see
  [UC-AM-002](UC-AM-002.md)).
- The user holds `DATA_PRODUCT_OWNER` or `MARKETPLACE_ADMIN` role.
- The tenant's billing integration is active (see
  [Billing](../../concepts/billing.md)).
- The asset supports the selected metering dimension (e.g., row-level
  access requires a query-capable data layer).

## Steps

1. DPO opens the listing's pricing configuration page or calls
   `PUT /api/v1/marketplace/listings/{listing_id}/pricing` with the
   pricing payload.
2. DPO selects the pricing model: `USAGE_BASED`.
3. DPO configures the metering dimensions:
   - **Per-request:** Each API call to the data access endpoint is
     counted. Price is set as `price_per_request` (e.g., $0.01).
   - **Per-row:** Each row returned in a query response is metered.
     Price is set as `price_per_1000_rows` (e.g., $0.50).
   - **Per-query:** Each distinct query execution is counted. Price is
     set as `price_per_query` (e.g., $0.05).
4. DPO optionally configures:
   - **Free tier:** Number of free requests/rows per billing period.
   - **Volume discounts:** Tiered pricing (e.g., first 10K rows at
     $0.50/1K, next 100K at $0.30/1K).
   - **Spending cap:** Maximum charge per consumer per billing period.
5. DPO saves the pricing configuration. The API validates the payload
   and returns `200 OK`.
6. When a consumer accesses the data, the metering service records each
   event and aggregates usage per billing period.
7. Usage summaries are available to both producer and consumer via
   `GET /api/v1/marketplace/listings/{id}/usage` and
   `GET /api/v1/users/me/usage`.

## Expected Outcome

- The listing's `pricing_model` is set to `USAGE_BASED` with the
  configured dimensions, thresholds, and discount tiers.
- The metering pipeline is active and records usage events in real time.
- Consumers see estimated costs before executing queries (cost preview).
- An `AUDIT_PRICING_CONFIGURED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Billing integration not active | `422` with `BILLING_REQUIRED` code |
| Invalid price value (<= 0) | `422 Unprocessable Entity` |
| Unsupported metering dimension | `422 Unprocessable Entity` |
| Listing not found | `404 Not Found` |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Billing](../../concepts/billing.md)
- Journeys: [JOURNEY-DPO-006 -- Manage Marketplace Listings](../journeys/JOURNEY-DPO-006.md)
- Personas: [Data Product Owner](../personas/data-product-owner/index.md), [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
