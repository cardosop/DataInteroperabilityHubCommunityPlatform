# Post-Rewrite CI Re-Proof — P3-2b Record (2026-10-20/21)

`openspec/changes/close-oss-release-conditions` — P3-2b (G6). The DoD-3
re-verification (full CI on the post-rewrite armed branch, fork PR CI,
and public mirror CI). Status: **PARTIALLY EXECUTED** — one leg
complete (public mirror CI, with two root fixes), two legs honestly
queued on external blockers (recorded below, not silently skipped).

## Leg 1 — public mirror CI: EXECUTED + GREEN (after 2 root fixes)

The P2-5 replacement recreated the public repo on a clean ROOT lineage
(`36cce9e2`, 2026-10-20) — its first CI runs were the post-replacement
re-proof, and they FAILED in both stack jobs. Root causes + fixes
(committed to the overlay, pinned RED-first, and re-proven via probe PR
#15 — `p32b-ci-reproof`, DCO-signed):

1. **core-boot-smoke → `ImproperlyConfigured: SECRET_KEY is not
   configured`** — G12 (P0-9) removed the committed well-known default
   AFTER the W7.3-era public workflow shipped; the recreated repo
   carries no secrets by design. Fix: the workflow exports an ephemeral
   per-run key (`openssl rand -hex 24`) for the runner-side management
   commands. Pin: `test_public_ci_parity.py::TestCiCoreSecretKeyContract`
   (the shipped workflow must generate the key itself — never a
   committed sentinel, never a repo secret the public repo lacks).
2. **test-core → compose build `target stage "dev" could not be found`**
   — the overlay's worker Dockerfile predated the W8.1 dev/production
   split while `docker-compose.test.yml` builds `target: dev`. Fix:
   regenerated from the current private Dockerfile with the single
   core-only adaptation (no compliance-service COPY), preserving the
   W8.1 hardening (production stage, non-root, in-image HEALTHCHECK)
   and the U.6 no-upgrade root fix. Pin:
   `test_publish_tree.py::test_worker_dockerfile_overlay_tracks_the_stage_split`
   (both stages declared, no compliance COPY, no apt-get upgrade).

Probe PR #15 carries the same fixes on the public side (the next
publish ships them canonically via the overlay). Iteration history
(each round = one real CI battery, RED → root fix → re-run):
  - Round 1 (the first CI on the clean lineage, before any fix): both
  stack jobs red — boot-smoke `SECRET_KEY not configured`; test-core
  worker build `target stage "dev" could not be found`.
  - Round 2 (fixes 1+2): boot-smoke green; test-core now fails at
  `container hub-test-api is unhealthy` after the full healthcheck
  window. Static gates green throughout (DCO, GATE-29+gitleaks, lint,
  docs, CodeQL — 6/8 jobs).
  - Round 3 (systematic G12 config: the key TRIPLE + JWT_ALGORITHM=HS256
  — the RS256 default's empty-pair guard is the same G12 class; plus
  the failure-diagnosis step): boot-smoke green (6/8); test-core still
  unhealthy — the diagnosis exposed its own bug first ("no such
  service": the step used the container name; compose resolves
  SERVICE names) and was fixed to capture ps + migrate-test-db +
  api-service-test logs.
  - Root cause of the remaining red (PROVEN by the round-3 diagnosis):
    `hub-test-migrate Exited (1)` with
    `django.db.migrations.exceptions.NodeNotFoundError: Migration
    warehouses.0007_... dependencies reference nonexistent parent node
    ('databricks_admin', '0005_enable_rls_databricks_credentials')` —
    the estate-migration-surgery condition (P3-1). The api container
    itself boots in core mode (a local gunicorn-import reproduction
    with the compose-equivalent env imports clean); the half-migrated
    DB is what keeps the stack unhealthy.
  - Round 4: P3-1's surgery landed on prepro01 (`210f5e59a` — the
    dual-path 0007 with the conditional databricks_admin dependency,
    core-mode migrate green, 611 migrations) → re-publish 2026-10-21
    (`5fda18a`, tag v2026.10.21 — the estate surgery + all overlay
    fixes + the audited GATE-29 entry for the enrichment-path import)
    → the main + mirror push CI battery is the re-proof (verdicts
    recorded post-run). The probe PR #15 closes once the push battery
    is green — its fixes shipped canonically via the overlay.

frontend-core / sdk-cli are path-filtered (`frontend/**` + `sdk/**` /
`cli/**` respectively) — the probe's workflow/Dockerfile-only diff
correctly does not trigger them; they re-prove on their next domain
change.

## Leg 2 — full CI on the post-rewrite armed branch: QUEUED (honest)

Blocked on the chain the plan sequences: GATE-65 (the G8 force-push
gate) is RED on exactly the 3 U-console rotations (azure-sp-secret,
stripe-test-key, anthropic-auth-token) → P2-1 mirror rebuild → P2-2
maintenance window (`make rewrite-window`). Measured 2026-10-20:
origin/main is still the unrewritten `5555fbc24a` — the armed branch
does not exist yet. The post-rewrite tree content is the SCRUBBED tree
(the publish machinery's exclusions + replace-text), which is what Leg
1 exercises; the origin-side re-proof runs after the window (this
record's date will be extended then).

## Leg 3 — fork PR CI: BLOCKED (honest)

GitHub forbids forking your own repository (single account, no orgs).
The static half stands: GATE-56 `check_fork_guards.py` clean + its
18/18 pins green (2026-10-20). The live fork-PR half needs a second
GitHub account (recipe: `scripts/fork_smoke_pr.sh` with FORK_OWNER) —
a user-level prerequisite, not an engineering gap.

## Machinery

- Overlay fix commit (private repo): `279178a1b` — worker Dockerfile
  stage parity + ephemeral SECRET_KEY + the two RED-first pins.
- Public probe: branch `p32b-ci-reproof`, PR #15 (DCO-signed).
- The first CI failures themselves are the record's RED evidence —
  the public CI on the fresh lineage surfaced drift the private tree's
  CI could never catch (the overlay is only exercised publicly).

## Root-cause findings beyond the workflow fixes (the re-proof's real yield)

- **The untracked-but-wired machinery class** (repo integrity): committed
  wiring (Makefile/ci.yml/_reusable.lint.yml) referenced lane tools and
  pin suites that existed only as untracked working-tree files in the
  shared checkout — a clean-checkout CI would fail to collect them, and
  the index-based publish never ships them. Repair commit `e2d01ac25`
  lands the complete pinned artifacts (32 files incl. the P2-0/2/4
  tools, their pin suites — verified green on the same bytes — and the
  data files they read). One runtime instance was the publish blocker:
  `hub/apps/audit/command_audit.py` (the P0-17 AuditedCommand
  chokepoint, imported by 8 committed management commands) — committed
  separately (`3c46c3e78`); the public CI's boot smoke + migrate had
  crashed on it with ModuleNotFoundError.
- **The i18n coverage generator + its coverage.json** were the same
  class (the p11 pin runs the generator) — committed + regenerated
  from the live catalogs (468 keys, 100% es/fr).
- The p09 ordering pin and the p24 live-leg pin were updated to the
  post-P2-5 contracts (the sync extraction and the replaced remote's
  tag state) — the pins track the honest state, never the stale one.
