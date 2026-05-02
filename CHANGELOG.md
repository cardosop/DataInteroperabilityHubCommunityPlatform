# Changelog

All notable changes to the Meshant Data Interoperability Hub are
documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Phase 230: Semantic platform expansion (REQ-SEM-* sub-phases)

> Phase 230 ships the semantic capability suite: SPARQL inference, bulk
> RDF export, tombstone lifecycle, Memento versioning, contract
> relationships, JSON-LD context alias, OWL inference, SPARQL
> federation with allow-list, Schema.org SEO, custom-ontology
> registration, ontology-aware search, W3C Linked Data Notifications,
> and the GraphQL-LD endpoint.  Every post-MVP sub-phase (230.7–230.13)
> ships behind a per-tenant flag with default OFF; production-tenant
> flip-on requires a separate ops change-request including capacity
> sizing, rollback plan, and post-deploy metric snapshot per Phase 230.DoD.2.

**New endpoints:**

- `POST /api/v1/semantic/export` — bulk RDF export (n-triples / turtle / rdf-xml / ld+json) with the 100M-triple cap and 5/5min throttle (Phase 230.2 / REQ-SEM-EXPORT-001).
- `GET /api/v1/semantic/relationships/<contract_id>` — RDF relationships with content negotiation, tenant-scoped 404 (Phase 230.5 / REQ-SEM-RELATIONSHIPS-001).
- `GET /api/v1/semantic/resource/<type>/<id>/version/<snapshot_at>` + `/timemap` — Memento RFC 7089 versioned dereference + TimeMap (Phase 230.4 / REQ-SEM-MEMENTO-001).
- `GET /api/v1/semantic/context` — extension-less alias for `context.jsonld` (Phase 230.6 / REQ-SEM-CONTEXT-ALIAS-001).
- CRUD `/api/v1/tenants/<id>/sparql-endpoints/` — per-tenant SPARQL federation allow-list, TENANT_ADMIN-only (Phase 230.8 / REQ-SEM-FED-001).
- CRUD `/api/v1/semantic/ontologies/` — per-tenant custom ontology upload + lifecycle (Phase 230.10 / REQ-SEM-ONTO-001).
- `POST /api/v1/semantic/ldn/inbox/<tenant_id>` + listing endpoints — W3C LDN inbox with HTTP-signature verification (Phase 230.12 / REQ-SEM-LDN-001).
- `POST /api/v1/semantic/graphql` — GraphQL-LD endpoint with depth ≤ 5, complexity ≤ 100, 10s timeout, 60 q/min throttle (Phase 230.13 / REQ-SEM-GQL-001).

**Behaviour changes (additive-only per D230.17 — no MODIFIED endpoints):**

- `GET /api/v1/semantic/sparql` now honours `Tenant.semantic_inference_enabled` — when True, queries route to the OWL Mini inferred dataset (Phase 230.7 / REQ-SEM-INFERENCE-001).
- `GET /api/search/?semantic=true` triggers ontology-aware query expansion when `Tenant.semantic_search_enabled=True` (Phase 230.11 / REQ-SEM-SEARCH-EXPAND-001).
- Dereference responses + SPARQL `DESCRIBE` now include `Link: <…/ldn/inbox/{tenant_id}>; rel="…ldp#inbox"` for tenants with LDN enabled (Phase 230.12 / REQ-SEM-LDN-002).
- Public marketplace listing / dataset / asset pages emit Schema.org `<script type="application/ld+json">` (Phase 230.9 / REQ-SEM-SEO-001) — behind-auth pages do NOT emit.
- Resources with `semantic_federate_optout=True` (per-resource opt-out on Asset / Contract / Dataset) are filtered at every cross-boundary surface: `rdf_export`, LDN outbound, SPARQL federation responses (Phase 230.8.9 / REQ-SEM-FED-002).

**New audit-event codes (registered in [hub/apps/audit/models.py](hub/apps/audit/models.py)):**

- `SEMANTIC_EXPORT` (Phase 230.2)
- `SEMANTIC_TOMBSTONE` (Phase 230.3)
- `SEMANTIC_FEDERATED_QUERY`, `SEMANTIC_FEDERATION_ALLOWLIST_ADD`, `SEMANTIC_FEDERATION_ALLOWLIST_REMOVE` (Phase 230.8)
- `SEMANTIC_LDN_INBOUND`, `SEMANTIC_LDN_OUTBOUND`, `SEMANTIC_LDN_SUBSCRIPTION_CREATED`, `SEMANTIC_LDN_SUBSCRIPTION_DELETED` (Phase 230.12)
- `SEMANTIC_GRAPHQL_QUERY` (Phase 230.13)

**New per-tenant flags (all default False):**

- `Tenant.semantic_inference_enabled` (230.7)
- `Tenant.semantic_custom_ontology_enabled` (230.10)
- `Tenant.semantic_search_enabled` (230.11)
- `Tenant.semantic_ldn_enabled` (230.12)
- `Tenant.semantic_graphql_ld_enabled` (230.13)

Phase 230.8 federation gates via empty `TenantSparqlEndpoint` allow-list (no boolean flag — empty list = OFF). Phase 230.9 Schema.org has no per-tenant flag because the gating model is page-visibility (public-page-only emission), which is a stricter privacy contract than a tenant flag.

**New runbooks under `docs/runbooks/`:**

- `semantic-export.md`, `semantic-tombstone.md`, `semantic-memento.md`, `semantic-inference.md`, `semantic-federation.md`, `semantic-ontology.md`, `semantic-ldn.md`, `semantic-graphql.md`.

**Threat models (per Phase 230.DoD.5):**

- `docs/security/threat-models/federation-cross-tenant.md` (Phase 230.8).
- `docs/security/threat-models/ldn-cross-tenant.md` (Phase 230.12).

Both threat models include a "Legal-team sign-off" section that MUST be filled in the merging PR description before the per-tenant flag is flipped True for any production tenant.

**Bundle-size CI gate extension (Phase 230.13.10):**

- [scripts/bundle_size_check.mjs](scripts/bundle_size_check.mjs) gains a layered 5% growth-ratio cap atop the existing 30 KB absolute cap. PRs fail on either trip.

### BREAKING — Phase 227: Structureless contracts now rejected at the API edge

**What changed:** `POST /api/v1/contracts/` and
`PATCH /api/v1/contracts/{id}/` now return **HTTP 400** with
`error.code = "STRUCTURELESS_CONTRACT"` when the submitted /
re-normalised contract has no resolvable
`models[*].fields[*]` AND no `schema.fields[*]`. Asset activation
(`PATCH /api/v1/assets/{id}/ {status: ACTIVE}`) returns the same
code as a blocker; marketplace publish
(`PATCH /api/v1/marketplace/listings/{id}/ {status: PUBLISHED}`)
returns **HTTP 422** with the same code. Pre-227 the API silently
accepted these payloads, persisting rows with `hub_contract_json =
NULL` or empty `models = []`.

The floor is **always-on** per the 2026-04-30 ungate directive — no
feature flag, no per-tenant override, no deprecation period. Wave-3
self-heal handles the bulk of pre-227 structureless rows
automatically; the rest require customer action via the Schema
editor.

**Affected endpoints:**

- `POST /api/v1/contracts/` — 400 `STRUCTURELESS_CONTRACT`
- `PATCH /api/v1/contracts/{id}/` — 400 `STRUCTURELESS_CONTRACT`,
  plus 412 `PRECONDITION_FAILED` when `If-Match` ETag is stale
- `PATCH /api/v1/assets/{id}/` — 400 with structural blocker in
  `error.details.blockers[]`
- `PATCH /api/v1/marketplace/listings/{id}/` — 422
  `STRUCTURELESS_CONTRACT` (both publish paths)
- Internal write paths (`ODPSService.create_odps`,
  `ContractService.link_odps_to_odcs`,
  `ODPSService.normalize_odps`) — same envelope

**New endpoints:**

- `GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>` —
  returns the canonical Pydantic-derived JSON Schema with
  `Content-Type: application/schema+json` (IANA registered)
- `GET /api/v1/contracts/?filter=structureless` — TENANT_ADMIN-only
  triage list of structureless contracts in the tenant
- `POST /api/v1/contracts/schema-editor/metrics` — backend OTel
  receiver for Schema-editor adoption telemetry (no client-supplied
  tenant_id; server-derived from session)

**New error codes** (full taxonomy at
[error catalog](docs/mvpdocs/reference/error-codes.md#structureless-contract-codes-phase-227)):

| Code | HTTP | Notes |
| ---- | ---- | ----- |
| `STRUCTURELESS_CONTRACT` | 400 / 422 | `details.subcode` ∈ `{STRUCTURELESS_ODPS_NO_PORTS, STRUCTURELESS_ODCS_NO_SCHEMA, STRUCTURELESS_GENERIC, STRUCTURELESS_CYCLIC_PORTS}` |
| `SCHEMA_TOO_DEEP` | 400 | ODCS nested-properties walker hit `CONTRACTS_MAX_NESTING_DEPTH` (default 20) |
| `INVALID_YAML` | 400 | Unsafe YAML construct rejected by `yaml.safe_load` |
| `PRECONDITION_FAILED` | 412 | `If-Match` ETag mismatch on contract PATCH |
| `PAYLOAD_TOO_LARGE` | 413 | `original_raw` exceeds 2 MB |

**New observability** (Phase 227 L7):

- OTel counters: `contract_validation_failed_total`,
  `contract_structureless_total`, `audit_events_total`,
  `schema_editor_opened_total`, `schema_editor_save_total`
- OTel histograms: `contract_normalization_models_count`,
  `contract_normalization_fields_total_count`,
  `contracts_renormalize_batch_duration_seconds`,
  `schema_editor_time_to_first_save_seconds`
- OTel gauge: `contract_structureless_backlog`
- New audit actions: `CONTRACT_VALIDATION_FAILED`,
  `CONTRACT_STRUCTURELESS_REJECTED`,
  `ASSET_AUTO_REVERTED_STRUCTURELESS`,
  `CONTRACT_BATCH_RENORMALIZED`,
  `ASSET_RESTORED_STRUCTURELESS`
- New Grafana dashboard:
  `monitoring/grafana/dashboards/structureless-contract-rollout.json`
  (UID `hub-structureless-rollout-227`) — 8 panels covering
  rejection rate, source distribution, backlog gauge,
  models-per-contract distribution, batch duration, schema-editor
  adoption funnel, time-to-first-save, asset auto-reverts

**New email types** (Phase 227 Wave 5):

- `ASSET_AUTO_REVERT_WARNING` — T+30 final-warning email sent to
  every TENANT_ADMIN of every tenant whose currently-active
  contracts remain structureless 14 days before the W5 cutover.
  Drives the new `wave5_send_final_warning_notifications`
  management command (W5.1).
- `ASSET_AUTO_REVERTED_NOTIFICATION` — per-asset notification
  emitted by the apply-asset-revert path right after an asset is
  demoted to DRAFT. Each TENANT_ADMIN of the affected tenant gets
  one email + one in-app `UserNotification` (governance category)
  carrying the asset name, the structureless contract id, the
  previous status, and the Schema-editor + Asset-detail
  deep-links. Wired into `_maybe_revert_asset`; best-effort —
  notification dispatch failures DO NOT roll back the demotion
  (which is the load-bearing operation).

**New management commands** (Phase 227 Wave 5):

- `wave5_send_final_warning_notifications --deadline=YYYY-MM-DD`
  — broadcasts the T+30 final warning to every tenant with at
  least one structureless ACTIVE contract. Mirrors the W4 driver
  conventions: idempotency-via-audit-row (`ASSET_AUTO_REVERT_WARNING_NOTIFIED`),
  per-recipient fail-soft, all-failed-batch-leaves-no-audit-row
  (so retries can self-heal), `--dry-run`, `--audit-output`,
  `--force`, `--tenant-id`, `--all-tenants`. Default scope guard
  excludes already-clean tenants so the warning doesn't reach
  customers who have already remediated.

**New audit actions** (Phase 227 Wave 5):

- `ASSET_AUTO_REVERT_WARNING_NOTIFIED` — written by the W5.1
  driver after a successful per-tenant dispatch. Powers the
  driver's idempotency check.

**New webhook event types** (Phase 227 W3.4):

- `contract.batch_renormalized` — emitted once per `renormalize_contracts
  --apply` batch per affected tenant. Resource is the tenant
  (`resource_type="TENANT"`, `resource_id=<tenant_uuid>`); payload `data`
  carries `{run_id, tenant_id, processed, healed, residual, failed}`.
  Subscribers wanting the rollup of bulk migrations subscribe here
  instead of `contract.updated` (which fires per-row when
  `--silent-events` is omitted).

**New `renormalize_contracts --apply` summary fields** (Phase 227 W3.5):

- `per_tenant` — map of `<tenant_uuid>` → `{processed, healed, residual,
  failed}` aggregated across batches.
- `residue_tenants` — sorted list of `<tenant_uuid>`s where `residual +
  failed > 0`. Drives Wave 4 follow-up email scoping.

**New management-command flags** on `renormalize_contracts`:

- `--apply` — re-normalise structureless contracts (vs. default
  `--dry-run` diagnosis)
- `--apply-asset-revert` — demote ACTIVE assets backed by
  contracts that REMAIN structureless after re-normalisation
- `--silent-events` — suppress per-contract webhooks; emit one
  batch summary
- `--checkpoint-table=<name>` — resumable across crashes
- `--output=count` — emit a single integer for the daily
  pushgateway cron

**New migrations:**

- `contracts/0023_migration_checkpoint.py` — adds `MigrationCheckpoint`
  table for resumable bulk operations
- `contracts/0024_unrevert_structureless_assets.py` — reversible
  data migration that restores assets demoted by
  `--apply-asset-revert`

**Migration paths:**

- SDK consumers: see
  [migration guide](docs/migration-guides/structureless-contracts-deprecation.md)
- Operators triaging tenants: see
  [ops runbook](docs/runbooks/structureless-contracts.md)
- Canonical contract shapes per spec version:
  [`docs/CONTRACTS.md`](docs/CONTRACTS.md)

### Removed

- `VITE_FEATURE_SCHEMA_EDITOR_ENABLED` frontend feature flag —
  Schema editor tab now visible to every user with the existing
  modify-role permission, per the 2026-04-30 ungate directive.
- `contracts.structural_floor.enabled` and
  `contracts.schema_editor.enabled` backend feature flags — never
  shipped; the directive retired flag-gating before registration.

### Internal

- New OTel metric module helpers in
  `hub.apps.contracts.normalization_metrics`
- New `hub.apps.contracts.structural_floor.enforce_structural_floor`
  module — single source of truth for the floor invariant
- New `MigrationCheckpoint` model + tests for resumable bulk ops
- 144 functional tests + 3 performance benchmarks added under
  `hub/apps/contracts/tests/test_*.py` and
  `hub/apps/marketplace/tests/test_marketplace_publish_structural_blocker.py`
