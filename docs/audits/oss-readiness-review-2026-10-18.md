# OSS Readiness Critical Review — 2026-10-18

Independent readiness assessment of the application for open-sourcing,
across frontend, backend, infrastructure, tests, security, ops, legal,
community and documentation. Every finding below is either **measured
today** (command run against the current tree / remotes) or **cited**
from a committed, pin-verified record (ledger, audit doc, matrix).

## Executive verdict

**NOT READY to promote the public repository as open source today.**

The engineering is largely complete and of high quality — the design,
enforcement machinery, and evidence discipline are exceptional. But
open-source readiness is not decided by what is *prepared*; it is
decided by what is *executed on the public surface*. The go/no-go
ledger's release-execution conditions are exactly that list, and today's
measurements show the public surface is still unsafe:

1. **The public repository's git history still contains committed
   credentials and staging backups.** (Measured today — see H-1.)
2. **The credentials in that history are not yet rotated** — GATE-51
   measured 6 surfaces PENDING-U today.
3. **The vulnerability posture is red** — 198 overdue `.trivyignore`
   entries (+3 `requirements.txt` pins outside this gate's scope) and
   reviews + 5 untriaged pip-audit advisories, measured today.
4. **The estate-migration surgery that blocks the public-tree CI and
   the full quickstart boot is recorded unexecuted** (the migration now
   exists in the tree, but the re-verification never ran).
5. **No release tag is visible on either remote** — `v0.1.0` exists
   only locally and points into the pre-rewrite lineage.

None of this is hidden — every item below is a recorded condition with
an owner. This review is the honest inventory of the remaining distance.

---

## 1. Security & secret hygiene

| # | Finding | Status | Evidence |
|---|---|---|---|
| H-1 | **Secret-laden history is LIVE on both remotes.** Commit `f3f84bc51` (an ancestor of BOTH `origin/main` and `public/main`) added `.env.staging`, `.env.test` (with populated credential values: postgres, minio, fuseki, AWS keys), and 12+ `backups/staging_*.tar.gz` config archives. The round-1 audit also recorded TLS keys in historical HEADs. | **BLOCKER** | Measured today: `git log --diff-filter=A` against `5555fbc24a` (origin/main) and `ad776193a` (public/main). The W0.4 rewrite (scratch mirror, dry-run gitleaks clean) is PREPARED but the force-push is HELD — ledger condition `w04-force-push`. |
| H-2 | **Credential rotations unexecuted.** The rotated-copies-elsewhere assumption only holds after U rotates; the committed values are still live until then. | **BLOCKER** | Measured today: `check_credential_rotation.py` FAILED — 6 PENDING-U surfaces incl. databricks-pat, snowflake-pat, stripe-test-key. Ledger condition `w05-rotations` (owner U). |
| H-3 | **Dependency-vulnerability gates red.** | HIGH → **RESOLVED (P0-1 + P0-2 wave 1 + P0-3 executed 2026-10-18)** | Measured today: `audit_pinned_cves.py --strict` — 198 OVERDUE `.trivyignore` entries (the earlier "396" was a double-count of the report's table rows + stderr lines — corrected); `check_dependency_vulns.py` — 5 UNTRIAGED (pyjwt PYSEC-2026-4152/4183, strawberry-graphql PYSEC-2026-4302/4303, weasyprint PYSEC-2026-4311). Ledger condition `g4-trivyignore-triage` (owner W11.10 lane). **Wave 1 (close-oss-release-conditions P0-2) landed the same day:** 198 entries bucketed with OSV evidence (110 fix-released / 6 fix-pending / 82 not-applicable), `.trivyignore` re-dated, strict gate green, pin `scripts/tests/test_cve_triage_waves.py` 6/6 CI-wired — `docs/audits/cve-triage-2026/`. **P0-1 (upgrade lane) landed the same day:** the pin bumps shipped in both requirement files (pyjwt 2.15.0, strawberry-graphql 0.327.2, WeasyPrint 70.0, requests 2.33.0, cryptography 46.0.7, databricks-sql-connector ≥4.0,<5.0) — `check_dependency_vulns.py` exit 0, RED-first pin `scripts/tests/test_p01_vuln_upgrade_pins.py` 5/5, compat battery green (graphql ×3 stacks 329/329 incl. F3 + ropa pdf; semantic / Django 6 UAT / auth green after the battery's root-fixes: the graphene DRF-auth gap via `hub/apps/auth/graphql_drf_auth.py` (graphene auth pin 7/7), the silent-audit-loss class (SSRF-block + worker-lifecycle `tenant_id=` kwarg + structlog `event=` collision, utility-level fix + pin 4/4), and the W102 pre-tenant-write enforcement regressions (lockout writes alias-routed, U.6 role-grant mirror, 19/19)). **P0-3 landed the same day:** the weekly strict cron, the monthly triage cadence and `docs/runbooks/cve-triage.md`. Full record: the W1.9 rows in both change tasks. |
| H-4 | Dev-only TLS private keys committed (`infrastructure/postgres/certs/{ca,pgbouncer,postgres}.key`). | LOW (advisory) | Measured today. Regenerable local-dev fixtures, but the committed-private-key shape should be documented as dev-only or generated at first boot. |
| H-5 | **Security posture itself is strong and honest.** ASVS v4.0 pack declares Level 2 (not L3) with a machine-enforced honesty section; the W10.3 independent re-audit's 4 GAPs + 1 BLOCKER were all root-fixed the same day with RED-first pins (impersonation escape, GraphQL auth false-pass, 5xx leak classes, refund race, magic-byte bypass). W11.2/W11.3/W11.7/W11.8/W11.9 matrices, ZAP delta gate (GATE-64), AI threat model + prompt-injection red team, crypto sweep all shipped with pins. | STRENGTH | Cited: `docs/audits/asvs-2026/asvs-evidence-pack.md` (+ pin 8/8), `docs/audits/w103-independent-reaudit-2026-10-17.md`. |
| H-6 | Third-party pentest undecided; SECURITY.md exists (PGP + SLA) but the private-advisories/CVE-process refresh is tied to the decision. | MEDIUM | Cited: decisions.md D9 (scheduled W11.14); tasks.md W11.14 unchecked. |

## 2. Public surface / release mechanics

| # | Finding | Status | Evidence |
|---|---|---|---|
| P-1 | Public mirror main (`ad776193a`, "sync: core subset @ 60ec6dd16") is on a scrubbed-but-**stale** lineage — months of work behind prepro01, structurally drifted (extra `.env.example`, `.cursor`, `.devcontainer`, `AGENTS.md`, `ARCHITECTURE.md` files). | HIGH | Measured today: fetched `public/main`; not an ancestor of prepro01; tree diff by inspection. |
| P-2 | No release tag published. `v0.1.0` is local-only and points into the pre-rewrite lineage; origin carries 0 tags; public carries 4 legacy tags (`v2026.08.14`…`v2026.10.14` + an archive tag). | HIGH | Measured today: `git ls-remote` both remotes; `git rev-parse v0.1.0`. |
| P-3 | Post-rewrite remote hygiene pending: dependabot PRs on the public repo, protected-branch settings, open PRs (S4 merge-back drill list). | MEDIUM | Cited: design.md §4 S4; public remote branch listing measured today. |
| P-4 | Public CI 7/8 — the 8th job blocked only by condition `estate-migration-surgery`; fork PR CI green by construction (GATE-56), live fork half pending a second GitHub account. | MEDIUM | Cited: ledger dod-3, W7.3 evidence. |
| P-5 | Version single-source verified: all seven surfaces agree on 0.1.0. | STRENGTH | Measured today: `check_release_versions.py --check` clean. |

## 3. Backend / architecture

| # | Finding | Status | Evidence |
|---|---|---|---|
| B-1 | **`estate-migration-surgery` (warehouses.0007 estate-FK split) recorded unexecuted** — blocks public-tree core-tests 8/8 and the full quickstart api boot. The migration file now EXISTS in the tree (landed with the 2026-10-18 commits) but the dual-path execution + the blocked verifications were never re-run. | HIGH (verification gap) | Measured today: `hub/apps/warehouses/migrations/0007_*.py` present; ledger condition + W10.4 pack still record it unexecuted. |
| B-2 | GATE-54 provider boundary: 1 remaining violation (`hub/apps/testing/idor_synthesis.py:199`). | LOW | Measured today. |
| B-3 | Deferred structure debt (all ticketed at W10.5): contracts monolith 215k LOC, GraphQL triple stack, settings.py 3.2k lines, 59 conftests, signal tenant_context lint, 101 unaudited management commands. None security-blocking. | TRACKED | Cited: design.md §8 + `openspec/changes/track-oss-deferred-debt/tasks.md`; W12.2 already deleted the legacy/dead-code mass (GATE-57 green). |
| B-4 | Tenant isolation, money integrity, injection, SSRF, upload abuse, webhook verification — all enforcement-point classes pinned with named tests after the W10.3 re-audit. | STRENGTH | Cited: W10.3 record + matrix docs. |
| B-5 | AI surface: agent/tool boundary absence machine-proven; but recorded open threats (dormant LLM path undocumented, predict endpoints bypass `run_inference`, cross-tenant predict ownership, marketplace agent contracts storing third-party keys verbatim). | TRACKED | Cited: tasks.md W11.12 OPEN-THREATS. |

## 4. Frontend / UX

| # | Finding | Status | Evidence |
|---|---|---|---|
| F-1 | `storybook-static` committed build output in the tree; `sw.js` PWA story undecided; `routes.tsx` 2.4k-line monolith; `glob` override in place. | TRACKED (deferred) | Cited: design.md §8 (tickets W105-FRONTEND-ROUTES-SPLIT / W105-PWA-STORY). |
| F-2 | i18n façade exists with 8 locale files (ar/de/en/es/fr/ja/pt) + coverage.json — completeness/retirement decision deferred. | TRACKED | Measured today: locales dir. |
| F-3 | E2E journey gaps: ODPS (5) + CPO (6) specs incomplete; DSAR persona unregistered — the persona aggregator coverage is incomplete for the ODPS/CPO personas. | TRACKED | Cited: design.md §8 (W105-E2E-PERSONA-COMPLETION). |
| F-4 | Substantial test surface: vitest suites with coverage ratchet, Playwright personas (13 fixture personas), a11y contract, strict-mode guards, e2e nightly + quarantine workflows. | STRENGTH | Cited: CI workflow inventory + memory-trapped E2E conventions. |

## 5. Tests / quality gates

| # | Finding | Status | Evidence |
|---|---|---|---|
| T-1 | GATE-40 skip/placeholder debt = **2813** unannotated sites (per-bucket ratchet holds, 0 expired). Large honest debt; the ratchet prevents growth but 2.8k placeholder-class sites are visible in a public repo. | MEDIUM | Measured today. |
| T-2 | GATE-05: the true debt was 21 unannotated sleeps across 11 files (the review's "1" was a truncated listing — corrected). **Resolved 2026-10-18 (P0-5): all 21 annotated with verified per-site reasons, checker exit 0, pin suite 10/10.** GATE-06/07 skip sites recorded at W10.1 in sibling files (current state unverified in this review). | LOW → CLOSED (GATE-05) | Measured (GATE-05) / cited (W10.1 attribution). |
| T-3 | 60+ gates falsifiability-registered; coverage pin enforces the registry; quality-gates battery last measured 53/66 with every failure attributed (ledger condition `sibling-red-gates` re-checks before release execution). | STRENGTH (re-verify pending) | Cited: W10.1 evidence; harness audit 61/61 at W10.1. |
| T-4 | Test-honesty machinery (no `assertTrue(True)`, stub inventory, mock/stub audit) shipped and wired. | STRENGTH | Cited: W12.7/W12.10. |

## 6. Ops / infra / data safety

| # | Finding | Status | Evidence |
|---|---|---|---|
| O-1 | Remaining ≥72h armed staging soak window still ops-scheduled (fail-closed signature already observed live during the postgres outage — the watch is for the full window). | TRACKED | Cited: ledger condition `soak-72h` (owner O); W10.2 ledger. |
| O-2 | W10.2-carried findings ticketed but open: compliance-run dispatch gap (Job rows PENDING, never enqueued — a real product bug), ASYNC listener staging liveness re-verification, redis-AOF runbook entry, compose-supervisor observation. | TRACKED | Cited: W10.2 ledger §4 + `track-oss-deferred-debt` carryover table. |
| O-3 | Real drill evidence committed: DR restore, exit-clause (tenant export/hard-delete), TLS rotation, k6 load, MinIO backup-integrity, Stripe test-mode (40 real events), crash drills D1–D4. | STRENGTH | Cited: `docs/operations/*/2026-10/` reports; W8.2/W10.2 evidence. |
| O-4 | Monitoring/alerting present (prometheus rules/alerts, dashboards), runbooks (privacy pack, oncall/escalation, fernet rotation), helm production config with RLS flags + kill switches. | STRENGTH | Measured today: tree inventory. |
| O-5 | Production restart policies fixed to `restart: always` (23 services) with the orchestrator-owns-restarts note recorded. | STRENGTH | Cited: W10.2 drills. |

## 7. Legal / community / docs

| # | Finding | Status | Evidence |
|---|---|---|---|
| L-1 | License shipped (Apache-2.0 core, MIT SDKs, LICENSE.txt/NOTICE.md, GATE-48 pinned) with U signature; **legal counsel countersign of the dual-license split still U-gated**. | MEDIUM | Cited: decisions.md D1 table. |
| L-2 | Community surface shipped and NOW COMMITTED: CODE_OF_CONDUCT, GOVERNANCE (maintenance model, cadence, support SLA), typed issue templates, CONTRIBUTING, SECURITY.md (PGP + disclosure SLAs). | STRENGTH | Measured today: files present in HEAD after the 2026-10-18 commit push. |
| L-3 | Doc traceability strong: 181 journeys / 146 use cases, critical-ID registry, marker-sync gates (GATE-26/27/28). | STRENGTH | Cited: docs + CLAUDE.md contract. |
| L-4 | Quickstart verified from a clean checkout (docker-only) — but the FULL api boot was blocked by `estate-migration-surgery`; the stranger-path claim covers the core stack only until B-1 closes. | MEDIUM | Cited: W9.2 evidence + ledger dod-5. |

---

## The flip checklist (what must happen before the public repo is promoted)

Ordered; each step has a ledger condition, owner and evidence contract:

1. **Execute the history rewrite** — force-push the W0.4-rewritten main to
   origin (condition `w04-force-push`), then re-sync the public mirror and
   coordinate re-clones (the S4 merge-back drill + dependabot/PR/
   protected-branch cleanup on the public remote). Until this runs, the
   public repo must not be advertised.
2. **U rotates the 6 remaining surfaces** (condition `w05-rotations`;
   GATE-51 red) — old credentials die before any public exposure.
3. **Triage the vulnerability backlog** — 198 `.trivyignore` entries + 3 pins + 5
   untriaged pip-audit advisories (condition `g4-trivyignore-triage`) —
   **EXECUTED 2026-10-18** (P0-2 wave 1 + P0-1 pin bumps + P0-3
   regrowth blocker, all with RED-first pins; `check_dependency_vulns.py`
   exit 0 and `audit_pinned_cves.py --strict` exit 0).
4. **Close `estate-migration-surgery`** — execute the rehearsed 0007
   split, then re-verify public-tree core-tests 8/8 and the full
   quickstart api boot (also lifts P-4 and L-4).
5. **Re-run the attributed red gates** (condition `sibling-red-gates`:
   GATE-05/06/07/54/58/59 + ZAP AUDITOR baseline) and confirm the
   quality-gates battery.
6. **Finish the soak** (condition `soak-72h`, owner O) and record the
   classification.
7. **Decide D9 pentest at W11.14** + refresh SECURITY.md (private
   advisories + CVE process) + obtain the L-1 legal countersign.
8. **Publish a release tag on the clean history** (P-2: v0.1.0 is
   local-only today) and re-verify the tag↔main anchor after the
   rewrite.
9. **Deferred debt stays deferred** — the 13 §8 tickets + 7 carryovers
   are ticketed and routed (W10.5, done 2026-10-18); they are explicitly
   not release-blocking but should be visible in the public roadmap.

## Honesty notes (what this review did NOT verify)

- GATE-06/07 current state, the full quality-gates battery, the full
  falsifiability audit, the full test suites, and the quickstart boot
  were not re-run end-to-end in this review (they are cited from
  W10.1/W10.4 records with their recorded red states).
- The pinned-CVE rows (198, corrected from the miscounted 396) were
  counted, then triaged the same day by wave 1 (P0-2) — see the H-3
  status update above.
- "Public mirror stale" is a lineage/tree observation; the exact parity
  delta vs prepro01 was not diffed file-by-file.
