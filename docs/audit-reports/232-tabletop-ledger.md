# Phase 232 regulator-audit tabletop ledger

**Phase:** 232.DoD.7
**Owner:** Compliance Engineering Lead (custodian) / EM (approver)
**Last reviewed:** 2026-05-05

This file records every run of the regulator-audit tabletop exercise
defined in [docs/runbooks/phase232-regulator-audit-tabletop.md](../runbooks/phase232-regulator-audit-tabletop.md).
Each run produces seven scenario rows (S1–S7); a run is **green** when
every row is `pass` AND every wall-clock duration is within budget.

## Closure criteria

- ≥ 1 green run on file.
- Closure block signed by Compliance Engineering Lead + DPO + Legal
  Counsel + EM.
- No row in the latest run references an open bug at HIGH/CRITICAL
  severity.

The closure block below records the latest signed-off run. A new run
is appended below the closure block; once it is signed off, the new
block replaces the old one (the prior is retained in the run history).

## Run history

### Run 1 — _YYYY-MM-DD_ — _outcome: pending_

| Scenario | Run date (UTC) | Duration vs budget | Result | Artefacts | Notes |
|----------|----------------|--------------------|--------|-----------|-------|
| **S1** DSAR ACCESS within statutory deadline | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _ZIP S3 key_ | _—_ |
| **S2** DSAR ERASURE with active legal hold | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _refusal payload_ | _—_ |
| **S3** Breach notification within 72 h | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _Object-Lock proof S3 keys_ | _—_ |
| **S4** RoPA export under load | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _PDF S3 key_ | _—_ |
| **S5** DPIA required for high-risk asset | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _DPIA record id_ | _—_ |
| **S6** Consent revocation propagates | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _webhook delivery id_ | _—_ |
| **S7** Statuspage incident communication | _YYYY-MM-DD_ | _−Δ min / +Δ min_ | _pass/partial/fail_ | _Statuspage URL_ | _—_ |

#### Run 1 closure block

| Role | Name | Date | Attestation |
|---|---|---|---|
| Compliance Engineering Lead | _to be filled_ | _YYYY-MM-DD_ | _all 7 scenarios green within budget_ |
| DPO | _to be filled_ | _YYYY-MM-DD_ | _regulator-side acceptance_ |
| Legal Counsel | _to be filled_ | _YYYY-MM-DD_ | _privacy posture defensible_ |
| EM | _to be filled_ | _YYYY-MM-DD_ | _approval to flip flags_ |

A green Run 1 closes 232.DoD.7. Subsequent quarterly runs are appended
below; the closure block of the most recent green run is the
authoritative attestation.

## Auditor checklist

Before flipping any Phase 232 tenant flag to ON in production:

- [ ] Most recent run is `green`.
- [ ] All four signatures present + dated within the last 90 days.
- [ ] No row references an open HIGH / CRITICAL incident in the
      tracker.
- [ ] Pen-test ledger ([docs/audit-reports/232-pen-test-ledger.md](./232-pen-test-ledger.md))
      is also `green` for the corresponding subsystem (DoD.6 gate).
