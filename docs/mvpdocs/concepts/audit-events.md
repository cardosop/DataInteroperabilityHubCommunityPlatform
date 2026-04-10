# Audit Events

Audit events are immutable log entries that record every significant action taken on the Meshant platform. Each entry captures who performed the action, what was changed, when it happened, and where the request originated. Audit events form the backbone of regulatory compliance, incident investigation, and operational accountability.

All audit records are retained for a minimum of 3 years, in compliance with common regulatory requirements (GDPR, SOC 2, HIPAA). Events are append-only and cannot be modified or deleted, even by platform administrators.

## Lifecycle

Audit events do not have a traditional lifecycle -- they are created once and exist immutably. However, they do progress through processing stages:

| Stage | Description |
|---|---|
| `ingested` | The event has been captured and written to the durable log. |
| `indexed` | The event has been indexed for search and filtering. There may be a brief delay (seconds) between ingestion and indexing. |
| `archived` | After the active retention period (configurable, default 90 days), events move to cold storage. They remain queryable but with higher latency. |
| `expired` | After the 3-year retention period, events are permanently deleted. Tenants can extend this period if required. |

## Event Structure

Every audit event contains the following fields:

| Field | Description |
|---|---|
| `event_id` | Globally unique identifier for the event (UUID v7, time-ordered). |
| `timestamp` | ISO 8601 timestamp of when the action occurred (microsecond precision). |
| `tenant_id` | The [tenant](tenants.md) in which the action occurred. |
| `actor_id` | The [user](users-and-roles.md) or service account that performed the action. |
| `actor_role` | The role the actor held at the time of the action. |
| `action` | The operation performed (e.g., `asset.create`, `contract.bind`, `user.suspend`). |
| `resource_type` | The type of resource affected (asset, contract, dataset, user, etc.). |
| `resource_id` | The identifier of the affected resource. |
| `details` | A JSON object with action-specific context (old/new values for updates, reason for suspension, etc.). |
| `source_ip` | The IP address from which the request originated. |
| `user_agent` | The client that made the request (CLI version, SDK version, browser). |
| `request_id` | Correlation ID for tracing the request across platform components. |

## Relationships

- **Users and Roles** -- Every audit event records the [user](users-and-roles.md) who performed the action and their role at the time.
- **Tenants** -- Audit events are partitioned by [tenant](tenants.md). Each tenant's log is isolated and independently queryable.
- **Assets** -- Asset lifecycle transitions (create, validate, publish, archive) generate audit events linked to the [asset](assets.md).
- **Compliance Runs** -- [Compliance run](compliance-runs.md) initiation and results are logged, supporting regulatory audit readiness.
- **Governance** -- Audit events are a key input for [governance](governance.md) reporting. Policy violations and enforcement actions are recorded.
- **Contracts** -- [Contract](contracts.md) creation, validation, binding, and version supersession all generate audit events.
- **Webhooks** -- [Webhook](webhooks.md) delivery successes and failures are logged for debugging and reliability tracking.
- **Jobs** -- [Job](jobs.md) creation, state transitions, retries, and completions generate audit events, providing a complete execution history.
- **Lineage** -- [Lineage](lineage.md) edge creation and verification events are logged, ensuring that data provenance records are themselves auditable.
- **Marketplace Listings** -- [Marketplace](marketplace-listings.md) publication, purchase, and delisting events are recorded for both buyer and seller tenants.
- **Billing** -- [Billing](billing.md) events including invoice generation, quota changes, and payment status transitions are logged.

## Querying and Filtering

The audit event API supports flexible querying with the following filter parameters:

| Filter | Description |
|---|---|
| `time_from` / `time_to` | ISO 8601 date range. Required for queries spanning more than 24 hours. |
| `actor_id` | Filter by the user or service account that performed the action. |
| `action` | Filter by action type (e.g., `asset.create`, `contract.bind`). Supports prefix matching (`asset.*`). |
| `resource_type` | Filter by the type of affected resource. |
| `resource_id` | Filter by the specific resource identifier. |
| `source_ip` | Filter by originating IP address or CIDR range. |

Results are returned in reverse chronological order with cursor-based pagination. Each page contains up to 100 events by default (configurable up to 1000).

## MVP Scope

**Available at launch:**

- Automatic audit event capture for all API operations.
- Event querying via API with filtering by time range, actor, action, resource type, and resource ID.
- CLI commands for searching and exporting audit logs.
- 3-year minimum retention with tenant-configurable extension.
- Immutable storage with tamper-evident checksums.
- Pagination and cursor-based iteration for large result sets.
- Export to JSON and CSV formats.

**Post-MVP:**

- Real-time audit event streaming (WebSocket or SSE).
- Integration with external SIEM systems (Splunk, Datadog, Elastic).
- Anomaly detection on audit patterns (unusual access patterns, bulk deletions).
- Compliance report generation (SOC 2 evidence, GDPR data processing records).
- Cross-tenant audit aggregation for platform-admin dashboards.
- Audit event correlation with lineage graphs for impact analysis.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| List events | `GET /api/v1/audit-events` | `meshant audit list` | `client.audit_events.list()` |
| Get event | `GET /api/v1/audit-events/{id}` | `meshant audit get <id>` | `client.audit_events.get(id)` |
| Search events | `POST /api/v1/audit-events/search` | `meshant audit search --actor <id> --action <action>` | `client.audit_events.search(filters)` |
| Export events | `POST /api/v1/audit-events/export` | `meshant audit export --from <date> --to <date>` | `client.audit_events.export(from_date, to_date)` |
| Get event count | `GET /api/v1/audit-events/count` | `meshant audit count` | `client.audit_events.count()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for filter syntax and export options.
