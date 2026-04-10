# Webhooks

Webhooks in Meshant deliver real-time event notifications to external HTTP endpoints. When a significant action occurs on the platform -- such as an asset being published, a DQ run completing, or a marketplace order being placed -- the system sends an HTTP POST request with a JSON payload describing the event. Webhooks enable integrations with external systems, monitoring tools, and automation pipelines without requiring polling.

Each webhook configuration is scoped to a [tenant](tenants.md) and managed by users with the `admin` or `tenant-admin` [role](users-and-roles.md). A tenant can register multiple endpoints and subscribe each to different event types.

## Lifecycle

| State | Description |
|---|---|
| `active` | The webhook is enabled and will fire for subscribed events. |
| `paused` | The webhook is temporarily disabled. Events are not queued or delivered. |
| `disabled` | The webhook has been automatically disabled after exceeding the failure threshold (10 consecutive delivery failures). |

An `active` webhook transitions to `disabled` after 10 consecutive delivery failures. It can be manually re-enabled after the endpoint issue is resolved. Pausing and resuming is an explicit user action.

## Supported Events

| Event | Trigger |
|---|---|
| `asset.created` | A new asset is registered. |
| `asset.published` | An asset transitions to the `published` state. |
| `asset.unpublished` | A published asset is pulled back to `active`. |
| `asset.archived` | An asset is archived. |
| `dq.completed` | A DQ run finishes (succeeded or failed). |
| `compliance.completed` | A compliance run finishes. |
| `contract.activated` | A contract version becomes active. |
| `contract.superseded` | A contract version is superseded by a newer version. |
| `order.placed` | A marketplace listing is purchased. |
| `job.completed` | A generic job finishes execution. |
| `user.invited` | A user invitation is sent. |
| `tenant.suspended` | A tenant is suspended. |

## Payload Format

Every webhook delivery includes a JSON payload with the following structure:

```json
{
  "id": "evt_abc123",
  "type": "dq.completed",
  "timestamp": "2026-04-09T14:30:00Z",
  "tenant_id": "tnt_xyz789",
  "data": {
    "run_id": "dqr_456",
    "asset_id": "ast_789",
    "score": 87,
    "status": "SUCCEEDED"
  }
}
```

The `data` field varies by event type but always includes the primary resource ID and a summary of the change.

## Security

- **Signature verification** -- Every delivery includes an `X-Meshant-Signature` header containing an HMAC-SHA256 signature computed over the raw request body using the webhook's secret key. Consumers must verify this signature to confirm the request originated from Meshant.
- **Secret rotation** -- Webhook secrets can be rotated without downtime. During rotation, both the old and new secrets are valid for a configurable overlap period (default: 24 hours).
- **HTTPS only** -- Webhook endpoints must use HTTPS. HTTP URLs are rejected at registration time.

## Retry Policy

Failed deliveries (non-2xx response or connection timeout) are retried with exponential backoff:

| Attempt | Delay |
|---|---|
| 1st retry | 30 seconds |
| 2nd retry | 2 minutes |
| 3rd retry | 10 minutes |
| 4th retry | 1 hour |
| 5th retry | 6 hours |

After 5 failed retries, the delivery is marked as permanently failed. If 10 consecutive deliveries fail, the webhook is automatically disabled.

## Relationships

- **Tenants** -- Webhooks are scoped to a [tenant](tenants.md). Each tenant manages its own webhook endpoints.
- **Assets** -- Asset lifecycle events (`asset.created`, `asset.published`, etc.) trigger webhook deliveries for the owning [tenant](tenants.md).
- **DQ Runs** -- The `dq.completed` event delivers summary results from [DQ runs](dq-runs.md).
- **Compliance Runs** -- The `compliance.completed` event delivers risk level and categories from [compliance runs](compliance-runs.md).
- **Marketplace Listings** -- The `order.placed` event notifies sellers of [marketplace](marketplace-listings.md) purchases.
- **Audit Events** -- Webhook deliveries (both successful and failed) are logged as [audit events](audit-events.md).
- **Users and Roles** -- Only `admin` and `tenant-admin` [roles](users-and-roles.md) can manage webhook configurations.

## MVP Scope

**Available at launch:**

- Webhook registration via API, CLI, and SDK.
- Subscription to individual event types or wildcard (all events).
- HMAC-SHA256 signature verification.
- Exponential backoff retry policy.
- Automatic disabling after consecutive failures.
- Delivery history log with response status codes.
- Manual retry of failed deliveries.

**Post-MVP:**

- Webhook filtering by resource attributes (e.g., only assets in a specific domain).
- Batched delivery (multiple events in a single request).
- Dead letter queue for permanently failed deliveries.
- Webhook testing endpoint (send a sample event for validation).
- Custom payload templates with Jinja-style transformations.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create webhook | `POST /api/v1/webhooks` | `meshant webhook create` | `client.webhooks.create()` |
| Get webhook | `GET /api/v1/webhooks/{id}` | `meshant webhook get <id>` | `client.webhooks.get(id)` |
| List webhooks | `GET /api/v1/webhooks` | `meshant webhook list` | `client.webhooks.list()` |
| Update webhook | `PATCH /api/v1/webhooks/{id}` | `meshant webhook update <id>` | `client.webhooks.update(id)` |
| Delete webhook | `DELETE /api/v1/webhooks/{id}` | `meshant webhook delete <id>` | `client.webhooks.delete(id)` |
| List deliveries | `GET /api/v1/webhooks/{id}/deliveries` | `meshant webhook deliveries <id>` | `client.webhooks.deliveries(id)` |
| Retry delivery | `POST /api/v1/webhooks/{id}/deliveries/{did}/retry` | `meshant webhook retry <id> <did>` | `client.webhooks.retry(id, did)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for event type details and signature verification examples.
