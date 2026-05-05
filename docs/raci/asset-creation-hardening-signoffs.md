# RACI sign-off ledger — Phase 250 Asset Creation Hardening

**Phase:** 250.DoD.6
**Status:** Open — entries appended as each phase × stakeholder approval lands.
**Owners:** Asset-Creation EM (custodian) / Phase 250 Driver (auditor)

This ledger records the **explicit** sign-offs required by Phase 250.DoD.6
("Stakeholder RACI sign-off per phase × {Eng, EM, PM, Sec, Legal, DPO, Support, SRE}").
The companion matrix at [`asset-creation-hardening.md`](./asset-creation-hardening.md)
defines who needs to sign for each row; this file records the actual approvals.

## Recording protocol

1. The Accountable (`A` cell) for each row collects the required sign-offs
   from every Consulted (`C`) and Responsible (`R`) stakeholder named in
   the matrix row.
2. Each sign-off MUST include the stakeholder's name, role, ISO date, and
   either:
   - a link to the GitHub PR review marked **Approved** by that user, or
   - a written attestation in this ledger when the stakeholder has no
     GitHub identity (e.g. Legal Counsel attesting to GDPR review via
     email, transcribed verbatim).
3. The Accountable marks the phase row complete in the table below ONLY
   after every required sign-off has landed.

## Phase 250.DoD.6 — sign-off matrix

| Phase / sub-phase | Accountable | Required sign-offs | Approval refs | Status |
|---|---|---|---|---|
| 250.0 OpenSpec / ADRs / verification | EM | Eng (R), PM (C), Sec (C) | _PR/attestation links_ | _open_ |
| 250.1.A Workflow re-sequence | EM | Eng (R), PM (C), Sec (C), Support (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.1.B Fail-closed cleanup test | EM | Eng (R), Sec (C) | _PR/attestation links_ | _open_ |
| 250.1.C Workflow versioning + in-flight | EM | Eng (R), PM (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.1.D Idempotency keys | EM | Eng (R), PM (C) | _PR/attestation links_ | _open_ |
| 250.1.E Orphan-DRAFT cleanup | EM | Eng (R), Support (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.1.F Search-vector rebuild timing | EM | Eng (R), SRE (C) | _PR/attestation links_ | _open_ |
| 250.1.G Webhook + internal-API consumer migration | EM | Eng (R), PM (C), Sec (C), Support (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.2.A Auto-activation default | EM | Eng (R), PM (C) | _PR/attestation links_ | _open_ |
| 250.2.B Schema-comparison step | EM | Eng (R), PM (C) | _PR/attestation links_ | _open_ |
| 250.2.C Scheduled-ingestion validation parity | EM | Eng (R), PM (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.3.A KYC gate | EM | Eng (R), PM (C), Sec (C), Legal (C), Support (C) | _PR/attestation links_ | _open_ |
| 250.3.B Status canonicalisation phase 1 | EM | Eng (R), PM (C), Support (C) | _PR/attestation links_ | _open_ |
| 250.3.C Status canonicalisation phase 2 | EM | Eng (R), PM (C), Support (C), Director (C) | _PR/attestation links_ | _open_ |
| 250.4 SDK programmatic flow | EM | Eng (R), PM (C), Support (C) | _PR/attestation links_ | _open_ |
| 250.5.A Federated import spec | DPO | Eng (R), EM (A), PM (C), Sec (C), Legal (C), SRE (C), Director (C) | _PR/attestation links_ | _open_ |
| 250.5.B SSRFGuard | Sec | Eng (R), EM (A), SRE (C) | _PR/attestation links_ | _open_ |
| 250.5.C Federated IDOR test | Sec | Eng (R), EM (A), DPO (C) | _PR/attestation links_ | _open_ |
| 250.5.D Spec drift remediation | EM | Eng (R), PM (C) | _PR/attestation links_ | _open_ |
| 250.5.E STRIDE threat model + pen-test | Sec | Eng (C), EM (C), Legal (C), DPO (C), Director (C) | _PR/attestation links_ | _open_ |
| 250.5.F GDPR + DPA | Legal + DPO | Eng (R), EM (C), PM (C), Sec (C), Director (C) | _PR/attestation links_ | _open_ |
| 250.6.A Per-tenant kill-switch | EM | Eng (R), PM (C), Support (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.7.A Semantic graceful-degrade | EM | Eng (R), PM (C), Support (C), SRE (C) | _PR/attestation links_ | _open_ |
| 250.7.B Optimistic-locking on every edit | EM | Eng (R), PM (C), Sec (C), Support (C) | _PR/attestation links_ | _open_ |

## Closeout-pass sign-offs (Phase 250 overall DoD)

These approvals belong to the overall phase, not a specific sub-phase. They
gate `250.DoD.6` itself.

| DoD item | Accountable | Required sign-offs | Approval refs | Status |
|---|---|---|---|---|
| 250.DoD.4 SLO escalation policy live | SRE on-call lead | EM, SRE on-call, Engineering Director (prod drill) | _GitHub run URLs from auto-rollback drill_ | _open_ |
| 250.DoD.5 30 % contingency buffer | EM | EM, Phase 250 Driver | `docs/audit-reports/250-dod-closure-pass-2026-05-04.md` | **closed** |
| 250.DoD.6 RACI sign-off (this ledger) | EM | EM (custodian), Phase 250 Driver (auditor) | _this file once all rows above are closed_ | _open_ |
| 250.DoD.7 Production smoke green | EM + SRE on-call | EM, SRE on-call | _CI run URL of `tests/smoke/test_phase250_data_first.py` against staging post-deploy_ | _open_ |
| 250.DoD.8 OpenSpec archive | Engineering Lead | Engineering Lead, EM, SRE on-call | _archive PR URL_ | _open_ |

## Auditor checklist

When closing 250.DoD.6 the Phase 250 Driver MUST verify:

- [ ] Every sub-phase row in `asset-creation-hardening.md` has a closed
      row in this ledger.
- [ ] Every sign-off entry includes a verifiable approval reference (PR
      review link or transcribed attestation).
- [ ] The closeout-pass table has `250.DoD.4`, `.7`, `.8` in **closed**
      state before flipping `250.DoD.6` itself.
- [ ] No row contains a placeholder (`_to be filled_`, `_open_`, etc.).
