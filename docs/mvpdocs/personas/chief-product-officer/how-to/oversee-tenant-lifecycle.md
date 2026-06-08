# Oversee Tenant Lifecycle

**Persona:** Chief Product Officer (CPO)
**Journey:** Manage tenants → oversee provisioning → handle offboarding

## Overview

As CPO, you oversee the full tenant lifecycle — from provisioning new tenants
to managing feature flags, monitoring tenant health, and handling offboarding
when a tenant leaves the platform.

## Tenant Provisioning

### Manual provisioning

```bash
python manage.py provision_tenant \
  --name "Acme Corp" \
  --slug "acme-corp" \
  --admin-email "admin@acme.com" \
  --plan "starter" \
  --regulations "GDPR,UK_GDPR"
```

### Verify provisioning

```
GET /api/v1/admin/tenants/{id}/
```

Check: status is ACTIVE, plan assigned, feature flags configured,
licensed regulations match the plan's `includes_regulations`.

## Feature Flag Management

### View all flags for a tenant

```
GET /api/v1/admin/tenants/{id}/feature-flags/
```

### Change a flag

```bash
curl -X PATCH https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/feature-flags/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"semantic_search_enabled": true, "reason": "Tenant request per CS #1234"}'
```

**Sensitive flags** (`compliance_fail_closed_enabled`, etc.) require two-person approval.

## Tenant Health Monitoring

### Active tenants by plan

```sql
SELECT tp.slug AS plan, COUNT(*) AS tenants
FROM tenants_tenant t
JOIN tenant_plans tp ON t.plan_id = tp.id
WHERE t.status = 'ACTIVE'
GROUP BY tp.slug;
```

### Tenants approaching limits

```
GET /api/v1/admin/tenants/?near_limit=true
```

### Inactive tenants

```sql
SELECT name, slug, updated_at
FROM tenants_tenant
WHERE status = 'ACTIVE'
  AND updated_at < NOW() - INTERVAL '90 days';
```

## Tenant Offboarding

### Pre-offboarding checklist

- [ ] Notify tenant 30 days in advance (use communication template in `RB-TENANTS-001`)
- [ ] Export tenant data if requested
- [ ] Cancel active Stripe subscriptions
- [ ] Revoke API keys
- [ ] Unschedule all ingestions/exports

### Deactivate tenant

```bash
curl -X POST https://api.stagingmeshant-internal.example.com/api/v1/admin/tenants/{id}/deactivate/ \
  -H "Authorization: Bearer $TOKEN"
```

### Post-deactivation verification

- [ ] Tenant status is INACTIVE
- [ ] All subscriptions cancelled
- [ ] API keys revoked
- [ ] Webhooks disabled
- [ ] Data retained per retention policy

## Related

- Runbook: `docs/runbooks/RB-TENANTS-001-provisioning.md`
- Feature flag lifecycle: `docs/runbooks/feature-flag-lifecycle.md`
- Tenant offboarding: `docs/runbooks/tenant-offboarding.md`
