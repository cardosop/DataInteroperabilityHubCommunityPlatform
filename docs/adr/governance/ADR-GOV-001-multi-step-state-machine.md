# ADR-GOV-001 — Multi-Step Approval State Machine

**Status:** Accepted
**Date:** 2026-05-12
**Phase:** 272 (Governance ABAC + Multi-Step Approval + Compliance Gate)
**Supersedes:** None (new capability)

## Context

Prior to Phase 272, governance approval was single-stage: any TENANT_ADMIN or designated approver could approve an access request in one step, and the entitlement was created immediately. The `AccessPolicy` model existed with claims-based ABAC rules, but the multi-step approval fields (`approval_workflow`, `current_approval_step`) were declared in the `AccessRequest` model and never populated — they were dead schema waiting for a business-rules consumer.

Phase 272 activates these fields with a state machine that respects a per-policy `required_approval_chain` — an ordered list of role keys that must approve sequentially before an entitlement is created.

## Decision

We add `PENDING_NEXT_APPROVER` as a new `AccessRequestStatus`, replicate it in the frontend badge lexicon, and implement a three-state flow:

```
PENDING → PENDING_NEXT_APPROVER → ... → PENDING_NEXT_APPROVER → APPROVED
   │                     │
   └── REJECTED ←────────┘  (any step)
```

On the FIRST approval (PENDING → first transition), the `AccessPolicy.required_approval_chain` is snapshotted into `AccessRequest.approval_workflow` so in-flight requests are immune to policy edits. The `current_approval_step` field increments with each step; the entitlement is created ONLY when the final step is approved.

The `GovernanceService.reject_access_request()` terminates the chain from any step.

## Alternatives Considered

- **Per-step approver assignment at request-creation time**: would require knowing the org chart at intake time; fragile under role changes. The snapshot-at-first-transition approach defers resolution to each step while keeping the chain shape stable.
- **Per-request custom chains (not policy-driven)**: more flexible but invites ad-hoc bypass; the spec intentionally constrains multi-step to policy-defined chains so compliance and audit have a predictable structure.
- **Separate workflow engine (Temporal / Prefect)**: over-engineered for a 2–4 step human approval flow. The Django ORM-based state machine with atomic status transitions is sufficient; migrate later if non-linear branching or SLA timers become necessary.

## Consequences

- **Positive**: governance approval now supports staged sign-off (e.g., data owner → CDO → DPO); compliance gate before ABAC provides defence-in-depth.
- **Positive**: in-flight requests are isolated from policy edits via the snapshot mechanism.
- **Negative**: the frontend must render per-step progress indicators (`MultiStepApprovalIndicator.tsx`) and role-matched pending-count filters — added UX surface for operators.
- **Negative**: notification fan-out per step requires a daily digest (`send_pending_approvals_digest`) and in-app notification delivery — increased background-job surface.

## Cross-references

- Spec: `openspec/changes/preprod01/specs/governance-abac-approval/spec.md`
- Design: `openspec/changes/preprod01/design.md` — D-272.2 (multi-step state machine)
- RACI: `docs/raci/governance-abac-approval.md`
- Model: `hub/apps/governance/models.py` — `AccessRequestStatus.PENDING_NEXT_APPROVER`, `approval_workflow`, `current_approval_step`
- Service: `hub/apps/governance/services.py` — `_advance_approval_workflow()`
- Metrics: `hub/apps/governance/metrics.py` — `governance_approval_step_duration_seconds`
