# OpenSpec archive — `preprod01` change (Phase 250 closeout)

**Phase:** 250 (overall — 250.DoD.8)
**Owner:** Asset-Creation Engineering Lead
**Last reviewed:** 2026-05-04

This runbook closes 250.DoD.8 — "OpenSpec archive after deploy: move
`openspec/changes/preprod01/specs/asset-creation/` into `openspec/specs/asset-creation/spec.md`
per `openspec archive preprod01 --skip-specs --yes` workflow". It is the **last**
step in Phase 250 closeout: only run AFTER every other 250.DoD item is `[x]`.

> The `preprod01` change manifest is shared across multiple closeout phases
> (Phase 228, Phase 250, Phase 260, …). Archiving the change directory is
> destructive — the change must be archived **once**, after the **last**
> phase to depend on it has fully completed. If any other phase still has
> open DoD items pointing at `openspec/changes/preprod01/`, do **not**
> archive yet; instead update this runbook's prerequisites.

## When to run

All of the following must be `[x]`:

- 250.DoD.1 — every Phase 250 sub-phase shipped with green quality gates,
  feature-flag and CHANGELOG hygiene, and at least one verification scenario
  exercised.
- 250.DoD.2 — `openspec validate preprod01 --strict` is green (re-asserted
  in step 1 below).
- 250.DoD.3 — every Phase 250 sub-phase has cleared the per-phase exit
  checklist (merged, soak ≥ 7 days, canary completed, retro filed).
- 250.DoD.4 — escalation alerts (`AssetWorkflowDurationP95TwoXSLO`,
  `AssetWorkflowDurationP95ThreeXSLOAutoRollback`) are deployed and have
  paged at least once in a non-incident drill.
- 250.DoD.5 — 30 % contingency buffer documented at
  `docs/audit-reports/250-dod-closure-pass-2026-05-04.md`.
- 250.DoD.6 — every row in `docs/raci/asset-creation-hardening.md` has a
  recorded sign-off in `docs/raci/asset-creation-hardening-signoffs.md`.
- 250.DoD.7 — `tests/smoke/test_phase250_data_first.py` ran green against
  staging post-deploy (latency P95 ≤ 8 s, fail-closed left zero orphan
  DRAFTs, federated import surfaced compliance-gate metadata, If-Match 412
  contract held).

Confirm via:

```bash
grep -nE '^- \[ \] 250\.DoD\.' openspec/changes/preprod01/tasks.md
# expected: zero matches (every DoD line is [x] before archiving)
```

If any of the above is incomplete, **stop** — don't archive yet.

Cross-phase prerequisite check (do NOT archive while another closeout phase
still depends on this change directory):

```bash
grep -nE '^- \[ \] 22[0-9]\.DoD\.|^- \[ \] 230\.DoD\.|^- \[ \] 240\.DoD\.|^- \[ \] 260\.DoD\.' \
  openspec/changes/preprod01/tasks.md
# expected: zero matches
```

## Procedure

### 1. Pre-flight validation

```bash
cd /home/ph/Desktop/DataInteroperabilityHub
openspec validate preprod01 --strict
# expected: "Change 'preprod01' is valid"
```

If validation fails, fix the spec / tasks.md issue before proceeding.

### 2. Capture pre-archive snapshot (audit trail)

Phase 250 introduced a new `asset-creation` capability and seven sub-phases.
Capture a one-liner inventory of what's about to move so the post-archive
diff is auditable:

```bash
cat > docs/audit-reports/250-archive-snapshot-$(date -u +%F).md <<EOF
# Phase 250 OpenSpec archive snapshot — $(date -u +%FT%TZ)

## Change directory contents
$(find openspec/changes/preprod01 -maxdepth 2 -type f | sort)

## Asset-creation spec line count
$(wc -l openspec/changes/preprod01/specs/asset-creation/spec.md)

## tasks.md DoD section (Phase 250)
$(awk '/^### 250 — Definition of Done/,/^---/' openspec/changes/preprod01/tasks.md)
EOF
git add docs/audit-reports/250-archive-snapshot-*.md
git commit -m "docs(audit): pre-archive snapshot for preprod01 (Phase 250)"
```

### 3. Run the archive

The exact command:

```bash
openspec archive preprod01 --skip-specs --yes
```

Why `--skip-specs`? Phase 250's `specs/asset-creation/spec.md` and earlier
phases' `specs/lineage-*/spec.md` are **already-merged-into-main** spec
content (every per-phase audit makes sure the implementation matches the
spec). The `--skip-specs` flag tells openspec to archive the change manifest
**without** re-applying the spec deltas (which would be a no-op at best, a
stale-vs-fresh conflict at worst).

The `--yes` flag skips the interactive confirmation — appropriate because
every prerequisite has already been verified in step 1.

### 4. Verify the archive

```bash
ls openspec/changes/archive/preprod01/ 2>/dev/null
# expected: the change manifest (proposal.md, tasks.md, design.md,
#           specs/asset-creation/, specs/auth-tenancy-hardening/, ...)

ls openspec/changes/preprod01 2>/dev/null
# expected: directory absent (moved to archive)

ls openspec/specs/asset-creation/ 2>/dev/null
# expected: spec.md (this is the merged-spec target — `--skip-specs` left
#           it unchanged because it was already lifted in by an earlier
#           pass; verify the file exists OR reconcile manually before
#           closing the runbook)
```

### 5. Commit + push

```bash
git add openspec/changes/archive/preprod01 openspec/changes/preprod01
git commit -m "chore(openspec): archive preprod01 (Phase 250 complete)

250.DoD.8 closeout — archives the preprod01 change manifest after all
Phase 250 DoD items (DoD.1 through DoD.7) and every cross-phase
prerequisite (Phase 228, Phase 240, Phase 260) have been signed off.
Validation pre-flight pass: 'Change preprod01 is valid'.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
git push origin staging
```

### 6. Open the archive PR

```bash
gh pr create --title "Archive preprod01 (Phase 250 complete)" \
    --body "$(cat <<'EOF'
## Summary
- 250.DoD.8 closeout — `openspec archive preprod01 --skip-specs --yes`.
- Phase 250 DoD.1–7 fully signed off (see
  `docs/audit-reports/250-dod-closure-pass-*.md` and
  `docs/raci/asset-creation-hardening-signoffs.md`).
- All cross-phase closeout phases (228 / 240 / 260) green.

## Test plan
- [ ] `openspec validate preprod01 --strict` was green pre-archive.
- [ ] `ls openspec/changes/archive/preprod01/` shows the manifest
      including `specs/asset-creation/spec.md`.
- [ ] `ls openspec/changes/preprod01` is absent.
- [ ] `tests/smoke/test_phase250_data_first.py` ran green against
      staging within the 24 h preceding the archive.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 7. Mark 250.DoD.8 complete

After the archive PR has merged, edit `openspec/changes/archive/preprod01/tasks.md`
(now in archive) ONLY if a follow-up phase reopens the change. The
authoritative state is the archive directory.

## Rollback

If the archive turns out to be premature (e.g. a P1 surfaces in the days
after deploy that requires a hot-fix change manifest), **recreate** the
change directory rather than `git revert`-ing the archive commit:

```bash
mkdir -p openspec/changes/preprod01
cp -r openspec/changes/archive/preprod01/* openspec/changes/preprod01/
git add openspec/changes/
git commit -m "chore(openspec): un-archive preprod01 (Phase 250 P1 hot-fix follow-up)"
```

This preserves the archive history while letting follow-up work land in a
live change directory.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Asset-Creation Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| Asset-Creation EM | _to be filled_ | _YYYY-MM-DD_ |
| SRE on-call (post-deploy soak attestation) | _to be filled_ | _YYYY-MM-DD_ |

250.DoD.8 closes once steps 1–7 above are complete + the archive PR has merged.
