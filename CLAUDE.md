# Tenant Isolation RLS Contract

- All new models with `tenant_id` MUST ship a paired RLS policy migration.
- CI enforces this through `lint-rls-policies` (`scripts/lint_rls_policies.py`).
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
  ``SPARQL_RATE_LIMIT_EXCEEDED`` via ``throttled()`` override.
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

### Semgrep guard
`semgrep/rules/prefer-chain.yaml` warns on direct `XxxBusinessRules(...).validate_*()` in services/views when a registered chain exists. Escape hatch: `# noqa: prefer-chain`.

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

### Per-tenant chain enablement (274.16.13)
- Chains may be gated per-tenant via `Tenant.business_rules_chain_<name>_enabled`
  BooleanField (default True for new tenants, False for existing).
- Migration template: `AddField` with `default=False`, model default callable
  returning True for new rows (mirrors Phase 271.1.2 `_default_connect_enabled`).
