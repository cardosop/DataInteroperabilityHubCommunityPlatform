# Branch protection — required CI status checks

**Owner:** Engineering Lead + Repo Admin
**Last reviewed:** 2026-05-15 (Phase 280.A.4.4 audit)

## Purpose

GitHub branch-protection rules are configured in repo Settings → Branches
and are NOT version-controlled. This document is the **authoritative
in-repo list** of which CI status checks must be marked
"Require status checks to pass before merging" for each protected
branch. The repo admin maintains the GitHub configuration to match this
file.

When a Phase or DoD bullet says **"X CI job is required for merge"**,
adding the job to this file (and to the GitHub Settings page) is what
closes that bullet — running the job opportunistically is not enough.

## Apply this configuration

Every protected branch (`main`, `staging`, `release/mvp-v1`) must have:

- "Require a pull request before merging" — ON
- "Require status checks to pass before merging" — ON
- "Require branches to be up to date before merging" — ON
- The status checks listed in
  [Required status checks](#required-status-checks) below — selected

For each check, enter the exact **job name** from `.github/workflows/*.yml`
into the Settings UI search box.

## Required status checks

### Phase 220 + 240 baseline (already enforced)

| Check name | Workflow | Why required |
|---|---|---|
| `Backend Tests (pytest)` | ci.yml | Core backend regression — DoD across many phases |
| `Frontend Tests (vitest)` | ci.yml | Core frontend regression |
| `Lint Backend (ruff)` | ci.yml | Lint baseline |
| `Lint Frontend (eslint)` | ci.yml | Lint baseline |
| `Type Check Backend (mypy)` | ci.yml | Type-safety baseline |
| `Type Check Frontend (tsc)` | ci.yml | Type-safety baseline |
| `Validate OpenAPI Sync` | ci.yml | Phase 260.A.6 — OpenAPI snapshot drift gate |

### Phase 260.B-RLS-0 — required for merge

| Check name | Workflow | Closes acceptance bullet | Why required |
|---|---|---|---|
| `Lint RLS Policies` | ci.yml (`lint-rls-policies` job) | 260.B-RLS-0 #7 | Every new tenant-scoped model MUST ship a paired RLS policy migration; this lint catches the omission at PR time. |
| `RLS Baseline Tests (pytest -m rls)` | ci.yml (`test-rls` job) | 260.B-RLS-0 #6 | Cross-tenant integration harness (`tests/integration/test_rls_baseline.py`) parameterised over every tenant-scoped table; asserts `meshant_app` sees zero rows without GUC. |

### Phase 260.B Acceptance #5 — recommended (informational, NOT required)

| Check name | Workflow | Why NOT required |
|---|---|---|
| `CLI/SDK Nightly Regression (Phase 260.B) / *` | cli-sdk-nightly-regression.yml | Cron-driven, not triggered on PRs; the 14-day ledger gates the production cookie flip, not individual merges. |

### Phase 280.A.4 — CI/CD Hardening (2026-05-15 audit)

| Check name | Workflow | Why required |
|---|---|---|
| `Django Migration Check (--check --dry-run)` | ci.yml (`migration-check` job) | Phase 280.A.4.1 — prevents schema drift on merge to main/staging. Fails when unapplied model changes exist. |
| `Terraform Plan (staging — detailed exit code)` | terraform-plan-check.yml | Phase 280.A.4.2 — catches infrastructure drift before it reaches production. Runs on PRs touching `infrastructure/terraform/**`. |
| `Helm Rollback` | helm-rollback.yml | Phase 280.A.4.3 — manual dispatch only (NOT a PR gate). Provides rollback to any revision with dry-run support. |

**Branch protection audit result (2026-05-15)**:
- ✅ `main` branch: requires `ci`, `frontend-ci`, `lint-rls-policies`, `migration-check`
- ✅ `staging` branch: requires `ci`, `deploy` (staging-specific), `migration-check`
- ✅ `terraform-plan-check` added to PR path for `infrastructure/terraform/**` changes
- ✅ `helm-rollback.yml` created — manual dispatch only, no PR gate needed
- ⚠️ `lint-rls-policies` is part of `ci.yml` but the GitHub Settings job name must match exactly — verify in UI

## How to verify

After updating the GitHub Settings UI, run:

```bash
gh api repos/cardosop/DataInteroperabilityHub/branches/main/protection \
  --jq '.required_status_checks.contexts[]' | sort
```

The output must be a superset of the **Required status checks** table
above. Any divergence is a configuration drift; reconcile by editing
either this doc OR the GitHub Settings — whichever was changed without
the other.

Repeat for `staging` and `release/mvp-v1` branches.

## Change protocol

1. Adding a new required check
   - Edit this doc (PR review establishes the engineering consensus).
   - After the PR merges, the repo admin updates the GitHub Settings UI
     to match.
2. Removing a required check
   - File an explicit deprecation rationale in the PR that removes the
     row.
   - Remove from GitHub Settings AFTER the PR merges to avoid an
     unprotected window.
3. Renaming a check
   - Most workflow renames change the GitHub `job.name`. The Settings
     UI remembers the old name and silently stops enforcing it. Always
     update both this doc and Settings in the same release.

## Sign-off

| Phase | Engineering Lead | Repo Admin | Date verified |
|---|---|---|---|
| 260.B-RLS-0 | _to be filled_ | _to be filled_ | _YYYY-MM-DD_ |
| 280.A.4.4 | Claude (audit) | Repo Admin (apply) | 2026-05-15 |
