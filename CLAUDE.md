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
