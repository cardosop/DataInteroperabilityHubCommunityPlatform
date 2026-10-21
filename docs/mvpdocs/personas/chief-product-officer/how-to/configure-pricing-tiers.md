# Configure Pricing Tiers

**Persona:** Chief Product Officer (CPO)
**Journey:** Oversee product strategy → configure pricing → monitor adoption

## Overview

As the CPO, you configure Meshant's plan pricing tiers to align with your
product strategy. This includes setting price points, defining plan limits,
and managing the pricing page that tenants see when they sign up or upgrade.

## Prerequisites

- PLATFORM_ADMIN role (or CPO with admin delegation)
- Access to the admin API at `https://api.<env>meshant-internal.example.com/api/v1/admin/`
- Pricing strategy document (target price points, competitive analysis)

## Step 1 — Review current pricing

```
GET /api/v1/admin/plans/
```

Returns all active plans with their current `price_amount_cents`, limits, and tier.

## Step 2 — Adjust a plan price

**Small change (≤$1,000/mo delta):**

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/plans/{plan_id}/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price_amount_cents": 29900, "reason": "Q2 market adjustment"}'
```

**Large change (>$1,000/mo delta):** Requires two-person approval.
First PLATFORM_ADMIN creates a `PlanPriceChangeApproval`; a second PLATFORM_ADMIN
must approve before the price takes effect.

## Step 3 — Update plan limits

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/plans/{plan_id}/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limits_json": {"max_assets": 1000, "max_api_calls_per_month": 100000}}'
```

## Step 4 — Verify pricing page

Visit `https://<tenant>meshant-internal.example.com/pricing` to confirm the updated plan
appears correctly with its new price, limits, and feature highlights.

## Step 5 — Monitor adoption

After pricing changes, monitor the Billing dashboard for:
- Plan upgrade/downgrade rate (`plan_upgrade_total` / `plan_downgrade_total` metrics)
- New tenant signups by plan tier
- Revenue impact

## Related

- Runbook: `docs/runbooks/RB-BILLING-001-pricing-changes.md`
- Model: `hub/apps/tenants/models.py` — `TenantPlan`, `PlanPriceChangeApproval`
- Dashboard: `monitoring/grafana/dashboards/billing-upgrade-funnel.json`
