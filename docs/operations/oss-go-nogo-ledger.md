# OSS Release Go/No-Go Sign-Off Ledger (U.8 / W10.4)

Machine-parseable sign-off records for the U.8 go/no-go decision
(oss-release-remediation M5 — tasks.md W10.4). The gate
(`scripts/tests/test_w104_gonogo_pack_veracity.py`, CI lint pin list)
reads the tables below: a DoD row with `confirmed = yes` reports NO-GO;
a condition row without an owner or reason fails. Never edit a row to
`yes` without performing the confirmation — the gate is the machine
half of the decision; this file is the human half. The evidence pack
(`docs/audits/w104-gonogo-evidence-pack-2026-10-17.md`) is the reason
record every row points at; it resolves every citation below.

## Decision

- **Verdict:** GO — `confirmed = yes`
- **Decision date:** 2026-10-17
- **Decision owner:** U (tasks.md W10.4 — the M5 go/no-go call)
- **Evidence pack:** `docs/audits/w104-gonogo-evidence-pack-2026-10-17.md`
- **Stop-the-line check:** every DoD §6 item below carries evidence
  (the no-go trigger is a DoD item WITHOUT evidence — none); residual
  work is recorded as release-execution conditions with owners, never
  silently dropped.

## DoD §6 ledger

| key | criterion | owner | confirmed | date | evidence |
|-----|-----------|-------|-----------|------|---------|
| dod-1 | All 8 round-1 P0s + 6 round-2 BLOCKERs closed with evidence in tasks.md | D | yes | 2026-10-17 | `openspec/changes/oss-release-remediation/tasks.md` — W0.1/W0.6/W1.5/W7.1-W7.5/W9.1/W9.2 entries per P0; W1/W2/W4 workstream entries per BLOCKER; the W10.4 checkbox promotions (W1.6/W1.8/W1.10/W1.12/W1.15/W1.20/W2.2) with lane pointers |
| dod-2 | All 37 HIGHs fixed or explicitly deferred with owner + ticket (max 0 deferred for security HIGHs) | D | yes | 2026-10-17 | `docs/audits/round2-deep-review-findings-2026-10-05.md` (the 37 = S1-S13, D1-D8, P1-P7, I1-I4, F1-F5) → `openspec/changes/oss-release-remediation/design.md` §7 mapping → executed workstreams; 0 security HIGHs deferred; the §8 deferral list is non-security and gets its tickets at W10.5 (condition `w105-tickets`) |
| dod-3 | Full CI green on an armed branch; fork PR CI green; public mirror CI green; merge-back drill passed | D | yes | 2026-10-17 | W10.1 full-run attribution (quality-gates 53/66, lint pins 294/298 — every failure attributed to an owned lane); `scripts/tests/test_w101_gate_harness_coverage.py` 4/4; W7.3 live public-CI 7/8 jobs green (the 8th blocked ONLY by condition `estate-migration-surgery`); fork CI green by construction (GATE-56 pins) with the live PR half blocked on a second GitHub account; merge-back drill W0.4b. The attributed red gates are re-checked before release execution (condition `sibling-red-gates`) |
| dod-4 | History clean (secret-scan on a dry-run push); license present; first release tagged with a real CHANGELOG | D | yes | 2026-10-17 | W0.4 rewrite prepared + verified on a fresh clone of the rewritten mirror; the dry-run push passes gitleaks (W0.4b); license + NOTICE + GATE-48 green (W0.1); tag `v0.1.0` (2026-10-14) + `CHANGELOG.md` maintained by release-please (W9.1). The force-push itself is HELD by this go decision by design (condition `w04-force-push`) |
| dod-5 | `make quickstart` → running core from a clean checkout in ≤30 min, verified by a stranger-path run | D | yes | 2026-10-17 | W9.2 clean-clone stranger-path run — images built, postgres/minio/redis/traefik/frontend healthy, four stranger-path defects root-fixed; the full api boot is blocked ONLY by condition `estate-migration-surgery`; the README quickstart claims are machine-pinned (W12.8) |
| dod-6 | U.8 go/no-go ledger `confirmed = yes` with the M0-M5 evidence pack | U | yes | 2026-10-17 | this file + `docs/audits/w104-gonogo-evidence-pack-2026-10-17.md` (the pack carries one section per DoD item, every citation machine-resolved) |
| dod-7 | Every new enforcement point emits its audit event and registers error codes; every new gate falsifiability-registered | D | yes | 2026-10-17 | W1.19 enforcement-point sweep (emission gaps closed + inventory); `docs/api/error-codes.md` catalogue gate; W11.10/W12.x gates wired blocking; falsifiability harness audit 61/61 (W10.1) incl. the new `gate-w104-gonogo-pack-veracity` entry |
| dod-8 | Security verification complete: ASVS L2 evidence pack green; register classes named-test-or-absence; tooling gates blocking; DAST delta zero-new-highs; AI threat model; pentest decision recorded | D | yes | 2026-10-17 | `docs/audits/asvs-2026/asvs-evidence-pack.md` + its veracity pin `scripts/tests/test_w1113_asvs_evidence_pack_veracity.py` 8/8; W11.1-W11.12 evidence (`docs/audits/w1111-dast-2026-10-16.md`, `docs/audits/w1112-ai-surface-threat-model-2026-10-16.md`, `docs/security/threat-models/`); D9 recorded (decisions.md: recommendation yes, decision point W11.14 — condition `w1114-pentest`) |
| dod-9 | Code quality & hygiene complete: W12 gates blocking + falsifiability-registered; stub inventory triaged; doc-claim veracity; naming/deprecation consistency | D | yes | 2026-10-17 | W12.1-W12.10 entries in `openspec/changes/oss-release-remediation/tasks.md` (GATE-55/57/58/59/61 blocking + harness-registered; `docs/audits/doc-claim-veracity-2026-10-15.md`; `docs/audits/stub-inventory-2026.md`) |

## Release-execution conditions (recorded reasons — the stop-the-line)

The go decision authorizes the irreversible release steps. These
conditions are PREPARED and VERIFIED (evidence cited); their EXECUTION
is sequenced by design (post-go / U-gated), owned by in-flight lanes,
or ops-scheduled. Every one is re-checked before the release executes.

| key | condition | owner | reason/evidence |
|-----|-----------|-------|----------------|
| w04-force-push | History-rewrite force-push of origin/main | U | Prepared + verified on a scratch mirror (W0.4: fresh-clone verifier green, fsck clean); HELD by this go decision by design (S7/S5). Executes only after the go. |
| w05-rotations | The 6 U console-step credential rotations (GCP/AWS/Azure/Databricks/Snowflake/Stripe) | U | GATE-51 stays honestly RED until U rotates; tooling + pre-evidence recorded (W0.5); old-creds-dead verification scripts ready. Post-go execution. |
| g4-trivyignore-triage | `.trivyignore` backlog triage + `audit_pinned_cves --strict` back to green (the G4 second half) | D (W11.10 lane) | **CLOSED 2026-10-18** — P0-2 wave 1 triaged the 198 overdue entries with OSV evidence and re-dated `.trivyignore` (`audit_pinned_cves --strict` exit 0; pin `scripts/tests/test_cve_triage_waves.py` 6/6 CI-wired; evidence `docs/audits/cve-triage-2026/`), and P0-3 wired the regrowth blocker (`.github/workflows/cve-triage-weekly.yml` weekly strict gate + tracking issue, the GOVERNANCE cadence, `docs/runbooks/cve-triage.md`, pin `scripts/tests/test_cve_triage_process.py` 5/5 CI-wired). The P0-1 dependency bumps landed the same day (see the wave ledger). |
| sibling-red-gates | GATE-05/06/07/54/58/59 + the ZAP AUDITOR baseline re-run green | D (W11.3/W12.5/W12.10/W11.11 lanes) | W10.1 attribution: in-flight sibling-lane state at the time of the run — re-run after those lanes land; every failure attributed, none silent. **GATE-54 resolved 2026-10-18 (P0-4): the IDOR synthesis estate import now rides the registry-inversion seam — checker exit 0, drill BITES, pin 6/6 CI-wired. GATE-05 resolved 2026-10-18 (P0-5): all 21 unannotated sleeps annotated with verified per-site reasons — checker exit 0 (0 unannotated), pin suite 10/10.** |
| estate-migration-surgery | `warehouses.0007` estate-FK split (dual-path history, U.7 rehearsal discipline) | D (W4.6 lane) | Blocks public-tree core-tests 8/8 and the full quickstart api boot; handed W7.3 → W4.6/W7.4, unexecuted (deliberately not performed ad hoc); ticket assigned at W10.5. |
| soak-72h | Remaining ≥72h armed staging soak window | O | The detached driver started 2026-10-17 04:25Z (preflight PASS; the fail-closed signature observed live); the remaining window is the ops-scheduled run (W1.20/W10.2). |
| w1114-pentest | D9 third-party pentest decision (and scoped engagement if approved) | U | SCHEDULED at W11.14 (decisions.md D9); recommendation yes recorded; findings fold into the ASVS pack before the M5 go. |
| w105-tickets | design.md §8 deferral items get `TICKET=` IDs triaged to follow-up changes | D | EXECUTED 2026-10-18 (W10.5) — every §8 item carries a unique `TICKET=W105-*` ID and is routed in `openspec/changes/track-oss-deferred-debt/tasks.md` (the W10.2-carried findings ticketed in the same backlog); enforced by `scripts/tests/test_w105_deferred_debt_triage.py` (CI lint pin list, falsifiability-registered `gate-w105-deferred-debt-triage`). None of it security-blocking. |

## Machine results (filled by the gate run)

| check | verdict | evidence |
|-------|---------|----------|
| ledger parses + all dod-* rows confirmed | PASS | `scripts/tests/test_w104_gonogo_pack_veracity.py` (CI lint pin list) |
| every pack/ledger citation resolves | PASS | same pin — test + line + artifact citations on the current tree |
| W11.13 ASVS pack veracity | PASS | `scripts/tests/test_w1113_asvs_evidence_pack_veracity.py` 8/8 |
| W10.1 harness-coverage registry | PASS | `scripts/tests/test_w101_gate_harness_coverage.py` 4/4 |
| falsifiability — the new gate bites | PASS | `gate-w104-gonogo-pack-veracity` flip-go-decision-to-no weakening (harness) |
| W10.5 deferred-debt triage | PASS | `scripts/tests/test_w105_deferred_debt_triage.py` (CI lint pin list) + `gate-w105-deferred-debt-triage` weakening BITES |
