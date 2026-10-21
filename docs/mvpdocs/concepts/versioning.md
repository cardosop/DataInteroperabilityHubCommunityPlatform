# Versioning

Versioning in Meshant provides controlled change management for [contracts](contracts.md) and [assets](assets.md). Every contract and asset supports semantic versioning (major.minor.patch), enabling teams to evolve their data products while maintaining backward compatibility and preserving full history. Version records are immutable snapshots that support diff, rollback, and audit.

Versioning ensures that consumers of a data product can rely on stability guarantees: a patch version bump means no breaking changes, a minor bump adds new fields or rules, and a major bump signals a breaking schema change that may require consumer action.

## Lifecycle

Each version progresses through the following states:

| State | Description |
|---|---|
| `draft` | A new version is being prepared. Changes can be freely made. Only one draft version exists per resource at a time. |
| `released` | The version has been finalized and is available for use. Released versions are immutable. |
| `active` | The version is the currently active version for the resource. For contracts, this means it is the version used by DQ runs. |
| `superseded` | A newer version has been activated. The superseded version is retained for historical reference and existing DQ run results. |
| `deprecated` | The version has been marked for removal. Consumers are warned to migrate. A deprecation date is set. |

Only one version can be in the `active` state at a time. When a new version is activated, the previously active version automatically transitions to `superseded`.

## Semantic Versioning Rules

| Bump | Trigger | Consumer Impact |
|---|---|---|
| Major (X.0.0) | Breaking schema change: removed columns, type changes, renamed fields, removed quality rules. | Consumers must update their integrations. Marketplace subscribers are notified. |
| Minor (x.Y.0) | Backward-compatible additions: new optional columns, new quality rules, expanded enums. | No consumer action required. Existing integrations continue to work. |
| Patch (x.y.Z) | Non-functional changes: description updates, rule threshold adjustments, metadata corrections. | No consumer action required. No schema impact. |

The platform validates that the declared bump type matches the actual changes. For example, removing a column and declaring it as a patch bump is rejected with a validation error.

## Diff and Comparison

Meshant provides a structured diff between any two versions of a contract or asset:

- **Schema diff** -- Added, removed, and modified columns with type information.
- **Rule diff** -- Added, removed, and modified quality rules with threshold changes.
- **Metadata diff** -- Changes to description, tags, domain, and other metadata fields.
- **SLA diff** -- Changes to service level targets (freshness, availability).

Diffs are available via API, CLI, and SDK and are rendered visually in the web UI.

## Relationships

- **Contracts** -- [Contracts](contracts.md) are the primary versioned resource. Each contract version contains a complete snapshot of the schema, rules, and SLA definitions.
- **Assets** -- [Assets](assets.md) support versioning for their metadata and configuration. Asset data versioning is handled through [dataset](datasets.md) replacements linked to the asset version.
- **DQ Runs** -- Each [DQ run](dq-runs.md) records which contract version was used, enabling historical comparison of results across versions.
- **Audit Events** -- Version creation, activation, supersession, and deprecation are all recorded as [audit events](audit-events.md).
- **Marketplace Listings** -- [Marketplace listings](marketplace-listings.md) reference a specific asset version. Major version bumps trigger subscriber notifications.
- **Governance** -- [Governance](governance.md) policies can enforce versioning practices (e.g., no major version bumps without a migration plan).
- **Lineage** -- [Lineage](lineage.md) edges reference specific versions, enabling point-in-time lineage reconstruction.

## MVP Scope

**Available at launch:**

- Semantic versioning for contracts (major.minor.patch).
- Version creation, release, activation, and supersession via API, CLI, and SDK.
- Structured diff between any two versions.
- Version history listing with timestamps and authors.
- Bump type validation (ensuring declared bump matches actual changes).
- Immutable released versions (no modification after release).
- One active version per resource at a time.
- Version reference in DQ run results.

**Post-MVP:**

- Asset metadata versioning with full snapshot history.
- Automated migration plan generation for major version bumps.
- Version branching (experimental versions that do not affect the main version line).
- Subscriber notification on version changes.
- Version pinning for consumers (lock to a specific version, ignore newer versions).
- Version deprecation with automatic sunset dates and consumer warnings.
- Changelog generation from version diffs.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create version | `POST /api/v1/{type}/{id}/versions` | `meshant version create <type> <id>` | `client.versions.create(type, id)` |
| Get version | `GET /api/v1/{type}/{id}/versions/{version}` | `meshant version get <type> <id> <version>` | `client.versions.get(type, id, version)` |
| List versions | `GET /api/v1/{type}/{id}/versions` | `meshant version list <type> <id>` | `client.versions.list(type, id)` |
| Activate version | `POST /api/v1/{type}/{id}/versions/{version}/activate` | `meshant version activate <type> <id> <version>` | `client.versions.activate(type, id, version)` |
| Diff versions | `GET /api/v1/{type}/{id}/versions/diff` | `meshant version diff <type> <id> --v1 <v1> --v2 <v2>` | `client.versions.diff(type, id, v1, v2)` |
| Deprecate version | `POST /api/v1/{type}/{id}/versions/{version}/deprecate` | `meshant version deprecate <type> <id> <version>` | `client.versions.deprecate(type, id, version)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for version payload schemas and diff format details.
