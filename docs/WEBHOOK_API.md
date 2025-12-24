# Webhook API Documentation

Complete guide for webhook subscriptions, delivery, and retry logic, including ODPS (Open Data Product Standard) event support.

## Table of Contents

1. [Overview](#overview)
2. [Webhook Subscriptions](#webhook-subscriptions)
3. [Event Types](#event-types)
4. [ODPS Events](#odps-events)
5. [Delivery and Retry](#delivery-and-retry)
6. [Authentication](#authentication)
7. [API Reference](#api-reference)
8. [Payload Examples](#payload-examples)
9. [Configuration Examples](#configuration-examples)
10. [Best Practices](#best-practices)

---

## Overview

The webhook system provides:

- **Event Subscriptions**: Subscribe to specific event types including ODPS events
- **Automatic Delivery**: Deliver webhooks asynchronously when events occur
- **Retry Logic**: Exponential backoff retry (1s, 5s, 30s, 5m, 30m)
- **Authentication**: HMAC-SHA256 signature for webhook authentication
- **Delivery Tracking**: Complete delivery history and status tracking
- **ODPS Support**: Full support for Open Data Product Standard events

---

## Webhook Subscriptions

### Creating a Webhook

Webhooks can be created via the REST API or programmatically. Each webhook subscribes to one or more event types and will receive notifications when those events occur.

### Webhook Configuration

- **URL**: Endpoint to receive webhooks (must be HTTPS in production)
- **Secret**: Shared secret for HMAC signature generation
- **Event Types**: List of event types to subscribe to
- **Status**: ACTIVE, PAUSED, or DISABLED
- **Max Retries**: Maximum number of delivery retries (default: 5)
- **Retry Intervals**: Retry intervals in seconds (default: [1, 5, 30, 300, 1800])

---

## Event Types

### Contract Events

- `contract.created`: Contract created
- `contract.updated`: Contract updated
- `contract.deleted`: Contract deleted

### Asset Events

- `asset.created`: Asset created
- `asset.updated`: Asset updated
- `asset.activated`: Asset activated

### Ingestion Events

- `ingestion.completed`: Scheduled ingestion completed
- `ingestion.failed`: Scheduled ingestion failed

### Quality Events

- `quality.check.completed`: Data quality check completed
- `compliance.check.completed`: Compliance check completed

### Version Events

- `version.created`: Dataset version created
- `version.updated`: Dataset version updated

---

## ODPS Events

The webhook system provides comprehensive support for Open Data Product Standard (ODPS) events. These events are triggered when ODPS contracts are created, updated, normalized, linked, or exported.

### ODPS Event Types

#### Lifecycle Events

- **`odps.created`**: ODPS contract created
  - Triggered when a new ODPS contract is created or generated from an ODCS contract
  - Contains contract metadata, ODPS version, and status information

- **`odps.updated`**: ODPS contract updated
  - Triggered when an existing ODPS contract is modified
  - Contains information about what changed

- **`odps.deleted`**: ODPS contract deleted
  - Triggered when an ODPS contract is deleted
  - Contains contract identification information

#### Processing Events

- **`odps.normalized`**: ODPS contract normalized
  - Triggered when an ODPS contract is successfully normalized
  - Contains normalization status and metadata

#### Linking Events

- **`odps.linked`**: ODPS contract linked to another contract
  - Triggered when an ODPS contract is linked to an ODCS contract or another ODPS contract
  - Contains source and target contract IDs

- **`odps.unlinked`**: ODPS contract unlinked from another contract
  - Triggered when a link between ODPS contracts is removed
  - Contains source and target contract IDs

#### Export Events

- **`odps.export.started`**: ODPS export operation started
  - Triggered when an ODPS contract export begins
  - Contains export format and target information

- **`odps.export.completed`**: ODPS export operation completed successfully
  - Triggered when an ODPS contract export finishes successfully
  - Contains export format and result information

- **`odps.export.failed`**: ODPS export operation failed
  - Triggered when an ODPS contract export fails
  - Contains error information and export format

### Subscribing to ODPS Events

You can subscribe to individual ODPS events or all ODPS events:

```json
{
  "name": "ODPS Lifecycle Webhook",
  "url": "https://example.com/webhooks/odps",
  "event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted"
  ],
  "status": "ACTIVE"
}
```

Or subscribe to all ODPS events:

```json
{
  "name": "All ODPS Events Webhook",
  "url": "https://example.com/webhooks/odps-all",
  "event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted",
    "odps.normalized",
    "odps.linked",
    "odps.unlinked",
    "odps.export.started",
    "odps.export.completed",
    "odps.export.failed"
  ],
  "status": "ACTIVE"
}
```

---

## Delivery and Retry

### Delivery Process

1. **Event Triggered**: ODPS event occurs in the system
2. **Webhook Matching**: Find active webhooks subscribed to the event type
3. **Payload Creation**: Build webhook payload with event data
4. **Payload Validation**: Validate ODPS webhook payload structure and data
5. **Signature Generation**: Generate HMAC-SHA256 signature
6. **HTTP Delivery**: POST payload to webhook URL
7. **Status Tracking**: Track delivery status and response

### Retry Logic

Exponential backoff retry with configurable intervals:

- **Attempt 1**: 1 second delay
- **Attempt 2**: 5 seconds delay
- **Attempt 3**: 30 seconds delay
- **Attempt 4**: 5 minutes delay
- **Attempt 5**: 30 minutes delay

After max retries, delivery moves to dead letter queue.

### Dead Letter Queue

Permanently failed deliveries (after max retries) are marked as `DEAD_LETTER` and can be manually retried via API.

---

## Authentication

### HMAC Signature

All webhooks include an HMAC-SHA256 signature in the `X-Webhook-Signature` header. The signature is computed from the JSON payload using the webhook secret.

**Signature Generation**:

```python
import hmac
import hashlib
import json

# Sort keys for consistent signature
payload_json = json.dumps(payload, sort_keys=True)

# Generate signature
signature = hmac.new(
    secret.encode('utf-8'),
    payload_json.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

**HTTP Headers**:

- `Content-Type: application/json`
- `X-Webhook-Signature: <64-character hex string>`
- `X-Webhook-Event-Type: <event_type>`
- `User-Agent: DataInteroperabilityHub/1.0`

### Verification

```python
import hmac
import hashlib

# In webhook receiver
received_signature = request.headers.get('X-Webhook-Signature')
payload_json = request.body.decode('utf-8')

expected_signature = hmac.new(
    secret.encode('utf-8'),
    payload_json.encode('utf-8'),
    hashlib.sha256
).hexdigest()

if hmac.compare_digest(received_signature, expected_signature):
    # Valid webhook
    process_webhook(payload)
else:
    # Invalid signature - reject
    return 401, "Invalid signature"
```

**Security Note**: Always use `hmac.compare_digest()` to prevent timing attacks.

---

## API Reference

### Webhook CRUD API

#### `POST /api/v1/webhooks/`

Create webhook subscription.

**Request Body**:
```json
{
  "name": "ODPS Created Webhook",
  "url": "https://example.com/webhooks/odps-created",
  "event_types": ["odps.created"],
  "status": "ACTIVE",
  "max_retries": 5,
  "retry_intervals": [1, 5, 30, 300, 1800]
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ODPS Created Webhook",
  "url": "https://example.com/webhooks/odps-created",
  "event_types": ["odps.created"],
  "status": "ACTIVE",
  "max_retries": 5,
  "retry_intervals": [1, 5, 30, 300, 1800],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/v1/webhooks/`

List webhook subscriptions.

**Query Parameters**:
- `status`: Filter by status (ACTIVE, PAUSED, DISABLED)
- `event_type`: Filter by event type

**Response** (200 OK):
```json
{
  "count": 2,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "ODPS Created Webhook",
      "url": "https://example.com/webhooks/odps-created",
      "event_types": ["odps.created"],
      "status": "ACTIVE"
    }
  ]
}
```

#### `GET /api/v1/webhooks/{id}/`

Get webhook subscription.

#### `PATCH /api/v1/webhooks/{id}/`

Update webhook subscription.

#### `DELETE /api/v1/webhooks/{id}/`

Delete webhook subscription.

#### `POST /api/v1/webhooks/{id}/test/`

Test webhook delivery with a test payload.

#### `GET /api/v1/webhooks/{id}/deliveries/`

Get webhook delivery history.

**Response** (200 OK):
```json
{
  "count": 10,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "event_type": "odps.created",
      "status": "SUCCESS",
      "attempt_number": 1,
      "http_status_code": 200,
      "delivered_at": "2024-01-15T10:31:00Z",
      "created_at": "2024-01-15T10:30:55Z"
    }
  ]
}
```

#### `GET /api/v1/webhooks/event-types/`

Get available webhook event types.

**Query Parameters**:
- `odps_only`: If `true`, return only ODPS event types

**Response** (200 OK):
```json
{
  "event_types": [
    {
      "value": "odps.created",
      "label": "ODPS Created"
    },
    {
      "value": "odps.updated",
      "label": "ODPS Updated"
    }
  ],
  "odps_event_types": [
    "odps.created",
    "odps.updated",
    "odps.deleted",
    "odps.normalized",
    "odps.linked",
    "odps.unlinked",
    "odps.export.started",
    "odps.export.completed",
    "odps.export.failed"
  ]
}
```

### Webhook Delivery API

#### `GET /api/v1/webhook-deliveries/`

List webhook deliveries (read-only).

#### `GET /api/v1/webhook-deliveries/{id}/`

Get webhook delivery details.

#### `POST /api/v1/webhook-deliveries/{id}/retry/`

Retry a failed webhook delivery.

---

## Payload Examples

### Standard Payload Structure

All webhook payloads follow this structure:

```json
{
  "event_type": "odps.created",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "data": {
    // Event-specific data
  }
}
```

### ODPS Event Payloads

#### `odps.created`

Triggered when an ODPS contract is created.

```json
{
  "event_type": "odps.created",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "DRAFT",
    "odps_version": "4.1",
    "original_format": "JSON",
    "normalization_status": "PENDING"
  }
}
```

#### `odps.updated`

Triggered when an ODPS contract is updated.

```json
{
  "event_type": "odps.updated",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:35:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "changes": {
      "status": {
        "old": "DRAFT",
        "new": "ACTIVE"
      },
      "odps_version": {
        "old": "4.0",
        "new": "4.1"
      }
    },
    "updated_fields": ["status", "odps_version"]
  }
}
```

#### `odps.deleted`

Triggered when an ODPS contract is deleted.

```json
{
  "event_type": "odps.deleted",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:40:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "deleted_at": "2024-01-15T10:40:00.123456Z"
  }
}
```

#### `odps.normalized`

Triggered when an ODPS contract is successfully normalized.

```json
{
  "event_type": "odps.normalized",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:45:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "normalization_status": "NORMALIZED_OK",
    "odps_version": "4.1",
    "validation_status": "VALID",
    "normalized_at": "2024-01-15T10:45:00.123456Z"
  }
}
```

#### `odps.linked`

Triggered when an ODPS contract is linked to another contract.

```json
{
  "event_type": "odps.linked",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:50:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_id": "770e8400-e29b-41d4-a716-446655440002",
    "link_type": "ODPS_TO_ODCS",
    "linked_at": "2024-01-15T10:50:00.123456Z"
  }
}
```

#### `odps.unlinked`

Triggered when a link between ODPS contracts is removed.

```json
{
  "event_type": "odps.unlinked",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:55:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_id": "770e8400-e29b-41d4-a716-446655440002",
    "link_type": "ODPS_TO_ODCS",
    "unlinked_at": "2024-01-15T10:55:00.123456Z"
  }
}
```

#### `odps.export.started`

Triggered when an ODPS export operation begins.

```json
{
  "event_type": "odps.export.started",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:00:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "started_at": "2024-01-15T11:00:00.123456Z"
  }
}
```

#### `odps.export.completed`

Triggered when an ODPS export operation completes successfully.

```json
{
  "event_type": "odps.export.completed",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:05:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "export_url": "https://storage.example.com/exports/odps-550e8400.json",
    "file_size": 12345,
    "started_at": "2024-01-15T11:00:00.123456Z",
    "completed_at": "2024-01-15T11:05:00.123456Z",
    "duration_seconds": 300
  }
}
```

#### `odps.export.failed`

Triggered when an ODPS export operation fails.

```json
{
  "event_type": "odps.export.failed",
  "resource_type": "ODPS",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T11:10:00.123456Z",
  "data": {
    "contract_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_format": "JSON",
    "export_target": "FILE",
    "error": {
      "code": "EXPORT_FAILED",
      "message": "Failed to write export file",
      "details": "Disk quota exceeded"
    },
    "started_at": "2024-01-15T11:00:00.123456Z",
    "failed_at": "2024-01-15T11:10:00.123456Z",
    "duration_seconds": 600
  }
}
```

---

## Configuration Examples

### Python Example

```python
import requests

# Create ODPS webhook
webhook_data = {
    "name": "ODPS Lifecycle Webhook",
    "url": "https://example.com/webhooks/odps",
    "event_types": [
        "odps.created",
        "odps.updated",
        "odps.deleted",
        "odps.normalized"
    ],
    "status": "ACTIVE",
    "max_retries": 5,
    "retry_intervals": [1, 5, 30, 300, 1800]
}

response = requests.post(
    "https://api.example.com/api/v1/webhooks/",
    json=webhook_data,
    headers={
        "Authorization": "Bearer <token>",
        "Content-Type": "application/json"
    }
)

webhook = response.json()
print(f"Created webhook: {webhook['id']}")
```

### cURL Example

```bash
# Create ODPS webhook
curl -X POST https://api.example.com/api/v1/webhooks/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ODPS Export Webhook",
    "url": "https://example.com/webhooks/odps-export",
    "event_types": [
      "odps.export.started",
      "odps.export.completed",
      "odps.export.failed"
    ],
    "status": "ACTIVE"
  }'
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

// Create ODPS webhook
const webhookData = {
  name: 'ODPS Linked Events Webhook',
  url: 'https://example.com/webhooks/odps-links',
  event_types: [
    'odps.linked',
    'odps.unlinked'
  ],
  status: 'ACTIVE',
  max_retries: 5,
  retry_intervals: [1, 5, 30, 300, 1800]
};

axios.post('https://api.example.com/api/v1/webhooks/', webhookData, {
  headers: {
    'Authorization': 'Bearer <token>',
    'Content-Type': 'application/json'
  }
})
.then(response => {
  console.log('Created webhook:', response.data.id);
})
.catch(error => {
  console.error('Error creating webhook:', error);
});
```

### Webhook Receiver Example (Flask)

```python
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret"

@app.route('/webhooks/odps', methods=['POST'])
def handle_odps_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data()

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return jsonify({"error": "Invalid signature"}), 401

    # Process webhook
    data = request.json
    event_type = data['event_type']

    if event_type == 'odps.created':
        handle_odps_created(data)
    elif event_type == 'odps.updated':
        handle_odps_updated(data)
    # ... handle other event types

    return jsonify({"status": "ok"}), 200

def handle_odps_created(data):
    contract_id = data['data']['contract_id']
    print(f"ODPS contract created: {contract_id}")
    # Process the event...

if __name__ == '__main__':
    app.run(port=5000)
```

---

## Best Practices

### Webhook URL Design

1. **HTTPS Only**: Always use HTTPS for webhook URLs in production
2. **Idempotency**: Design webhook handlers to be idempotent (handle duplicate deliveries)
3. **Quick Response**: Respond quickly (within 5 seconds) to avoid timeouts
4. **Status Codes**: Return 2xx for success, 4xx/5xx for retry
5. **Async Processing**: Process webhooks asynchronously when possible

### Security Best Practices

1. **Secret Rotation**: Rotate webhook secrets periodically
2. **Signature Verification**: Always verify HMAC signature before processing
3. **Rate Limiting**: Implement rate limiting on webhook receivers
4. **IP Whitelisting**: Consider IP whitelisting for additional security
5. **TLS Verification**: Verify TLS certificates when making outbound requests

### Error Handling

1. **Retry Logic**: Use exponential backoff for retries (already handled by the system)
2. **Dead Letter Queue**: Monitor dead letter queue for issues
3. **Alerting**: Set up alerts for high failure rates
4. **Manual Retry**: Support manual retry for failed deliveries via API
5. **Logging**: Log all webhook deliveries for debugging

### ODPS-Specific Best Practices

1. **Event Filtering**: Subscribe only to ODPS events you need
2. **Payload Validation**: Validate ODPS payload structure in your receiver
3. **Contract Lookup**: Use `contract_id` from payload to fetch full contract details if needed
4. **Version Handling**: Check `odps_version` field to handle different ODPS versions
5. **Link Tracking**: Track `odps.linked` and `odps.unlinked` events to maintain relationship graphs

### Performance Considerations

1. **Batch Processing**: Process multiple webhooks in batches when possible
2. **Database Indexing**: Index webhook delivery tables for faster queries
3. **Monitoring**: Monitor webhook delivery latency and success rates
4. **Scaling**: Scale webhook receivers horizontally for high throughput

---

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [API Standards](API_STANDARDS.md) - API consistency standards
- [Event Bus](EVENT_BUS.md) - Event-driven communication
- [Event Types Reference](EVENT_TYPES_REFERENCE.md) - Complete event type documentation
- [Services Architecture](SERVICES_ARCHITECTURE.md) - Webhook service architecture

---

## Support

For issues or questions about webhooks:

1. Check delivery history via API: `GET /api/v1/webhooks/{id}/deliveries/`
2. Review error messages in failed deliveries
3. Test webhook configuration: `POST /api/v1/webhooks/{id}/test/`
4. Contact support with webhook ID and delivery ID for troubleshooting

