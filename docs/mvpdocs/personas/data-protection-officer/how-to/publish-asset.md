# How to Publish an Asset to the Marketplace

This guide explains how to take an existing asset from your internal catalog
and list it on the Meshant Marketplace so external consumers can discover,
preview, and purchase access.

## Prerequisites

- The asset must be in `active` state (all DQ and compliance checks passed).
- You must hold the **data_product_owner** role for the asset's domain.
- Your tenant must have the Marketplace module enabled.

## Step 1 -- Verify Data Quality Has Passed

Before listing an asset on the marketplace, confirm that its latest DQ run
shows a passing score.

**UI:** Navigate to **Assets > [Your Asset] > Quality** and verify the
status badge is green.

**CLI:**

```bash
datahub dq list --asset-id <ASSET_ID> --latest
```

The output includes `status`, `overall_score`, and `threshold`. The status
must be `passed`.

If the latest run has failed, address the flagged columns first. See
[How to Review Quality Reports](review-quality-reports.md).

## Step 2 -- Set Pricing

1. Navigate to **Assets > [Your Asset] > Marketplace**.
2. Under **Pricing**, choose a model:
   - **Free** -- no charge; consumers get immediate access upon request.
   - **One-time** -- a single payment grants perpetual read access.
   - **Subscription** -- recurring monthly or annual billing.
3. Enter the price amount and currency.
4. Click **Save Pricing**.

**CLI:**

```bash
datahub marketplace set-pricing \
  --asset-id <ASSET_ID> \
  --model subscription \
  --amount 99.00 \
  --currency USD \
  --interval monthly
```

## Step 3 -- Choose Visibility and Access Controls

1. Under **Visibility**, select **Public** to list on the open marketplace
   or **Restricted** to limit to pre-approved organizations.
2. Optionally enable **Sample Preview** so consumers can inspect a few rows
   before purchasing.
3. Add a marketplace description and tags to improve discoverability.

## Step 4 -- Submit for Review

1. Click **Submit for Marketplace Review**.
2. The platform administrator (MPA persona) receives a notification and
   reviews your listing for policy compliance.
3. Once approved, the asset appears in the marketplace catalog.

**CLI:**

```bash
datahub marketplace submit --asset-id <ASSET_ID>
```

Check approval status:

```bash
datahub marketplace status --asset-id <ASSET_ID>
```

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| "Asset must be active" error | Asset is still in `draft` state | Run DQ check and publish internally first |
| "Compliance check required" | No compliance run on record | Run `datahub compliance run --asset-id <ID>` |
| Listing stuck in review | MPA has not yet reviewed | Contact your platform administrator |

## Next Steps

- [Manage Data Contracts](manage-contracts.md)
- [Review Quality Reports](review-quality-reports.md)
- [Marketplace Listings Concept](../../../concepts/marketplace-listings.md)
