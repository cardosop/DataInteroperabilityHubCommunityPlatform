# Lineage

Data lineage in Meshant tracks the origin, movement, and transformation of data across the platform. It answers three fundamental questions: where did this data come from, what transformations were applied, and what downstream systems depend on it. Lineage is represented as a directed acyclic graph (DAG) where nodes are [assets](assets.md) and [datasets](datasets.md), and edges represent data flow or transformation relationships.

Lineage is captured automatically when data moves through platform operations (uploads, transformations, exports) and can also be registered manually for external pipelines. The lineage graph is queryable via API and rendered visually in the web UI.

## Lifecycle

Lineage edges are immutable records. Once created, they are never modified -- only new edges are added as data flows through additional operations. The lifecycle is centered on the lineage graph itself:

| Stage | Description |
|---|---|
| `captured` | A lineage edge has been recorded, linking a source node to a target node with transformation metadata. |
| `enriched` | The edge has been enriched with additional context: transformation type, column-level mappings, and job reference. |
| `verified` | An operator or automated process has confirmed the lineage edge is accurate (optional quality gate). |
| `stale` | The source or target asset has been archived. The edge is retained for historical reference but marked as no longer active. |

## Edge Types

| Type | Description |
|---|---|
| `upload` | Data was uploaded to the platform and registered as a new dataset. Source is external; target is the platform asset. |
| `transformation` | Data was processed by a pipeline or job. Source and target are both platform assets. |
| `derivation` | A new asset was derived from one or more existing assets (aggregation, join, filter). |
| `export` | Data was exported from the platform to an external system. Source is the platform asset; target is external. |
| `reference` | A non-data dependency (e.g., a lookup table used during transformation). |

## Column-Level Lineage

Beyond asset-level lineage, Meshant tracks column-level mappings when transformation metadata is available. This allows users to trace a specific field from its origin through every transformation to its current form. Column-level lineage is captured from:

- Contract schema mappings between source and target assets.
- Transformation job metadata that declares input-to-output column relationships.
- Schema inference that matches columns by name and type across linked assets.

## Graph Traversal

The lineage API supports configurable traversal:

| Parameter | Default | Description |
|---|---|---|
| `direction` | `both` | Traverse `upstream`, `downstream`, or `both` from the starting asset. |
| `max_depth` | 3 | Maximum number of hops to traverse. Range: 1-10. |
| `edge_types` | all | Filter by edge type (upload, transformation, derivation, export, reference). |
| `include_archived` | false | Whether to include edges involving archived assets. |

The graph response includes nodes (assets with summary metadata) and edges (with transformation type, job reference, and timestamp). The response format is compatible with common graph visualization libraries.

## Relationships

- **Assets** -- [Assets](assets.md) are the primary nodes in the lineage graph. Every asset's lineage tab shows its upstream sources and downstream dependents.
- **Datasets** -- [Datasets](datasets.md) provide the physical-layer lineage, tracking which files contributed to which outputs.
- **Jobs** -- Transformation [jobs](jobs.md) create lineage edges. The job ID is recorded on the edge for traceability.
- **Contracts** -- [Contracts](contracts.md) can define expected lineage relationships (this asset should always derive from these sources).
- **Search** -- Lineage depth and connectivity are available as [search](search.md) facets (e.g., find all root assets with no upstream dependencies).
- **Audit Events** -- Lineage edge creation is logged as an [audit event](audit-events.md).
- **Governance** -- [Governance](governance.md) policies can enforce lineage completeness requirements (no asset may be published without documented upstream lineage).

## MVP Scope

**Available at launch:**

- Automatic lineage capture for platform uploads and transformations.
- Manual lineage registration via API for external pipelines.
- Asset-level lineage graph query (upstream and downstream traversal).
- Visual lineage graph in the web UI (up to 3 hops in each direction).
- Lineage edge metadata: transformation type, job reference, timestamp.
- Impact analysis: given an asset, list all downstream dependents.
- Root cause analysis: given an asset with quality issues, trace upstream to the source.

**Post-MVP:**

- Column-level lineage with visual mapping.
- Cross-tenant lineage for marketplace-shared assets.
- Lineage-driven change impact notifications (alert downstream consumers when an upstream asset changes).
- OpenLineage standard integration for external tool interoperability.
- Lineage graph versioning (point-in-time lineage snapshots).
- Automated lineage verification against declared contract relationships.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Get upstream lineage | `GET /api/v1/lineage/{asset_id}/upstream` | `meshant lineage upstream <asset_id>` | `client.lineage.upstream(asset_id)` |
| Get downstream lineage | `GET /api/v1/lineage/{asset_id}/downstream` | `meshant lineage downstream <asset_id>` | `client.lineage.downstream(asset_id)` |
| Register edge | `POST /api/v1/lineage/edges` | `meshant lineage add-edge` | `client.lineage.add_edge()` |
| Get full graph | `GET /api/v1/lineage/{asset_id}/graph` | `meshant lineage graph <asset_id>` | `client.lineage.graph(asset_id)` |
| Impact analysis | `GET /api/v1/lineage/{asset_id}/impact` | `meshant lineage impact <asset_id>` | `client.lineage.impact(asset_id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for traversal depth options and filtering parameters.
