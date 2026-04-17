# Data Product Owner -- 5-Minute Quickstart

This guide walks you through publishing your first data product on Meshant
using the Data-First onboarding flow. By the end you will have a live asset
with an inferred schema, a passing DQ check, and a catalog entry visible to
your organization.

## Prerequisites

- A Meshant account with the **data_product_owner** role.
- A sample CSV file (or any supported tabular format) ready to upload.
- (Optional) The Meshant CLI installed if you prefer the terminal:
  ```bash
  pip install datahub
  datahub config set --api-url https://meshant-internal.example.com --token <YOUR_TOKEN>
  ```

## Step 1 -- Log In and Navigate to Assets

1. Open your browser and go to your Meshant instance
   (e.g., `https://meshant-internal.example.com`).
2. Sign in with your organizational credentials (SSO or email/password).
3. In the left sidebar, click **Assets**. You will see the asset list
   filtered to your domain by default.

**CLI alternative:**

```bash
datahub asset list --domain my-domain
```

## Step 2 -- Create a New Asset (Data-First Flow)

1. Click **+ New Asset** in the top-right corner.
2. Select **Data First** as the onboarding flow.
3. Drag and drop your CSV file into the upload area, or click **Browse** to
   select it from your filesystem.
4. Meshant uploads the file, infers column names, data types, and
   nullability, and presents the draft schema for your review.

**CLI alternative:**

```bash
datahub asset create \
  --name "quarterly-revenue-2026-q1" \
  --domain finance \
  --flow data-first \
  --file ./revenue_q1.csv
```

The CLI prints the new asset ID and a summary of the inferred schema.

## Step 3 -- Review the Inferred Schema

1. On the **Schema** tab, verify each column's name, type, and nullable
   flag. Edit any incorrect inferences (e.g., change a `string` column to
   `date` if Meshant could not auto-detect the format).
2. Optionally add column descriptions -- these are surfaced in the catalog
   and help consumers understand each field.
3. Click **Save Schema**.

## Step 4 -- Run a Data Quality Check

1. Switch to the **Quality** tab.
2. Click **Run DQ Check**. Meshant applies the default DQ rule set for
   your domain (or the global default if none is configured).
3. Wait for the job to complete -- the status badge turns green on success.
4. Review the results: per-column completeness, uniqueness, and pattern
   conformance scores. A score below the threshold is flagged in red.

**CLI alternative:**

```bash
datahub dq run --asset-id <ASSET_ID>
datahub dq status --run-id <RUN_ID>
```

## Step 5 -- Publish the Asset

1. Return to the **Overview** tab.
2. Confirm the asset state is `draft` and all checks have passed.
3. Click **Publish** and choose the visibility level:
   - **Private** -- only you and explicitly shared users.
   - **Organization** -- everyone in your tenant.
   - **Public** -- listed on the marketplace (requires marketplace admin
     approval).
4. Click **Confirm**. The asset transitions to `active`.

**CLI alternative:**

```bash
datahub asset publish --asset-id <ASSET_ID> --visibility organization
```

## What You Just Did

- Uploaded raw data and let Meshant infer its schema.
- Validated data quality with an automated DQ check.
- Published the asset to your organization's internal catalog.

## Next Steps

- [How to Publish an Asset to the Marketplace](how-to/publish-asset.md)
- [How to Create and Manage Data Contracts](how-to/manage-contracts.md)
- [How to Review Quality Reports](how-to/review-quality-reports.md)
- [Full Reference (API / CLI / SDK)](reference.md)
