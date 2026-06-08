# CI Test Workflow Audit

**Date:** 2026-05-21
**Scope:** 62 workflow files in `.github/workflows/`; 16 principal test workflows + 5 supplementary workflows audited.
**Methodology:** Each workflow's `name`, `on:` triggers, `jobs`, test commands, services, and inter-workflow dependencies were extracted.

---

## Summary

| Category | Count | Workflows |
|---|---|---|
| **PR-gated test workflows** | 8 | ci.yml, e2e.yml, e2e-pr-smoke.yml, e2e-metrics.yml, playwright-e2e.yml, playwright-e2e-strict.yml, contracts-perf-benchmark.yml, lineage-x-ci-gates.yml |
| **Nightly/scheduled test workflows** | 6 | e2e-nightly-full.yml, perf-nightly.yml, cli-sdk-nightly-regression.yml, mutmut-*.yml (3) |
| **Path-triggered test workflows** | 4 | semantic-e2e.yml, sdk-integration.yml, test-marketplace-integration.yml, frontend-tests.yml |
| **Workflow-dispatch only** | 2 | openlineage-f4-dod.yml, visual-regression-playwright.yml |
| **Meta/support workflows** | 5 | test-results-reporting.yml, chromatic.yml, deploy.yml (smoke tests), bundle-size-check.yml, docs-ci.yml |
| **Total** | **25** | |

---

## 1. Individual Workflow Analysis

### 1.1 `ci.yml` (116,890 bytes — largest)

| Field | Value |
|---|---|
| **Name** | CI |
| **Triggers** | `push: [main, develop, release/mvp-v1]`, `pull_request: [main, develop, release/mvp-v1]` |
| **Jobs** | ~50+ jobs across backend, frontend, quality, security, RLS, linting, microservices |
| **Key test jobs** | `Backend Tests (pytest)`, `Backend MVP subset (pytest -m mvp)`, `RLS Baseline Tests (pytest -m rls)`, `Lint RLS Policies`, `Lint Tenant Context`, `Stale Feature Flags`, `GA Gate Score Check`, `Stale Default Check`, `Lint CLI/SDK OpenAPI parity`, `Lint OpenAPI completeness`, `Documentation Link Check`, `API Contract Test (OpenAPI Baseline)`, `Microservice Tests`, `Frontend Unit Tests (vitest)`, `Accessibility Tests` |
| **Services** | PostgreSQL, Redis (via docker-compose) |
| **DJANGO_SETTINGS_MODULE** | `hub.settings` (L284, L412, L471, L549, L621, L738, L1122, L1146, L1159) |
| **Notable** | Sets `PYTEST_DOCKER_COMPOSE_RUNTIME: "1"` (L1793) |

### 1.2 `e2e.yml` (11,032 bytes)

| Field | Value |
|---|---|
| **Name** | E2E Tests |
| **Triggers** | `push: [main, develop]`, `pull_request: [main, develop]`, `workflow_dispatch` |
| **Jobs** | E2E batch jobs (batched by marker) |
| **Notable** | Uses `workflow_e2e_coverage_report.py` |

### 1.3 `e2e-nightly-full.yml` (7,912 bytes)

| Field | Value |
|---|---|
| **Name** | E2E Nightly Full |
| **Triggers** | `schedule` (nightly cron), `workflow_dispatch` |
| **Jobs** | Full E2E suite — all batches |
| **Notable** | No PR trigger — purely nightly |

### 1.4 `e2e-pr-smoke.yml` (4,428 bytes)

| Field | Value |
|---|---|
| **Name** | E2E PR Smoke (Critical) |
| **Triggers** | `pull_request: [main, develop, staging]` with path filters |
| **Jobs** | Smoke tests only — critical path verification |
| **Notable** | Path-filtered for efficiency |

### 1.5 `e2e-metrics.yml` (10,047 bytes)

| Field | Value |
|---|---|
| **Name** | E2E Metrics Baseline |
| **Triggers** | `push: [main, develop, staging]`, `pull_request: [main, develop, staging]`, `workflow_dispatch` |
| **Jobs** | E2E hidden-failure metrics baseline |
| **Notable** | Produces `e2e-metrics.json` artifact |

### 1.6 `semantic-e2e.yml` (3,581 bytes)

| Field | Value |
|---|---|
| **Name** | Semantic E2E |
| **Triggers** | `pull_request` (path-filtered), `push: [main]` (path-filtered) |
| **Jobs** | Semantic/SPARQL-specific E2E tests |
| **Notable** | Path-filtered to semantic-related changes only |

### 1.7 `sdk-integration.yml` (3,178 bytes)

| Field | Value |
|---|---|
| **Name** | SDK Integration Tests |
| **Triggers** | `schedule` (nightly), `workflow_dispatch`, `push: [main]` (SDK path-filtered) |
| **Jobs** | SDK integration validation |
| **Notable** | Manual trigger for ad-hoc validation |

### 1.8 `test-marketplace-integration.yml` (28,102 bytes)

| Field | Value |
|---|---|
| **Name** | Marketplace Integration Tests |
| **Triggers** | `push: [main, develop]` (path-filtered), `pull_request: [main, develop]` (path-filtered), `schedule`, `workflow_dispatch` |
| **Jobs** | Marketplace connector integration tests |
| **Notable** | Large — extensive marketplace service verification |

### 1.9 `cli-sdk-nightly-regression.yml` (17,280 bytes)

| Field | Value |
|---|---|
| **Name** | (CLI/SDK Nightly Regression) |
| **Triggers** | `schedule` (nightly), `workflow_dispatch` |
| **Jobs** | CLI and SDK end-to-end regression tests |
| **Notable** | Nightly only — no PR gate |

### 1.10 `playwright-e2e.yml` (18,341 bytes)

| Field | Value |
|---|---|
| **Name** | Playwright E2E Tests |
| **Triggers** | `push: [main, develop]` (path-filtered), `pull_request: [main, develop]` (path-filtered), `workflow_dispatch` |
| **Jobs** | Frontend E2E tests via Playwright |

### 1.11 `playwright-e2e-strict.yml` (5,068 bytes)

| Field | Value |
|---|---|
| **Name** | Playwright E2E (strict mode) |
| **Triggers** | `pull_request: [main, develop, staging]`, `schedule`, `workflow_dispatch` |
| **Jobs** | Playwright E2E with `PLAYWRIGHT_STRICT=1` |
| **Notable** | Stricter assertions; runs on PR to staging |

### 1.12 `contracts-perf-benchmark.yml` (5,210 bytes)

| Field | Value |
|---|---|
| **Name** | Contracts perf benchmark (Phase 227 L8.6) |
| **Triggers** | `pull_request` (path-filtered), `push: [main, staging]` (path-filtered) |
| **Jobs** | Contract performance benchmarks |
| **Notable** | Phase 227 artifact — still active |

### 1.13 `perf-nightly.yml` (3,936 bytes)

| Field | Value |
|---|---|
| **Name** | Perf Nightly |
| **Triggers** | `schedule` (04:00 UTC nightly), `workflow_dispatch`, `push: [release/*]` |
| **Jobs** | Nightly performance regression suite |

### 1.14 `lineage-x-ci-gates.yml` (10,561 bytes)

| Field | Value |
|---|---|
| **Name** | Lineage X — cross-cutting CI gates |
| **Triggers** | `pull_request: [main, staging]`, `push: [main, staging]` |
| **Jobs** | Cross-cutting CI gates for lineage |

### 1.15 `openlineage-f4-dod.yml` (6,961 bytes)

| Field | Value |
|---|---|
| **Name** | OpenLineage F4 — DoD gates (k6 SLO + round-trip) |
| **Triggers** | `workflow_dispatch`, `push: tags: [f4-*]` (release tag only), `schedule` |
| **Jobs** | k6 SLO validation + round-trip tests |

### 1.16 Mutmut Mutation Testing (3 workflows)

| Workflow | Bytes | Trigger |
|---|---|---|
| `mutmut-asset-saga.yml` | 4,551 | `schedule`, `workflow_dispatch` |
| `mutmut-lineage-validator.yml` | 2,244 | `schedule`, `workflow_dispatch` |
| `mutmut-magic-bytes.yml` | 2,205 | `schedule`, `workflow_dispatch` |

All three are scheduled + manual dispatch only. No PR gating.

---

## 2. Supplementary Workflows

| Workflow | Bytes | Trigger | Notes |
|---|---|---|---|
| `test-results-reporting.yml` | 5,799 | `schedule`, `workflow_dispatch` | Meta-aggregator for test results across workflows |
| `frontend-tests.yml` | 6,674 | `push: [main, develop]`, `pull_request` (path-filtered) | Frontend unit/component tests |
| `visual-regression-playwright.yml` | 4,708 | `schedule`, `workflow_dispatch` | Visual regression snapshots |
| `chromatic.yml` | 1,081 | `push: [main, master]` (path-filtered), `workflow_dispatch` | Storybook visual testing |
| `deploy.yml` | 165,629 | (deploy triggers) | Contains smoke test steps post-deploy |

---

## 3. Trigger Analysis

### 3.1 Branch Coverage

| Branch | Workflows Triggered |
|---|---|
| `main` | 14 (ci, e2e, e2e-metrics, semantic-e2e, sdk-integration, test-marketplace, playwright, contracts-perf, lineage-x, openlineage, frontend-tests, visual-regression, chromatic, deploy) |
| `develop` | 8 (ci, e2e, e2e-metrics, test-marketplace, playwright, frontend-tests, deploy) |
| `staging` | 6 (e2e-metrics, e2e-pr-smoke, playwright-strict, contracts-perf, lineage-x, deploy) |
| `release/mvp-v1` | 1 (ci) |
| `release/*` | 1 (perf-nightly) |

### 3.2 Trigger Types

| Trigger | Count |
|---|---|
| `pull_request` | 12 |
| `push` | 11 |
| `schedule` | 11 |
| `workflow_dispatch` | 15 |

---

## 4. Overlap & Duplication Analysis

### 4.1 Overlapping Coverage

| Test Area | Workflows Covering It | Overlap |
|---|---|---|
| **E2E** | `e2e.yml`, `e2e-nightly-full.yml`, `e2e-pr-smoke.yml`, `e2e-metrics.yml`, `playwright-e2e.yml`, `playwright-e2e-strict.yml`, `semantic-e2e.yml` | **7 workflows** — PR smoke + full nightly + metrics baseline + Playwright variants + semantic-specific |
| **Performance** | `perf-nightly.yml`, `contracts-perf-benchmark.yml` | 2 workflows, different scope |
| **Mutation testing** | `mutmut-asset-saga.yml`, `mutmut-lineage-validator.yml`, `mutmut-magic-bytes.yml` | 3 workflows, separate targets |
| **Frontend** | `frontend-tests.yml`, `playwright-e2e.yml`, `playwright-e2e-strict.yml`, `visual-regression-playwright.yml`, `chromatic.yml` | **5 workflows** for frontend quality |

### 4.2 Consolidation Opportunities

1. **Merge `e2e.yml` + `e2e-nightly-full.yml` + `e2e-pr-smoke.yml`** — use a single workflow with conditional job execution based on trigger type (PR → smoke, push → full, schedule → full + metrics).
2. **Merge `playwright-e2e.yml` + `playwright-e2e-strict.yml`** — strict mode can be a matrix parameter.
3. **Merge 3 mutmut workflows** — use a matrix strategy for different mutation targets.

---

## 5. Gaps & Issues

### 5.1 Workflows Missing Timeouts

Several workflows lack explicit `timeout-minutes`:
- `cli-sdk-nightly-regression.yml` — no timeout found in header (17KB file, likely set per-job)
- `openlineage-f4-dod.yml` — push-triggered without timeout

### 5.2 Workflows That May Never Run

- `chromatic.yml` triggers on `push: [main, master]` with path filter — if `master` branch doesn't exist, the `master` trigger is dead.
- `openlineage-f4-dod.yml` triggers on `push: tags: [f4-*]` — only release tags, **not** every push. The `push:` key uses a `tags:` filter, so this is intentional and safe.

### 5.3 CI Resource Contention

The `ci.yml` workflow at 116KB is the largest by far. It contains 40+ jobs and runs on every PR to main/develop/release. This likely causes:
- Queue contention for self-hosted runners
- Long feedback cycles (all jobs must complete)
- Difficulty debugging individual job failures

---

## 6. `DJANGO_SETTINGS_MODULE` Usage in CI

All workflows consistently use `DJANGO_SETTINGS_MODULE: hub.settings`. There are NO references to `hub.test_settings_phase11` in any current CI workflow — confirming `test_settings_phase11.py` is legacy.

Workflows referencing `DJANGO_SETTINGS_MODULE`:
- `ci.yml` (9 occurrences — L284, L412, L471, L549, L621, L738, L1122, L1146, L1159)
- `lineage-snapshots-f5-dod.yml` (2 occurrences)
- `lineage-snapshots-f5-soak.yml` (1 occurrence)
- `api-naming-validation.yml` (1 occurrence)

---

## Recommendations

1. **Consolidate E2E workflows** — merge `e2e.yml`, `e2e-nightly-full.yml`, and `e2e-pr-smoke.yml` into one parameterized workflow.
2. **Consolidate Playwright workflows** — merge `playwright-e2e.yml` and `playwright-e2e-strict.yml` with strict mode as a matrix/input parameter.
3. **Consolidate mutmut workflows** — merge 3 mutmut workflows using a matrix strategy.
4. **Fix `chromatic.yml` trigger** — remove `master` branch reference if it doesn't exist.
5. **Add `timeout-minutes` to all workflows** — ensure no workflow can hang indefinitely.
6. **Consider splitting `ci.yml`** — at 116KB, it's a monolith. Split into logical sub-workflows (`backend-ci.yml`, `security-ci.yml`, `quality-ci.yml`).
7. **Archive `release/mvp-v1` branch reference** in `ci.yml` — if MVP-v1 is shipped, this branch trigger is dead.
