# RB-BaaS-001 — BaaS Rate Limit Investigation

**Feature:** BaaS (CANARY, `baas_enabled`)
**Owner:** platform-eng@meshant.com
**Created:** 2026-05-17 (Phase 285.5.6)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| API key requests returning 429 | Tenant exceeded tier rate limit | `baas_rate_limit_hits_total{tenant_id, tier}`; Redis counters |
| All tenants getting 429 | Rate limit middleware misconfigured; Redis down | `baas_rate_limit_middleware_errors_total`; Redis connectivity |
| Single tenant rate limit not resetting | Redis key TTL misconfigured; clock skew | Redis key TTL check; `baas_rate_limit_window_seconds` |
| Free tier users blocked | Quota exhausted; billing cycle not rolled over | `baas_usage_current_month{tenant_id}`; billing cycle date |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/baas.json`
- **Primary:** `baas_rate_limit_hits_total{tenant_id, tier, endpoint}`
- **Quota:** `baas_usage_current_month{tenant_id}`
- **Redis:** `baas_rate_limit_redis_errors_total`

## Investigation Checklist

1. Identify affected tenant: `GET /api/v1/admin/tenants/{id}/` → `baas_enabled`
2. Check Redis counters: `GET baas_usage:{tenant_id}:{date}`
3. Verify tier: `MLModel.inference_pricing_tier` or `APIKey.pricing_tier`
4. Check quota: `is_within_free_tier(tenant_id)` → True/False
5. Rate limit config: `DEFAULT_THROTTLE_RATES["baas_api"]`

## Remediation

- **Per-tenant override:** `PUT /api/v1/admin/tenants/{id}/feature-flags/` → `baas_enabled = true`
- **Tier upgrade:** Change `pricing_tier` field to higher tier
- **Emergency bypass:** Set `baas_rate_limit_bypass = true` in Django admin (audited)

## Escalation

- **P3:** Single tenant hitting rate limit (tier upgrade recommended)
- **P2:** Rate limit middleware returning 429 for all tenants (Redis down)
- **P1:** BaaS API completely unavailable (middleware panic/crash)

## Maintenance

- **Owner:** Platform Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
