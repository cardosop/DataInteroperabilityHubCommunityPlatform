# Data Consumer Quickstart

This guide walks you through finding, evaluating, and purchasing your
first dataset on the Meshant marketplace. By the end, you will have
accessed a real data asset.

**Prerequisites:**

- A Meshant account with the `DATA_CONSUMER` role.
- A funded billing account (or access to a tenant with a billing plan).


## Step 1: Browse the Marketplace

Log in to the Meshant web UI and navigate to **Marketplace** in the left
sidebar. The marketplace landing page shows featured listings, recently
published assets, and category filters.

You can also browse from the CLI:

```bash
datahub search search \
  --query "customer demographics" \
  --domain "marketing" \
  --quality-status "PASSED" \
  --format table
```

This returns a paginated table of matching assets filtered to the
`marketing` domain with passing data quality status.


## Step 2: Search for Datasets

Use the search bar or faceted filters to narrow results:

| Filter | Description | Example |
|--------|-------------|---------|
| `--domain` | Business domain | `finance`, `marketing`, `healthcare` |
| `--type` | Resource type | `ASSET`, `DATASET`, `CONTRACT` |
| `--classification` | Data classification | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL` |
| `--tags` | Comma-separated tags | `pii,gdpr-compliant` |
| `--quality-status` | DQ check result | `PASSED`, `WARNING`, `FAILED` |
| `--compliance-status` | Compliance scan result | `COMPLIANT`, `NON_COMPLIANT` |

**Tip:** Combine filters for precise results. For example, to find
GDPR-compliant healthcare datasets with passing quality:

```bash
datahub search search \
  --query "patient outcomes" \
  --domain "healthcare" \
  --quality-status "PASSED" \
  --compliance-status "COMPLIANT" \
  --sort-by relevance \
  --limit 10
```


## Step 3: Evaluate Trust Indicators

Click on a listing to view its detail page. Key trust indicators include:

- **Quality Score** -- An aggregate score from automated data quality
  checks (completeness, uniqueness, validity, freshness). Look for the
  green "PASSED" badge.
- **Compliance Badges** -- Icons indicating GDPR, HIPAA, or SOC2
  compliance scan results. Hover for scan date and details.
- **Lineage** -- A visual graph showing where the data originates and
  how it was transformed.
- **Schema Preview** -- Column names, data types, and sample values.
- **Community Ratings** -- Star ratings and reviews from other consumers.

For a deeper understanding of these indicators, see
[How-To: Evaluate Data Quality](how-to/evaluate-data-quality.md).


## Step 4: Complete Checkout

Once you have chosen a dataset:

1. Select the **pricing tier** (Free, One-Time, Subscription, or
   Usage-Based) from the listing detail page.
2. Click **Add to Cart** and review the order summary.
3. Confirm billing details and click **Purchase**.
4. The system binds a data contract between you and the provider,
   governing schema, SLAs, and retention terms.

Your purchase is now visible under **My Purchases** in the billing
dashboard.


## Step 5: Access the Purchased Asset

After checkout you can access the data in several ways:

**Download (for file-based assets):**

Navigate to **My Purchases**, find the asset, and click **Download**.

**API access (for API-backed assets):**

```bash
datahub assets get --id <asset-id> --format json
```

**SDK access:**

```python
from datahub_interoperability import DataHubClient

client = DataHubClient.from_env()
asset = client.assets.get("<asset-id>")
print(asset.name, asset.status)
```


## What Next?

- [How-To: Discover Datasets](how-to/discover-datasets.md) -- advanced
  search techniques
- [How-To: Evaluate Data Quality](how-to/evaluate-data-quality.md) --
  interpret quality scores in depth
- [How-To: Purchase and Access](how-to/purchase-and-access.md) --
  subscription management, usage tracking
- [Reference](reference.md) -- full API, CLI, and SDK links
