# Critical Review — close-oss-release-conditions plan (2026-10-18)

Adversarial review of the execution plan against the ACTUAL state of
the repo and remotes (measured today, 2026-10-18). Question answered:
is the plan sufficient to make the application OSS-ready?

## Verdict

**Not yet — the plan is directionally correct and well-sequenced, but
as committed it cannot be executed as written, and even a successful
execution would leave residual exposure.** Phase 2 (the rewrite) cites
tooling that no longer exists in the tree and inputs that were
transient `/tmp` files now deleted; Phase 2's public-mirror step uses a
mechanism that by design APPENDS sync commits onto the existing
(tainted) public history; and several contamination surfaces (forks,
PR refs, container images, Actions artifacts) are outside the plan's
blast radius. Each gap below is fixable with the amendments listed;
after amendment the plan is sufficient.

## Gaps (ranked)

### G1 — CRITICAL — the plan cites a deleted verifier

`scripts/verify_history_rewrite.py` (11 pins, cited in P2-1 and the
W0.4 record) is NOT in the current tree — it was removed in the
scripts consolidation (recoverable from history at commit `2cd813511`).
P2-1 as written fails on the first command. **Fix:** restore the
script from history (`git show 2cd813511:scripts/verify_history_rewrite.py`)
or rebuild it RED-first against a fixture, keep it as a one-shot
execution tool (the W0.4 record deliberately kept it out of the
always-on battery: the dev checkout carries local-only leak commits
until the push), and cite its restored path in the plan.

### G2 — CRITICAL — the rewrite inputs are gone

Measured today: `/tmp/w02-fragments.txt` (7 fragments),
`/tmp/w02-replace.txt` (11 values), `/tmp/w04-mirror3.git`,
`/tmp/w04-fresh-clone.git` — all deleted. Surviving in-repo:
`scripts/history_rewrite_paths.txt` (the path half of the filter) and
the procedure record (`history-rewrite-2026-10-06.md`, which names the
fragment/value inventory's provenance but not the values — correctly,
values must not be committed). **Fix:** add a reconstruction task
BEFORE the rebuild: full-history gitleaks pass over the current refs
→ candidate fragments/values → reconcile against the record's
inventory description (8 fragments incl. the ANTHROPIC token; 11
replace values incl. TLS material) → regenerate the replace file with
a completeness assertion (every candidate is either filtered or
rotation-verified dead). Only then does "re-run the filter-repo build"
become possible.

### G3 — HIGH — public history replacement is under-specified

`publish_public.sh` states its contract explicitly: "The scrubbed
HISTORY is produced once by the one-time filter-repo run — this script
only appends sync commits." Appending sync commits CANNOT remove
`f3f84bc51` (measured today: reachable from public/main, contains
`.env.staging`, `.env.test` with live-at-the-time values, 12+ staging
tarballs). P2-5 as written would leave the public history tainted.
**Fix:** specify public-history REPLACEMENT: delete-and-recreate the
public repo (or force-push a fresh scrubbed mirror over its main), and
delete the public branches that fork the tainted lineage
(`community/core-fix`, the dependabot branches) and the 4 legacy tags
+ archive tag — before the first `publish_public.sh` sync commit.

### G4 — HIGH — origin-side contamination surfaces not addressed

GitHub retains PR refs (`refs/pull/*` — the record notes they were
deleted in the MIRROR but exist server-side), Actions run logs and
artifacts may retain printed secret values (a prior incident involved
env-value printing), and old dependabot branches on origin fork the
tainted lineage. **Fix:** add a task: close/delete the open PRs and
stale dependabot branches on origin, purge Actions artifact/cache
history where values may have been printed, and open a GitHub support
ticket for dangling-object/retention purges if the post-push sweep
finds reachable fragments outside the pushed refs.

### G5 — MEDIUM-HIGH — container images predate the scrub

Published images (registry publish W6.0 COMPLETE) were built from
pre-scrub trees; any image whose build context copied `.env*` files
carries the values regardless of the git rewrite. **Fix:** audit the
image build contexts for baked env files; rebuild-and-republish or
delete affected public images; record the audit.

### G6 — MEDIUM — no post-rewrite full-CI re-proof

The W10.1 full-CI record is on the pre-rewrite lineage. After the
force-push every SHA changes: Actions re-runs from scratch, and the
DoD-3 claims (full CI green, fork PR CI, public mirror CI) must be
re-proven on the NEW history. P3-2 covers only the attributed red
gates. **Fix:** add a Phase 3 task: full CI pass on the post-rewrite
armed branch + fork-PR CI + public mirror CI, recorded as the DoD-3
re-verification.

### G7 — MEDIUM — dependency-license scan gap

`scripts/check_copyleft.py` was deleted; the surviving license
machinery is `check_root_license.py` (root LICENSE/NOTICE) plus the
copyleft pre-flight INSIDE `publish_public.sh` (requirements.txt
closure only — misses the frontend npm closure and pyproject extras).
For Apache-2.0 publication a dependency-license scan over both
closures is a real obligation, not a nicety. **Fix:** restore/extend
the copyleft audit to py + npm closures and wire it into the publish
pre-flight.

### G8 — MEDIUM — no history-content → rotation-status mapping

The plan rotates the 6 GATE-51 surfaces + the ANTHROPIC token. The
tainted history ALSO contains `.env.staging` (staging stack), `.env.test`
(test stack), TLS material and the staging tarballs. Prior sessions
report those rotated/regenerated (W0.5 window, 2026-10-06: staging
passwords, TLS regen; test-stack wipe + re-mint) — but the plan never
re-verifies or records it. **Fix:** add a Phase 1 deliverable: a
mapping table of every credential CLASS visible in history → its
rotation/retirement evidence, signed off as the force-push gate.

### G9 — LOW-MEDIUM — release-please state after the rewrite

release-please owns versioning on main; a manually re-created tag on
the rewritten lineage can desync its release history/CHANGELOG.
**Fix:** add a release-please dry-run + CHANGELOG reconciliation task
to P2-4.

### G10 — LOW — GATE-54 fix is ambiguous in the plan

The plan offers two mechanisms (registry seam vs string references).
The boundary contract's own pattern is registry inversion — decide it
in the design (recommend the seam) so the task is executable without
re-litigating.

### G11 — LOW — GATE-40 waves must state the W16 contract

Env-gated skip conversions must NOT carry TICKET/EXPIRES annotations
(CLAUDE.md environment-policy contract). State it as a hard rule in
the P0-10 task so a wave can't regress the policy.

### G12 — LOW — push-protection ordering

P0-9 enables push protection before the force-push. The rewritten
push is clean by construction so it passes, but enable it on origin
AFTER P2-2 and on public BEFORE P2-5, and verify the force-push is not
blocked (the maintenance window should not discover this mid-flight).

### G13 — LOW — public-only file regression on re-sync

P2-5 re-syncs origin→public; verify no public-only files exist
(AGENTS.md/ARCHITECTURE.md/.devcontainer now exist locally — re-verify
with a diff) so the sync cannot silently drop public-side additions.

### G14 — LOW — trademark/branding in the legal bundle

npm scope `@meshant` + Meshant branding ties the OSS packages to the
company identity. Add a trademark/scope review to the P0-12 legal
package.

## What the plan gets right (recorded honestly)

- Root-cause framing per finding (process rot for CVEs, observability
  gap for the listener, generate-at-boot for dev certs) — fixes the
  cause, not the symptom.
- Sequencing is correct: rotations BEFORE the rewrite (dead values make
  residual exposure inert), rewrite gated on rotations, verification
  phase last.
- TDD discipline per task (RED-first pins), falsifiability registration
  for new gates, and the closure-pin idea (no ledger condition flips
  without evidence) closes the review loop.
- The risk register and the U.7 contingency are real; both validators
  pass.

## Bottom line

With amendments G1–G14 folded in (restore the verifier, reconstruct
the rewrite inputs, replace-not-append the public history, cover forks
/PR refs/images/artifacts, add post-rewrite CI re-proof + dependency
license scan + the history→rotation mapping, and resolve G9–G14), the
plan is sufficient to drive the application to a defensible OSS-ready
state. Without them, Phase 2 fails on day one and residual exposure
survives a "successful" execution.

**Status (2026-10-18, same day):** all G1–G14 amendments folded into
the plan — design.md §1.1/1.6/1.8/1.12/1.14 + new §1.15/§1.16, the
risk register, the sequencing, and tasks.md (P0-4/9/10/12 amended;
P0-13/14, P1-3, P2-0, P2-6, P3-2b added; P2-1…P2-5 amended).
