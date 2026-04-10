# How-To: Handle Webhooks

Webhooks allow your application to receive real-time notifications when
events occur on the Meshant platform. This guide covers setup, signature
verification, and best practices.


## Registering a Webhook

### Via the SDK

```python
from datahub_interoperability import DataHubClient

client = DataHubClient.from_env()

webhook = client.webhooks.create(
    url="https://your-app.example.com/webhooks/meshant",
    events=[
        "asset.published",
        "asset.archived",
        "dq.check.completed",
        "compliance.scan.completed",
        "contract.created",
        "contract.expired",
    ],
    secret="a-strong-random-secret",
)
print(f"Created webhook {webhook.id}")
```

### Via the CLI

```bash
datahub-cli webhooks create \
  --url "https://your-app.example.com/webhooks/meshant" \
  --events "asset.published,dq.check.completed,contract.created" \
  --secret "a-strong-random-secret"
```

### Via the API

```bash
curl -X POST https://meshant-internal.example.com/api/v1/webhooks/webhooks/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.example.com/webhooks/meshant",
    "events": ["asset.published", "dq.check.completed"],
    "secret": "a-strong-random-secret"
  }'
```


## Verifying Signatures

Every webhook delivery includes an `X-Meshant-Signature` header
containing an HMAC-SHA256 hex digest of the request body, computed with
the secret you provided at registration.

**Always verify this signature** before processing the payload.

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: bytes) -> bool:
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Example in a Flask handler:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
WEBHOOK_SECRET = b"a-strong-random-secret"

@app.route("/webhooks/meshant", methods=["POST"])
def handle():
    sig = request.headers.get("X-Meshant-Signature", "")
    if not verify_signature(request.data, sig, WEBHOOK_SECRET):
        return jsonify({"error": "invalid signature"}), 401

    event = request.json
    event_type = event["type"]
    resource_id = event["resource_id"]
    timestamp = event["timestamp"]

    # Route to handler based on event type
    if event_type == "asset.published":
        handle_asset_published(resource_id)
    elif event_type == "dq.check.completed":
        handle_dq_completed(resource_id, event["payload"])

    return jsonify({"status": "ok"}), 200
```


## Event Payload Structure

All webhook payloads follow a consistent structure:

```json
{
  "id": "evt_abc123",
  "type": "asset.published",
  "resource_id": "a1b2c3d4-...",
  "tenant_id": "t_xyz789",
  "timestamp": "2026-04-09T14:30:00Z",
  "payload": {
    "name": "Customer Demographics",
    "status": "ACTIVE",
    "published_by": "user@example.com"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique event ID (for idempotency) |
| `type` | string | Event type identifier |
| `resource_id` | string | ID of the affected resource |
| `tenant_id` | string | Tenant that owns the resource |
| `timestamp` | string | ISO 8601 timestamp |
| `payload` | object | Event-specific data |


## Retry Policy

If your endpoint returns a non-2xx status or does not respond within
30 seconds, Meshant retries the delivery:

| Attempt | Delay |
|---------|-------|
| 1st retry | 1 minute |
| 2nd retry | 5 minutes |
| 3rd retry | 30 minutes |
| 4th retry | 2 hours |
| 5th retry | 12 hours |

After 5 failed retries, the webhook is marked `INACTIVE`. Reactivate it
via the API or admin panel once your endpoint is healthy.


## Idempotency

Use the `id` field in the event payload to detect duplicate deliveries.
Store processed event IDs and skip duplicates. This is important because
retries can deliver the same event more than once.


## Managing Webhooks

```bash
# List registered webhooks
datahub-cli webhooks list --format table

# View webhook delivery history
datahub-cli webhooks deliveries --webhook-id <id> --format table

# Deactivate a webhook
datahub-cli webhooks update --id <id> --status INACTIVE
```


## See Also

- [How-To: Authenticate and Authorize](authenticate-and-authorize.md)
- [How-To: Integrate Semantic Layer](integrate-semantic-layer.md)
- [External Developer Reference](../reference.md)
