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
