# Changelog

All notable changes to the Meshant Data Interoperability Hub are
documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Phase 250: Asset-creation hardening (250.1–250.7)

> Phase 250 hardens data-first asset creation and closes the identified
> security/operability gaps: fail-closed persistence, workflow versioning,
> idempotent create semantics, federated-import safety gates, tenant feature
> controls, semantic graceful-degrade, optimistic-locking enforcement, and
> rate-limit controls.

**New and updated controls:**

- Workflow WARN audit event support with `ASSET_WORKFLOW_WARN_LOGGED` emission for non-fatal warning paths in asset-creation workflows.
- Per-user and per-tenant throttling for asset creation surfaces (`create` + `data_first`) to reduce abuse risk while preserving tenant isolation.
- Hardened test-database bootstrap path in `scripts/migrate-test-dbs.sh` to detect/drop invalid PostgreSQL DB states (`datconnlimit=-2`) before clone fallback.
- Asset-creation operational artifacts under `docs/` including runbooks, ADR set, risk register, capacity plan, and RACI matrix for cross-functional execution.
- Prometheus asset-creation alert rules are wired in both development and production Prometheus rule files.

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

### Added — Phase 240: Data-quality feature hardening (240.0–240.5 sub-phases)

> Phase 240 closes the 28-gap audit on the data-quality feature
> identified pre-MVP: engine-agnostic adapter abstraction, ODPS-aligned
> profile suite, alert-delivery channel parity, structured-logging
> migration, distributed tracing across the hub→dq-service boundary,
> Helm-canonical configuration, payload signing on the internal
> network, PII redaction sweep, and the operational runbook + SLOs.
> Per-tenant rollout follows D240.18: `Tenant.data_quality_enabled`
> defaults TRUE on existing tenants (no surprise disable);
> `Tenant.data_quality_advanced_enabled` defaults FALSE everywhere
> and is flipped per-tenant after a 14d soak of 240.3.B.

**New endpoints / capabilities:**

- `POST /api/v1/quality/dq-runs/{id}/trends/`, `/scorecards/`, `/anomalies/`, `/root-cause-analysis/` — advanced quality endpoints gated by `data_quality_enabled AND data_quality_advanced_enabled` (Phase 240.3.B).
- `POST /run` (dq-service) now routes by profile-key suffix to the engine-agnostic `DQAdapter`: `*_soda` → `SodaAdapter`, all others → `GXAdapter` (Phase 240.3.A).
- DQ alert delivery across 4 channels (`EMAIL`, `SLACK`, `WEBHOOK`, `PAGERDUTY`) at [hub/apps/dq/clients/](hub/apps/dq/clients/), each with circuit-breaker integration via `hub.apps.core.resilience.service_breakers` (Phase 240.1.A).
- Tenant-scoped DQ alerting rules (`DQAlertingRule`) with comparison operator + threshold + dedup window + retry / dead-letter lifecycle (Phase 240.1.A.5).

**Behaviour changes (additive-only — no MODIFIED endpoints):**

- All hub→dq-service calls now carry `traceparent` + `tracestate` (W3C TraceContext) — `service.name=hub-api` and `service.name=dq-service` spans connect in Tempo (Phase 240.2.C).
- Hub→dq-service POST bodies now carry `X-Internal-Payload-Signature` + `X-Internal-Payload-Timestamp` headers (HMAC-SHA256 over `timestamp + "\n" + body`); dq-service verifies in soak mode (`DQ_REQUIRE_PAYLOAD_SIGNATURE=false`) on day-0, flips to enforce after 7d telemetry confirms 100% Hub coverage (Phase 240.5.G).
- DQ runs that exhaust dq-service retries now route to the dead-letter queue + emit `DQ_ALERT_DEAD_LETTER_OPS_PAGERDUTY` audit events for ops paging (Phase 240.5.A).
- All `logger.*(..., extra={...})` calls in DQ Hub-side files (`views.py`, `services.py`, `service_client.py`, `alerting.py`, `tasks.py`, `clients/*.py`) wrap their dict in `_redact()` from `hub.apps.dq.log_helpers` — recursively strips `row_samples`, `sample_value`, `sample_data_json`, `file_content`, `body`, `raw_data`, `data`, `details_json` keys before log emission (Phase 240.5.F).

**New audit-event codes (registered in [hub/apps/audit/models.py](hub/apps/audit/models.py)):**

- `DQ_RUN_STARTED`, `DQ_RUN_COMPLETED`, `DQ_RUN_FAILED` (Phase 240.0)
- `DQ_ALERT_RULE_CREATED`, `DQ_ALERT_RULE_UPDATED`, `DQ_ALERT_RULE_DELETED` (Phase 240.1.A.5)
- `DQ_ALERT_FIRED`, `DQ_ALERT_DELIVERED`, `DQ_ALERT_DELIVERY_FAILED`, `DQ_ALERT_RETRY_SCHEDULED`, `DQ_ALERT_DEAD_LETTER_OPS_PAGERDUTY` (Phase 240.1.A)
- `DQ_ALERT_CHANNEL_DEGRADED`, `DQ_ALERT_CHANNEL_RECOVERED` (Phase 240.1.A.6 — circuit-breaker)

**New per-tenant flags:**

- `Tenant.data_quality_enabled` — default **True** on existing tenants (no surprise disable per D240.18).  Kill-switch: flip to False to disable the entire DQ feature for the tenant; in-flight runs complete (no abort), subsequent reads return 403 (D240.18 + 240.4.B.2 / OQ240.4).
- `Tenant.data_quality_advanced_enabled` — default **False** everywhere.  Conjunctive with the base flag.  Gates the four 240.3.B advanced endpoints (`/trends/`, `/scorecards/`, `/anomalies/`, `/root-cause-analysis/`).  Per-tenant flip after 14d production stability of the 240.3.B endpoints (D240.18).

**Operational assets:**

- Grafana dashboard at [monitoring/grafana/dashboards/data-quality.json](monitoring/grafana/dashboards/data-quality.json) with run-rate / latency / engine success / queue-depth / alert-delivery panels (Phase 240.5.B.1).
- Prometheus alert rules at [monitoring/prometheus/alerts/dq.yml](monitoring/prometheus/alerts/dq.yml) — 8 alerts covering run-failure-rate, p95 duration regression, circuit-open, alert-delivery, engine-success, queue-depth, audit-write, S3 payload growth (Phase 240.5.B.2).
- Synthetic firing tests at [monitoring/prometheus/alerts/dq-synthetic-firing.yml](monitoring/prometheus/alerts/dq-synthetic-firing.yml) (Phase 240.5.B.4).
- Operational runbook at [docs/runbooks/data-quality.md](docs/runbooks/data-quality.md) — SLOs, alert anchors, capacity sizing, kill switches, rolling-deploy for payload signing, PII redaction contract.
- Trivy DQ-service image vulnerability gate enforced in [.github/workflows/deploy.yml](.github/workflows/deploy.yml) — blocks deploy on CRITICAL/HIGH; pinned by contract test [tests/ci/test_dq_image_vulnerability_scan.py](tests/ci/test_dq_image_vulnerability_scan.py) (Phase 240.5.D).
- Helm-canonical DQ-service configuration at [helm/values.yaml](helm/values.yaml) under `dqService.config.*` — single source of truth replacing the prior `k8s/dq-service/base/` Kustomize tree (Phase 240.1.D).

**Internal (no API surface):**

- Hub-side `_redact()` helper at [hub/apps/dq/log_helpers.py](hub/apps/dq/log_helpers.py); AST-based lint script at [scripts/check_dq_log_extras.py](scripts/check_dq_log_extras.py); pre-commit + CI gates (`check-dq-log-extras` + `lint-dq-log-extras`) — drift safeguard `TestLintRuleParity` pins `_REDACTED_KEYS` ↔ `_FORBIDDEN_KEYS` parity (Phase 240.5.F).
- Post-deploy DQ smoke-test script at [scripts/smoke_tests_dq.sh](scripts/smoke_tests_dq.sh) covering DoD.4: synthetic runs across registered profile keys, alert dry-run for all 4 channels, Grafana DQ board non-zero-data check (Phase 240.DoD.4).

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
