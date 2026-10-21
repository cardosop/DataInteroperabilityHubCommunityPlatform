# W11.11 ZAP DAST — finding triage ledger

Every NEW HIGH / escalation accepted into the baselines MUST have a row
here BEFORE the baseline promotion PR lands (see
[docs/runbooks/w1111-dast-zap.md](../../runbooks/w1111-dast-zap.md)).
A baseline promotion without a triage entry for every accepted new
alert is a process violation.

## Triage row format

| Date | Surface | Plugin ID | Alert | URI | Verdict | Rationale + sign-off |

Verdicts:

* **FIXED** — root-fixed in code (cite the fix commit + pin test), then re-scanned.
* **FALSE-POSITIVE** — scanner artifact / staging-only behaviour / edge difference; explain why it is not exploitable and who signed it off.

## Rows

| Date | Surface | Plugin ID | Alert | URI class | Verdict | Rationale + sign-off |
|---|---|---|---|---|---|---|
| 2026-10-17 | all authenticated roles | 40018 | SQL Injection (OR/AND-based heuristic, empty evidence) | `{uuid}` path params fuzzed with `id AND 1=1 --` (governance access-requests/certifications/comments, contracts, jobs DLQ, …) | FALSE-POSITIVE | Reproduced live: every fuzzed path returns the typed 404 `NOT_FOUND` envelope (UUID validation rejects before any SQL path); no error text, no stack, no time delta — the OR/AND heuristic fires on identical typed responses. Sign-off: Security Engineering Lead (W11.11 evidence audit §2b). |
| 2026-10-17 | all authenticated roles | 40018 | SQL Injection (evidence: HTTP/1.1 500) | `int()` query params (`days_ahead`, `limit`, …) | FIXED | Real validation-defect class — root-fixed with the canonical `parse_int_query_param` helper across 20 files (typed 400s; RED-proven pins + live 500→400 verification). Not a baseline row — recorded here as the disposition trail. |

_Initial-baseline note: the first baselines are the first authenticated
scan snapshots — by construction nothing is "new" until the second run.
The rows above document why the initial baselines carry the empty-
evidence 40018 HIGHs as accepted false positives; every HIGH surfacing
on subsequent runs that is accepted rather than fixed gets a row here,
and findings root-fixed instead are recorded in
docs/audits/w1111-dast-2026-10-16.md._
