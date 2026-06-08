# RB-CMP-002 — Legal-Basis Strict-Mode Incident

## Status

Stub created in Phase 270.0. Populate during Phase 270.C implementation.

## Purpose

Incident triage playbook for the per-tenant compliance legal-basis
strict mode (D-270.9): `Tenant.compliance_legal_basis_strict=True`
causes the compliance microservice to reject scans missing an
explicit `legal_basis` field per the
`X-Compliance-Legal-Basis-Strict` request header. Operators trigger
this runbook when:

- A tenant who just enabled strict mode is seeing unexpected
  `LEGAL_BASIS_REQUIRED` rejections on legitimate intake flows.
- A staged rollout of strict mode (Phase 270.C) catches a backlog of
  pre-existing assets that lack the field.
- A Hub→microservice header mismatch causes the strict check to be
  silently bypassed.

## Scope

- Alert intake (`ComplianceStrictModeRejectionBurst` if/when wired)
  and severity classification (single-tenant vs. cross-tenant)
- Verify Hub-side flag state: `Tenant.compliance_legal_basis_strict`
  matches the operator's expectation (read via the tenants admin API)
- Verify header propagation: capture a sample request between
  `api-service` and `compliance-service`; the
  `X-Compliance-Legal-Basis-Strict` header MUST equal the tenant's
  current flag value (D-270.9 contract — microservice does NOT read
  the flag from a DB lookup)
- Identify the rejection source: microservice
  `compliance_report.py` rejection (legitimate strict-mode trip) vs.
  Hub-side validation (caller-side bug — strict mode is a
  microservice concern, Hub should not pre-reject)
- Distinguish a `LEGAL_BASIS_REQUIRED` rejection (caller payload is
  missing the field) from a `LEGAL_BASIS_INVALID` rejection (caller
  sent a value but it's not in the registry)
- Containment options:
  - Per-tenant flip OFF via the PLATFORM_ADMIN feature-flag endpoint
    (Phase 235.1) — emits `TENANT_FEATURE_FLAG_CHANGED` audit
  - Global feature-flag override (`COMPLIANCE_LEGAL_BASIS_STRICT_FORCE_OFF`
    env-var) — last-resort kill-switch; deploys via standard rolling
    restart
- Forensic queries:
  - Audit-event search for the rejected scans (`COMPLIANCE_RUN_*`
    with `result=FAILURE` + `details_json.code='LEGAL_BASIS_REQUIRED'`)
  - Compliance-service structured logs filtered by `tenant_id` +
    `legal_basis_strict=true`
- Recovery actions:
  - Backfill missing `legal_basis` fields on assets via the
    `compliance-backfill-legal-basis` management command (Phase 270.C)
  - Re-run rejected scans after the backfill
- Postmortem evidence pack (audit-event sample, header capture,
  tenant flag history, backfill report)

## Related

- Spec: [`marketplace-tax-compliance-deltas/spec.md`](../../openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md) §
  *Per-Tenant Compliance Legal-Basis Strict Mode*
- Design: [`design.md#decision-d-2709`](../../openspec/changes/preprod01/design.md) (D-270.9)
- Code (populate at implementation time):
  `hub/apps/compliance/services.py` (header forwarding),
  `services/compliance-service/compliance_report.py` (strict-mode
  enforcement), `hub/apps/tenants/models.py`
  (`compliance_legal_basis_strict` field)
- Related runbook: [`audit-tamper-evidence.md`](audit-tamper-evidence.md)
  (audit-event reconstruction during compliance incidents)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
