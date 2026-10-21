# Asset fail-closed rollback — runbook

**Phase**: 250.0.19 (250.1.A operational support)
**Status**: Authoritative
**Severity**: HIGH (fail-closed rejection blocks customer asset creation)

## Scope

Diagnose + remediate cases where the Phase 250.1.A workflow re-sequence rejects asset creation due to compliance OR DQ gate failures.

## Symptoms

- Customer reports HTTP 422 on `POST /api/v1/assets/data-first/` polling.
- `WorkflowRun.state=FAILED` with `error_code=ASSET_FAIL_CLOSED_REJECTED`.
- Audit events: `ASSET_FAIL_CLOSED_REJECTED` with linked `compliance_run_id` OR `dq_run_id`.
- Tenant Slack ticket: "I uploaded my CSV but no asset appeared".

## Diagnostic procedure

1. Get the failed workflow run id from the audit event:
   ```
   audit_event = AuditEvent.objects.filter(
       audit_type='ASSET_FAIL_CLOSED_REJECTED',
       tenant_id='<tenant_uuid>',
   ).order_by('-created_at').first()
   ```
2. Inspect `audit_event.details_json` for the rejection reason. Two cases:
   - `compliance_run_id` populated → compliance rejected.
   - `dq_run_id` populated → DQ rejected.

### Case A: compliance rejection

```
ComplianceRun.objects.get(id='<compliance_run_id>').decision  # REJECT or BLOCK
ComplianceRun.objects.get(id='<compliance_run_id>').details_json
```

Common reasons + remediation:

| Reason | Customer-facing remediation |
|---|---|
| `PII_DETECTED_NO_LEGAL_BASIS` | Tenant must provide `legal_basis` query param OR upload after configuring the tenant compliance regime. |
| `CROSS_BORDER_TRANSFER_BLOCKED` | Tenant's compliance regime prohibits the data destination region; configure tenant `data_residency` or remove the file. |
| `RETENTION_POLICY_MISMATCH` | Tenant's retention policy is shorter than the file's required retention; reconfigure tenant policy. |
| `BLOCKED_BY_TENANT_KILL_SWITCH` | Tenant `compliance_intake_gate_enabled=False` (Phase 232 kill switch); contact tenant admin. |

### Case B: DQ rejection

```
DQRun.objects.get(id='<dq_run_id>').overall_status  # FAIL
DQRun.objects.get(id='<dq_run_id>').details_json
```

Common reasons + remediation:

| Reason | Customer-facing remediation |
|---|---|
| `SCHEMA_VIOLATION_REQUIRED_COLUMN_MISSING` | Required column missing per tenant's `intake_basic_*` profile; tenant fixes the file. |
| `THRESHOLD_BREACH` (e.g. >50% null in a column) | Tenant `dq_threshold` exceeded; tenant fixes the data OR loosens the threshold via `/settings/dq/thresholds`. |
| `CIRCUIT_BREAKER_OPEN` | dq-service circuit breaker open; this is a SYSTEM issue not a customer issue — see [docs/runbooks/data-quality.md](data-quality.md). |

## Permissive override (D250.9)

If compliance circuit-breaker is OPEN AND the tenant has explicit opt-in (`tenant.allow_intake_on_compliance_degraded=True`), the workflow allows asset creation with a `COMPLIANCE_DEGRADED_ALLOWED` audit event. Use this as a deliberate emergency-override only.

To enable:
```
python manage.py shell -c "
from hub.apps.tenants.models import Tenant
t = Tenant.objects.get(id='<tenant_uuid>')
t.allow_intake_on_compliance_degraded = True
t.save(update_fields=['allow_intake_on_compliance_degraded'])
"
```

## Rollback (NOT for fail-closed rejections — for production incidents only)

If a Phase 250.1.A bug causes systemic false-positives across many tenants:

1. Disable the fail-closed flag for affected tenants:
   ```
   python manage.py disable_compliance_fail_closed --tenants=<csv-of-uuids> --reason="<incident_id>"
   ```
   This sets `compliance_fail_closed_enabled=False` per affected tenant, falling back to legacy "create-then-validate" semantics for the duration of the incident.

2. Open Phase 250.1.A bug ticket.

3. After fix lands, re-enable per tenant in batches (NOT all-at-once) per RACI matrix sign-off.

## Verification post-incident

After the incident is resolved, run:

```
python manage.py audit_phase_250_1_a_invariants --since=<incident_start>
```

The script asserts:
- Every `Asset` row has a corresponding successful `WorkflowRun.state=COMPLETED`.
- Zero orphan `Asset` rows (no associated WorkflowRun).
- Zero `ASSET_FAIL_CLOSED_REJECTED` audit events that resulted in an `Asset` being created (contract violation).

## Escalation

- **Customer issue (single tenant)**: customer-success → Eng on-call.
- **Systemic (multiple tenants)**: SRE on-call → Eng EM → Compliance Lead.
- **Compliance microservice down**: dq-service / compliance-service runbooks; on-call for the affected microservice.

## Related

- [audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md](../audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md) — direct caller bypass risks.
- [adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md](../adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md) — design rationale.
