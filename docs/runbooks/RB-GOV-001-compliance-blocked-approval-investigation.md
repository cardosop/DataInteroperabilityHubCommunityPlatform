# RB-GOV-001 — Compliance-Blocked Approval Investigation

## Status

Stub created in Phase 272.0.6. Populate during Phase 272 implementation as the compliance gate surface lands.

## Purpose

Operational procedure for investigating an access-request approval that is blocked by the compliance gate — the resource has no `ComplianceRun` or the latest run has `allowed_to_store=False`. This runbook is the Support + SRE counterpart to D-272.3's "compliance gate before ABAC" decision.

## When this fires

- **API response 422 `compliance_run_required`** — approver sees "No compliance scan exists for this resource."
- **API response 422 `compliance_not_allowed_to_store`** — approver sees "Compliance scan disallows storage for this resource."
- **PLATFORM_ADMIN override** — admin uses `?force_approve=true` to bypass; `ACCESS_REQUEST_COMPLIANCE_GATE_OVERRIDDEN` audit fires.
- **Prometheus metric `governance_approval_compliance_blocked_total`** — increment triggers ops awareness.

## Scope

1. **Verify compliance state**: query `ComplianceRun.objects.filter(resource_id=asset_id).latest("created_at")` to confirm `allowed_to_store`.
2. **Trigger a re-scan** if no run exists or the latest is stale.
3. **PLATFORM_ADMIN bypass** for emergency access — audit-recorded, time-limited.
4. **Postmortem evidence pack**: compliance run details, audit trail of the blocked approval, force_approve audit row (if applicable).

## Decision tree

```
Approval returns 422 compliance gate
        │
        ▼
  Latest ComplianceRun exists?
        │
   ┌────┴────┐
   NO        YES
   │          │
   ▼          ▼
Trigger     allowed_to_store?
compliance      │
scan        ┌──┴──┐
            YES   NO
            │     │
            ▼     ▼
        Should   Resource failed
        not      compliance;
        happen   escalate to
                 asset owner
```

## Forensic queries (Django shell)

```python
# Populated at 272.2 implementation.
# - ComplianceRun.objects.filter(resource_id=<asset_id>).latest("created_at")
# - AuditEvent.objects.filter(action="ACCESS_REQUEST_BLOCKED_COMPLIANCE").order_by("-created_at")[:10]
```

## Recovery actions

| Symptom | Likely cause | Recovery |
|---|---|---|
| No ComplianceRun | Asset ingested before Phase 231 compliance gate | Trigger compliance scan; tenant should re-publish listing |
| `allowed_to_store=False` | PII in unclassified dataset, DQ scan failed | Review compliance report; asset owner must remediate; re-scan |
| Gate fires after force_approve | Second approval in multi-step chain; bypass was per-step | Re-apply force_approve or run compliance scan |

## Related

- **Spec**: `governance-abac-approval/spec.md` — Compliance Gate on Approval requirement.
- **Design**: `design.md` — D-272.3 (compliance gate before ABAC).
- **RACI**: `docs/raci/governance-abac-approval.md` — Legal consulted on compliance gate.
- **Alerts**: `governance_approval_compliance_blocked_total` Prometheus counter.
- **Cross-runbook**: [`RB-GOV-002-multi-step-policy-misconfigured.md`](RB-GOV-002-multi-step-policy-misconfigured.md) — policy misconfiguration can also block approval.

## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
