# Test Suite Gap Analysis

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-12  
**Status**: Draft — Engineering-grade review  
**Purpose**: In-depth gap analysis of unit, integration, e2e, security, performance, and related tests across backend, frontend, infra, and ops to identify gaps, problems, and improvements. A follow-up phase will organize gap fixes and test execution.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Backend Tests](#2-backend-tests)
3. [Frontend Tests](#3-frontend-tests)
4. [Security Tests](#4-security-tests)
5. [Performance Tests](#5-performance-tests)
6. [Concurrency, Regression, Smoke, Chaos, UAT](#6-concurrency-regression-smoke-chaos-uat)
7. [Use Case and User Journey Traceability](#7-use-case-and-user-journey-traceability)
8. [CI/CD and Test Execution](#8-cicd-and-test-execution)
9. [Infrastructure and Ops](#9-infrastructure-and-ops)
10. [Services (Non-Hub) Tests](#10-services-non-hub-tests)
11. [Gaps Summary Table](#11-gaps-summary-table)
12. [Recommendations and Next Steps](#12-recommendations-and-next-steps)

---

## 1. Executive Summary

### 1.1 Scope of Review

- **Backend**: Hub Django apps (`hub/apps/*`), root-level `tests/` (unit, integration, e2e, security, performance, concurrency, regression, smoke, chaos, UAT, SDK).
- **Frontend**: Vitest unit/component, Playwright E2E, accessibility.
- **Infra/Ops**: Docker Compose, K8s, monitoring, runbooks.
- **Use cases**: ~109 (USE_CASES.md); **User journeys**: 96 (USER_JOURNEYS.md); traceability in TEST_TRACEABILITY.md and TEST_COVERAGE_MATRIX.md.

### 1.2 Findings at a Glance

| Area | Strengths | Critical Gaps |
|------|-----------|----------------|
| **Backend** | Large suite (1,400+ test files), app-level and root-level tests, pytest markers, conftest with real DB/Redis. | Main CI runs `tests/unit/` and `tests/integration/` and `tests/e2e/` but **not** hub app unit tests by path; full `tests/security/` suite not in CI; platform app has no tests. |
| **Frontend** | Vitest + Playwright, journey-based E2E, phase specs. | Workflow references `test:component` and `test:a11y` and `test:coverage:check` which **do not exist** in `frontend/package.json`; risk of CI false pass or fail. |
| **Security** | ODPS ref resolver + penetration in CI; dedicated security workflow (Bandit, Safety, Trivy). | Broader security suite (`tests/security/`: IDOR, injection, AllowAny, etc.) **not** run in main CI. |
| **Performance** | Locust and pytest performance tests, baselines. | Performance suite **not** in main CI; run manually or separate pipeline. |
| **Traceability** | TEST_TRACEABILITY and TEST_COVERAGE_MATRIX document feature/UC/journey → tests. | Some doc references point to filenames that differ or are missing; 96 journeys vs finite E2E specs. |
| **CI** | Single CI runs unit (root) + integration + e2e + ODPS security; frontend and Playwright separate. | No single “run all tests” canonical flow; regression, concurrency, performance not in CI. |

---

## 2. Backend Tests

### 2.1 Structure and Conventions

- **Locations**:
  - **App-level**: `hub/apps/<app>/tests/test_*.py` (837+ test files under hub/apps).
  - **Root-level**: `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/security/`, `tests/performance/`, `tests/concurrency/`, `tests/regression/`, `tests/smoke/`, `tests/chaos/`, `tests/uat/`, `tests/sdk_python/`.
- **Config**: `pytest.ini` (markers: unit, integration, e2e, slow, performance, requires_services, e2e_batch1–5, security, etc.); `testpaths = hub/apps tests`.
- **Fixtures**: `tests/conftest.py` (Django/DB/Redis patches and shared fixtures); `tests/factories.py`; `tests/fixtures/` (ODPS, etc.).

### 2.2 Unit Tests

**Current state**:

- **Root unit**: `tests/unit/` — CLI, contracts, jobs, monitoring, notifications, rate_limiting, semantic, tenant_config, worker, plus standalone modules (event bus, Redis, ODPS fixtures, DPO workflows).
- **App-level**: Every major app has `tests/` with multiple `test_*.py` files (e.g. contracts, assets, auth, orchestration, marketplace).

**Gaps and issues**:

1. **CI command mismatch**: Main CI runs `pytest tests/unit/` (root unit only). It does **not** run `hub/apps/*/tests/` explicitly as “unit” in a dedicated step; app-level tests are included only because `testpaths = hub/apps tests` and the later steps run `tests/integration/` and `tests/e2e/`. So “unit” in CI is effectively “root unit only”; app-level unit tests run only as part of integration/e2e or not at all in the unit job. **Gap**: Clarify or fix so that “unit” in CI includes app-level unit tests (e.g. `pytest hub/apps/ tests/unit/ -m unit` or equivalent).
2. **Platform app**: `hub/apps/platform/` has no `tests/` directory (only `__init__.py`, `apps.py`, `urls.py`, `views.py`). **Gap**: Add unit (and if needed integration) tests for platform views/behavior or explicitly document as thin wrapper with no logic.
3. **Coverage**: Coverage is collected across unit + integration + e2e in CI. No separate coverage gate per layer (e.g. unit-only coverage threshold). **Improvement**: Consider unit-only coverage reporting and threshold.

### 2.3 Integration Tests

**Current state**:

- **Root**: `tests/integration/` — API endpoints, Docker Compose, use-case comprehensive tests (asset, contract, marketplace, data quality, compliance, billing, dataset, files, virtualization, observability, etc.), service availability, tenant isolation.
- **App-level**: Many apps have integration-style tests (e.g. contracts, orchestration, scheduled_ingestion, jobs).

**Gaps and issues**:

1. **Docker Compose runtime**: Docs (TEST_EXECUTION_PLAN.md) require `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and `--docker-compose-runtime` for integration; CI does **not** set `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and runs `pytest tests/integration/` without that marker. So either CI is not using the same contract as the doc, or the marker is optional and some tests skip. **Gap**: Align CI with TEST_EXECUTION_PLAN (either set env + marker or document that CI uses in-process/services started by CI job).
2. **Service discovery**: Some integration tests depend on microservices (datacontract, dq, compliance, semantic, worker). CI starts these in Docker. No single “integration test environment” doc that lists minimal required services for each test directory. **Improvement**: Document minimal service set per suite and ensure CI matches.

### 2.4 E2E Tests

**Current state**:

- **Root**: `tests/e2e/` — many modules (persona-based, contract, marketplace, scheduled ingestion/export, DQ, compliance, auth, tenant, rate limiting, workflows, etc.) plus `journey_results/` (JSON) and journey tracker.
- **Markers**: e2e_batch1–5 in pytest.ini for batching.

**Gaps and issues**:

1. **Execution time**: E2E suite is large; 60-minute timeout in E2E workflow. Risk of flakiness and resource contention. **Improvement**: Ensure E2E batches are balanced and can be run in parallel or with clear ordering (see TEST_EXECUTION_PLAN).
2. **Journey coverage**: Backend E2E tests reference journeys/use cases in names and docstrings; no automated check that every JOURNEY-* or UC-* in USER_JOURNEYS/USE_CASES has at least one test. **Gap**: Add traceability checks (e.g. script or CI step) from USE_CASES/USER_JOURNEYS to test files.

### 2.5 Backend Summary

| Item | Status | Action |
|------|--------|--------|
| App-level unit tests in CI | Unclear / partial | Define and run unit phase to include `hub/apps/` + `tests/unit/` |
| Platform app tests | Missing | Add tests or document as no-logic |
| Integration vs CI contract | Inconsistent | Align CI with TEST_EXECUTION_PLAN (Docker Compose runtime) |
| Unit-only coverage | Not split | Optional: unit-only coverage report and threshold |

---

## 3. Frontend Tests

### 3.1 Structure

- **Unit/component**: Vitest; `vitest.config.ts` includes `src/**/*.{test,spec}.{ts,tsx}`, excludes `e2e/**`.
- **E2E**: Playwright in `frontend/e2e/` — auth journeys (JOURNEY-AUTH-001–004), phase specs (phase3–phase7.5), journey folders (dpo, contracts-odps, marketplace-dc, dq-compliance-governance, governance-retention, integrations-jobs-webhooks, mesh-virtualization-search-ai, admin-audit-settings, scheduled-export, scheduled-ingestion), cross-cutting, templates.

### 3.2 Critical Gap: Missing npm Scripts

**Finding**: `.github/workflows/frontend-tests.yml` runs:

- `npm run test:component`
- `npm run test:a11y`
- `npm run test:coverage:check`

**Problem**: In `frontend/package.json`, these scripts **do not exist**. The package.json only has:

- `test`, `test:run`, `test:run:ci`, `test:ui`, `test:coverage`, `test:e2e*`, `test:e2e:routes*`.

So either:

1. The workflow will **fail** when it hits those steps, or  
2. The workflow was changed and these steps are skipped/optional (they are not marked `continue-on-error`).

**Gap**: Add `test:component`, `test:a11y`, and `test:coverage:check` to `frontend/package.json` (with appropriate Vitest/Playwright/axe commands), or remove those steps from the workflow and document that component and a11y are run differently (e.g. only in Playwright or manually).

### 3.3 Other Frontend Gaps

1. **Component tests**: No separate “component” script; Vitest already runs `src/**/*.{test,spec}.{ts,tsx}`. So “component” might mean “same as unit” or a subset. **Recommendation**: Define `test:component` (e.g. same as `test:run` or a pattern for components only) so CI is consistent.
2. **Accessibility (a11y)**: No `test:a11y` in package.json. Often a11y is run via Playwright with axe or in Vitest. **Recommendation**: Implement `test:a11y` (e.g. Playwright + axe or Vitest a11y) and add script.
3. **Coverage check**: No `test:coverage:check` script. **Recommendation**: Add script that fails if coverage falls below threshold (e.g. 80% lines/functions/branches) to match the PR comment thresholds.
4. **Traceability**: Frontend E2E specs are mapped in TEST_TRACEABILITY to journeys; not all 96 journeys have a dedicated frontend E2E spec. **Gap**: Document which journeys are covered by Playwright and which only by backend E2E.

### 3.4 Frontend Summary

| Item | Status | Action |
|------|--------|--------|
| test:component | Missing in package.json | Add or remove from workflow |
| test:a11y | Missing in package.json | Add (e.g. Playwright+axe) or remove from workflow |
| test:coverage:check | Missing in package.json | Add threshold check script |
| Journey coverage (frontend) | Partial | Document and optionally automate |

---

## 4. Security Tests

### 4.1 Current Coverage

- **In main CI**: ODPS ref resolver security (`hub.apps.contracts.tests.security.test_ref_resolver_security`), penetration (`tests.security.penetration_test_odps_ref_resolver`). Run in both a dedicated job and inside the main test job.
- **Dedicated workflow** (security-scan.yml): Dependency scan (Safety, pip-audit), Bandit (hub/, services/), Trivy container scan (api image). All with `continue-on-error: true` or conditional uploads.
- **Root security suite**: `tests/security/` — e.g. `test_allowany_public_endpoints.py`, `test_gateway_headers_forged.py`, `test_idor.py`, `test_injection.py`, `test_marketplace_security.py`, `test_phase25_security.py`, `test_production_secrets.py`, `test_security_features*.py`.

### 4.2 Gaps

1. **Full security suite not in CI**: The broad `tests/security/` suite (IDOR, injection, AllowAny, marketplace, production secrets, etc.) is **not** run in the main CI workflow. Only ODPS ref resolver and penetration tests are. **Gap**: Run `pytest tests/security/` in CI (e.g. in main test job or a dedicated security job with DB/Redis).
2. **Security workflow does not run app/security tests**: security-scan.yml focuses on dependency/static/container scans, not the functional security tests in `tests/security/`. **Gap**: Either add a job that runs `tests/security/` (with services) or document that these are run in a separate schedule/manual run.
3. **Continue-on-error**: Dependency and Bandit steps use `continue-on-error: true`, so failures do not fail the workflow. **Improvement**: Define policy (e.g. fail on high/critical, warn on medium) and reflect in workflow.

### 4.3 Security Summary

| Item | Status | Action |
|------|--------|--------|
| tests/security/ in CI | Not run | Add job or step to run pytest tests/security/ |
| Security vs quality policy | Soft | Decide fail vs warn for dependency/Bandit |

---

## 5. Performance Tests

### 5.1 Current State

- **Location**: `tests/performance/` — Locust files (load, stress, endurance, spike, API endpoints, DB, file upload/download, job queue, ODPS ingestion/ref resolution), pytest performance tests (baselines, marketplace, CLI/SDK, scheduled export, workflow, etc.).
- **Docs**: TEST_EXECUTION_PLAN and COMPREHENSIVE_TEST_PLAN describe performance test commands and baselines.

### 5.2 Gaps

1. **Not in main CI**: Performance tests are **not** run in the main CI or E2E workflows. They are intended for manual or scheduled runs. **Gap**: Document clearly that performance is out-of-band; optionally add a nightly or weekly job that runs a minimal performance smoke set.
2. **Baseline and environment**: Performance depends on environment (CPU, memory, services). **Improvement**: Document baseline environment and how to compare results (e.g. baseline manager and thresholds).

### 5.3 Performance Summary

| Item | Status | Action |
|------|--------|--------|
| Performance in CI | Not run | Document; optional nightly job |
| Baseline and env | Documented in plan | Keep and reference in runbooks |

---

## 6. Concurrency, Regression, Smoke, Chaos, UAT

### 6.1 Concurrency

- **Location**: `tests/concurrency/` — atomic operations, concurrent access, workflows, data consistency, locks, race conditions, shared state, synchronization, thread safety, workflow conflicts/recovery/state.
- **CI**: Not run in main CI. **Gap**: Document as out-of-band or add a (long-running) concurrency job (e.g. nightly).

### 6.2 Regression

- **Location**: `tests/regression/` — API endpoints, audit/health, auth, billing, DB, file storage, governance, integrations, job queue, middleware, phase25, phase26 CLI/SDK, tenant isolation, workflows.
- **CI**: Not run as a dedicated “regression” phase in main CI. Many of these may be covered by integration/e2e. **Gap**: Either run `pytest tests/regression/` in CI or document that regression is covered by integration + e2e and retire redundant tests.

### 6.3 Smoke

- **Location**: `tests/smoke/test_api_health.py` — health endpoints (main, semantic, datacontract, compliance, DQ), OpenAPI, API root, auth (unauthenticated rejected, login exists), tenants/assets/contracts existence.
- **Issue**: Smoke tests use `API_BASE_URL` default `http://localhost:8001` and direct microservice URLs (e.g. semantic 8082, datacontract 8081, compliance 8083, DQ 8084). Ports and service names may not match docker-compose (e.g. api-service often 8000). **Gap**: Align smoke test defaults with docker-compose and CI; run smoke in CI or in deploy pipeline.

### 6.4 Chaos

- **Location**: `tests/chaos/` — ODPS workflow chaos (service/network/DB failures, compensation, event replay) using real services.
- **CI**: Not run in main CI. **Gap**: Document as optional/manual or add to nightly.

### 6.5 UAT

- **Location**: `tests/uat/` — Django 6 compatibility (API, user-facing, SDK, general UAT).
- **CI**: Not run in main CI. **Gap**: Run on release branches or document as manual UAT.

### 6.6 Summary

| Suite | In CI? | Action |
|-------|--------|--------|
| Concurrency | No | Document or add nightly |
| Regression | No | Run in CI or merge into integration/e2e |
| Smoke | No | Align ports/env; add to CI or deploy |
| Chaos | No | Document or add nightly |
| UAT | No | Run on release or document |

---

## 7. Use Case and User Journey Traceability

### 7.1 Documentation

- **USE_CASES.md**: ~109 use cases with IDs (UC-*).
- **USER_JOURNEYS.md**: 96 journeys (JOURNEY-*), ~730+ steps.
- **TEST_TRACEABILITY.md**: Maps features, use cases, and journeys to backend and frontend tests; includes Phase 25/26 and gap remediation.
- **TEST_COVERAGE_MATRIX.md**: Feature/UC/journey/persona matrices; 29 features, status Complete/Partial.

### 7.2 Gaps

1. **Naming convention**: Traceability states backend tests should be named e.g. `test_uc_{id}_*.py` or `test_journey_{id}_*.py`. In practice, many tests are named by feature or persona (e.g. `test_*_use_cases_comprehensive.py`, `test_persona_*_comprehensive.py`). So traceability is by document, not by filename. **Improvement**: Either rename tests to UC/journey IDs where useful or keep current names and ensure traceability doc and matrix are the source of truth; add a script to list tests per UC/journey from doc or tags.
2. **Missing test files**: Some TEST_TRACEABILITY references (e.g. `test_retention_service.py`, `test_webhook_api_integration.py`, `test_scheduled_export/test_internal_worker_api.py`) may exist under different paths; a few referenced paths were verified to exist. **Improvement**: Audit all TEST_TRACEABILITY links to actual files and fix or remove broken references.
3. **96 journeys vs E2E count**: Backend E2E has many persona/journey tests; frontend has a limited set of journey specs. No automated “coverage of all 96 journeys” check. **Gap**: Add a traceability report (e.g. script) that lists which UC/journey have at least one backend or frontend test.

### 7.3 Traceability Summary

| Item | Status | Action |
|------|--------|--------|
| UC/journey naming | Inconsistent | Keep doc as source of truth; optional script per UC/journey |
| Broken doc links | Possible | Audit TEST_TRACEABILITY file paths |
| Coverage report | Manual | Add script or CI step for UC/journey coverage |

---

## 8. CI/CD and Test Execution

### 8.1 Workflows

- **ci.yml**: Lint, ODPS lint/format/scan, ODPS ref resolver security, ODPS versions, ODCS contracts, ODPS ref resolution, **test** (unit root + integration + e2e + ODPS security, with microservices), phase7 scheduled ingestion, Prefect integration, scheduled export, docker-build.
- **e2e.yml**: E2E tests (same stack), scheduled ingestion/export E2E, workflow coverage report.
- **frontend-tests.yml**: Typecheck, lint, test:run, **test:component**, **test:a11y**, test:coverage, **test:coverage:check** (all missing scripts).
- **playwright-e2e.yml**: Backend via docker compose, then Playwright (chromium).
- **security-scan.yml**: Dependency (Safety, pip-audit), Bandit, Trivy; no pytest tests/security/.

### 8.2 Gaps

1. **Single “run all” flow**: No one workflow or script that runs unit (app + root) → integration → e2e → security → (optional) performance/concurrency/regression in a defined order. Phase 12A scripts (`run_phase_12a_backend_suites.sh`, `run_phase_12a_full_suites.sh`) are referenced in docs; CI does not call them. **Gap**: Define canonical “full suite” (local and CI) and either use Phase 12A scripts or align CI jobs with that order.
2. **Redundancy**: Main CI and E2E workflow both run e2e tests (ci.yml runs `pytest tests/e2e/`, e2e.yml runs same). **Improvement**: Either run E2E only in e2e.yml and keep ci.yml for unit + integration, or document why both run E2E.
3. **Frontend workflow**: Will fail on missing scripts unless fixed (see Section 3).

### 8.4 CI Summary

| Item | Status | Action |
|------|--------|--------|
| Full suite definition | Scattered | Canonical order and scripts; align CI |
| E2E in both ci and e2e | Redundant | Clarify or deduplicate |
| Frontend scripts | Missing | Add test:component, test:a11y, test:coverage:check |

---

## 9. Infrastructure and Ops

### 9.1 Current State

- **Docker Compose**: docker-compose.yml, docker-compose.dev.yml, docker-compose.test.yml; used by tests and docs.
- **K8s**: `k8s/` with many manifests; no automated “k8s apply and run tests” in CI.
- **Monitoring**: Prometheus (alerts), Grafana (dashboards); `tests/integration/test_monitoring_infrastructure.py`, `test_prometheus_metrics.py`, `test_grafana_dashboards.py` exist.
- **Runbooks**: `runbooks/` (DB, deploy, DR, queue, scheduled export/ingestion, security, service); no automated “runbook validation” tests.

### 9.2 Gaps

1. **K8s**: No CI job that deploys to a test cluster and runs smoke or integration. **Gap**: Document as out-of-scope for current CI or add optional K8s test job.
2. **Runbooks**: No tests that assert runbook steps (e.g. “script X exists and is executable”). **Improvement**: Optional suite that checks runbook scripts and critical commands.
3. **Compose vs CI**: CI starts individual service containers; it does not use `docker-compose.test.yml` as a single stack. **Improvement**: Document difference and ensure service versions/ports match.

### 9.3 Infra Summary

| Item | Status | Action |
|------|--------|--------|
| K8s tests in CI | No | Document or add optional job |
| Runbook checks | No | Optional script/suite |
| Compose vs CI | Different | Document and align ports/env |

---

## 10. Services (Non-Hub) Tests

### 10.1 Current State

- **compliance-service**, **dq-service**, **semantic-service**, **event-schema-registry**, **worker**, **workflow-engine**, **workflow-registry**, **odh-integration**: Have their own `tests/` (unit/integration).
- **datacontract-service**: Has tests; CI runs ODCS validation from repo root and builds the image.
- **api** (Dockerfile only), **api-gateway**, **event-bus**, **observability-service**, **prefect-integration**, **search-service**, **webhook-service**: Limited or no test directories listed.

### 10.2 Gaps

1. **CI**: Main CI builds service images and runs Hub tests against them; it does not run each service’s own test suite (e.g. `pytest services/dq-service/tests/`). **Gap**: Optionally add a job per service or a matrix job to run service tests.
2. **Coverage**: No aggregated coverage across Hub + services. **Improvement**: Document; optional coverage merge.

### 10.3 Services Summary

| Item | Status | Action |
|------|--------|--------|
| Service-owned tests in CI | Not run | Optional: run services/*/tests in CI |
| Cross-service coverage | No | Document |

---

## 11. Gaps Summary Table

| # | Category | Gap | Severity | Suggested fix |
|---|----------|-----|----------|----------------|
| 1 | Backend / CI | Unit phase in CI runs only `tests/unit/`, not app-level unit explicitly | High | Run `pytest hub/apps/ tests/unit/ -m unit` or equivalent in CI |
| 2 | Backend | Platform app has no tests | Medium | Add tests or document as no-logic |
| 3 | Backend / CI | Integration: PYTEST_DOCKER_COMPOSE_RUNTIME not set in CI | Medium | Align CI with TEST_EXECUTION_PLAN |
| 4 | Frontend | test:component, test:a11y, test:coverage:check missing in package.json | High | Add scripts or remove workflow steps |
| 5 | Security | tests/security/ not run in CI | High | Add pytest tests/security/ to CI |
| 6 | Performance | Performance tests not in CI | Low | Document; optional nightly |
| 7 | Concurrency/Regression/Smoke/Chaos/UAT | None run in main CI | Medium | Document; run smoke in CI; optional nightly for rest |
| 8 | Smoke | Default ports (8001, 8081–8084) may not match compose/CI | Medium | Align API_BASE_URL and service URLs |
| 9 | Traceability | No automated UC/journey coverage check | Medium | Script or CI step listing tests per UC/journey |
| 10 | CI | No single canonical “full suite” run | Medium | Define and document; use Phase 12A or align CI |
| 11 | CI | E2E run in both ci.yml and e2e.yml | Low | Clarify or deduplicate |
| 12 | Infra | Smoke/runbook/K8s not automated | Low | Document; optional runbook/K8s checks |
| 13 | Services | Service-owned test suites not run in CI | Low | Optional matrix job for services/*/tests |

---

## 12. Recommendations and Next Steps

### 12.1 Immediate (Gap Fix)

1. **Frontend**: Add `test:component`, `test:a11y`, and `test:coverage:check` to `frontend/package.json` (or remove those steps from frontend-tests.yml and document).
2. **Security**: Add a CI job or step to run `pytest tests/security/` with required services (DB, Redis).
3. **Backend unit in CI**: Define “unit” phase to include both `hub/apps/` and `tests/unit/` and run it in CI.
4. **Smoke**: Align `tests/smoke/test_api_health.py` with docker-compose ports and service names; consider running smoke in CI or deploy pipeline.

### 12.2 Short-Term (Test Organization)

1. **Canonical full suite**: Define order (e.g. unit → integration → e2e → security → smoke) and implement via scripts (e.g. Phase 12A) and document in TEST_EXECUTION_PLAN. Optionally run regression/concurrency/performance in nightly.
2. **Traceability**: Audit TEST_TRACEABILITY file paths; add a script or CI step that reports which use cases/journeys have at least one test.
3. **CI cleanup**: Resolve E2E duplication between ci.yml and e2e.yml; ensure integration step matches TEST_EXECUTION_PLAN (Docker Compose runtime if required).

### 12.3 Follow-Up (Ongoing)

1. **Platform app**: Add tests or explicit “no logic” note.
2. **Performance/chaos/concurrency**: Run in nightly or release pipeline; document in runbooks.
3. **Services**: Optionally run each service’s test suite in CI (matrix or separate jobs).
4. **Runbooks**: Optional automated checks for runbook scripts and critical commands.

This gap analysis should be updated after fixes are applied and when test strategy or scope changes.

**Implementation plan**: [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) — comprehensive plan to implement gap fixes and run the full test suite in batches of 100–200 tests, with fix → rerun cycles until all pass (no mocks/stubs; root-cause fixes only).
