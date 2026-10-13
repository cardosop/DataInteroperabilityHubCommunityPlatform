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

> Generated from `WebhookEventType` by `scripts/sync_webhook_events_doc.py` — run it when the enum changes; the drift gate (tests/docs/test_webhook_doc_drift.py) enforces the sync at CI time.

| Event | Trigger |
|---|---|
| `asset.activated` | An asset activated event occurs. (auto-generated — edit the doc row for a curated description) |
| `asset.created` | An asset created event occurs. (auto-generated — edit the doc row for a curated description) |
| `asset.updated` | An asset updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.dq.run.completed` | A billing completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.report.generated` | A billing generated event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.report.sent` | A billing sent event occurs. (auto-generated — edit the doc row for a curated description) |
| `breach.incident.opened` | A breach opened event occurs. (auto-generated — edit the doc row for a curated description) |
| `breach.notification.sent` | A breach sent event occurs. (auto-generated — edit the doc row for a curated description) |
| `compliance.check.completed` | A compliance completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `compliance.completed` | A compliance completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `consent.granted` | A consent granted event occurs. (auto-generated — edit the doc row for a curated description) |
| `consent.revoked` | A consent revoked event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.batch_renormalized` | A contract batch renormalized event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.created` | A contract created event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.deleted` | A contract deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.updated` | A contract updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.budget.exceeded` | A databricks exceeded event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.dlt.update.failed` | A databricks failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.job.run.failed` | A databricks failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.approved` | A databricks approved event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.executed` | A databricks executed event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.failed` | A databricks failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.rejected` | A databricks rejected event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.rolled_back` | A databricks rolled back event occurs. (auto-generated — edit the doc row for a curated description) |
| `databricks.uc_change.submitted` | A databricks submitted event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.created` | A dpia created event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.review.decision` | A dpia decision event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.status.changed` | A dpia changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.fulfilled` | A dsar fulfilled event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.rejected` | A dsar rejected event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.critical` | A dsar critical event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.escalated` | A dsar escalated event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.suspended` | A dsar suspended event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.warning` | A dsar warning event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.status.changed` | A dsar changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.submitted` | A dsar submitted event occurs. (auto-generated — edit the doc row for a curated description) |
| `file.purged` | A file purged event occurs. (auto-generated — edit the doc row for a curated description) |
| `ingestion.completed` | An ingestion completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ingestion.failed` | An ingestion failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.compliance.checked` | A mesh checked event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.domain.created` | A mesh created event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.domain.updated` | A mesh updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.health.status_changed` | A mesh status changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.policy.applied` | A mesh applied event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.topology.updated` | A mesh updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.inference.executed` | A ml executed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.archived` | A ml archived event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.deployed` | A ml deployed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.registered` | A ml registered event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.completed` | A ml completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.failed` | A ml failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.started` | A ml started event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.created` | An odps created event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.deleted` | An odps deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.completed` | An odps completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.failed` | An odps failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.started` | An odps started event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.linked` | An odps linked event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.normalized` | An odps normalized event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.unlinked` | An odps unlinked event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.updated` | An odps updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `processor_agreement.expired` | A processor_agreement expired event occurs. (auto-generated — edit the doc row for a curated description) |
| `processor_agreement.expiring` | A processor_agreement expiring event occurs. (auto-generated — edit the doc row for a curated description) |
| `quality.check.completed` | A quality completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ropa.generated` | A ropa generated event occurs. (auto-generated — edit the doc row for a curated description) |
| `transformation.completed` | A transformation completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `transformation.failed` | A transformation failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `version.created` | A version created event occurs. (auto-generated — edit the doc row for a curated description) |
| `version.updated` | A version updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.dataset.created` | A virtualization created event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.completed` | A virtualization completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.failed` | A virtualization failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.progress` | A virtualization progress event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.started` | A virtualization started event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.created` | A warehouse created event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.deleted` | A warehouse deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.test_failed` | A warehouse test failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.updated` | A warehouse updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.export.completed` | A warehouse completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.export.failed` | A warehouse failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.schema.drift_detected` | A warehouse drift detected event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.share.accessed` | A warehouse accessed event occurs. (auto-generated — edit the doc row for a curated description) |
| `webhook.test` | A webhook test event occurs. (auto-generated — edit the doc row for a curated description) |

## Supported Events

> Generated from `WebhookEventType` by `scripts/sync_webhook_events_doc.py` — run it when the enum changes; the drift gate (tests/docs/test_webhook_doc_drift.py) enforces the sync at CI time.

| Event | Trigger |
|---|---|
| `asset.activated` | A asset activated event occurs. (auto-generated — edit the doc row for a curated description) |
| `asset.created` | A new asset is registered. |
| `asset.updated` | A asset updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.dq.run.completed` | A billing completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.report.generated` | A billing generated event occurs. (auto-generated — edit the doc row for a curated description) |
| `billing.report.sent` | A billing sent event occurs. (auto-generated — edit the doc row for a curated description) |
| `breach.incident.opened` | A breach opened event occurs. (auto-generated — edit the doc row for a curated description) |
| `breach.notification.sent` | A breach sent event occurs. (auto-generated — edit the doc row for a curated description) |
| `compliance.check.completed` | A compliance completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `compliance.completed` | A compliance run finishes. |
| `consent.granted` | A consent granted event occurs. (auto-generated — edit the doc row for a curated description) |
| `consent.revoked` | A consent revoked event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.batch_renormalized` | A contract batch renormalized event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.created` | A contract created event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.deleted` | A contract deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `contract.updated` | A contract updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.created` | A dpia created event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.review.decision` | A dpia decision event occurs. (auto-generated — edit the doc row for a curated description) |
| `dpia.status.changed` | A dpia changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.fulfilled` | A dsar fulfilled event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.rejected` | A dsar rejected event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.critical` | A dsar critical event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.escalated` | A dsar escalated event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.suspended` | A dsar suspended event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.sla.warning` | A dsar warning event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.status.changed` | A dsar changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `dsar.submitted` | A dsar submitted event occurs. (auto-generated — edit the doc row for a curated description) |
| `file.purged` | A file purged event occurs. (auto-generated — edit the doc row for a curated description) |
| `ingestion.completed` | A ingestion completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ingestion.failed` | A ingestion failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.compliance.checked` | A mesh checked event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.domain.created` | A mesh created event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.domain.updated` | A mesh updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.health.status_changed` | A mesh status changed event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.policy.applied` | A mesh applied event occurs. (auto-generated — edit the doc row for a curated description) |
| `mesh.topology.updated` | A mesh updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.inference.executed` | A ml executed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.archived` | A ml archived event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.deployed` | A ml deployed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.model.registered` | A ml registered event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.completed` | A ml completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.failed` | A ml failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ml.training.started` | A ml started event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.created` | A odps created event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.deleted` | A odps deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.completed` | A odps completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.failed` | A odps failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.export.started` | A odps started event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.linked` | A odps linked event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.normalized` | A odps normalized event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.unlinked` | A odps unlinked event occurs. (auto-generated — edit the doc row for a curated description) |
| `odps.updated` | A odps updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `processor_agreement.expired` | A processor_agreement expired event occurs. (auto-generated — edit the doc row for a curated description) |
| `processor_agreement.expiring` | A processor_agreement expiring event occurs. (auto-generated — edit the doc row for a curated description) |
| `quality.check.completed` | A quality completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `ropa.generated` | A ropa generated event occurs. (auto-generated — edit the doc row for a curated description) |
| `transformation.completed` | A transformation completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `transformation.failed` | A transformation failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `version.created` | A version created event occurs. (auto-generated — edit the doc row for a curated description) |
| `version.updated` | A version updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.dataset.created` | A virtualization created event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.completed` | A virtualization completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.failed` | A virtualization failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.progress` | A virtualization progress event occurs. (auto-generated — edit the doc row for a curated description) |
| `virtualization.query.execution.started` | A virtualization started event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.created` | A warehouse created event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.deleted` | A warehouse deleted event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.test_failed` | A warehouse test failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.connection.updated` | A warehouse updated event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.export.completed` | A warehouse completed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.export.failed` | A warehouse failed event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.schema.drift_detected` | A warehouse drift detected event occurs. (auto-generated — edit the doc row for a curated description) |
| `warehouse.share.accessed` | A warehouse accessed event occurs. (auto-generated — edit the doc row for a curated description) |
| `webhook.test` | A webhook test event occurs. (auto-generated — edit the doc row for a curated description) |

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
