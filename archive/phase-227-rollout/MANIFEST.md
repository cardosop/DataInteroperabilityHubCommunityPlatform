# Phase 227 Rollout — Archive Manifest

Phase 227 (the structureless-contract elimination programme) ran from
the L0 spec lock (2026-04-23) through the W5 cutover (2026-04-30).
This directory is the git-tracked **manifest** of the artefacts that
operationally drove the rollout.  The artefacts themselves are NOT
checked in — they live in `audit-reports/` (gitignored per the
existing convention) and the run-evidence S3 bucket per the runbook.

## Why a manifest, not a copy

`audit-reports/README.md` is unambiguous: those files MUST NOT be
`git add`-ed (they may carry tenant-scoped identifiers under
data-handling policy, even when the dry-run count is zero, and the
pre-commit hook rejects bypasses via `git add -f`).  This manifest
honours that convention while still giving compliance and future
maintainers a permanent breadcrumb to:

* what artefacts existed,
* when each one was produced,
* what the SHA-256 was at archival time (so a future spot-check
  against an S3 copy can verify integrity),
* the runbook section that documents how to retrieve them.

## Artefacts

| Artefact                                                  | Produced (UTC) | SHA-256 (at archival)                                                | Disposition |
| --------------------------------------------------------- | -------------- | -------------------------------------------------------------------- | ----------- |
| `audit-reports/structureless-pre-rollout-2026-04-30.jsonl` | 2026-04-30     | `6d2ee194c2873a8c317e7ad3f7a42d7bd7e3837806fb3d094a321c0bfe4bf882` | Local working tree → S3 (`s3://meshant-run-evidence/phase-227/`) per runbook §227.0.1 |
| `audit-reports/structureless-summary-2026-04-30.md`       | 2026-04-30     | `13a8aa70364e76817246db78d2aed03ddede4448cac4716f652c427884f2880c` | Local working tree → S3 (same bucket)                                                |

Both artefacts are dry-run diagnosis output (the staging-clone DB had
zero structureless contracts at Wave 0 time — reflecting the fact
that the L1/L2 walkers had already self-healed the population before
the dry-run ran).  They are kept for compliance retention only.

## Retrieval

To restore an artefact for an audit:

```bash
aws --profile staging s3 cp \
    s3://meshant-run-evidence/phase-227/structureless-pre-rollout-2026-04-30.jsonl \
    audit-reports/

sha256sum audit-reports/structureless-pre-rollout-2026-04-30.jsonl
# Compare against the row above.
```

If the hash mismatches, **STOP** and escalate via the audit runbook —
that's a tamper-evidence signal.  S3 Object Lock (Phase 234.1, when
shipped) guards against in-place mutation, but the SHA in this file
is the canonical baseline.

## Cross-references

* `docs/runbooks/structureless-contracts.md` — operational doctrine
  + retrieval procedure.
* `openspec/changes/archive/2026-04-30-structureless-contract-elimination/`
  — the OpenSpec capability spec moved here per W6.6 (note: the
  `openspec/` tree is gitignored, so the move is local-only; the
  authoritative spec body lives in this commit's `tasks.md`).
* `CHANGELOG.md` — the `[Unreleased]` BREAKING entry that documents
  the structural-floor invariant publicly.
