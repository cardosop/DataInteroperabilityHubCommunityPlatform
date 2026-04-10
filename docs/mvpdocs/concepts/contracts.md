# Contracts

A data contract in Meshant is a machine-readable agreement that defines the schema, quality rules, SLA targets, and ownership information for a data asset. Contracts follow the Open Data Contract Standard (ODCS) format, ensuring portability and tooling interoperability across the data ecosystem.

Contracts serve as the single source of truth for what a data asset should look like. When a contract is bound to an [asset](assets.md), the platform can automatically validate conformance through [DQ runs](dq-runs.md), flag schema drift, and enforce quality gates before publishing to the [Marketplace](marketplace-listings.md).

## Lifecycle

| State | Description |
|---|---|
| `draft` | The contract is being authored. Schema and rules can be freely edited. |
| `valid` | The contract has passed structural validation (valid ODCS YAML, no conflicting rules). It has not yet been bound to any asset. |
| `active` | The contract is bound to one or more assets and is actively enforced. DQ runs reference this contract version. |
| `superseded` | A newer version of the contract has been activated. The superseded version is retained for historical DQ run results and [audit](audit-events.md) purposes. |

Transition from `draft` to `valid` is triggered by a validation call that checks the ODCS structure, column definitions, and rule syntax. Transition from `valid` to `active` happens when the contract is explicitly bound to an asset or when a new version is promoted.

When a new contract version enters `active`, the previous version automatically moves to `superseded`. This ensures that there is only one active version per contract at any time.

## Contract Structure

An ODCS contract in Meshant contains the following sections:

| Section | Description |
|---|---|
| `metadata` | Contract name, version, domain, owner, and description. |
| `schema` | Column definitions including name, data type, nullable, description, and constraints. |
| `quality_rules` | Named rules with type (completeness, accuracy, consistency, timeliness, validity), expression, and threshold. |
| `sla` | Service level targets: freshness interval, availability percentage, maximum latency. |
| `terms` | Usage terms, licensing, and data classification level. |

The platform validates each section independently during the `draft` to `valid` transition. Schema columns are checked for valid data types, quality rules are parsed for syntactic correctness, and SLA values are checked against allowed ranges.

## Schema Drift Detection

When a contract is bound to an asset, the platform compares the contract's schema definition against the actual schema inferred from the asset's [datasets](datasets.md). Mismatches are classified as:

- **Missing columns** -- The dataset lacks columns defined in the contract. Severity: error.
- **Extra columns** -- The dataset contains columns not defined in the contract. Severity: warning.
- **Type mismatches** -- A column exists in both but has a different data type. Severity: error.
- **Nullable mismatches** -- A column marked as non-nullable in the contract contains null values. Detected during [DQ runs](dq-runs.md).

Schema drift findings are surfaced in the asset detail view and can trigger [webhook](webhooks.md) notifications.

## Relationships

- **Assets** -- A contract can be bound to one or more [assets](assets.md). Each asset can also reference multiple contracts (for example, one for schema and another for SLA).
- **DQ Runs** -- [DQ runs](dq-runs.md) execute the quality rules defined in the contract. Each run records which contract version was used, allowing historical comparison.
- **Versions** -- Contracts use [semantic versioning](versioning.md). Major version bumps indicate breaking schema changes; minor and patch bumps are backward-compatible additions or rule refinements.
- **Governance** -- Contracts are a key enforcement mechanism within the [governance](governance.md) framework. Policy rules can require that every published asset has at least one active contract.
- **Semantic Resources** -- Contract metadata is exposed as linked data through the [semantic layer](semantic-resources.md), enabling SPARQL queries across contract definitions.
- **Search** -- Contracts are indexed for [full-text and faceted search](search.md), including by domain, quality rule type, and owning team.

## MVP Scope

**Available at launch:**

- Contract authoring in ODCS YAML format via API, CLI, and SDK.
- Structural validation (schema completeness, rule syntax).
- Binding contracts to assets with automatic DQ run triggering.
- Semantic versioning with major/minor/patch.
- Version history and diff between any two versions.
- Contract search by name, domain, and rule type.

**Post-MVP:**

- Visual contract editor in the web UI.
- Contract templates and inheritance (base contracts with overrides).
- Auto-generated contracts from schema inference.
- Cross-tenant contract sharing and forking.
- Contract compliance scoring and trend dashboards.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create contract | `POST /api/v1/contracts` | `meshant contract create` | `client.contracts.create()` |
| Get contract | `GET /api/v1/contracts/{id}` | `meshant contract get <id>` | `client.contracts.get(id)` |
| Validate contract | `POST /api/v1/contracts/{id}/validate` | `meshant contract validate <id>` | `client.contracts.validate(id)` |
| Bind to asset | `POST /api/v1/contracts/{id}/bind` | `meshant contract bind <id> --asset <asset_id>` | `client.contracts.bind(id, asset_id)` |
| List versions | `GET /api/v1/contracts/{id}/versions` | `meshant contract versions <id>` | `client.contracts.versions(id)` |
| Diff versions | `GET /api/v1/contracts/{id}/diff` | `meshant contract diff <id> --v1 1.0.0 --v2 2.0.0` | `client.contracts.diff(id, v1, v2)` |
| Delete contract | `DELETE /api/v1/contracts/{id}` | `meshant contract delete <id>` | `client.contracts.delete(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for payload schemas and filtering options.
