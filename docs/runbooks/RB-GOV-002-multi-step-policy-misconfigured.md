# RB-GOV-002 — Multi-Step Policy Misconfiguration Investigation

## Status

Stub created in Phase 272.0.6. Populate during Phase 272 implementation as the multi-step state machine surface lands.

## Purpose

Operational procedure for investigating an access-request that is stuck at `PENDING_NEXT_APPROVER` — the chain has stalled because no matching approver is available (role misconfiguration, delegation expired, policy chain references a deleted role). This runbook is the Support + SRE counterpart to D-272.2's multi-step state machine.

## When this fires

- **Stuck request alert**: request in `PENDING_NEXT_APPROVER` > SLA threshold (72h soft, 7d hard).
- **Next-approver resolution failure**: the `_advance_approval_workflow()` step cannot resolve a valid approver for the next role in the chain.
- **Delegation window gap**: an active delegation exists but the delegate lacks the required role for the current step.

## Scope

1. **Inspect the request's `approval_workflow` snapshot**: what roles are expected and at which step the request is waiting.
2. **Resolve approvers**: enumerate users with the required role in the listing's tenant.
3. **Check active delegations**: `ApprovalDelegation` rows active for this step's role.
4. **Policy cross-check**: verify the `AccessPolicy.required_approval_chain` hasn't been edited to an invalid state (the snapshot protects in-flight requests, but a POST-edit state may break NEW requests).

## Decision tree

```
Request stuck at PENDING_NEXT_APPROVER > SLA
        │
        ▼
Read approval_workflow snapshot
        │
        ▼
  Role at current_step exists in tenant?
        │
   ┌────┴────┐
   NO        YES
   │          │
   ▼          ▼
Policy chain   Any user with
references     that role?
deleted role       │
→ escalate     ┌──┴──┐
to tenant      YES   NO
admin          │     │
               ▼     ▼
           Notify   Active
           user;   delegation
           may     covers this
           need    step?
           digest     │
                 ┌──┴──┐
                 YES   NO
                 │     │
                 ▼     ▼
              Delegate Escalate
              should   to tenant
              approve  admin;
                        role
                        unstaffed
```

## Recovery actions

| Symptom | Likely cause | Recovery |
|---|---|---|
| Role not found in tenant | Policy chain references a role deleted after policy creation | Tenant admin must update `required_approval_chain` |
| No user with required role | Org has zero members with that role | Tenant admin must assign the role |
| Delegation exists but delegate lacks role | Delegate was granted delegation but not the underlying approval role | Tenant admin must assign role to delegate |
| Policy snapshot empty | Race condition at deploy boundary | Re-apply `_advance_approval_workflow()` via management command |

## Related

- **Spec**: `governance-abac-approval/spec.md` — Multi-Step Approval State Machine requirement.
- **Design**: `design.md` — D-272.2 (multi-step snapshot semantics).
- **RACI**: `docs/raci/governance-abac-approval.md` — Support consulted on stuck-chain escalations.
- **Model**: `hub/apps/governance/models.py` — `ApprovalDelegation`, `AccessPolicy.required_approval_chain`.
- **Cross-runbook**: [`RB-GOV-001-compliance-blocked-approval-investigation.md`](RB-GOV-001-compliance-blocked-approval-investigation.md) — compliance gate can also block approval.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
