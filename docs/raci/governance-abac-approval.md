# RACI matrix — Phase 272 Governance ABAC + Multi-Step Approval + Compliance Gate

**Phase**: 272.0.5
**Status**: Authoritative
**Owners**: Governance EM, Phase 272 Driver
**Capability spec**: [`openspec/changes/preprod01/specs/governance-abac-approval/spec.md`](../../openspec/changes/preprod01/specs/governance-abac-approval/spec.md)
**Design**: [`openspec/changes/preprod01/design.md` — Phase 272](../../openspec/changes/preprod01/design.md) (D-272.1 through D-272.5)

## Purpose

Phase 272 introduces ABAC policy evaluation in the approval path, a multi-step state machine, a compliance gate on approval, delegation for out-of-office approvers, and notification fan-out. This crosses Engineering, Product, Security, Legal (compliance gate), and Support (approver confusion / delegation queries).

## Stakeholders

| Code | Stakeholder |
|---|---|
| **Eng** | Governance Engineering team (backend + frontend) |
| **EM** | Governance Engineering Manager |
| **PM** | Product Manager |
| **Sec** | Security Engineering |
| **Legal** | Legal Counsel (compliance gate on asset access) |
| **Support** | Customer Support (approver delegation queries, stuck-chain escalations) |
| **SRE** | Site Reliability Engineering (digest delivery, WebSocket reliability) |

## Matrix

| Phase / sub-phase | Eng | EM | PM | Sec | Legal | Support | SRE |
|---|---|---|---|---|---|---|---|
| **272.0** OpenSpec / ADR / RACI / runbooks | R | A | C | I | I | I | I |
| **272.1** `AccessRequestComment` model + persistence | R | A | C | I | I | I | I |
| **272.2** Compliance gate on approval | R | A | C | C | **C** | I | I |
| **272.3** ABAC into approval path | R | A | C | **C** | C | I | I |
| **272.4** Multi-step state machine | R | A | C | C | C | C | I |
| **272.5** Notifications (in-app + email digest + WebSocket) | R | A | C | I | I | C | C |
| **272.6** Revocation reason + delegation | R | A | C | C | I | C | I |
| **272.7** Rollout (per-tenant flag + notice window) | R | A | C | I | C | C | I |

## Sign-offs

| Sub-phase | EM | PM | Sec | Legal | Date |
|---|---|---|---|---|---|
| 272.0 (kickoff) | _pending_ | _pending_ | _pending_ | _pending_ | — |
| 272.1 (comments) | _pending_ | _pending_ | n/a | n/a | — |
| 272.2 (compliance gate) | _pending_ | _pending_ | _pending_ | _pending_ | — |
| 272.3 (ABAC) | _pending_ | _pending_ | _pending_ | _pending_ | — |
| 272.4 (multi-step) | _pending_ | _pending_ | _pending_ | n/a | — |
| 272.5 (notifications) | _pending_ | _pending_ | n/a | n/a | — |
| 272.6 (delegation) | _pending_ | _pending_ | _pending_ | n/a | — |
| 272.7 (rollout) | _pending_ | _pending_ | n/a | _pending_ | — |

## Cross-references

- Spec: [`openspec/changes/preprod01/specs/governance-abac-approval/spec.md`](../../openspec/changes/preprod01/specs/governance-abac-approval/spec.md) — 9 ADDED Requirements.
- Design: [`openspec/changes/preprod01/design.md` — Phase 272](../../openspec/changes/preprod01/design.md) — D-272.1 through D-272.5.
- ADR: [`docs/adr/governance/ADR-GOV-001-multi-step-state-machine.md`](../adr/governance/ADR-GOV-001-multi-step-state-machine.md).
- Runbooks: [`RB-GOV-001`](../runbooks/RB-GOV-001-compliance-blocked-approval-investigation.md), [`RB-GOV-002`](../runbooks/RB-GOV-002-multi-step-policy-misconfigured.md).
