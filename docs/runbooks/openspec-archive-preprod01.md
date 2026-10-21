# OpenSpec archive — `preprod01` change

**Phase:** 228 (overall — 228.DoD.8)
**Owner:** Engineering Lead
**Last reviewed:** 2026-05-01

This runbook closes 228.DoD.8 — "OpenSpec archive prepared via
`openspec archive preprod01 --skip-specs --yes` workflow". It is
the LAST step in the Phase 228 closeout: only run AFTER every
other 228.DoD item is `[x]`.

## When to run

All of:

- F5 100% rollout has completed (228.F5.DoD.6).
- Post-launch retro is filed (228.DoD.5).
- Eng-days tracker has its final-row entry (228.DoD.7).
- Cost forecast + capacity baseline are signed off
  (228.DoD.6 — both [docs/cost/lineage-feature.md](../cost/lineage-feature.md)
  and [docs/capacity/lineage-storage.md](../capacity/lineage-storage.md)).
- Customer announcement has been sent for every phase (228.DoD.4).
- `openspec validate preprod01 --strict` passes (228.DoD.3) — this
  is asserted again in step 1 below.

If any of the above is incomplete, **stop** — don't archive yet.

## Procedure

### 1. Pre-flight validation

```bash
cd /home/ph/Desktop/DataInteroperabilityHub
openspec validate preprod01 --strict
# expected: "Change 'preprod01' is valid"
```

If validation fails, fix the spec / tasks.md issue before proceeding.

### 2. Run the archive

The spec's exact command:

```bash
openspec archive preprod01 --skip-specs --yes
```

Why `--skip-specs`? The Phase 228 specs under
`openspec/changes/preprod01/specs/lineage-*/spec.md` are
**already-merged-into-main** spec content (every per-phase audit
made sure the implementation matches the spec). The `--skip-specs`
flag tells openspec to archive the change manifest WITHOUT
re-applying the spec deltas (which would be a no-op at best, a
stale-vs-fresh conflict at worst).

The `--yes` flag skips the interactive confirmation — appropriate
because every prerequisite has already been verified.

### 3. Verify the archive

```bash
ls openspec/changes/archive/preprod01/ 2>/dev/null
# expected: the change manifest (proposal.md, tasks.md, design.md)
ls openspec/changes/preprod01 2>/dev/null
# expected: directory absent (moved to archive)
```

### 4. Commit + push

```bash
git add openspec/changes/archive/preprod01 openspec/changes/preprod01
git commit -m "chore(openspec): archive preprod01 (Phase 228 complete)

228.DoD.8 closeout — archives the preprod01 change manifest after
all per-phase DoDs (0/F1/F2/F3/F4/F5/X) and the Phase 228 overall
DoD items (DoD.1-7) have completed. Validation pre-flight pass:
'Change preprod01 is valid'.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
git push origin staging
```

### 5. Open the archive PR

```bash
gh pr create --title "Archive preprod01 (Phase 228 complete)" \
    --body "$(cat <<'EOF'
## Summary
- 228.DoD.8 closeout — `openspec archive preprod01 --skip-specs --yes`.
- All per-phase DoDs (0/F1/F2/F3/F4/F5/X) completed.
- All overall DoDs (DoD.1 through DoD.7) signed off.

## Test plan
- [ ] `openspec validate preprod01 --strict` was green pre-archive.
- [ ] `ls openspec/changes/archive/preprod01/` shows the manifest.
- [ ] `ls openspec/changes/preprod01` is absent.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Rollback

If the archive turns out to be premature (e.g. a P1 surfaces in
the days after F5 rollout that requires a hot-fix change manifest),
**recreate** the change directory rather than `git revert`-ing the
archive commit:

```bash
mkdir -p openspec/changes/preprod01
cp -r openspec/changes/archive/preprod01/* openspec/changes/preprod01/
git add openspec/changes/
git commit -m "chore(openspec): un-archive preprod01 (P1 hot-fix follow-up)"
```

This preserves the archive history while letting follow-up work
land in a live change directory.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| EM | _to be filled_ | _YYYY-MM-DD_ |

228.DoD.8 closes once steps 1-5 above are complete + the archive
PR has merged.
