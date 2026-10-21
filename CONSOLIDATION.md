# Consolidation: `consolidate/since-last-deploy`

**Created:** 2026-06-08  
**Base branch:** `staging` (HEAD: `e4bae3ee`)  
**Deploy reference:** `3690717a` ("before django 6", Dec 7-8, 2025)  
**Consolidation branch:** `consolidate/since-last-deploy`

## Purpose

This branch consolidates all changes since the last known deploy (Dec 2025) into a single reviewable branch. It captures:

- 574 committed changes from `staging` (Phases 277–278)
- ~1,136 unstaged modifications to tracked files
- ~2,585 new untracked files

## What's Included

### Committed Changes (574 commits)
All commits from `staging` branch since `3690717a`, spanning Phase 277 (Audit, usage, rate limiting, ABAC, webhooks, breach, RoPA, SDK release) and Phase 278 (UX themes, ProductTour, persona hooks, auto-save drafts, saved_views, keyboard shortcuts, bulk multi-select, inline validation).

### Unstaged Modifications (1,136 files)
Backend (all Django apps), CLI (commands, auth, config), SDK (Python), Frontend (components, hooks, services, types), Infrastructure (Dockerfiles, requirements, Makefile), Config (.bandit, pytest.ini, .gitignore).

### New Files (2,585 files)
- **Backend:** New apps (dsar, breach, consent, processor_agreements, ropa, dpia)
- **Migrations:** 299 migrations across 45+ apps
- **Frontend:** Components, hooks, services, E2E journeys, scripts
- **CLI:** 28 new command modules
- **SDK:** Python + JS modules
- **CI/CD:** 24 GitHub Actions workflows
- **Infrastructure:** 14 Helm cronjobs
- **Monitoring:** 20 Grafana dashboards, 15 Prometheus alerts
- **Documentation:** 110 runbooks, 39 docs
- **Security:** .semgrep/ rules, threat models

## What's Excluded

### Junk Files (deleted)
- 44 accidental command fragments (all, always, and, best, etc.)
- 14 empty version artifacts (=, =0.4.27, CACHED, transferring, etc.)
- --help/ directory, core dump (112MB), .terraform/ (3.4GB)
- 23 test output XMLs/results, openapitools.json

### Security
- **.env.test** — Untracked via `git rm --cached`. Live API keys (CKAN, Dados.gov.br, Snowflake). **All keys must be rotated.**

### Stashes (skipped — intermediate versions superseded by WT commits)
- stash@{0}: 20 test files (WIP on HEAD)
- stash@{1}: Empty stash from agents/fix-makefile-test-batch-1
- stash@{2}: 1,875 files (426 overlap with WT)
- stash@{3}: 45 files (149 commits behind HEAD)

### On Disk (not committed)
- 1,965 server log files (~92GB) at repo root

## .gitignore Patterns Added
```
results-*.xml, results-*.xm, backend-test-results.xml, results-frontend-*
=*, openapitools.json, --help, --help/
server.*.log
tests/e2e/journey_results/
```

## Validation Results

| Check | Result |
|-------|--------|
| Migration tree (makemigrations --check --dry-run) | Pending schema changes — expected for staging |
| Dependency resolution (pip install --dry-run) | pyarrow build failure — use pre-built wheels |
| Frontend build | Skipped — needs node_modules install |
| Django system check (--deploy) | Clean — no errors or warnings |
| Diff vs last deploy (3690717a) | 14,273 files, 4.6M insertions, 60k deletions |
| Large file scan | Clean — no large files committed |

## Key Risks

1. **Django version pin removed** — `django>=5.2,<6.0` no longer in requirements.txt
2. **Dependency downgrades** — pandas <2.3.0, pyarrow <15.0.0 for databricks-sql-connector
3. **WeasyPrint upgrade** — 62.3 → 63.0 (breaking change)
4. **Merge migrations** — 21+ merge migrations need ordering validation
5. **Frontend tsc -b flag** — verify tsconfig project references
6. **.env.test key rotation** — all keys in git history must be rotated
7. **Stash@{2} .env.dev/.env.staging** — dev credentials in stash; already tracked in repo

## Next Steps
1. Review Django pin removal — restore or verify Django 6 compat
2. Generate migrations before deploy: `python hub/manage.py makemigrations`
3. Rotate all keys in .env.test
4. Install frontend deps and typecheck: `cd frontend && npm ci && npm run typecheck`
5. Reconcile main's divergent commit: `5555fbc2`
