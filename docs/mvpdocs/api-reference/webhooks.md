# Meshant Webhooks API

The Webhooks API lets tenants register HTTP callback endpoints that
receive real-time notifications when events occur on the platform --
such as dataset creation, quality check completion, or compliance
findings. Each webhook can subscribe to specific event types and
includes HMAC signature verification for security.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/webhooks/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /webhooks/ | List registered webhook endpoints |
| POST | /webhooks/ | Register a new webhook endpoint |
| GET | /webhooks/{id}/ | Get webhook details by ID |
| PUT | /webhooks/{id}/ | Update URL, events, or secret for a webhook |
| DELETE | /webhooks/{id}/ | Delete a webhook endpoint |
| POST | /webhooks/{id}/test/ | Send a test payload to the webhook URL |
| GET | /webhooks/{id}/deliveries/ | List delivery attempts for a webhook |
| GET | /webhooks/{id}/deliveries/{delivery_id}/ | Get delivery details including response |
| POST | /webhooks/{id}/deliveries/{delivery_id}/retry/ | Retry a failed delivery |
| GET | /webhooks/events/ | List all subscribable event types |

## Request / Response Examples

### POST /webhooks/

**Request body:**

```json
{
  "url": "https://hooks.example.com/meshant",
  "events": ["dataset.created", "dq.check.completed", "compliance.finding.opened"],
  "secret": "whsec_mySharedSecret",
  "active": true
}
```

**Response 201:**

```json
{
  "id": "whk_001",
  "url": "https://hooks.example.com/meshant",
  "events": ["dataset.created", "dq.check.completed", "compliance.finding.opened"],
  "active": true,
  "created_at": "2026-04-09T16:00:00Z"
}
```

### POST /webhooks/{id}/test/

**Response 200:**

```json
{
  "delivery_id": "dlv_test_001",
  "status_code": 200,
  "response_time_ms": 142,
  "success": true
}
```

## Payload Signature

Every webhook delivery includes an `X-Meshant-Signature` header containing
an HMAC-SHA256 digest of the request body, computed using the webhook secret.
Verify this signature on your server to confirm authenticity.

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `active` (bool) -- Filter by active/inactive status.
- `event` (string) -- Filter deliveries by event type.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `WEBHOOK_URL_INVALID` | URL is not reachable or uses an unsupported scheme |
| 400 | `WEBHOOK_EVENT_UNKNOWN` | One or more event types are not recognized |
| 404 | `WEBHOOK_NOT_FOUND` | Webhook ID does not exist |
| 404 | `WEBHOOK_DELIVERY_NOT_FOUND` | Delivery ID does not exist |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub webhooks`](../cli-reference/webhooks.md)
- SDK: [`WebhooksAPI`](../sdk-reference/python/webhooks.md)
