# Billing

Billing in Meshant tracks resource consumption, manages subscriptions, enforces quotas, and generates invoices for each [tenant](tenants.md). The billing system covers both platform usage (storage, compute, API calls) and marketplace transactions (purchases, subscriptions, revenue sharing). It provides cost visibility per tenant and per asset, enabling data teams to understand the economics of their data operations.

Every billable action is metered in real-time and aggregated into usage records. Invoices are generated at the end of each billing cycle (monthly by default) and include line items for platform usage and marketplace activity.

## Lifecycle

Billing accounts mirror the [tenant](tenants.md) lifecycle:

| State | Description |
|---|---|
| `active` | The billing account is operational. Usage is metered and invoices are generated on schedule. |
| `grace_period` | An invoice is overdue. The tenant has a configurable grace period (default: 14 days) before suspension. |
| `suspended` | The tenant has been suspended due to non-payment. Read-only access is maintained. New operations are blocked. |
| `closed` | The tenant has been decommissioned. Final invoice has been generated. No further charges accrue. |

The transition from `grace_period` to `suspended` is automatic. Reactivation requires clearing the outstanding balance.

## Usage Metering

| Metric | Unit | Description |
|---|---|---|
| Storage | GB-month | Total data stored in managed storage, measured daily and averaged over the billing cycle. |
| Compute | Job-minutes | Total execution time of [jobs](jobs.md) (DQ runs, compliance scans, transformations). |
| API calls | Requests | Total API requests made by users and service accounts. |
| Data transfer | GB | Data downloaded from the platform (dataset downloads, API responses). |
| Marketplace revenue | Currency | Revenue from [marketplace](marketplace-listings.md) sales, subject to platform commission. |

Metering events are captured at the point of action and aggregated into hourly buckets. Real-time usage is visible through the billing dashboard with a delay of no more than 5 minutes.

## Quota Enforcement

Each tenant has configurable quotas that cap resource consumption:

| Quota | Default | Enforcement |
|---|---|---|
| Storage limit | 100 GB | Upload operations are rejected when the limit is reached. |
| Concurrent jobs | 10 | New jobs are queued (not rejected) when the limit is reached. |
| API rate limit | 1000 req/min | Requests beyond the limit receive 429 responses with retry-after headers. |
| Monthly compute | 5000 job-minutes | Jobs are blocked when the limit is reached. Admin can raise the limit. |

Quotas can be adjusted by `tenant-admin` or `platform-admin` [roles](users-and-roles.md). Approaching a quota threshold (80%, 90%, 100%) triggers [webhook](webhooks.md) notifications.

## Relationships

- **Tenants** -- Each [tenant](tenants.md) has exactly one billing account. Billing state directly affects tenant lifecycle (non-payment triggers suspension).
- **Marketplace Listings** -- [Marketplace](marketplace-listings.md) purchases generate billing events for both buyer (charge) and seller (revenue, minus platform commission).
- **Jobs** -- [Job](jobs.md) execution time is the primary compute billing metric.
- **Datasets** -- [Dataset](datasets.md) storage is the primary storage billing metric.
- **Users and Roles** -- Billing management is restricted to `tenant-admin` and `platform-admin` [roles](users-and-roles.md).
- **Audit Events** -- Invoice generation, payment events, quota changes, and suspension actions are logged as [audit events](audit-events.md).
- **Webhooks** -- Quota threshold alerts and invoice events are delivered via [webhooks](webhooks.md).

## MVP Scope

**Available at launch:**

- Real-time usage metering for storage, compute, API calls, and data transfer.
- Monthly invoice generation with line-item breakdown.
- Quota configuration and enforcement (storage, concurrent jobs, API rate).
- Usage dashboard with daily and monthly views.
- Billing alerts at 80% and 90% quota thresholds.
- Marketplace transaction billing (buyer charges, seller revenue).
- Platform commission on marketplace sales (configurable percentage).
- Invoice export in PDF and CSV formats.

**Post-MVP:**

- Custom billing cycles (weekly, quarterly, annual).
- Cost allocation tagging (charge specific assets or domains to internal cost centers).
- Budget alerts and spending forecasts.
- Prepaid credit pools for enterprise contracts.
- Usage-based marketplace pricing with real-time metering.
- Multi-currency support.
- Integration with external billing systems (Stripe, AWS Marketplace).
- Cost optimization recommendations based on usage patterns.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Get usage summary | `GET /api/v1/billing/usage` | `meshant billing usage` | `client.billing.usage()` |
| Get current invoice | `GET /api/v1/billing/invoices/current` | `meshant billing invoice` | `client.billing.current_invoice()` |
| List invoices | `GET /api/v1/billing/invoices` | `meshant billing invoices` | `client.billing.list_invoices()` |
| Get quotas | `GET /api/v1/billing/quotas` | `meshant billing quotas` | `client.billing.quotas()` |
| Update quotas | `PATCH /api/v1/billing/quotas` | `meshant billing set-quota <metric> <value>` | `client.billing.set_quota(metric, value)` |
| Get marketplace revenue | `GET /api/v1/billing/revenue` | `meshant billing revenue` | `client.billing.revenue()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for usage breakdown parameters and invoice filtering.
