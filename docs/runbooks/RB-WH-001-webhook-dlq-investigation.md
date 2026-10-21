# RB-WH-001: Webhook DLQ Investigation

**Owner:** Platform Engineering
**Last reviewed:** 2026-05-13
**Alert(s):** `WebhookDLQSizeHigh`, `WebhookDLQPerTenantHigh`

## Purpose

Investigate webhook deliveries that have reached `DEAD_LETTER` status
(all retries exhausted).  Undelivered webhooks mean subscribers are
not receiving events — this may indicate a subscriber outage, a
platform-side delivery bug, or a rate-limiting configuration issue.

## Symptoms

- `WebhookDLQSizeHigh` fires (>50 total DLQ deliveries)
- `WebhookDLQPerTenantHigh` fires (>100 DLQ deliveries for one tenant)
- Subscribers report missing events
- `webhook_dlq_size` gauge shows a monotonic increase over time

## Investigation steps

### 1. Check the DLQ dashboard

Open the Grafana webhooks dashboard and check:
- Total DLQ size and growth rate
- Per-tenant DLQ breakdown
- Most recent DLQ entries and their error messages

### 2. Identify affected tenants and subscribers

```bash
# Query the DLQ via Django management shell
python manage.py shell -c "
from hub.apps.webhooks.models import WebhookDelivery, DeliveryStatus
from django.db.models import Count

qs = (WebhookDelivery.objects
      .filter(status=DeliveryStatus.DEAD_LETTER)
      .values('webhook__tenant__name', 'webhook__url')
      .annotate(count=Count('id'))
      .order_by('-count')[:20])
for row in qs:
    print(f\"{row['webhook__tenant__name']}: {row['count']} DLQ → {row['webhook__url']}\")
"
```

### 3. Inspect error messages on recent DLQ entries

```sql
SELECT id, webhook_id, event_type, error_message, retry_count, created_at
FROM webhook_deliveries
WHERE status = 'DEAD_LETTER'
ORDER BY created_at DESC
LIMIT 20;
```

Common error patterns:
- **Connection refused / timeout** → subscriber endpoint is down or unreachable
- **HTTP 5xx** → subscriber application error
- **HTTP 429** → subscriber rate-limiting the webhook source
- **TLS / certificate error** → subscriber TLS configuration changed
- **Signature verification failed** → signing key rotated without subscriber update

### 4. Check for signing-key rotation issues

If the error is signature-related, verify:
- The `WebhookSigningKey` for the affected webhook is ACTIVE
- The subscriber has the correct public `key_id` in their verification logic
- No recent key rotation that the subscriber hasn't picked up

```bash
python manage.py shell -c "
from hub.apps.webhooks.models import WebhookSigningKey, WebhookSigningKeyStatus
keys = WebhookSigningKey.objects.filter(status=WebhookSigningKeyStatus.ACTIVE)
for k in keys:
    print(f'{k.webhook_id} → {k.key_id} (ACTIVE)')
"
```

### 5. Check per-tenant rate limits

If the tenant's outbound webhook rate limit is exhausted, new deliveries
may be rate-limited. Check `TenantConfig.rate_limits` for the tenant.

## Remediation

### Replay dead-lettered deliveries

To replay DLQ deliveries for a specific tenant:

```bash
python manage.py shell -c "
from hub.apps.webhooks.models import WebhookDelivery, DeliveryStatus
from hub.apps.webhooks.tasks import deliver_webhook

# Replay the 10 most recent DLQ deliveries for tenant X
tenant_id = '<UUID>'
dlq = (WebhookDelivery.objects
       .filter(status=DeliveryStatus.DEAD_LETTER, webhook__tenant_id=tenant_id)
       .order_by('-created_at')[:10])
for d in dlq:
    deliver_webhook.delay(str(d.id))
    print(f'Re-enqueued delivery {d.id}')
"
```

### Fix subscriber endpoint

If the subscriber endpoint is permanently down:
1. Contact the subscriber via their registered email
2. If the webhook subscription is abandoned, deactivate the webhook
3. Replay any missed events after the subscriber confirms they're back online

### Bulk DLQ purge

To purge DLQ entries for a deactivated webhook (irrecoverable):

```bash
python manage.py shell -c "
from hub.apps.webhooks.models import WebhookDelivery, DeliveryStatus
# WARNING: permanently deletes DLQ entries — cannot be undone
WebhookDelivery.objects.filter(
    status=DeliveryStatus.DEAD_LETTER,
    webhook_id='<UUID>',
).delete()
"
```

## Prevention

- Monitor `webhook_dlq_size` growth rate; an increase >10/hour warrants investigation
- Set up subscriber endpoint health checks on the webhook registration page
- Ensure signing-key rotation follows the documented procedure with subscriber notification
- Review per-tenant rate limits quarterly to ensure they match expected volume

## Related

- Alert: `monitoring/prometheus/alerts/webhooks.yml`
- Metric: `hub/apps/observability/otel_metrics.py` → `webhook_dlq_size`
- Emitter: `hub/apps/webhooks/dlsla_metrics.py` → `emit_webhook_dlq_metrics`
- Model: `hub/apps/webhooks/models.py` → `WebhookDelivery.DeliveryStatus`
- Signing key rotation: `hub/apps/webhooks/management/commands/drill_webhook_key_rotation.py`

## Maintenance

| Owner | Last reviewed | Next review |
|---|---|---|
| Platform Engineering | 2026-05-13 | 2026-08-11 |
