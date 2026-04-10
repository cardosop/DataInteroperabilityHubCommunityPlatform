# UC-AM-002: Publish Asset to Marketplace

**Persona:** [Data Product Owner (DPO)](../personas/data-product-owner/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_marketplace_commands_real_api.py::test_publish_asset`

## Description

A Data Product Owner publishes a ready asset to the Meshant marketplace
by configuring pricing, visibility, and access terms, then submitting
it for review. Once approved, the asset appears as a public or
tenant-scoped listing that Data Consumers can discover, preview, and
purchase.

## Preconditions

- The asset is in `READY` status with a valid schema and at least one
  successful DQ run (see [UC-AM-001](UC-AM-001.md)).
- The user holds the `DATA_PRODUCT_OWNER` role in the owning tenant.
- The tenant's marketplace publishing feature is enabled.
- A compliance scan has been completed with no blocking findings (see
  [UC-COMP-001](UC-COMP-001.md)).

## Steps

1. DPO navigates to the asset detail page and clicks "Publish to
   Marketplace" or calls
   `POST /api/v1/marketplace/listings` with
   `{ asset_id, visibility, pricing, description, terms }`.
2. DPO configures the listing:
   - **Visibility:** `PUBLIC` (anyone) or `TENANT` (same-tenant only).
   - **Pricing model:** Free, flat-rate, or usage-based (see
     [UC-MKT-ADV-001](UC-MKT-ADV-001.md)).
   - **Description / tags:** Marketing copy for the listing card.
   - **Terms of use:** License text or link to external terms.
3. DPO optionally enables a data preview (sample rows) for the listing
   (see [UC-MKT-ADV-002](UC-MKT-ADV-002.md)).
4. DPO submits the listing for review by setting
   `status = PENDING_REVIEW`.
5. A Marketplace Platform Admin receives a notification and reviews the
   listing for completeness, compliance, and quality score thresholds.
6. The reviewer approves the listing via
   `PATCH /api/v1/marketplace/listings/{listing_id}`
   with `{ status: "PUBLISHED" }`.
7. The listing is now visible on the marketplace and indexed for search.

## Expected Outcome

- A `MarketplaceListing` record exists with `status = PUBLISHED` linked
  to the source asset.
- The listing is discoverable via `GET /api/v1/marketplace/listings`
  with appropriate filters.
- An `AUDIT_LISTING_PUBLISHED` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- The DPO can view analytics (views, purchases) on the listing
  dashboard.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Asset not in READY status | `422 Unprocessable Entity` |
| Missing DQ run | `422` with `DQ_REQUIRED` code |
| Blocking compliance finding | `422` with `COMPLIANCE_BLOCK` code |
| Duplicate listing for same asset | `409 Conflict` |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Assets](../../concepts/assets.md), [Compliance Runs](../../concepts/compliance-runs.md)
- Journeys: [JOURNEY-DPO-002 -- Publish Asset to Marketplace](../journeys/JOURNEY-DPO-002.md), [JOURNEY-DPO-006 -- Manage Marketplace Listings](../journeys/JOURNEY-DPO-006.md)
- Personas: [Data Product Owner](../personas/data-product-owner/index.md)
