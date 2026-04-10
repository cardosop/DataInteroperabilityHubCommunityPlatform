# UC-MKT-ADV-002: Preview Data Before Purchase

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_marketplace_commands_real_api.py::test_data_preview`

## Description

A Data Consumer previews sample rows from a marketplace listing before
committing to a purchase or subscription. The preview provides enough
data to evaluate schema, content quality, and relevance while protecting
the producer's intellectual property by limiting the number of rows
returned and optionally masking sensitive columns.

## Preconditions

- The marketplace listing has `preview_enabled = true` (configured by
  the DPO during publication; see [UC-AM-002](UC-AM-002.md)).
- The user is authenticated (preview is not available to anonymous
  visitors to prevent scraping).
- The underlying asset has at least one data version uploaded.

## Steps

1. DC navigates to the listing detail page and clicks "Preview Data",
   or calls
   `GET /api/v1/marketplace/listings/{listing_id}/preview`.
2. The API checks that the user is authenticated and that the listing
   has previews enabled.
3. The preview engine reads the asset's latest data version and applies
   the producer-configured preview rules:
   - **Row limit:** Maximum number of sample rows (default 25, max 100).
   - **Column masking:** Sensitive columns identified by the compliance
     scan may be partially masked (e.g., emails show `j***@example.com`).
   - **Randomization:** Rows are sampled randomly (not always the first
     N) to give a representative picture.
4. The API returns `200 OK` with:
   - `columns[]`: Array of column metadata (name, type, description).
   - `rows[]`: Array of sample row objects.
   - `total_row_count`: Total rows in the full dataset.
   - `preview_row_count`: Number of rows in this preview.
   - `masked_columns[]`: List of columns with masking applied.
5. DC reviews the preview in a table view on the UI, inspecting column
   types, data patterns, and overall quality.
6. DC decides whether to proceed with purchase/subscription or move on
   to another listing.

## Expected Outcome

- The consumer sees a representative sample of the dataset with schema
  metadata.
- Sensitive columns are masked according to the producer's compliance
  configuration.
- The preview does not count as billable usage under usage-based pricing
  (see [UC-MKT-ADV-001](UC-MKT-ADV-001.md)).
- An `AUDIT_LISTING_PREVIEWED` event is recorded in the
  [audit log](../../concepts/audit-events.md) for the producer's
  analytics.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Preview disabled for listing | `403 Forbidden` with `PREVIEW_DISABLED` code |
| Unauthenticated request | `401 Unauthorized` |
| Asset data unavailable | `503 Service Unavailable` |
| Listing not found | `404 Not Found` |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Assets](../../concepts/assets.md), [Compliance Runs](../../concepts/compliance-runs.md)
- Journeys: [JOURNEY-DC-001 -- Discover and Purchase Asset](../journeys/JOURNEY-DC-001.md)
- Personas: [Data Consumer](../personas/data-consumer/index.md)
