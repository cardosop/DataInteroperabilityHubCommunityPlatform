# Audit reports

Operator-generated diagnosis artefacts. Files in this directory are
**evidence** for compliance / migration runs and are NOT committed to
git (see `.gitignore`). Treat them like SQL dumps — they may contain
contract IDs, tenant IDs, and other identifiers that fall under tenant
data-handling policy.

## Naming convention

```text
audit-reports/<phase-slug>-<purpose>-YYYY-MM-DD.<ext>
```

Examples:

* `audit-reports/structureless-pre-rollout-2026-04-30.jsonl` (Phase 227 Wave 0)
* `audit-reports/dq-soak-baseline-2026-05-12.json` (Phase 240 perf snapshot)

## Retention

* **Local**: keep until the corresponding wave completes (then move to
  the run-evidence S3 bucket per the wave's runbook).
* **S3**: retained 7 years (matches the audit retention setting).
* **Never**: `git add` these files. The `.gitignore` rule prevents
  accidental commits; if you bypass it via `git add -f`, the pre-commit
  hook will reject the diff.

## Structureless contracts (Phase 227 Wave 0)

See [`docs/runbooks/structureless-contracts.md`](../docs/runbooks/structureless-contracts.md) — the runbook documents the JSONL row shape, classifications, and customer-coordination playbook.
