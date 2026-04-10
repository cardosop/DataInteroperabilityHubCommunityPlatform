# Webhooks

Meshant can send HTTP POST callbacks to your application when events occur
on the platform. Webhooks enable real-time integration without polling.

## Event Types

| Event | Description |
|-------|-------------|
| `asset.created` | A new data asset was created |
| `asset.published` | An asset was published to the marketplace |
| `asset.retired` | An asset was retired |
| `asset.updated` | Asset metadata was updated |
| `contract.created` | A new data contract was created |
| `contract.validated` | A contract passed or failed validation |
| `dq.started` | A data quality check run started |
| `dq.completed` | A data quality check run finished |
| `compliance.started` | A compliance scan started |
| `compliance.completed` | A compliance scan finished |
| `order.placed` | A marketplace order was placed |
| `order.fulfilled` | A marketplace order was fulfilled |
| `user.invited` | A user was invited to a tenant |
| `webhook.test` | A test event sent via the API |

You can subscribe to specific events or use wildcards (`asset.*`, `*`).

## Payload Format

Every webhook delivery sends a JSON payload:

```json
{
  "id": "evt_abc123",
  "type": "asset.published",
  "timestamp": "2026-04-09T14:30:00Z",
  "tenant_id": "t-001",
  "data": {
    "asset_id": "a-123",
    "name": "customer_events",
    "status": "published"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique event ID (use for deduplication) |
| `type` | `string` | Event type from the table above |
| `timestamp` | `string` | ISO 8601 UTC timestamp |
| `tenant_id` | `string` | Tenant that owns the resource |
| `data` | `object` | Event-specific payload |

## HMAC-SHA256 Signature Verification

Every delivery includes a `X-Meshant-Signature` header containing an
HMAC-SHA256 signature of the request body, computed with your webhook secret.

### Verification Example (Python)

```python
import hmac
import hashlib

def verify_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# In your webhook handler:
is_valid = verify_signature(
    payload_bytes=request.body,
    signature=request.headers["X-Meshant-Signature"],
    secret="whsec_your_secret_here"
)
```

### Verification Example (curl test)

```bash
echo -n '{"id":"evt_abc123"}' | \
  openssl dgst -sha256 -hmac "whsec_your_secret_here"
```

## Retry Policy

If your endpoint does not return a `2xx` status code, Meshant retries
the delivery with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 1 minute |
| 3 | 10 minutes |

After 3 failed attempts, the delivery is marked as failed. Failed
deliveries are visible in the webhook delivery log.

## Delivery Guarantees

- **At-least-once delivery** -- events may be delivered more than once.
  Use the `id` field to deduplicate on the consumer side.
- **Ordering** -- events are delivered in approximate chronological order
  but strict ordering is not guaranteed.
- **Timeout** -- your endpoint must respond within 10 seconds or the
  attempt is considered failed.

## Registering a Webhook

```bash
curl -X POST https://meshant-internal.example.com/api/v1/webhooks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/hooks/meshant",
    "events": ["asset.created", "dq.completed"],
    "secret": "whsec_abc123"
  }'
```

SDK:

```python
wh = client.webhooks.create(
    url="https://example.com/hooks/meshant",
    events=["asset.created", "dq.completed"],
    secret="whsec_abc123"
)
```

## Related

- [WebhooksAPI](../sdk-reference/python/webhooks-api.md) -- Python SDK reference
- [Error Codes](error-codes.md) -- WEBHOOK_DELIVERY_FAILED error code
- [Authentication](authentication.md) -- securing webhook endpoints
