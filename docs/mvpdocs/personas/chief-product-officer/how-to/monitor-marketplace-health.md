# Monitor Marketplace Health

**Persona:** Chief Product Officer (CPO)
**Journey:** Oversee marketplace → monitor supply/demand → ensure platform trust

## Overview

As CPO, you monitor the health of your Meshant marketplace to ensure a
balanced ecosystem of data providers and consumers. Key metrics include
listing quality, transaction volume, provider onboarding, and trust signals.

## Key Metrics

### Supply-Side Health

- **Active listings:** Total published listings across all providers
- **Provider onboarding rate:** New Connect accounts with `charges_enabled=True`
- **Listing quality:** Average trust signal scores across published listings
- **Stale listings:** Listings not updated in >90 days

### Demand-Side Health

- **Monthly orders:** Total orders placed (`marketplace_orders_per_month` plan limit)
- **Consumer growth:** New consumers placing first orders
- **Repeat purchase rate:** Consumers with >1 order in 90 days

### Trust & Compliance

- **KYB completion rate:** Providers completing Stripe Connect onboarding
- **Compliance pass rate:** Listings passing compliance gate on publish
- **Dispute rate:** Orders with disputes or refunds

## Monitoring Dashboards

| Dashboard | Purpose |
|---|---|
| `billing-upgrade-funnel.json` | Revenue, plan changes, payment failures |
| `connect-onboarding-funnel.json` | Provider KYB funnel, stuck onboardings |
| `hub-overview.json` | Platform-wide health |

## Health Check Queries

### Listings by status

```
GET /api/v1/admin/marketplace/stats/
```

### Provider onboarding pipeline

```
GET /api/v1/admin/connect/review-queue/
```

### Monthly transaction volume

```sql
SELECT DATE_TRUNC('month', created_at) AS month,
       COUNT(*) AS orders,
       SUM(amount_cents) / 100.0 AS revenue
FROM orders
WHERE status NOT IN ('CANCELLED', 'REJECTED')
GROUP BY DATE_TRUNC('month', created_at)
ORDER BY month DESC LIMIT 12;
```

## Taking Action

### Low supply → Increase provider acquisition

1. Review provider onboarding friction (KYB pass rate)
2. Adjust marketplace take rate (`marketplace_take_rate_bps` on TenantPlan)
3. Promote marketplace to potential providers via communication templates

### Low demand → Improve discovery

1. Review search quality (empty-result rate in `search_no_result_total`)
2. Verify listings have complete metadata (title, description, tags)
3. Consider featuring high-quality listings on the marketplace landing page

### Trust signal degradation

1. Review compliance scan results for affected listings
2. Contact providers with degraded trust signals
3. Temporarily de-list listings with critical compliance failures

## Related

- Runbook: `docs/runbooks/RB-MKT-001-stripe-connect-onboarding-failure.md`
- Dashboard: `monitoring/grafana/dashboards/connect-onboarding-funnel.json`
