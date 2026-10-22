# W10.4 U.8 Go/No-Go Evidence Pack (M0–M5) — 2026-10-17

The M5 go/no-go evidence: one section per DoD §6 item
(`openspec/changes/oss-release-remediation/design.md` §6), every
citation machine-resolved by `scripts/tests/test_w104_gonogo_pack_veracity.py`
(CI lint pin list), the W11.13 ASVS pack folded in as the security half
(DoD 8). The decision record is `docs/operations/oss-go-nogo-ledger.md`
(the machine half is the pin; that file is the human half — U's
sign-off, 2026-10-17).

**Stop-the-line rule honored:** no DoD item lacks evidence (the no-go
trigger). Residual work is recorded below under Release-execution
conditions with owners — nothing silently dropped.

---

## DoD 1 — All 8 round-1 P0s + 6 round-2 BLOCKERs closed with evidence in tasks.md

The round-1 P0 list (`docs/audits/oss-maturity-assessment-2026-10-05.md`)
and the round-2 BLOCKER list
(`docs/audits/round2-deep-review-findings-2026-10-05.md`), mapped to
executed workstreams in `openspec/changes/oss-release-remediation/tasks.md`:

| P0 | Closure |
|---|---|
| No OSI license | W0.1 [x] — Apache-2.0 core + MIT SDKs, GATE-48 green, legal sign-off recorded |
| Live cloud credentials in git history + 17 tags | W0.4 prepared + verified on a scratch mirror (verifier green on a fresh clone); the force-push is HELD by this go decision by design — condition `w04-force-push` |
| Staging credentials in tracked tarballs | W0.6 [x] — S3-archived + deleted, GATE-52 green |
| Unauthenticated OIDC SSO account takeover | W1.5 [x] — JWKS-verified ID tokens, adversarial matrix green |
| Zero CI runs since 2025-04-25 | W7.4 [x] — Actions re-armed, first-run triage loop, every RED job fixed-or-triaged |
| TLS private keys tracked | W0.7 [x] — ssl-setup regenerated, 6 fingerprints differ, staging boots hardened |
| Zero releases | W9.1 [x] — single-source VERSION + release-please + `v0.1.0` tagged (2026-10-14) with `CHANGELOG.md` |
| Broken stranger bootstrap | W9.2 [x] — clean-clone quickstart driven end-to-end, four stranger-path defects root-fixed |

The 6 round-2 BLOCKERs (anonymous cross-tenant enrollment, API-key scope
escalation, self-defeating event bus, pre-commit event publishing, dead
contract-search reindex, tenant hard-delete blocked forever) are closed
by the W1/W4 workstreams ([x] with evidence — W1.1/W1.3, W4.1/W4.2/W4.3).

The W10.4 checkbox promotions (tasks.md): W1.6 (impersonation backend —
promotion corrected by the round-3 re-audit, see the W10.3 section
below), W1.8 (stop-the-line sweep:
`docs/audits/client-tenant-id-stop-the-line-2026-10-08.md` — 15
allowlisted sites with written reasons, 0 open trust gaps), W1.10
(refresh grace — executed by W11.2,
`hub/apps/auth/tests/test_refresh_grace_w110.py:94`), W1.12 (staging-key
presign replay — executed by W11.8,
`hub/apps/files/tests/test_presigned_replay_w112.py:78`), W1.15
(SPARQL on all three virtual-dataset paths,
`hub/apps/virtualization/tests/test_sparql_validation_w115.py:87`),
W1.20 (RLS arming — middleware + the live W10.2 soak), W2.2 (plan
change — the live W10.2 Stripe drill). W1.9 (G4) stays split-honest:
pip-audit blocking GREEN, the `.trivyignore`/pinned-CVE half RED —
condition `g4-trivyignore-triage`.

---

## DoD 2 — All 37 HIGHs fixed or explicitly deferred (0 security HIGHs deferred)

The 37 = S1–S13 + D1–D8 + P1–P7 + I1–I4 + F1–F5
(`docs/audits/round2-deep-review-findings-2026-10-05.md` §3), mapped
finding-by-finding to workstreams in
`openspec/changes/oss-release-remediation/design.md` §7 — every
workstream executed ([x] with named-pin evidence in
`openspec/changes/oss-release-remediation/tasks.md`). Security HIGHs
deferred: **zero**. The §8 deferral list is explicitly non-security
(monolith decomposition, i18n, PWA story, SDK pagination, …) and gets
its `TICKET=` IDs at W10.5 — condition `w105-tickets`. The round-3
re-audit (W10.3) re-checked the highest-risk classes of this register
and root-fixed what it found — `docs/audits/w103-independent-reaudit-2026-10-17.md`.

---

## DoD 3 — Full CI green on an armed branch; fork PR CI green; public mirror CI green; merge-back drill passed

- **Armed-branch CI:** the W10.1 full run — quality-gates 53/66 and the
  CI lint pin list 294/298, **every failure attributed to an owned lane**
  (the attribution ledger is in the W10.1 block of
  `openspec/changes/oss-release-remediation/tasks.md`); the harness
  coverage pin `scripts/tests/test_w101_gate_harness_coverage.py` keeps
  the convention-11 registry honest (harness audit 61/61 falsifiable).
  The attributed red gates are re-checked before the release executes —
  condition `sibling-red-gates`.
- **Fork PR CI:** green by construction — GATE-56's 18 fork-guard pins
  (every non-GITHUB_TOKEN secret behind a fork guard; the one
  allowlisted triple documented); the live fork-PR half needs a second
  GitHub account (GitHub forbids forking your own repo) and the recipe
  is ready (`scripts/fork_smoke_pr.sh`). W7.3 evidence.
- **Public mirror CI:** the re-synced public repo's own CI — 7/8 jobs
  green (DCO, GATE-29+gitleaks, lint, docs, CodeQL, boot smoke); the
  8th (core-tests) is blocked ONLY by the W4.6 estate-boundary migration
  surgery — condition `estate-migration-surgery`. W7.3 evidence.
- **Merge-back drill:** W0.4b [x] — the synthetic DCO'd community PR
  travels public → private → publish through the real
  `scripts/pull_public_pr.sh`/`scripts/publish_public.sh` chain.

---

## DoD 4 — History clean (secret-scan on a dry-run push); license present; first release tagged with a real CHANGELOG

- W0.4 rewrite executed + verified on a scratch mirror (the verifier's
  fresh-clone run: `git log -S` clean on all rotated-secret fragments,
  `git fsck` clean) —
  `openspec/changes/oss-release-remediation/history-rewrite-2026-10-06.md`.
- The dry-run publish passes gitleaks (W0.4b: `SKIP_PUSH=1
  scripts/publish_public.sh` exit 0 — the publish-tree scan caught 2
  real blockers in its own fixtures and fixed them).
- License: W0.1 [x] — `LICENSE.txt` (Apache-2.0, verbatim-verified),
  `NOTICE.md`, SDK/CLI MIT headers, GATE-48 green (25/25 pins), legal
  sign-off recorded.
- Release: `v0.1.0` tagged 2026-10-14 with a real
  `CHANGELOG.md` (release-please-maintained). The force-push itself is
  the post-go step — condition `w04-force-push`.

---

## DoD 5 — `make quickstart` → running core from a clean checkout in ≤30 min (stranger-path run)

W9.2 drove `make quickstart` from a fresh clone for real: images built,
postgres/minio/redis×4/traefik/frontend healthy, and the run
root-fixed FOUR stranger-path defects (the `frontend/scripts/sync-shared.sh`
build-context fix, the missing HUB_WORKER_API_KEY, the stale
container-name collision, the traefik port collision). The full api
boot is blocked ONLY by the W4.6 estate migration surgery — condition
`estate-migration-surgery`. The quickstart contract (`README.md` +
`docker-compose.yml`) is machine-pinned by the W12.8 veracity suite
(`docs/audits/doc-claim-veracity-2026-10-15.md`).

---

## DoD 6 — U.8 go/no-go ledger `confirmed = yes` with the M0–M5 evidence pack

`docs/operations/oss-go-nogo-ledger.md` records the GO decision
(`confirmed = yes`, U sign-off 2026-10-17) with one confirmed row per
DoD item and the conditions table below. This pack
(`docs/audits/w104-gonogo-evidence-pack-2026-10-17.md`) is its reason
record; `scripts/tests/test_w104_gonogo_pack_veracity.py` enforces both
files (rows, dates, owners, citations) in the CI lint job. The ledger
follows the beta go/no-go precedent
(`docs/operations/beta-go-nogo-ledger.md`): machine-parseable sign-off
rows — the gate is the machine half of the decision, the ledger is the
human half.

---

## DoD 7 — Every new enforcement point emits its audit event and registers error codes; every new gate falsifiability-registered (conventions 8 + 11)

- The W1.19 enforcement-point sweep closed the emission gaps and left an
  itemized inventory (per-point status recorded in
  `openspec/changes/oss-release-remediation/tasks.md`).
- Error codes: every new code this program introduced is catalogued in
  `docs/api/error-codes.md` (incl. the W10.3 additions
  `IMPERSONATION_SESSION_ENDED`, `IMPERSONATION_TENANT_SWITCH_BLOCKED`,
  `FILE_CONTENT_VALIDATION_UNAVAILABLE` — the per-code fixes recorded in
  `docs/audits/w103-independent-reaudit-2026-10-17.md`).
- Falsifiability: the harness audit is 61/61 (W10.1), and the new
  `gate-w104-gonogo-pack-veracity` entry (flip-go-decision-to-no
  weakening) is registered + drill-proven.

---

## DoD 8 — Security verification complete (ASVS L2 pack, register classes, tooling gates, DAST, AI threat model, pentest decision)

- **ASVS evidence pack:** `docs/audits/asvs-2026/asvs-evidence-pack.md`
  — all fourteen chapters V1–V14, every chapter declares Level ≥2 with
  citations; the acceptance criterion is machine-enforced by
  `scripts/tests/test_w1113_asvs_evidence_pack_veracity.py` (8/8 — every
  citation resolves, ≥3 citations per chapter, the pack cites all its
  W11.x veracity pins).
- **Register classes:** W11.1–W11.9 (threat-model one-pagers +
  adversarial matrices + property suites —
  `docs/security/threat-models/stride-auth-tenant-w1.md`,
  `docs/security/threat-models/stride-money-w2.md`,
  `docs/audits/w1111-dast-2026-10-16.md`,
  `docs/audits/w1112-ai-surface-threat-model-2026-10-16.md`); the
  W10.3 round-3 re-audit re-checked the highest-risk classes
  independently and root-fixed its findings —
  `docs/audits/w103-independent-reaudit-2026-10-17.md`.
- **Tooling gates blocking:** W11.10 — bandit ratchet, semgrep local
  rules, pip-audit/npm-audit, trivy, gitleaks, each planted-violation
  drill-proven.
- **DAST delta zero-new-highs:** W11.11 — GATE-64 + per-role
  authenticated ZAP scans + committed baselines under
  `docs/security/zap/` (the first plan-driven run's real SQLi-class
  finding root-fixed; baselines promoted from the fixed tree).
- **AI-surface threat model:** W11.12 recorded (private layer).
- **Pentest decision recorded:** decisions.md D9 — recommendation yes,
  decision point W11.14 — condition `w1114-pentest`.

---

## DoD 9 — Code quality & hygiene complete (W12)

W12.1–W12.10 all [x] in `openspec/changes/oss-release-remediation/tasks.md`:
shipped-tree litter removed + GATE-55 blocking; dead-code (GATE-57),
orphan-script (GATE-59), exception-swallowing, `# noqa` (GATE-58), and
version-single-source gates blocking + falsifiability-registered; stub
inventory triaged (`docs/audits/stub-inventory-2026.md`); doc-claim
veracity landed (`docs/audits/doc-claim-veracity-2026-10-15.md`);
naming/deprecation consistency enforced (W12.10).

---

## W10.3 — the round-3 independent re-audit (convention 13)

The independent second-pass agent reviewed the ten §1.1-register classes
on the W1/W2 security surfaces against the CURRENT tree (2026-10-17).
Verdicts: 5 PASS, 4 GAP, 1 NOT-COVERED (pipeline crash-recovery — the
W3 lane's own evidence stands). Findings F1–F11 triaged the same day:
**F1 (BLOCKER — the impersonation escape guards existed as pins only,
zero implementation), F1b (the strawberry GraphQL path ran NO DRF auth
— the W11.2 matrix row 2.11 was a false PASS), F10 (the W1.15 SPARQL
seam was lost in a later refactor — 8/8 pins RED), and every other
MEDIUM/LOW root-fixed with RED-first pins** (F2 envelope-guard
ordering, F3 billing refund idempotency key, F4 webhook refund row
lock, F5 ingestion magic-byte gate + fail-closed read + multipart
bounds, F6 the `str(exc)` view sites, F7 the MOVE/COPY/ADD keyword gap,
F8 the constant-time comparison, F11 the fail-open pin rewritten);
F9's two items recorded as deliberate postures. Full record + per-
finding fix and pin citations:
`docs/audits/w103-independent-reaudit-2026-10-17.md`.

**Verification battery (session-private pg_dump clone of 313full,
host-side, 2026-10-17/18):** `test_impersonation_w16.py` **7/7**,
`test_graphql_auth.py` **9/9** (8/8 pre-fix RED incl. the valid-JWT
control), `test_sparql_validation_w115.py` **13/13** (8/8 pre-fix RED),
`test_w38_catalog_records.py` **9/9**, `test_magic_bytes.py` **27/27**,
`WorkerKeyComparisonPin` **1/1**, `BillingRefundIdempotencyPinTest`
**3/3**, `ChunkUploadInitSerializerTest` **4/4**,
`test_w117_refund_race.py` **3/3** (the two W11.7 races + the new
`WebhookRefundHandlerRaceTest` — the race suite's documented env: the
wire-stub key + host redis URLs),
`TestExceptionHandlerNoLeak` **6/6**. The sibling-lane
`TestErrorResponseContract` shape drift (4 tests, flat-vs-nested
envelope) is attributed, not this lane's change. New pin anchors:
`hub/apps/auth/tests/test_impersonation_w16.py:115`,
`hub/apps/api/tests/test_error_response_contract.py:115`,
`hub/apps/billing/tests/test_services.py:772`,
`hub/apps/marketplace/tests/test_w117_refund_race.py:271`,
`hub/apps/scheduled_ingestion/tests/test_w38_catalog_records.py:117`,
`hub/apps/files/tests/test_magic_bytes.py:139`,
`hub/apps/files/tests/test_serializers.py:278`,
`hub/apps/virtualization/tests/test_sparql_validation_w115.py:119`,
`hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py:379`.

---

## Release-execution conditions (recorded reasons — the stop-the-line)

Every one is PREPARED and VERIFIED (evidence cited in the ledger);
execution is sequenced by design (post-go / U-gated), owned by
in-flight lanes, or ops-scheduled — re-checked before the release
executes. Keys (one-to-one with `docs/operations/oss-go-nogo-ledger.md`):

| key | condition | owner | state |
|-----|-----------|-------|-------|
| w04-force-push | history-rewrite force-push of origin/main | U | prepared + verified (fresh-clone verifier green); HELD by this go decision by design (S7/S5) |
| w05-rotations | the 6 U console-step credential rotations | U | GATE-51 honestly RED until U rotates; tooling + pre-evidence ready (W0.5) |
| g4-trivyignore-triage | `.trivyignore` backlog + `audit_pinned_cves --strict` green (G4 second half) | D (W11.10 lane) | measured 2026-10-17: 198 OVERDUE rows, exit 1; the pip-audit half is GREEN |
| sibling-red-gates | GATE-05/06/07/54/58/59 + ZAP AUDITOR baseline re-run green | D (W11.3/W12.5/W12.10/W11.11 lanes) | W10.1 attribution — in-flight lane state, every failure attributed |
| estate-migration-surgery | `warehouses.0007` estate-FK split (dual-path history, U.7 rehearsal) | D (W4.6 lane) | blocks public-tree core-tests 8/8 + full quickstart boot; handed W7.3 → W4.6/W7.4, unexecuted; ticket at W10.5 |
| soak-72h | remaining ≥72h armed staging soak window | O | detached driver started 2026-10-17 04:25Z (preflight PASS, fail-closed signature observed live) — `docs/audits/w102-staging-soak-2026-10-17.md` |
| w1114-pentest | D9 pentest decision (+ scoped engagement if approved) | U | SCHEDULED at W11.14; recommendation yes recorded |
| w105-tickets | §8 deferral items get `TICKET=` IDs | D | post-go bookkeeping (W10.5) |

## Honesty section — what this pack does NOT claim

- ASVS **Level 3** is not claimed anywhere (the pack declares L2; V4
  notes its L3-scale breadth). V9 TLS termination is infra; V10.2
  vendor cadence is ops (per the W11.13 honesty notes).
- "Full CI green" as of this date is NOT claimed — the W10.1 run's
  failures are attributed above and re-checked before release execution
  (condition `sibling-red-gates`).
- The 72h soak is not claimed complete — the window is ops-scheduled
  (condition `soak-72h`); what IS proven is the preflight + the live
  fail-closed signature.
- The third-party pentest is not claimed executed — the decision point
  is W11.14 (condition `w1114-pentest`).
- Class 10 of the independent pass (pipeline crash-recovery) is not
  claimed re-audited — recorded NOT-COVERED; the W3 lane's own evidence
  stands.
