# RACI matrix — Phase 250 Asset Creation Hardening

**Phase**: 250.0.16 / D250.18
**Status**: Authoritative
**Owners**: Asset-Creation EM, Phase 250 Driver

## Purpose

Cross-functional dependencies caused delivery slippage in prior phases (notably DPO + Legal sign-off on cross-tenant data-sharing). This matrix front-loads the conversation: every phase × stakeholder cell is one of R / A / C / I:

- **R — Responsible**: does the work.
- **A — Accountable**: signs off on completion (single accountable owner per row).
- **C — Consulted**: input solicited before decisions are made.
- **I — Informed**: kept aware; no decision authority.

## Stakeholders

| Code | Stakeholder |
|---|---|
| **Eng** | Asset-Creation Engineering team (backend + frontend + SDK) |
| **EM** | Asset-Creation Engineering Manager |
| **PM** | Product Manager |
| **Sec** | Security Engineering |
| **Legal** | Legal Counsel |
| **DPO** | Data Protection Officer |
| **Support** | Customer Support / Customer Success |
| **SRE** | Site Reliability Engineering |
| **Director** | Engineering Director (escalation path) |

## Matrix

| Phase / sub-phase | Eng | EM | PM | Sec | Legal | DPO | Support | SRE | Director |
|---|---|---|---|---|---|---|---|---|---|
| **250.0** OpenSpec / ADRs / verification | R | A | C | C | I | I | I | I | I |
| **250.1.A** Workflow re-sequence (HIGH) | R | A | C | C | I | I | C | C | I |
| **250.1.B** Fail-closed cleanup test | R | A | I | C | I | I | I | I | I |
| **250.1.C** Workflow versioning + in-flight | R | A | C | I | I | I | I | C | I |
| **250.1.D** Idempotency keys | R | A | C | I | I | I | I | I | I |
| **250.1.E** Orphan-DRAFT cleanup | R | A | I | I | I | I | C | C | I |
| **250.1.F** Search-vector rebuild timing | R | A | I | I | I | I | I | C | I |
| **250.1.G** Webhook + internal-API consumer migration | R | A | C | C | I | I | C | C | I |
| **250.2.A** Auto-activation default | R | A | C | I | I | I | I | I | I |
| **250.2.B** Schema-comparison step | R | A | C | I | I | I | I | I | I |
| **250.2.C** Scheduled-ingestion validation parity | R | A | C | I | I | I | I | C | I |
| **250.3.A** KYC gate | R | A | C | C | C | I | C | I | I |
| **250.3.B** Status canonicalisation phase 1 | R | A | C | I | I | I | C | I | I |
| **250.3.C** Status canonicalisation phase 2 | R | A | C | I | I | I | C | I | C |
| **250.4** SDK programmatic flow | R | A | C | I | I | I | C | I | I |
| **250.5.A** Federated import spec | R | A | C | C | **C** | **A** | I | C | C |
| **250.5.B** SSRFGuard | R | A | I | **A** | I | I | I | C | I |
| **250.5.C** Federated IDOR test | R | A | I | **A** | I | C | I | I | I |
| **250.5.D** Spec drift remediation | R | A | C | I | I | I | I | I | I |
| **250.5.E** STRIDE threat model + pen-test | C | C | I | **R/A** | C | C | I | I | C |
| **250.5.F** GDPR + DPA | R | C | C | C | **R/A** | **R/A** | I | I | C |
| **250.6.A** Per-tenant kill-switch | R | A | C | I | I | I | C | C | I |
| **250.7.A** Semantic graceful-degrade | R | A | C | I | I | I | C | C | I |
| **250.7.B** Optimistic-locking on every edit | R | A | C | C | I | I | C | I | I |

## Stakeholder responsibilities by phase

### Sec (Security)
- **250.1.A** consulted on the new `ASSET_FAIL_CLOSED_REJECTED` audit emission to ensure no PII leaks.
- **250.1.G** consulted on webhook timing changes (webhook subscribers may rely on prior latency).
- **250.3.A** consulted on KYC gate behavior to ensure no information disclosure.
- **250.5.A** consulted on federated import; cross-tenant data-sharing surface.
- **250.5.B** ACCOUNTABLE for the SSRFGuard implementation (security primary control).
- **250.5.C** ACCOUNTABLE for the IDOR test sweep (existence-leak protection).
- **250.5.E** RESPONSIBLE + ACCOUNTABLE for the STRIDE threat model + pen-test execution.
- **250.5.F** consulted on GDPR controls (data flow, retention).
- **250.7.B** consulted on optimistic-locking ETag generation (cryptographic vs counter-based).

### Legal
- **250.5.A** CONSULTED on federated import spec (cross-tenant data-sharing legal review).
- **250.5.E** consulted on threat model exposure to regulator audits.
- **250.5.F** RESPONSIBLE + ACCOUNTABLE for GDPR + DPA review, contract templates, retention policy.

### DPO (Data Protection Officer)
- **250.5.A** ACCOUNTABLE for federated import privacy review (default-OFF flag, per-tenant opt-in).
- **250.5.C** consulted on cross-tenant existence-leak protection.
- **250.5.F** RESPONSIBLE + ACCOUNTABLE for GDPR records-of-processing updates.

### Support
- **250.1.A** consulted on user-facing error messaging when fail-closed rejects an asset.
- **250.1.E** consulted on orphan-DRAFT cleanup to anticipate customer queries.
- **250.1.G** consulted on webhook subscriber notifications.
- **250.3.A** consulted on KYC-gate-related customer escalations.
- **250.3.B/C** consulted on `visibility` field deprecation customer comms.
- **250.4** consulted on SDK polling behavior changes for existing SDK customers.
- **250.6.A** consulted on `asset_creation_enabled=False` UX (DisabledCapabilityPage messaging).
- **250.7.A** consulted on `semantic_status=FAIL` banner UX.

### SRE
- **250.1.A** consulted on the workflow re-sequence rollout (rolling-deploy, soak windows).
- **250.1.C** consulted on workflow versioning runtime behavior.
- **250.1.E** consulted on cleanup-job operational concerns.
- **250.1.F** consulted on search-index rebuild impact on read latency.
- **250.1.G** consulted on webhook delivery rate during migration.
- **250.2.C** consulted on scheduled-ingestion validation runtime impact.
- **250.5.B** consulted on SSRF guard runtime impact (DNS re-resolve cost).
- **250.6.A** consulted on kill-switch operational toggling.
- **250.7.A** consulted on async retry queue depth + dead-letter alerting.

### Director (Engineering Director)
- **250.3.C** CONSULTED on the irreversible drop-column migration.
- **250.5.A** consulted on the cross-tenant data-sharing scope expansion.
- **250.5.E** consulted on threat-model findings + pen-test results.
- **250.5.F** consulted on GDPR + DPA contract obligations.

## Decision rights

| Decision | Owner | Constraints |
|---|---|---|
| Phase 250.1.A workflow re-sequence sign-off | EM (Eng) | Sec consult; DPO consult on audit-event PII; Support consult on UX |
| Phase 250.5.A federated import production flip | DPO | Legal sign-off prerequisite; Eng RACI = R |
| Phase 250.5.E threat-model release | Sec Director | findings ≥ HIGH gate the merge |
| Phase 250.5.F GDPR + DPA contract | Legal Counsel | DPO co-sign |
| Phase 250.6.A kill-switch flip in production | Tenant Admin (per-tenant) OR Platform Admin (cross-tenant) | Audit event emitted on every flip; PLATFORM_ADMIN escalation only with documented incident reason |
| Phase 250.7.B `OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True` flip | EM (Eng) + SRE | 7-day soak with zero `ASSET_PATCH_MISSING_IF_MATCH` events prerequisite |

## Escalation paths

| Issue | First escalation | Second escalation |
|---|---|---|
| Workflow rollback in production | SRE on-call | Eng EM |
| Compliance gate false-positive blocking customer | Compliance team | Legal + DPO |
| Webhook subscriber breakage post-250.1.A | Support team | Eng EM |
| Threat-model finding HIGH/CRITICAL | Sec Director | Engineering Director |
| GDPR-related customer complaint | DPO | Legal Counsel |

## Cadence

- **Phase kickoff**: 30-min meeting with R + A + each C-cell stakeholder. Ad-hoc.
- **Weekly status**: Engineering team posts in `#asset-creation-eng`; consulted parties read async.
- **Sign-off** (mandatory before deploy): RACI shows ACCOUNTABLE party; written sign-off in PR description.
- **Post-mortem**: any production incident traceable to a Phase 250 sub-phase auto-spawns a post-mortem with the full RACI list as participants.

## Maintenance

This matrix is reviewed at:
1. **Phase 250 closeout** — final RACI verification per the audit-pass discipline.
2. **Annually thereafter** — until Phase 250 capabilities transition to BAU.

Updates require sign-off from EM (Eng) + at least one consulted stakeholder per modified row.
