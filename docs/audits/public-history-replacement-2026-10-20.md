# Public-History Replacement + Re-Sync — P2-5 Execution Record (2026-10-20)

`openspec/changes/close-oss-release-conditions` — P2-5 (G3, G13) EXECUTED
2026-10-20. Closes the public-history replacement (G3), the public-only
file regression check (G13), and the public-mirror staleness (P-1).

## Measured "before" state (the taint)

- Public repo `cardosop/DataInteroperabilityHubCommunityPlatform`
  (created 2026-08-14), visibility public, 0 stars / 0 forks / 0
  watchers, 14 open dependabot PRs, 4 legacy/archive tags.
- **Gitleaks (house config) over the FULL public mirror: 1,736 findings**
  across 4 deep pre-resync commits — Playwright E2E trace artifacts
  (`frontend/test-results/.playwright-artifacts-*/traces/*.network`)
  carrying JWTs (1,650) + generic API keys (86):
  - `04231b9f21` 2026-06-20 chore(preprod01): snapshot working state
  - `315762ae1f` 2026-03-12 revisando02
  - `9a085e00d9` 2026-03-11 reviewing01
  - `ec348f7bbf` 2026-02-27 running front e2e
- **Taint classification (machine, via the backup mirror): ALL 50 refs
  TAINTED** — main, mirror/public-core, community/core-fix, all 14
  dependabot branches, every `refs/pull/*` head+merge, and all 4 tags.
  Because PR refs cannot be deleted by users, force-push could never
  close this — delete-and-recreate was the root-cause path (and lost
  nothing: 0 stars/forks/watchers).
- The specific `f3f84bc51` object (H-1's citation) is NOT fetchable
  from the public repo by SHA (both API endpoints 404/422) — the review's
  claim was imprecise, but the substance (tainted public lineage) was
  confirmed and exceeded by the measurement above.

## Machinery (TDD, RED-first — commit c5beb75c5 + fixes)

- `scripts/publish_sync.sh` — sync mechanics extracted from
  publish_public.sh with the P2-5 root fixes: ROOT-lineage bootstrap
  (never forks the stale tainted local branch), exact-tree index
  discipline (`git rm --cached` + literal-pathspec adds — checkout
  litter can never enter a sync commit; the P-1 drift root cause),
  remote main fast-forwarded to the same commit, dirty/diverged/
  missing-remote guards, post-commit exactness gate (committed tree
  byte-identical to the built tree).
- `scripts/replace_public_repo.py` — plan/execute with the backup guard
  (fsck-clean mirror covering every live ref at the same SHA) and the
  G12 ordering (push protection re-armed BEFORE the first sync via the
  P0-9 tool).
- `scripts/check_public_resync_diff.py` + `public_resync_drift_allowlist.txt`
  — the G13 acceptance diff.
- Pins: `scripts/tests/test_p25_public_replacement.py` 22/22 (real git
  fixtures + the real gh API live legs, W16-gated; no mocks).
- `scripts/tests/test_publish_gates.py` updated for the extracted
  post-commit gate + the built-tree GATE-29 pin.

## Pre-flight evidence (all against the REAL tree)

- Dry-run publish GREEN: copyleft 101 entries / 0 hard-copyleft,
  replace-text 34 entries, built tree 12,553 files, gitleaks on the
  built tree PASSED.
- Live-value absence (the 3 PENDING-U surfaces — values read from disk,
  never printed): STRIPE_SECRET_KEY ABSENT-OK; anthropic auth token
  ABSENT-OK; azure-sp-secret not present in any disk env file (its
  leaked value lives only in ORIGIN's history — P2-2 scope). The
  STRIPE_PUBLISHABLE_KEY ships by design (public key; the gitleaks gate
  accepts the publishable shape).
- No real `.env*` files ship — only the templates/examples set.
- G13 diff: 12,151 kept / 332 drift-classified (13 prefix entries; every
  sampled path's deleting commit verified — 2026-10-18/20 consolidations
  - the `git add -A` litter class) / 403 added / overlay preserved.

## Replacement execution

- Backup mirror `/tmp/p25-evidence/public-before.git` (all 51 live refs
  incl. HEAD), fsck clean, verified by the execute's backup guard.
- Push protection verified ENABLED pre-replacement (the G12 ordering).
- `replace_public_repo.py execute --yes`: deleted →
  recreated public+empty → push protection re-armed → verified
  (public + enabled + empty). The first execute attempt failed CLOSED
  (exit 2) on the missing `delete_repo` token scope — the guard ladder
  working as designed; the scope was added by the user (device flow,
  recorded 2026-10-20).
- Local public checkout realigned (stale branches + remote-tracking
  refs removed; HEAD detached).

## Re-sync

- `publish_public.sh` real publish (2026-10-20 ~21:50 local): the
  first sync commit `36cce9e2` is a ROOT lineage on the recreated repo
  (the P2-5 orphan bootstrap); main == mirror/public-core ==
  `36cce9e2`; tag `v2026.10.20` lands on the same commit; 12,553 files
  shipped; the post-commit exactness gate verified the committed tree
  byte-identical to the built tree; post-commit verification green
  (GATE-29 67/67 allowlisted, gitleaks clean, compose config OK).
- Root fixes landed in the same window (each pinned):
  - GATE-29 pre-flight scans the BUILT tree, not the working tree
    (a peer-lane WIP import produced a false failure on content the
    index-based publish never ships) — commit 1a8fb453b.
  - the boundary allowlist anchors the INDEX state, not transient WIP
    (the reanchor had tracked the working-tree lines).
  - `publish_sync.sh` exact-tree index discipline made deterministic:
    `git read-tree --empty` + ONE `git add --pathspec-from-file
    --pathspec-file-nul` + ONE `git diff --no-index` gate (the real
    first sync's `git rm --cached` clear silently failed and unioned
    the stale tree into the commit — the exactness gate CAUGHT it and
    no push happened; the redo root-fixed it) — commit b15c45b02.
  - the sync tolerates a fresh empty checkout (the clean-room redo
    pattern) with the stale-branch detach/delete hard-failing instead
    of masking.

## Post-sync verification (fresh-clone fsck evidence)

- Fresh mirror clone `fsck --full` clean; `git rev-list --all --count`
  = the single root + the dependabot refs (dependabot re-engaged on
  the recreated repo within minutes — every new ref roots at the clean
  `36cce9e2`, never the tainted lineage).
- **Gitleaks (house config) over the FULL new public history: 0
  findings** (the "before" measurement: 1,736 across 4 deep commits).
- All 5 tainted SHAs unreachable in the new repo
  (04231b9f21 / 315762ae1f / 9a085e00d9 / ec348f7bbf /
  f3f84bc51fe… — `git cat-file -e` fails on each).
- The ONLY tag is `v2026.10.20` (the 4 legacy/archive tags died with
  the old repo). No real `.env*` files ship (the 6 template/example
  entries only); zero `frontend/test-results` entries.
- Parity pins green in the same session: GATE-56
  (`check_fork_guards.py` clean + 18/18 pins), `test_public_ci_parity.py`,
  `test_publish_gates.py` 6/6, `test_p25_public_replacement.py` 24/24.

## Residuals (honest)

- The ORIGIN-side force-push (ledger `w04-force-push`, P2-2) remains
  QUEUED on P1-1 close (azure/stripe/anthropic console rotations) —
  P2-5 closes the PUBLIC half of the history-rewrite condition; the
  origin half is P2-2's execution.
- The P2-4 public tag publication (`v0.1.0`) is QUEUED on P2-2 (its
  anchor is the rewritten origin main); the 4 legacy public tags were
  deleted with the repo, which clears its preconditions on the public
  side.
- Recreated-repo settings: description/homepage/topics were unset on the
  old repo (nothing to restore); has_wiki/defaults are GitHub defaults.
- Public CI (Actions) on the recreated repo: workflows ship in the
  overlay — the first run evidence belongs to P3-2b (post-rewrite CI
  re-proof), not this record.
