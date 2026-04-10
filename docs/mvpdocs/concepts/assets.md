# Assets

A data asset is the foundational entity in Meshant. It represents any file, dataset, or data product that is registered, governed, and optionally shared through the platform. Assets carry metadata (name, description, domain, tags), quality scores, compliance status, and lineage information that together form a complete picture of the data for producers and consumers.

Every asset belongs to exactly one [tenant](tenants.md) and is owned by a [user](users-and-roles.md) who has at least the `editor` role. Assets can be bound to one or more [data contracts](contracts.md), which codify the schema and quality expectations that the asset must satisfy.

## Lifecycle

Assets progress through the following states:

| State | Description |
|---|---|
| `draft` | Newly registered. Metadata is being filled in. Not visible outside the owning team. |
| `validating` | A [DQ run](dq-runs.md) or [compliance run](compliance-runs.md) is currently executing against the asset. |
| `active` | Validation passed. The asset is usable within the tenant but not published externally. |
| `published` | The asset has been listed on the [Marketplace](marketplace-listings.md) and is discoverable by other tenants. |
| `archived` | The asset is retained for lineage and audit purposes but is no longer served or updated. |

Transitions are recorded as [audit events](audit-events.md). Moving from `active` to `published` requires at least one passing DQ run and a compliance scan with `risk_level` at or below the tenant's configured threshold.

Rolling back from `published` to `active` (unpublishing) is permitted but triggers an `asset.unpublished` [webhook](webhooks.md) so that downstream consumers are notified.

## Asset Metadata

Every asset carries a structured metadata record:

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Human-readable name for the asset (unique within the tenant). |
| `description` | Yes | Free-text description of the asset's contents and purpose. |
| `domain` | Yes | Business domain classification (e.g., finance, marketing, operations, engineering). |
| `tags` | No | Free-form key-value pairs for categorization and [search](search.md) filtering. |
| `owner_id` | Yes | The [user](users-and-roles.md) responsible for the asset. |
| `format` | Auto | Inferred from the underlying [dataset](datasets.md) format (CSV, Parquet, JSON, etc.). |
| `quality_score` | Auto | Populated from the most recent passing [DQ run](dq-runs.md). |
| `compliance_status` | Auto | Populated from the most recent [compliance run](compliance-runs.md). |
| `created_at` | Auto | Timestamp of asset registration. |
| `updated_at` | Auto | Timestamp of last metadata or data change. |

Metadata changes are versioned. The full history of metadata changes is available through the [versioning](versioning.md) API.

## Relationships

- **Contracts** -- An asset may be bound to one or more [data contracts](contracts.md). The contract defines the expected schema, quality rules, and SLA targets. When a new contract version is activated, a DQ run is automatically queued.
- **DQ Runs** -- Every quality check produces a [DQ run](dq-runs.md) record linked back to the asset. The most recent passing run determines the asset's quality score.
- **Compliance Runs** -- [Compliance runs](compliance-runs.md) scan the asset for PII and regulatory risk. Results feed into the asset's compliance status badge.
- **Lineage** -- [Lineage](lineage.md) edges connect assets to their upstream sources and downstream consumers, forming a directed acyclic graph.
- **Marketplace Listings** -- A published asset may have one or more [marketplace listings](marketplace-listings.md) that control pricing and visibility.
- **Datasets** -- An asset's physical storage is represented by one or more [datasets](datasets.md) (files, tables, or streams).
- **Jobs** -- Long-running operations on the asset (DQ, compliance, export) are tracked as [jobs](jobs.md).
- **Versions** -- Assets support [versioning](versioning.md); each version is an immutable snapshot of the metadata and data at a point in time.

## MVP Scope

**Available at launch:**

- Asset registration via API, CLI, and SDK.
- Full lifecycle management (draft through archived).
- Binding to ODCS data contracts.
- DQ and compliance scanning integration.
- Marketplace publishing with basic pricing.
- Keyword and faceted [search](search.md) across assets.
- Lineage capture for upload and transformation operations.

**Post-MVP:**

- Real-time streaming asset registration.
- Cross-tenant lineage federation.
- Asset recommendations based on usage patterns.
- Automatic schema inference for unstructured assets.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Register asset | `POST /api/v1/assets` | `meshant asset create` | `client.assets.create()` |
| Get asset | `GET /api/v1/assets/{id}` | `meshant asset get <id>` | `client.assets.get(id)` |
| List assets | `GET /api/v1/assets` | `meshant asset list` | `client.assets.list()` |
| Update metadata | `PATCH /api/v1/assets/{id}` | `meshant asset update <id>` | `client.assets.update(id)` |
| Transition state | `POST /api/v1/assets/{id}/transition` | `meshant asset transition <id> <state>` | `client.assets.transition(id, state)` |
| Delete asset | `DELETE /api/v1/assets/{id}` | `meshant asset delete <id>` | `client.assets.delete(id)` |
| List versions | `GET /api/v1/assets/{id}/versions` | `meshant asset versions <id>` | `client.assets.versions(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for parameter details, filtering options, and pagination.
