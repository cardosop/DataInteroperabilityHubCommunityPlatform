# OpenSpec archive — `preprod01` change (Phase 260 closeout)

**Phase:** 260 (overall — 260.DoD.8)
**Owner:** Auth Engineering Lead + Datasets-Files Engineering Lead + SRE on-call
**Last reviewed:** 2026-05-07

This runbook closes 260.DoD.8 — "OpenSpec archive after deploy: move
`openspec/changes/preprod01/specs/datasets-files/` into
`openspec/specs/datasets-files/spec.md` per
`openspec archive preprod01 --skip-specs --yes` workflow". The same
single archive command also moves the `auth-tenancy-hardening`,
`file-virus-scanning`, and every other capability under
`openspec/changes/preprod01/specs/` into their archive targets in one
atomic operation — the runbook scope is intentionally the FULL
`preprod01` change manifest, not just one capability.

It is the **last** step in Phase 260 closeout: only run AFTER every
other 260.DoD item is `[x]` AND no other phase still depends on the
change directory.

> The `preprod01` change manifest is shared across multiple closeout
> phases (Phase 228, Phase 250, Phase 260, Phase 274, …). Archiving the
> change directory is destructive — the change must be archived
> **once**, after the **last** phase to depend on it has fully
> completed. Phase 260's archive runbook coexists with Phase 228 and
> Phase 250 archive runbooks; whichever runs last is the one that
> actually executes the `openspec archive` command. The other two
> become no-ops (the change directory is already gone).

## When to run

All of the following must be `[x]`:

- 260.DoD.1 — every Phase 260 sub-phase shipped with green quality
  gates, feature-flag and CHANGELOG hygiene, and at least one
  verification scenario exercised.
- 260.DoD.2 — `openspec validate preprod01 --strict` is green
  (re-asserted in step 1 below).
- 260.DoD.3 — per-phase exit checklist closed for every sub-phase:
  code merged, tests green, runbook(s) committed, alert rules
  deployed, dashboard published
  ([monitoring/grafana/dashboards/datasets-files.json](../../monitoring/grafana/dashboards/datasets-files.json)),
  flag flipped staging, soak ≥ 7 days, no P1 incidents, prod canary
  10% → 100%, post-launch retro held.
- 260.DoD.4 — SLO miss escalation policy live: P95 > 2× SLO for 15 min
  → auto-page on-call (`DatasetFilesP95TwoXSLO`); P95 > 3× SLO for
  30 min → auto-rollback via `helm rollback`
  (`DatasetFilesP95ThreeXSLOAutoRollback` →
  [.github/workflows/auto-rollback-datasets-files.yml](../../.github/workflows/auto-rollback-datasets-files.yml)).
  Rehearsal drill executed at least once on staging.
- 260.DoD.5 — 35% contingency buffer absorbed (or unused) per pass-3
  self-review.
- 260.DoD.6 — Stakeholder RACI sign-off captured in
  [docs/raci/datasets-files-hardening.md](../raci/datasets-files-hardening.md).
- 260.DoD.7 — production smoke green:
  - file upload + virus scan + dataset create + retire + orphan-cleanup
    chain completes
    ([tests/smoke/test_phase260_dod7_post_deploy.py::TestPhase260DoD7FullLifecycleChain](../../tests/smoke/test_phase260_dod7_post_deploy.py)),
  - INFECTED EICAR upload blocks download
    ([tests/smoke/test_phase260_dod7_post_deploy.py::TestPhase260DoD7EicarUploadBlocksDownload](../../tests/smoke/test_phase260_dod7_post_deploy.py)),
  - magic-byte mismatch rejects PE-as-CSV
    ([tests/smoke/test_phase260_dod7_post_deploy.py::TestPhase260DoD7MagicByteMismatchRejectsPeAsCsv](../../tests/smoke/test_phase260_dod7_post_deploy.py)),
  - quota meter shows correct percentage
    ([tests/smoke/test_phase260_dod7_post_deploy.py::TestPhase260DoD7QuotaMeterReflectsBytes](../../tests/smoke/test_phase260_dod7_post_deploy.py)),
  - synthetic cross-tenant denial counter incremented
    ([tests/smoke/test_phase260_cross_tenant_denial.py](../../tests/smoke/test_phase260_cross_tenant_denial.py)),
  - cookie mode confirmed
    ([tests/smoke/test_cookie_mode.py](../../tests/smoke/test_cookie_mode.py)),
  - logout-all invalidates a probe JWT within 1 s
    ([tests/smoke/test_phase260_dod4_post_deploy.py](../../tests/smoke/test_phase260_dod4_post_deploy.py)).
- All Phase 260.A / 260.B / 260.B-RLS-{0,1,2,3} / 260.C / 260.7.A–J
  acceptance bullets `[x]`, including the operational gates:
  - 14-day cookie-rollout ledger closed
    ([docs/audit-reports/260-cookie-rollout-nightly-ledger.md](../audit-reports/260-cookie-rollout-nightly-ledger.md)).
  - Branch-protection required-checks doc signed off
    ([docs/ops/branch-protection-required-checks.md](../ops/branch-protection-required-checks.md)).

Confirm via:

```bash
grep -nE '^- \[ \] 260\.(DoD|A|B|B-RLS|C)\.' openspec/changes/preprod01/tasks.md
# expected: zero matches (every Phase 260 line is [x] before archiving)
```

If any of the above is incomplete, **stop** — don't archive yet.

Cross-phase prerequisite check (do NOT archive while another closeout
phase still has open DoD items pointing at this change directory):

```bash
grep -nE '^- \[ \] 22[0-9]\.DoD\.|^- \[ \] 230\.DoD\.|^- \[ \] 240\.DoD\.|^- \[ \] 250\.DoD\.|^- \[ \] 274\.DoD\.' \
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

If validation fails, fix the spec/tasks.md issue before proceeding.

### 2. Capture pre-archive snapshot (audit trail)

Phase 260 introduced the `auth-tenancy-hardening` capability with 18
ADDED Requirements + 44 scenarios. Capture an inventory before the
move so the post-archive diff is auditable:

```bash
cat > docs/audit-reports/260-archive-snapshot-$(date -u +%F).md <<EOF
# Phase 260 OpenSpec archive snapshot — $(date -u +%FT%TZ)

## Change directory contents
$(find openspec/changes/preprod01 -maxdepth 2 -type f | sort)

## auth-tenancy-hardening spec line count
$(wc -l openspec/changes/preprod01/specs/auth-tenancy-hardening/spec.md)

## Requirement / scenario counts
- Requirements: $(grep -c '^### Requirement:' openspec/changes/preprod01/specs/auth-tenancy-hardening/spec.md)
- Scenarios:    $(grep -c '^#### Scenario:' openspec/changes/preprod01/specs/auth-tenancy-hardening/spec.md)

## tasks.md DoD section (Phase 260)
$(awk '/^### Definition of Done \(Phase 260\)/,/^---/' openspec/changes/preprod01/tasks.md)
EOF
git add docs/audit-reports/260-archive-snapshot-*.md
git commit -m "docs(audit): pre-archive snapshot for preprod01 (Phase 260)"
```

### 3. Run the archive

The exact command (matches Phase 250 archive runbook for consistency):

```bash
openspec archive preprod01 --skip-specs --yes
```

`--skip-specs`: the spec content has already been merged into the live
codebase via per-phase audits. The flag tells `openspec` to archive the
change manifest **without** re-applying the spec deltas.

`--yes`: skips interactive confirmation — appropriate because every
prerequisite has been verified in step 1.

### 4. Verify the archive

```bash
ls openspec/changes/archive/preprod01/ 2>/dev/null
# expected: the change manifest (proposal.md, tasks.md, design.md,
#           specs/auth-tenancy-hardening/, specs/asset-creation/, ...)

ls openspec/changes/preprod01 2>/dev/null
# expected: directory absent (moved to archive)

ls openspec/specs/auth-tenancy-hardening/ 2>/dev/null
# expected: spec.md (the merged-spec target — verify file exists OR
#           reconcile manually before closing this runbook)
```

### 5. Commit + push

```bash
git add openspec/changes/archive/preprod01 openspec/changes/preprod01
git commit -m "chore(openspec): archive preprod01 (Phase 260 complete)

260.DoD.8 closeout — archives the preprod01 change manifest after
all Phase 260 DoD items (DoD.1 through DoD.7) and every cross-phase
prerequisite (Phase 228, Phase 250, Phase 274) have been signed off.
Validation pre-flight pass: 'Change preprod01 is valid'.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
git push origin staging
```

### 6. Open the archive PR

```bash
gh pr create --title "Archive preprod01 (Phase 260 complete)" \
    --body "$(cat <<'EOF'
## Summary
- 260.DoD.8 closeout — `openspec archive preprod01 --skip-specs --yes`.
- Phase 260 DoD.1–7 fully signed off.
- 14-day cookie-rollout ledger closed.
- Branch-protection required-checks doc signed off.
- All cross-phase closeout phases (228 / 250 / 274) green.

## Test plan
- [ ] `openspec validate preprod01 --strict` was green pre-archive.
- [ ] `ls openspec/changes/archive/preprod01/` shows the manifest
      including `specs/auth-tenancy-hardening/spec.md`.
- [ ] `ls openspec/changes/preprod01` is absent.
- [ ] Production smoke (`tests/smoke/test_phase260_*.py`) green
      against staging within the 24 h preceding the archive.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 7. Mark 260.DoD.8 complete

After the archive PR has merged, the authoritative state is the
archive directory at `openspec/changes/archive/preprod01/`. If a
follow-up phase reopens the change, copy the manifest back per the
rollback section.

## Rollback

If the archive turns out to be premature (e.g. a P1 surfaces in the
days after deploy that requires a hot-fix change manifest),
**recreate** the change directory rather than `git revert`-ing the
archive commit:

```bash
mkdir -p openspec/changes/preprod01
cp -r openspec/changes/archive/preprod01/* openspec/changes/preprod01/
git add openspec/changes/
git commit -m "chore(openspec): un-archive preprod01 (Phase 260 P1 hot-fix follow-up)"
```

This preserves the archive history while letting follow-up work land
in a live change directory.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Auth Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| Auth EM | _to be filled_ | _YYYY-MM-DD_ |
| SRE on-call (post-deploy soak attestation) | _to be filled_ | _YYYY-MM-DD_ |

260.DoD.8 closes once steps 1–7 above are complete and the archive PR
has merged.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
