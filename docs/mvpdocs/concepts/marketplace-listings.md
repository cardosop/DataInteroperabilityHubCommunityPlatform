# Marketplace Listings

A marketplace listing makes a data [asset](assets.md) discoverable and purchasable by other [tenants](tenants.md) on the Meshant platform. Listings define pricing, visibility controls, terms of use, and access mechanisms. The Marketplace is the primary channel for data monetization and cross-organizational data sharing within the platform.

Every listing is backed by a published asset that has passed both [DQ](dq-runs.md) and [compliance](compliance-runs.md) checks. The platform enforces that listed assets meet minimum quality and compliance thresholds defined by the data producer's [governance](governance.md) policies.

## Lifecycle

| State | Description |
|---|---|
| `draft` | The listing is being configured. Pricing, description, and visibility have not been finalized. |
| `pending_review` | The listing has been submitted for review. Automated checks verify that the asset meets quality and compliance thresholds. |
| `published` | The listing is live and visible to the target audience. Other tenants can browse, evaluate, and purchase. |
| `suspended` | The listing has been temporarily removed due to a quality regression, compliance finding, or policy violation. |
| `delisted` | The listing has been permanently removed. Existing subscribers retain access until their subscription term expires. |

Transition from `pending_review` to `published` requires that the backing asset has at least one `SUCCEEDED` DQ run with a score above the tenant's minimum threshold and a compliance run with a risk level at or below the allowed maximum.

## Pricing Models

| Model | Description |
|---|---|
| `one_off` | Single payment grants permanent access to the current version of the dataset. Updates require a new purchase. |
| `subscription` | Recurring payment (monthly or annual) grants continuous access, including all updates during the subscription period. |
| `usage_based` | Pay per API call, row accessed, or data volume downloaded. Metering is handled by the [billing](billing.md) system. |
| `free` | No charge. The listing is available to all tenants that accept the terms of use. Useful for open data or promotional offerings. |

Pricing can include a free trial period (configurable in days) and volume discounts for usage-based plans.

## Access Provisioning

When a buyer completes a purchase, the platform automatically provisions access:

1. A read-only credential scoped to the purchased asset is generated for the buyer's tenant.
2. The buyer can access the data through the API, CLI, or SDK using their existing authentication.
3. Access is logged in both the buyer's and seller's [audit events](audit-events.md).
4. For subscription plans, access is automatically revoked when the subscription expires or is cancelled.
5. For one-off purchases, access persists indefinitely for the purchased version.

The seller retains full control over the underlying asset. Publishing a new version does not automatically grant access to previous one-off buyers; subscription buyers receive updates automatically.

## Relationships

- **Assets** -- Each listing references exactly one [asset](assets.md). The listing is a distribution and pricing wrapper around the asset.
- **Billing** -- Purchases, subscriptions, and usage metering flow into the [billing](billing.md) system for both the buyer and seller tenants.
- **Tenants** -- Listings are created by a seller [tenant](tenants.md) and purchased by buyer tenants. Visibility can be restricted to specific tenants (private listings).
- **DQ Runs** -- The listing displays the asset's quality score from the most recent [DQ run](dq-runs.md). A score regression below the threshold triggers automatic suspension.
- **Compliance Runs** -- The listing shows the asset's compliance status from the most recent [compliance run](compliance-runs.md).
- **Search** -- Published listings are indexed in the marketplace [search](search.md) index, separate from the tenant-internal asset search.
- **Webhooks** -- The `order.placed` event fires when a buyer purchases a listing, notifying the seller via [webhooks](webhooks.md).
- **Audit Events** -- Listing creation, publication, purchases, and delistings are all recorded as [audit events](audit-events.md).

## MVP Scope

**Available at launch:**

- Listing creation and publishing via API, CLI, and SDK.
- Three pricing models: one-off, subscription, and free.
- Visibility controls: public (all tenants) or private (invite-only).
- Automated quality and compliance gate before publishing.
- Buyer browsing, search, and filtering of published listings.
- Purchase flow with access provisioning.
- Seller dashboard: listing views, purchases, revenue summary.
- Rating and review system (1-5 stars with text review).

**Post-MVP:**

- Usage-based pricing with real-time metering.
- Negotiated pricing and custom contracts for enterprise deals.
- Data previews and sample downloads before purchase.
- Listing analytics (funnel conversion, search impression tracking).
- Bundled listings (multiple assets sold as a package).
- Automated re-certification on schedule.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create listing | `POST /api/v1/marketplace/listings` | `meshant marketplace create` | `client.marketplace.create()` |
| Get listing | `GET /api/v1/marketplace/listings/{id}` | `meshant marketplace get <id>` | `client.marketplace.get(id)` |
| List listings | `GET /api/v1/marketplace/listings` | `meshant marketplace list` | `client.marketplace.list()` |
| Publish listing | `POST /api/v1/marketplace/listings/{id}/publish` | `meshant marketplace publish <id>` | `client.marketplace.publish(id)` |
| Purchase listing | `POST /api/v1/marketplace/listings/{id}/purchase` | `meshant marketplace purchase <id>` | `client.marketplace.purchase(id)` |
| Delist | `POST /api/v1/marketplace/listings/{id}/delist` | `meshant marketplace delist <id>` | `client.marketplace.delist(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for pricing configuration and visibility options.
