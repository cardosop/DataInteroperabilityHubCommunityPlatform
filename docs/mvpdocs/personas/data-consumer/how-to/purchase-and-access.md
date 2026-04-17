# How-To: Purchase and Access Data

This guide covers the end-to-end flow from selecting a dataset on the
Meshant marketplace through checkout and into accessing the purchased
data.


## Pricing Models

Meshant supports four pricing models. The model is set by the Data
Product Owner when they create the marketplace listing.

| Model | Description |
|-------|-------------|
| **Free** | No charge. Access is granted immediately upon request. |
| **One-Time** | Single payment for permanent access to a snapshot of the data. |
| **Subscription** | Recurring payment (monthly or annual) for ongoing access with updates. |
| **Usage-Based** | Pay-per-query or pay-per-download, metered against your tenant plan. |

The pricing model and amounts are displayed on the listing detail page.


## Checkout Flow (Web UI)

1. Open the marketplace listing detail page.
2. Select the desired **pricing tier** if multiple are offered.
3. Click **Add to Cart**.
4. Review the **order summary**, which shows line items, taxes (if
   applicable), and total amount.
5. Confirm your **billing method**. Meshant charges to the payment method
   on file for your tenant.
6. Click **Confirm Purchase**.
7. On success, the system creates a **data contract** between your tenant
   and the provider tenant. The contract specifies:
   - Schema (columns, types, constraints).
   - Quality SLAs (minimum DQ score, freshness guarantee).
   - Retention period.
   - Access method (download, API, or both).

You will receive a confirmation and the asset appears under
**My Purchases** in the billing dashboard.


## Access Methods

### Download

For file-based assets (CSV, Parquet, JSON):

1. Go to **My Purchases** in the web UI.
2. Find the asset and click **Download**.
3. The file is served from Meshant's storage layer with a signed URL.

Via CLI:

```bash
datahub assets get --id <asset-id> --format json
```

### API Access

For API-backed assets, the data contract includes an API endpoint:

```
GET /api/v1/assets/<asset-id>/data/
Authorization: Bearer <your-token>
```

The response format depends on the asset type (JSON by default).

### SDK Access

```python
from datahub_interoperability import DataHubClient

client = DataHubClient.from_env()
asset = client.assets.get("<asset-id>")
print(asset.name, asset.status)

# If the asset supports data download:
data = client.assets.download("<asset-id>")
```


## Managing Subscriptions

For subscription-based assets:

- **View active subscriptions** in the billing dashboard under
  **Subscriptions**.
- **Cancel a subscription** from the subscription detail page. Access
  continues until the end of the current billing period.
- **Upgrade/downgrade tier** if the provider offers multiple tiers.

Via CLI:

```bash
datahub billing subscriptions --format table
```


## Monitoring Usage

For usage-based assets, track your consumption:

```bash
datahub tenants usage --format table
```

This shows current-period API calls, storage, and asset counts against
your tenant plan limits.


## Troubleshooting

| Issue | Resolution |
|-------|------------|
| "Insufficient permissions" on checkout | Confirm you have the `DATA_CONSUMER` role. Contact your Tenant Admin. |
| "Payment method required" | Add a payment method in **Settings > Billing**. |
| Download returns 403 | Your data contract may have expired. Check contract status under **My Purchases**. |
| API returns 429 (rate limited) | You have exceeded your plan's API call quota. Upgrade your plan or wait for the next billing cycle. |


## See Also

- [How-To: Discover Datasets](discover-datasets.md)
- [How-To: Evaluate Data Quality](evaluate-data-quality.md)
- [Data Consumer Reference](../reference.md)
