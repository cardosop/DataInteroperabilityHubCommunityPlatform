# CI Workflow Audit — Phase 277.B.091

**Date:** 2026-05-13
**Scope:** All 53 `.github/workflows/*.yml` files

## Summary

| Status | Count | Action |
|---|---|---|
| **ACTIVE** | 38 | No action — regularly triggered, clearly in use |
| **DORMANT** | 6 | Annotated with `# Phase 277.B.091 — DORMANT` header |
| **REVIEW** | 9 | Documented as intentionally dormant / runbook reference |

## DORMANT (6 workflows)

Phase-complete workflows that are no longer triggered. Annotated with
`# Phase 277.B.091 — DORMANT` header so future maintainers know they
were intentionally left in place. To reactivate, remove the header
and verify pipeline dependencies.

| Workflow | Phase | Triggers | Recommended action |
|---|---|---|---|
| `phase-12a-nightly.yml` | 12A | cron, manual | Archive after 2026-06-30 |
| `phase-12a-release.yml` | 12A | push, manual | Archive after 2026-06-30 |
| `mutmut-asset-saga.yml` | Mutation testing | cron, manual | Archive — mutmut not in active use |
| `mutmut-lineage-validator.yml` | Mutation testing | cron, manual | Archive — mutmut not in active use |
| `mutmut-magic-bytes.yml` | Mutation testing | cron, manual | Archive — mutmut not in active use |
| `phase232-public-zap-baseline.yml` | 232 | cron, manual | Archive after 2026-06-30 |

## REVIEW (9 workflows)

Special-purpose workflows that require ops verification before
re-categorization. These are **not** annotated as DORMANT because
they serve operational or runbook purposes despite being manual-only
or phase-tagged.

| Workflow | Triggers | Assessment | Recommended action |
|---|---|---|---|
| `auto-ledger-260b.yml` | workflow_run | Depends on ci.yml completion | Verify still wired; keep if active |
| `auto-rollback-asset-creation.yml` | manual | Manual rollback for asset creation | Keep as operational runbook |
| `auto-rollback-datasets-files.yml` | manual | Manual rollback for datasets/files | Keep as operational runbook |
| `lineage-snapshots-f5-dod.yml` | push, cron, manual | Lineage F5 DoD snapshots | Verify phase F5 is still active; if not, downgrade to DORMANT |
| `lineage-snapshots-f5-soak.yml` | cron, manual | Lineage F5 soak testing | Verify phase F5 is still active; if not, downgrade to DORMANT |
| `openlineage-f4-dod.yml` | push, cron, manual | OpenLineage F4 DoD | Verify phase F4 is still active; if not, downgrade to DORMANT |
| `semantic-inference-benchmark.yml` | cron, manual | Semantic inference benchmarks | Verify still needed post-Phase 230 |
| `terraform-bootstrap.yml` | manual | One-time TF bootstrap | Keep as runbook reference (documented procedure) |
| `terraform-destroy-staging.yml` | manual | TF destroy staging | Keep as runbook reference (documented procedure) |

## Verification

All 53 workflow YAML files parse successfully. No broken dependencies
detected via `actionlint`. No workflows reference non-existent jobs
or actions from the current commit.

## Follow-up

- Q3 2026: Archive the 6 DORMANT workflows (after 90-day grace period).
- Q3 2026: Re-evaluate the 9 REVIEW workflows against current phase
  status and downgrade any phase-complete ones to DORMANT.
