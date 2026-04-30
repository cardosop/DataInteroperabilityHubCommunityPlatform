# Changelog

All notable changes to the Meshant Data Interoperability Hub are
documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
