# How-To: Monitor Marketplace Metrics

This guide covers the key metrics an MPA should track to maintain a
healthy marketplace, and how to access them.


## Marketplace Dashboard

The marketplace dashboard is available at **Analytics > Marketplace** in
the admin panel. It provides real-time and historical views of platform
activity.


## Revenue Metrics

| Metric | Description | Where to Find |
|--------|-------------|---------------|
| **Monthly Recurring Revenue (MRR)** | Sum of all active subscription fees | Dashboard: Revenue tab |
| **Total Revenue (MTD)** | All revenue in the current month (subscriptions + one-time + usage) | Dashboard: Revenue tab |
| **Revenue by Tenant** | Breakdown of revenue per tenant | Dashboard: Revenue tab > By Tenant |
| **Revenue by Plan Tier** | Revenue grouped by Free/Starter/Pro/Enterprise | Dashboard: Revenue tab > By Plan |
| **Average Revenue Per Tenant** | MRR divided by active tenant count | Dashboard: Revenue tab |

### Investigating Revenue Changes

If revenue drops unexpectedly:

1. Check **Tenant Churn** -- are tenants downgrading or deactivating?
2. Check **Subscription Cancellations** -- filter billing events by
   type `CANCELLATION` in the audit log.
3. Check **Usage-Based Revenue** -- a drop in API calls may indicate
   integration issues on the consumer side.

Via CLI:

```bash
datahub billing subscriptions --format table
datahub tenants usage --format table
```


## Asset and Listing Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Total Active Listings** | Marketplace listings with status ACTIVE | Growing month-over-month |
| **New Listings (MTD)** | Listings published this month | Depends on onboarding velocity |
| **Listings by Domain** | Distribution across business domains | Balanced across key domains |
| **Listings per Tenant** | Average listings per active provider tenant | Indicator of provider engagement |
| **Stale Listings** | Listings with freshness WARNING or FAILED | Target: < 5% of total |


## Quality and Compliance Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **DQ Pass Rate** | % of assets with PASSED quality status | >= 90% |
| **Compliance Score (avg)** | Average compliance scan score | >= 85% |
| **Non-Compliant Listings** | Listings with NON_COMPLIANT status | Target: 0 for public listings |
| **Scan Coverage** | % of assets scanned in the last scan cycle | >= 95% |

If the DQ pass rate drops:

1. Identify the failing assets via **Governance > DQ Results** in the
   admin panel.
2. Check if a recent platform default change tightened thresholds.
3. Notify affected tenant admins with remediation guidance.


## SLA Tracking

Meshant tracks SLAs defined in data contracts between providers and
consumers. The MPA monitors aggregate SLA compliance.

| Metric | Description | Target |
|--------|-------------|--------|
| **SLA Compliance Rate** | % of contracts meeting all SLA terms | >= 98% |
| **SLA Breaches (MTD)** | Count of SLA violations this month | Trending toward 0 |
| **Mean Time to Resolution** | Average time to resolve an SLA breach | < 24 hours |

SLA breaches generate audit log entries and (if configured) webhook
notifications to both the provider and the MPA.


## Tenant Onboarding Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Pending KYC Applications** | Tenants awaiting review | Process within 48 hours |
| **Approval Rate** | % of applications approved | Track for quality, not a fixed target |
| **Time to Activation** | From application to first asset published | Minimize |
| **Tenant Churn Rate** | % of tenants deactivating per month | < 5% |


## Setting Up Alerts

For critical metric thresholds, configure webhook notifications:

1. Navigate to **Settings > Webhooks** in the admin panel.
2. Create a webhook with event types:
   - `tenant.kyc.pending` -- new KYC application
   - `billing.invoice.overdue` -- overdue payment
   - `dq.check.failed` -- asset DQ failure
   - `compliance.scan.non_compliant` -- compliance violation
   - `contract.sla.breached` -- SLA breach
3. Point the webhook URL to your ops notification channel (Slack, PagerDuty, email relay).


## See Also

- [How-To: Onboard Tenant](onboard-tenant.md)
- [How-To: Configure Platform Defaults](configure-platform-defaults.md)
- [MPA Reference](../reference.md)
