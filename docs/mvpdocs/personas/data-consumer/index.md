# Data Consumer

| Field | Value |
|-------|-------|
| Persona ID | DC |
| Aliases | Data Scientist, Analyst, Business User, External Buyer |
| RBAC Roles | `USER`, `DATA_CONSUMER` |
| Technical Level | Variable (low to medium) |
| Primary Journeys | JOURNEY-DC-001 (Discover and Purchase Asset), JOURNEY-DC-002 (Subscribe to Asset) |


## Who Is This Persona?

The Data Consumer is anyone who needs to **find, evaluate, and access**
data products published on the Meshant marketplace. Data Consumers range
from business analysts running ad-hoc reports to data scientists building
ML training sets to external buyers procuring datasets through a formal
purchasing flow.

Unlike the Data Engineer, the Data Consumer typically interacts through the
web UI rather than the CLI or SDK, though both are fully supported. The
persona does not publish or transform data -- they consume it.


## Goals

1. **Discover relevant datasets quickly.** Search by domain, concept,
   tags, classification, quality status, or free text. Browse curated
   marketplace listings with rich metadata.

2. **Trust what they find.** Evaluate data quality scores, compliance
   badges (GDPR, HIPAA), lineage provenance, freshness indicators, and
   community ratings before committing.

3. **Purchase or access with transparent pricing.** Understand pricing
   models (free, one-time, subscription, usage-based) up front. Complete
   checkout through a clear billing flow with no hidden costs.

4. **Get data into their tools.** Download files directly, access via
   API endpoint, or connect through a data contract that governs schema,
   SLAs, and retention.


## Key Concepts

Before diving in, familiarize yourself with these Meshant concepts:

- **Marketplace Listings** -- The public-facing catalog entries that
  describe a data product, its pricing, and its trust indicators.
  See [Concepts: Marketplace](../../concepts/marketplace.md).

- **Assets** -- The underlying data resource (table, file, API) behind a
  listing. Each asset has a lifecycle status (DRAFT, ACTIVE, ARCHIVED).
  See [Concepts: Assets](../../concepts/assets.md).

- **Search** -- Full-text and faceted search across contracts, assets,
  and datasets. Supports domain, classification, quality-status, and
  compliance-status filters.
  See [Concepts: Search](../../concepts/search.md).

- **Billing** -- Meshant tracks purchases, subscriptions, and usage-based
  charges at the tenant level. Invoices and cost breakdowns are available
  in the billing dashboard.
  See [Concepts: Billing](../../concepts/billing.md).

- **Data Contracts** -- Formal agreements between provider and consumer
  that specify schema, quality SLAs, retention, and access terms.
  See [Concepts: Contracts](../../concepts/contracts.md).


## What Can You Do?

### Discover and Evaluate

| Task | Guide |
|------|-------|
| Search and filter marketplace listings | [How-To: Discover Datasets](how-to/discover-datasets.md) |
| Read quality scores and compliance badges | [How-To: Evaluate Data Quality](how-to/evaluate-data-quality.md) |
| Preview sample data before purchasing | Available on listings with preview enabled |

### Purchase and Access

| Task | Guide |
|------|-------|
| Complete checkout and manage subscriptions | [How-To: Purchase and Access](how-to/purchase-and-access.md) |
| Download purchased assets | [How-To: Purchase and Access](how-to/purchase-and-access.md) |
| Access assets via API endpoint | [Reference](reference.md) |

### Monitor

| Task | Guide |
|------|-------|
| Track your active subscriptions | Billing dashboard |
| View usage and cost history | Billing dashboard |
| Receive alerts on data freshness | Webhook or notification preferences |


## Journeys

### JOURNEY-DC-001: Discover and Purchase Asset

This is the primary end-to-end journey for a Data Consumer:

1. **Browse or search** the marketplace for datasets matching your needs.
2. **Evaluate** the listing using quality scores, compliance badges,
   lineage, schema preview, and community ratings.
3. **Select a pricing tier** (if multiple are offered) and add to cart.
4. **Complete checkout** through the billing flow.
5. **Access the asset** -- download the file, call the API endpoint, or
   bind a data contract.

### JOURNEY-DC-002: Subscribe to Asset

For assets with subscription or usage-based pricing:

1. **Subscribe** to the asset from the marketplace listing.
2. **Receive access credentials** (API key or contract binding).
3. **Consume data** on an ongoing basis within the terms of the contract.
4. **Monitor usage** against your plan limits in the billing dashboard.


## Permissions

Data Consumers require the `DATA_CONSUMER` role, which grants:

- Read access to all ACTIVE marketplace listings.
- Ability to purchase or subscribe to listings.
- Read access to purchased assets and their metadata.
- Access to billing history for own purchases.

Data Consumers do **not** have permission to:

- Create, edit, or publish assets (requires `DATA_PROVIDER`).
- Run compliance scans (requires `COMPLIANCE_OFFICER`).
- Manage tenant settings (requires `TENANT_ADMIN`).


## Next Steps

- [Quickstart: Your first dataset purchase](quickstart.md)
- [Reference: API, CLI, and SDK links](reference.md)
- [How-To Guides](how-to/)
