# Tenant Isolation RLS Contract

- All new models with `tenant_id` MUST ship a paired RLS policy migration.
- CI enforces this through `lint-rls-policies` (`scripts/lint_rls_policies.py`).
- **Request-path arming (W1.20 / D2)**: `TenantScopingMiddleware` sets
  `app.current_tenant_id` + every `app.rls_<table>_enabled` GUC
  transaction-locally inside the request transaction, gated behind the
  `RLS_REQUEST_PATH_ENABLED` master kill switch (default armed).
  Transaction-local GUCs are mandatory — staging/production use
  PgBouncer transaction pooling, where a session-level SET leaks onto
  the next pooled client. Arming fails closed: no tenant → NULL/empty
  GUC → policies hide every row. Pre-tenant identity reads (API keys,
  JWT users, memberships) MUST route through
  `hub.apps.auth.db_aliases.user_lookup_alias()`. Every deployed
  `app.rls_*_enabled` policy GUC must have a paired `RLS_*_ENABLED`
  settings kill switch (pinned bidirectionally by
  `test_rls_guc_settings_sync.py`); `RLS_REQUEST_PATH_ENABLED` is the
  master switch, never a table flag.
- Worker/signal code that touches tenant-scoped models MUST run inside
  `tenant_context(tenant_id)`.
- Management commands are cross-tenant by default and MUST use
  `DATABASES["admin"]` (`meshant_admin`, BYPASSRLS), then iterate per
  tenant with `tenant_context(...)` when doing tenant-scoped work.

# Governance ABAC + Multi-Step Approval Contract (Phase 272)

- `GovernanceService.approve_access_request()` now runs three checks before
  mutation: (1) business-rules validation (existing), (2) compliance gate
  (Phase 272.2 — queries latest ComplianceRun for the resource, blocks when
  `allowed_to_store` is not True), (3) ABAC evaluation (Phase 272.3 — calls
  `ABACEngine.evaluate_access()` with action=`approve_access_request`; DENY
  policy → 403 `ABAC_POLICY_DENIED`).
- PLATFORM_ADMIN can bypass the compliance gate via `?force_approve=true`
  query param; emits `ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN` audit.
- Multi-step approval (Phase 272.4): `AccessPolicy.required_approval_chain`
  (JSONField, default `[]`) defines ordered steps. On first approval the
  chain is snapshotted into `AccessRequest.approval_workflow`. Intermediate
  steps set status `PENDING_NEXT_APPROVER`; entitlement + order fulfillment
  fire on final step only.
- `ApprovalDelegation` (Phase 272.6): delegates can approve during an
  active time window; checked in `_validate_access_request_approval()`.
- All new models (`AccessRequestComment`, `ApprovalDelegation`) ship RLS
  policies in the same migration as the CreateModel.

# Search/Semantic Throttle + Audit + Metric Contract (Phase 273)

- Every search / semantic / marketplace ``View`` or ``ViewSet`` MUST carry
  a ``throttle_classes`` attribute (enforced by
  ``check_throttle_coverage`` management command at CI).
- Throttle cache keys MUST include tenant_id: ``f"throttle_{name}_{tenant_id}"``
  — tenant A's exhaustion must never affect tenant B's quota.
- Every search / SPARQL execution MUST emit an audit event (try/except
  wrapped — audit-DB outage must never block the response):
  * ``SEARCH_PERFORMED`` — UnifiedSearchView, ``query_truncated[:256]``
  * ``SPARQL_EXECUTED`` — SPARQLQueryService.run(), ``query_hash`` only
    (never log the query body — PII risk)
  * ``RDF_INGESTED`` — rdf_ingest view
- Every 429 (rate-limit hit) MUST emit ``SEARCH_RATE_LIMIT_EXCEEDED`` /
  ``SPARQL_RATE_LIMIT_EXCEEDED`` (plus the per-surface
  ``MARKETPLACE_RATE_LIMIT_EXCEEDED`` / ``BAAS_RATE_LIMIT_EXCEEDED`` /
  ``API_KEY_RATE_LIMIT_EXCEEDED`` events). NOTE: DRF 3.16 REMOVED the
  ``throttled()`` override hook — audit emission MUST run in
  ``allow_request()``'s failure branch (``_on_throttled`` helpers in
  ``hub/apps/*/throttles.py``); a ``throttled()`` override is dead code
  on this DRF and its ``super()`` call crashes.
- Search hot-path metrics (``search_request_duration_seconds``,
  ``search_results_count_total``, ``search_no_result_total``,
  ``sparql_execution_seconds``, ``sparql_timeout_total``) MUST be
  emitted from the view/service layer via ``hub.apps.search.metrics``.
- ``/search`` is permanently MVP-in-scope (Phase 273.1). Do NOT add it
  back to ``NON_MVP_PATHS``, ``MvpGatedRoute``, or
  ``MVP_GATED_RELATIVE_PREFIXES``.

## Business Rules Chain Primitive (Phase 274)

### Chain convention
- New multi-rule operations MUST use `execute_chain("<chain.name>", ctx, **kwargs)`.
- Chains are registered via `@register_chain("chain.name")` in `hub/apps/core/business_rules/chain_registry.py`.
- Direct `XxxBusinessRules(...).validate_*()` remains canonical for single-rule validation.
- Chain runner requires an active `transaction.atomic()` context; raises `RuntimeError` otherwise.

### Decision tree for new validations
1. Single rule check? → direct `XxxBusinessRules(...).validate_*()` instantiation.
2. Multi-rule check where ordering matters? → register a chain, invoke via `execute_chain()`.
3. Side effects (cache, search-index, webhook, lineage) after validation? → fire AFTER chain returns PASS.
4. Async job validation? → wrap in `transaction.atomic()`, set `ctx.metadata["is_async"]=True`.

### State-machine pattern
- New state-machine logic → chain naming: `<resource>.transition.<from-to>` (e.g. `access_request.transition.pending-approved`).
- Existing ad-hoc state machines → leave alone unless touched for another reason.

### Existing chains (Phase 274.7)
| Chain | Steps | Owner |
|---|---|---|
| `contract.publish` | TenantScoping → StructuralFloor → ContractValidation | contracts |
| `asset.activate` | TenantScoping → AssetActivation | assets |
| `marketplace.listing.publish` | TenantScoping → KYB → ComplianceThreshold → ListingValidation | marketplace |
| `governance.approval.advance` | TenantScoping → ApproverIdentity → ApprovalStage → ApprovalQuorum | governance |
| `semantic.query.execute` | TenantFlag → SPARQLSyntax → SPARQLComplexity | semantic |

### Semgrep guard — NOT ENFORCED (Phase P.9 verdict)
`semgrep/rules/prefer-chain.yaml` exists as a LOCAL ADVISORY rule flagging
direct `XxxBusinessRules(...).validate_*()` in services/views when a
registered chain exists. It is NOT wired into CI: GATE-25 runs
`--config=auto` only, and semgrep is not installed in any CI job — the
previous "warns" claim described enforcement that does not exist. If
semgrep enters the CI toolchain, wire the rule in the blocking lint job;
until then the `# noqa: prefer-chain` escape hatch has no consumer.

### Health endpoint
`GET /api/v1/health/business-rules` returns `{status, degraded_rules, degraded_count}`.
SRE alert fires when `degraded_count > 0`.

### Migration backfill convention (274.16.7)
- Migration commands MUST go through the service layer.
- Raw SQL writes are forbidden unless accompanied by a chain-bypass
  justification audit event (`RULE_CHAIN_BYPASSED`).
- Backfill migrations that skip the chain must document the bypass
  reason in the migration file docstring.

### Audit retention category (274.16.8)
- Chain events use `audit_retention_category='business_rules'`.
- Phase 234.5 retention policy applies 30-day window for chain events.
- `RULE_CHAIN_COMPLETED` audit events are retained for 30 days.

### Per-tenant chain enablement (274.16.13) — RETRACTED (Phase P.9 D8)
- The claim that chains are gated per-tenant via a
  `Tenant.business_rules_chain_<name>_enabled` BooleanField was prose with no
  field, migration, or runtime check. Chains are registered and enabled
  GLOBALLY via `@register_chain`; there is no per-tenant chain switch. Do
  not build such a feature to satisfy documentation; do not add the claim
  back.

# Control-Plane Provider Boundary Contract (openspec add-databricks-control-plane)

- Control-plane estate models and API clients are PER-PROVIDER: the Databricks
  estate lives in `hub/apps/databricks_admin`; a future provider (e.g.
  Snowflake) gets its own app. No control-plane domain-model imports across
  provider apps — `hub.apps.databricks_admin.models`/clients MUST NOT be
  imported outside `databricks_admin`, and `databricks_admin` MUST NOT import
  another provider's estate models.
- SANCTIONED SEAM (openspec task 1.7): the marketplace connector
  (`hub/apps/integrations/connectors/databricks_connector.py`) is the ONE
  sanctioned consumer of `DatabricksApiClient` outside `databricks_admin`.
  It uses DELEGATION MODE only — `request_path()` (raw paths, no
  version-pinned operations, no OBO), `client=` (the connector's own
  transport), `use_breaker=False` (the connector's own breaker owns
  failure accounting), `backoff_waiter=` (the connector's deterministic
  backoff) — never estate models, never control-plane operations. Any
  FURTHER consumer of the client outside `databricks_admin` needs design
  review before landing.
- SANCTIONED SEAM (openspec task 7.5, design D4): the warehouse
  connectors' `_record_cost` writes ONE `DatabricksCostLedger` row per
  executed query through the provider-agnostic registry inversion —
  `hub/apps/warehouses/cost_recording.py` (the `CostRecord` shape +
  `record_cost()` facade, never raises) with the ledger writer
  `hub/apps/databricks_admin/cost_ledger.py::record_ledger_cost`
  registered by `databricks_admin/apps.py::ready()`. The inversion is
  the boundary: `warehouses` NEVER imports `databricks_admin` — only the
  APPEND path (create rows inside `tenant_context(record.tenant_id)`),
  never estate-model reads or control-plane operations. A future
  provider estate registers its own writer the same way (Appendix B
  "Cost-recording seam").
- SANCTIONED SEAM (oss-release-remediation W4.3, R2-B6/E2): tenant
  hard-delete offboarding. `hub/apps/tenants/offboarding.py` is the
  provider-agnostic sweeper registry
  (`register_tenant_offboard_sweeper` / `run_tenant_offboard_sweepers` —
  every sweeper runs inside `tenant_context(tenant_id)`; mandatory on
  the delta-share tables: strict RLS policy + FORCE ROW LEVEL SECURITY,
  an unarmed DELETE matches zero rows). `tenants` NEVER imports
  `databricks_admin` estate models — the tenant hard-delete sweep
  (`tenant_hard_delete_sweep._pre_sweep_tenant`) and the E2E cascade
  path invoke whatever sweepers provider apps register in `ready()`
  (`databricks_admin/offboarding.py::sweep_delta_share_estate` deletes
  the PROTECT-FK estate itemized). A future provider estate registers
  its own sweeper the same way.
- SANCTIONED SEAMS (oss-release-remediation W4.6, G1 — all registered by
  `databricks_admin/apps.py::ready()`, all consumer-side modules NEVER
  import estate code):
  * Budget gate — `hub/apps/warehouses/budget_gate.py` (the
    `BudgetDecision` shape + `register_budget_enforcer`/`enforce_budget`;
    unregistered → `None` = no budget concept, the provider-agnostic
    default) ← `databricks_admin/budget_enforce.py::enforce_budget`.
  * M2M token-cache seam — `hub/apps/integrations/m2m_token_cache.py`
    (`register_m2m_token_cache_factory`/`default_m2m_token_cache`;
    unregistered → `None` = best-effort no-cache mode) ←
    `databricks_admin/token_cache.py::M2MTokenCache`; consumed by
    `data_movement/dlt_credentials.py` and
    `transformation/credential_resolver.py`.
  * Estate-job handlers — `hub/apps/jobs/estate_handlers.py`
    (`register_estate_job_handler`/`get_estate_job_handler`; the
    dispatcher refuses classified when unregistered) ← the UC-sync /
    cost-sync / UC-change-reaper handlers.
  * Staging-volume provisioner — registry in
    `hub/data_movement/staging.py` (`register_staging_volume_provisioner`;
    unregistered → classified `DatabricksStagingRefused`) ←
    `databricks_admin/staging_provisioner.py::provision_staging_volume`.
  * Business-rules chains — the 6 databricks chains register IN
    `databricks_admin/chains.py` (the 313.1 owning-app convention);
    `core/business_rules/chain_registry.py` holds NO estate reference.
  * E2E UC-mirror seed — `databricks_admin` management command
    `seed_e2e_uc_mirror` (tenant-scoped writes inside
    `tenant_context`), invoked BY NAME from
    `users/.../ensure_e2e_user_roles.py` via `call_command`.
  * Estate admin tooling lives WITH the estate —
    `hub/apps/databricks_admin/e2e_tooling/` (the nightly sandbox
    lifecycle + audit emitter moved out of `scripts/databricks_e2e/`).
- The cross-provider contract is `openspec/changes/add-databricks-control-plane/design.md`
  Appendix B "Reused utilities" (encryption, SSRF/residency validators, circuit
  breaker, backoff, chains, ABAC, approval pattern, job dispatch, flags/kill
  switches, dbt adapter, dlt, + the W4.6 seams above). New shared needs are
  added to that table and homed in a provider-agnostic app (`core`,
  `integrations`, `jobs`, `warehouses`, `data_movement`, ...) — never
  duplicated per provider.
- Normative requirement: "Control-Plane Provider Boundary" in
  `openspec/changes/add-databricks-control-plane/specs/databricks-control-plane-roadmap/spec.md`.
- Enforcement (oss-release-remediation W4.6): **GATE-54**
  `scripts/check_provider_boundary.py` — AST import checker, wired into CI
  (lint workflow) + `make quality-gates` + the falsifiability harness.
  Scope: non-test Python files (the G1 audit's "non-test consumers");
  `if TYPE_CHECKING:` imports are exempt (no runtime coupling); test-file
  imports are advisory (`--include-tests`); allowlist
  `scripts/provider_boundary_allowlist.txt` holds exact `path:lineno:reason`
  triples (dead anchors FAIL; per-file ratchet vs git HEAD via
  `--check-allowlist-growth`). String references (`apps.get_model`,
  migration FK labels, OpenAPI `target_class`) are not imports — out of
  checker scope by design (review-enforced).

# Environment Failure Policy (Phase T.4 / W16)

- ONE policy governs every "service unavailable / not authenticated /
  dependency missing" branch in the test trees: when `CI=true` the branch
  RAISES instead of skipping; local runs keep the graceful skip.
- Python: `envpolicy.py` (project root) — `environment_guard()`,
  `skip_or_fail()`, `api_available()`, `probe_service()`. A 5xx counts as
  DOWN (`probe_service` returns False) — the retired per-file
  `_check_api_available()` accepted anything `< 600`. `api_available()`
  is the ONLY reachability probe; do not reintroduce per-file copies.
  CLI auto-skip hooks share one implementation:
  `cli/tests/_env_skip.py::auto_skip_unreachable_api`.
- Frontend: `frontend/e2e/fixtures/envPolicy.cjs` (CJS so both TS specs and
  the Node harness require it unchanged) — `environmentSkipGuard()` throws a
  `[W16]` error under CI. `loginUser`'s `failOnFallback` option is RETIRED:
  the policy decides (CI raises, local falls back to API injection).
- TDD pins: `scripts/tests/test_env_policy_py.py`,
  `scripts/tests/test_cli_env_skip.py`,
  `scripts/tests/test_env_policy.cjs` (wired into frontend-ci.yml).
- Never catch `EnvironmentFailureError` to convert it back into a skip.

# Skip/Placeholder Debt Contract (Phase T.5 / W17)

- Every `skip`/`fixme`/`xfail` REASON carries `TICKET=<id> EXPIRES=<YYYY-MM-DD>`
  (expiry date inclusive). Placeholder-bodied tests (comment-only bodies,
  tautology assertions, Phase-105 export-existence stubs) annotate as the
  first comment inside the body.
- GATE-40 `scripts/check_skip_expiry.py`: EXPIRED annotations fail always
  (even under baseline); unannotated sites are ratcheted per bucket
  (`scripts/skip_expiry_baseline.json`, `--update` after a fix wave).
  Phase sign-off reads the debt count, not the file count.
- Dynamic env-gated skips (W16 `auto_skip_unreachable_api`) are governed by
  the environment policy, not by this gate — never add TICKET/EXPIRES to
  them.

# Documentation Sync Contract (Phase 312.5)

When implementing a feature that introduces a user journey or use case:

1. Add journey entry to `docs/USER_JOURNEYS.md` — ID, title, persona, phase.
2. Add use case entry to `docs/USE_CASES.md` — ID, title, persona, file ref.
3. Add `@pytest.mark.journey("JOURNEY-XXX")` to ≥1 backend test method.
4. Add `@pytest.mark.uc("UC-XXX")` to ≥1 backend test method.
5. Create frontend E2E spec at `frontend/e2e/journeys/<persona>/JOURNEY-XXX.spec.ts`.
6. Import the spec in the persona aggregator at `frontend/e2e/personas/<persona>.spec.ts`.
7. If critical, add the ID to `docs/CRITICAL_UC_JOURNEY_IDS.yaml`.
8. Run `make audit-docs` before merge.

**Enforcement**:
- CI GATE-26 (`lint_journey_marker_coverage.py --blocking`) — critical journeys MUST have markers.
- CI GATE-27 (`check_doc_journey_marker_sync.py --ci-mode`) — bidirectional journey doc↔marker sync.
- CI GATE-28 (`check_doc_uc_marker_sync.py --ci-mode`) — bidirectional UC doc↔marker sync.
- Pre-commit hooks run on changed docs/test files.
- `check_persona_mapping_drift.py` enforces persona fixture consistency.
- `check_assert_true_true.py` blocks `assertTrue(True)` stubs.

**Traceability registries** (single source of truth):
1. `docs/USER_JOURNEYS.md` — 181 canonical journeys across 13 personas.
2. `docs/USE_CASES.md` — 146 canonical use cases across 23 domains.
3. `docs/CRITICAL_UC_JOURNEY_IDS.yaml` — CI gate critical ID subset (35 UC + 29 journey).
4. `docs/mvpdocs/_meta/persona-mapping.yaml` — 13 fixture personas → 6 canonical personas.
5. `docs/mvpdocs/_meta/persona-journey-mapping.yaml` — persona → journey ID list (frontend-extracted).

**See also**: `docs/TRACEABILITY_ARCHITECTURE.md` for the full traceability system reference.
