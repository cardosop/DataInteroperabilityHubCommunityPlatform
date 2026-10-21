# Backend-as-a-Service (BaaS)

**Status:** CANARY (285.5.3.H, 2026-05-17)
**Feature Flag:** `baas_enabled`
**Target:** 100% Production-Ready

## Overview

BaaS enables external developers to access Meshant APIs programmatically via
API keys with tiered pricing, usage tracking, and billing integration.

## Tier Pricing

| Tier | Rate Limit | Monthly Quota | Price |
|------|-----------|---------------|-------|
| Free | 60 req/min | 10,000 req/month | $0 |
| Starter | 300 req/min | 100,000 req/month | $49 |
| Professional | 1,200 req/min | 1,000,000 req/month | $299 |
| Enterprise | Custom | Custom | Contact sales |

## API Keys

API keys are provisioned per tenant and scoped to specific endpoints. Key
lifecycle:
1. **Create:** `POST /api/v1/baas/keys/` — generates a `baas_`-prefixed key
2. **Rotate:** `POST /api/v1/baas/keys/{id}/rotate/` — invalidates old key, issues new
3. **Revoke:** `DELETE /api/v1/baas/keys/{id}/` — immediately invalidates
4. **Expire:** Keys auto-expire after 365 days unless rotated

Keys are stored hashed (SHA-256); the raw key is shown only once at creation.

## Usage Reporting

- **Per-call tracking:** `BaaSUsageMiddleware` increments a Redis counter per
  authenticated BaaS call (`baas_usage:{tenant_id}:{date}:{key_id}`)
- **Aggregation:** `CustomerBillingReport.generate()` aggregates per tenant per
  month from the `APIKeyPricing` tier × call count
- **Dashboard:** `monitoring/grafana/dashboards/baas.json` — usage by tenant,
  key, endpoint, tier

## Stripe Integration

- **Provisioning:** Stripe subscription `customer.subscription.created` webhook
  provisions the API key at the purchased tier
- **Revocation:** `customer.subscription.deleted` webhook revokes all keys for
  the tenant
- **Webhook verification:** `stripe.Webhook.construct_event()` with signing secret
- **Quota enforcement:** API key creation rejected if tenant has unpaid invoices
  or exceeds plan limit

## Rate Limiting

- `BaaSRateLimitMiddleware` — Redis-backed, tenant-scoped counters
- `BaaSAPIRateThrottle` — DRF throttle on BaaS views (scope: `baas_api`)
- Throttle coverage tracked in `check_throttle_coverage.py` `_MODULES`

## Production Readiness Checklist

| Item | Status |
|------|--------|
| Rate limit middleware | Planned (285.5.3.H1) |
| Usage tracking | Planned (285.5.3.H2) |
| Billing reports | Planned (285.5.3.H3) |
| Stripe integration | Planned (285.5.3.H4) |
| Quota enforcement | Planned (285.5.3.H5) |
| Throttle coverage | ✅ Done (285.5.3.H6) |
| Documentation | ✅ Done (this file) |
| Feature flag | ✅ `baas_enabled` (CANARY) |

## Related

- `hub/apps/baas/views.py` — BaaS ViewSet
- `hub/apps/tenants/feature_flag_registry.py` — `baas_enabled` flag
- `hub/apps/billing/` — CustomerBillingReport
- `docs/runbooks/BAAS_INFRASTRUCTURE.md` — BaaS infrastructure runbook

## Maintenance

- **Owner:** Platform Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
