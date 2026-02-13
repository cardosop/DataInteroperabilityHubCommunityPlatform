# Test Execution Plan

**Document Version**: 1.1.0
**Last Updated**: 2026-02-08
**Status**: ✅ Active
**Task**: Phase 1.3 - Test Execution Plan Documentation; gapfix1 Phase 2.1 - Six mandatory principles and test pyramid order (2.1.1, 2.1.2)

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Test Execution Commands](#test-execution-commands)
4. [Test Execution Order](#test-execution-order)
5. [Parallelization Strategy](#parallelization-strategy)
6. [CI/CD Integration](#cicd-integration)
7. [Environment Configuration](#environment-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Overview

This document provides comprehensive, engineering-grade test execution commands, execution order, and parallelization strategies for the Data Interoperability Hub platform. All commands follow best practices and use real services (no mocks/stubs except at external boundaries).

**Related**: [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) — plan to implement gap fixes and run the full suite in batches of 100–200 tests with fix → rerun cycles until all pass. **Canonical full suite definition**: [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md) — single place for run order, commands per step, and CI vs nightly/manual.

### Mandatory Test Quality Principles (Six Principles)

These six principles are enforced throughout all test phases. Canonical source: [testreview1/tasks.md](../openspec/changes/testreview1/tasks.md) (MANDATORY TEST QUALITY PRINCIPLES).

1. **Real Services Only**: All tests MUST use real services, real databases, real APIs, and real infrastructure. No mock or stub implementations permitted except at external process boundaries (e.g., third-party APIs). All mocks/stubs must be audited, removed, and replaced with real implementations.
2. **No Error Masking**: Tests MUST NOT mask errors or problems. All error conditions must be tested explicitly. No silent exception catching or skipped error scenarios.
3. **Root Cause Fixes**: When tests fail or are flaky, root cause MUST be identified and fixed. No workarounds, bypasses, retries without fixes, or "skip if flaky" patterns permitted.
4. **No Quality Reduction**: Software quality MUST NOT be reduced to make tests pass. Application code must be fixed, not tests relaxed.
5. **Never Bypass Problems**: Problems MUST be fixed at root cause. No bypassing, ignoring, or working around problems.
6. **Development Best Practices**: All tests MUST follow TDD, DRY, SOLID, clean code, and Django best practices.

### Test Types

- **Unit Tests**: Fast, isolated component tests (< 1 second per test)
- **Integration Tests**: Service interaction and API endpoint tests (5-30 seconds per test)
- **E2E Tests**: Complete user journey tests (30-300 seconds per test)
- **Security Tests**: Security and vulnerability tests (10-60 seconds per test)
- **Performance Tests**: Load and performance tests (5-60 minutes per test)
- **Concurrency Tests**: Race condition and thread safety tests (5-20 minutes per test)
- **Regression Tests**: Existing functionality verification tests (5-30 seconds per test)
- **Frontend Unit Tests**: React component and utility tests (< 1 second per test)
- **Frontend E2E Tests**: Playwright browser-based tests (30-300 seconds per test)

---

## Prerequisites

### Environment Setup

1. **Python Environment**: Python 3.12+ with virtual environment activated
2. **Django Settings**: `DJANGO_SETTINGS_MODULE=hub.settings` must be set
3. **Database**: PostgreSQL database accessible (test database created automatically)
4. **Redis**: Redis server running (for rate limiting and job queue tests)
5. **Docker Compose**: For integration and E2E tests requiring services
6. **Node.js**: Node.js 18+ for frontend tests

### Required Packages

**Backend Test Dependencies**:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Frontend Test Dependencies**:
```bash
cd frontend && npm install
```

### Service Dependencies

**For Integration/E2E Tests**:
- PostgreSQL (database)
- Redis (caching, rate limiting, job queue)
- MinIO/S3 (file storage)
- External microservices (DQ, Compliance, Semantic) - optional, can be mocked at external boundary

**For Docker Compose Runtime Tests**:
```bash
# Start services
docker compose -f docker-compose.dev.yml up -d

# Verify services are ready
./scripts/health-checks/health-check-all.sh
```

### Docker Compose and test runtime (integration and E2E)

Integration and E2E tests require a running stack. Use one of the following so `pytest tests/integration/ -v --docker-compose-runtime` and E2E run consistently with no silent dependency gaps.

#### Compose files and when to use them

| File | Purpose | API service name | Use for |
|------|---------|------------------|--------|
| `docker-compose.yml` | Production-style full stack | `api-service` | Production, full stack testing |
| `docker-compose.dev.yml` | Development with hot-reload | `api-service` | Local dev and running integration/E2E from host |
| `docker-compose.test.yml` | Test stack (isolated DB, test config) | `api-service-test` | Dedicated test runs; use `COMPOSE_FILE=docker-compose.test.yml` and scripts that support it |

#### Minimal services for integration and E2E

All three compose files provide at least:

- **Postgres** (database)
- **Redis** (cache and queue instances as defined in each file)
- **API service** (Django app; `api-service` or `api-service-test`)
- **MinIO** (object storage for file tests)
- **Worker service** (for job/queue tests when required)

Optional for specific tests: Fuseki, semantic-service, dq-service, compliance-service, prefect-server, etc. Bring up the full stack or the minimal set required by the suite; see `docs/DOCKER_COMPOSE_DEPLOYMENT.md` for per-service startup.

#### Environment variable required for integration and E2E

Set **`PYTEST_DOCKER_COMPOSE_RUNTIME=1`** when running integration or E2E with `--docker-compose-runtime`, so tests that depend on the compose runtime are selected and behave correctly:

```bash
export PYTEST_DOCKER_COMPOSE_RUNTIME=1
pytest tests/integration/ -v --docker-compose-runtime
pytest tests/e2e/ -v --docker-compose-runtime
```

Or inline:

```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime
```

#### Consistent run (recommended)

1. **Start the stack** (choose one):
   - Dev: `docker compose -f docker-compose.dev.yml up -d`
   - Test: `COMPOSE_FILE=docker-compose.test.yml docker compose up -d`
   - Full: `docker compose -f docker-compose.yml up -d`
2. **Wait for services** (e.g. health checks or `docker compose ps`).
3. **Run tests** with `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and `--docker-compose-runtime` as in this document.

Phase 12A scripts (`scripts/run_phase_12a_backend_suites.sh`, `scripts/run_phase_12a_full_suites.sh`) assume the stack is already up and use the default compose file unless `COMPOSE_FILE` is set; when `COMPOSE_FILE=docker-compose.test.yml` they use the `api-service-test` service name so integration and E2E run consistently against the test stack.

---

## Test Execution Commands

### Unit Tests

**Description**: Fast, isolated tests for individual components, business logic, and utilities.

**Command**:
```bash
pytest hub/apps/*/tests/test_*.py -v --cov=hub --cov-report=html --cov-report=term
```

**CI/CD Command** (with XML and JUnit reports):
```bash
pytest hub/apps/*/tests/test_*.py -v \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=unit-test-results.xml \
  --tb=short
```

**With Markers**:
```bash
pytest hub/apps/*/tests/test_*.py -v -m unit --cov=hub --cov-report=html
```

**Specific App**:
```bash
pytest hub/apps/assets/tests/ -v --cov=hub.apps.assets --cov-report=html
```

**Specific Test File**:
```bash
pytest hub/apps/assets/tests/test_asset_crud.py -v
```

**Specific Test Class/Method**:
```bash
pytest hub/apps/assets/tests/test_asset_crud.py::TestAssetCRUD::test_create_asset -v
```

**Parallel Execution**:
```bash
pytest hub/apps/*/tests/test_*.py -v -n auto --cov=hub --cov-report=html
```

**Exclude Integration/E2E**:
```bash
pytest hub/apps/*/tests/test_*.py -v -m "unit and not integration and not e2e" --cov=hub
```

**Duration**: 5-10 minutes
**Per Test**: < 1 second
**Parallel**: Yes (recommended)

---

### Integration Tests

**Description**: Tests for API endpoints, service interactions, and cross-service integration.

**Command** (with Docker Compose runtime):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime
```

**Command** (services already running):
```bash
pytest tests/integration/ -v
```

**With Coverage**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime --cov=hub --cov-report=html
```

**CI/CD Command** (with XML and JUnit reports, append coverage):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-append \
  --junit-xml=integration-test-results.xml \
  --tb=short
```

**Specific Integration Test**:
```bash
pytest tests/integration/test_auth_apis_comprehensive.py -v --docker-compose-runtime
```

**With Markers**:
```bash
pytest tests/integration/ -v -m "integration and docker_compose_runtime" --docker-compose-runtime
```

**Parallel Execution** (where possible):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime -n auto
```

**Note**: Some integration tests may require sequential execution due to shared state or resource constraints.

**Duration**: 15-30 minutes
**Per Test**: 5-30 seconds
**Parallel**: Yes (where possible, with caution)

---

### E2E Tests

**Description**: End-to-end tests for complete user journeys and full-stack workflows.

**Command** (with Docker Compose runtime):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime
```

**Command** (services already running):
```bash
pytest tests/e2e/ -v
```

**With Coverage**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime --cov=hub --cov-report=html
```

**CI/CD Command** (with XML and JUnit reports, append coverage):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-append \
  --junit-xml=e2e-test-results.xml \
  --tb=short
```

**Specific E2E Test**:
```bash
pytest tests/e2e/test_marketplace_comprehensive.py -v --docker-compose-runtime
```

**E2E Batches** (for parallel execution):
```bash
# Batch 1: Core API, Contracts, Assets
pytest tests/e2e/ -v -m e2e_batch1 --docker-compose-runtime

# Batch 2: Worker Service, Jobs, DQ, Compliance
pytest tests/e2e/ -v -m e2e_batch2 --docker-compose-runtime

# Batch 3: Email, Notifications, Rate Limiting
pytest tests/e2e/ -v -m e2e_batch3 --docker-compose-runtime

# Batch 4: Tenant Config, Personas, CLI
pytest tests/e2e/ -v -m e2e_batch4 --docker-compose-runtime

# Batch 5: Marketplace, Semantic, Monitoring, Edge Cases
pytest tests/e2e/ -v -m e2e_batch5 --docker-compose-runtime
```

**E2E in CI vs E2E workflow (Gap 11)**: Backend E2E (`tests/e2e/`) runs in **two places** by design:

| Where | Purpose | Trigger |
|-------|---------|---------|
| **ci.yml** (test job) | PR/main gate: run `tests/e2e/` in the same job as unit and integration so every push/PR gets a single consistent gate (smoke → unit → integration → e2e). Same services (Postgres, Redis, microservices). Fast feedback. |
| **e2e.yml** (E2E workflow) | Dedicated E2E validation: full `tests/e2e/` plus **scheduled ingestion** and **scheduled export** E2E tests that require Prefect (separate stack, 60 min timeout). Used for deeper E2E coverage and workflow_dispatch. |

We do **not** deduplicate into one place: the CI gate keeps a single job for developer feedback; the E2E workflow provides extended E2E (Prefect, scheduled flows) and can be run on demand. See [.github/workflows/README.md](../.github/workflows/README.md).

**Sequential Execution** (recommended for full stack):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime -x
```

**Duration**: 30-60 minutes
**Per Test**: 30-300 seconds
**Parallel**: Sequential recommended (full stack)

---

### Security Tests

**Description**: Security and vulnerability tests for authentication, authorization, secrets, CORS, and security features.

**Command**:
```bash
pytest tests/security/ -v -m security
```

**CI/CD Command** (with XML and JUnit reports):
```bash
pytest tests/security/ -v -m security \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-append \
  --junit-xml=security-test-results.xml \
  --tb=short
```

**With Verbose Output**:
```bash
pytest tests/security/ -v -m security --tb=long
```

**Specific Security Test**:
```bash
pytest tests/security/test_security_features.py -v
```

**Parallel Execution**:
```bash
pytest tests/security/ -v -m security -n auto
```

**Duration**: 10-20 minutes
**Per Test**: 10-60 seconds
**Parallel**: Yes

---

### Performance Tests

**Description**: Load and performance tests using Locust for throughput, latency, and resource utilization.

**Prerequisites**:
```bash
# Start API server
python hub/manage.py runserver

# Create test users (optional)
python tests/performance/setup_test_users.py

# Or set environment variables
export PERF_TEST_USER_EMAIL=perf-test@example.com
export PERF_TEST_USER_PASSWORD=perf-test-password-123
```

**Command** (using pytest):
```bash
pytest tests/performance/ -v -m performance
```

**Command** (using Locust script - recommended):
```bash
# Run all performance tests
./tests/performance/run_performance_tests.sh

# Run specific test type
TEST_TYPE=api ./tests/performance/run_performance_tests.sh
TEST_TYPE=file ./tests/performance/run_performance_tests.sh
TEST_TYPE=job ./tests/performance/run_performance_tests.sh
TEST_TYPE=db ./tests/performance/run_performance_tests.sh
```

**Custom Parameters**:
```bash
API_HOST=http://localhost:8000 \
USERS=100 \
SPAWN_RATE=10 \
RUN_TIME=10m \
TEST_TYPE=all \
./tests/performance/run_performance_tests.sh
```

**Interactive Locust UI**:
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000
# Then open http://localhost:8089 in browser
```

**With Baseline Comparison**:
```bash
pytest tests/performance/ -v -m performance --performance-baseline
```

**Duration**: 60-120 minutes
**Per Test**: 5-60 minutes
**Parallel**: Sequential (resource intensive)

---

### Concurrency Tests

**Description**: Tests for race conditions, thread safety, concurrent workflows, and shared state protection.

**Note**: Concurrency tests are integrated into other test suites (unit, integration, E2E) rather than having a dedicated directory. They are marked with appropriate markers.

**Command** (from unit tests):
```bash
pytest hub/apps/*/tests/test_*.py -v -m "unit and concurrency"
```

**Command** (from integration tests):
```bash
pytest tests/integration/ -v -m "integration and concurrency" --docker-compose-runtime
```

**Command** (from E2E tests):
```bash
pytest tests/e2e/ -v -m "e2e and concurrency" --docker-compose-runtime
```

**Sequential Execution** (required for concurrency testing):
```bash
pytest hub/apps/*/tests/test_*.py -v -m concurrency
```

**Duration**: 20-40 minutes
**Per Test**: 5-20 minutes
**Parallel**: Sequential (test concurrency)

---

### Regression Tests

**Description**: Tests to verify existing functionality hasn't regressed after changes.

**Command**:
```bash
pytest tests/regression/ -v -m regression
```

**With Coverage**:
```bash
pytest tests/regression/ -v -m regression --cov=hub --cov-report=html
```

**Specific Regression Test**:
```bash
pytest tests/regression/test_api_endpoints.py -v
```

**Parallel Execution** (where possible):
```bash
pytest tests/regression/ -v -m regression -n auto
```

**Duration**: 30-60 minutes
**Per Test**: 5-30 seconds
**Parallel**: Yes (where possible)

---

### Frontend Unit Tests

**Description**: React component tests, utility tests, and frontend logic tests using Vitest.

**Command**:
```bash
cd frontend && npm test
```

**With UI**:
```bash
cd frontend && npm run test:ui
```

**With Coverage**:
```bash
cd frontend && npm run test:coverage
```

**Watch Mode**:
```bash
cd frontend && npm test -- --watch
```

**Specific Test File**:
```bash
cd frontend && npm test -- src/components/AssetCard.test.tsx
```

**Duration**: 2-5 minutes
**Per Test**: < 1 second
**Parallel**: Yes (default)

---

### Frontend E2E Tests

**Description**: Browser-based end-to-end tests using Playwright for complete user journeys.

**Prerequisites**:
```bash
# Install Playwright browsers (first time only)
cd frontend && npx playwright install

# Start backend services
docker compose -f docker-compose.dev.yml up -d

# Start frontend dev server (in separate terminal)
cd frontend && npm run dev
```

**Command**:
```bash
cd frontend && npm run test:e2e
```

**With UI**:
```bash
cd frontend && npm run test:e2e:ui
```

**Headed Mode** (visible browser):
```bash
cd frontend && npm run test:e2e:headed
```

**Debug Mode**:
```bash
cd frontend && npm run test:e2e:debug
```

**Specific Journey**:
```bash
cd frontend && npm run test:e2e -- e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts
```

**Route-Based Tests**:
```bash
cd frontend && npm run test:e2e:routes
```

**Batch Execution**:
```bash
# Batch 1
cd frontend && npm run test:e2e:routes:batch1

# Batch 2
cd frontend && npm run test:e2e:routes:batch2

# Batch 3
cd frontend && npm run test:e2e:routes:batch3
```

**Duration**: 30-60 minutes
**Per Test**: 30-300 seconds
**Parallel**: Sequential recommended (browser-based)

---

### Full Test Suite

**Description**: Run all backend tests (unit + integration + E2E + security + regression).

**Command**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime --cov=hub --cov-report=html --cov-report=term
```

**CI/CD Command** (with XML and JUnit reports):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=test-results.xml \
  --tb=short
```

**Excluding Performance**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime -m "not performance" --cov=hub --cov-report=html
```

**With JSON Report**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime --cov=hub --cov-report=html --json-report --json-report-file=test-results.json
```

**Duration**: 60-120 minutes
**Coverage**: All test types

---

## Test Execution Order

### Test Pyramid and Suite Order (Mandatory)

The test pyramid and suite execution order MUST follow this sequence (unit → integration → E2E → security → performance → concurrency → regression). This order is required by the test strategy (gapfix1 Phase 2.1.2, testreview1) and maximizes efficiency while catching failures early. Full commands and rationale are in [Recommended Execution Order](#recommended-execution-order) below.

| Order | Suite        | Rationale |
|-------|--------------|------------|
| 1     | Unit         | Fast, no dependencies; catch quick failures early |
| 2     | Integration  | Service dependencies; verify API and service interactions |
| 3     | E2E          | Full stack; verify complete user journeys |
| 4     | Security     | Independent verification; can run parallel with E2E where appropriate |
| 5     | Performance  | Long-running, resource intensive |
| 6     | Concurrency  | Race conditions and thread safety; sequential execution |
| 7     | Regression   | Verify existing functionality; run after other suites pass |

### Recommended Execution Order

Tests should be executed in the following order to maximize efficiency and catch failures early:

#### 1. Unit Tests (First)
- **Rationale**: Fast, no dependencies, catch quick failures early
- **Duration**: 5-10 minutes (target &lt; 15–20 min; split into multiple jobs if needed)
- **Command (canonical)**: `pytest hub/apps/ tests/unit/ -v -m "not integration and not e2e" --cov=hub --cov-report=xml --cov-report=term-missing --junit-xml=unit-test-results.xml --tb=short`
- **Exclusion**: The unit phase does **not** include `tests/integration/` or `tests/e2e/` (path-based). Tests under `hub/apps/` that are marked `integration` or `e2e` are excluded by marker `-m "not integration and not e2e"` so the unit job stays fast. See Gap #1 (task 1.3) in GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md.
- **Parallel**: Yes
- **Stop on Failure**: Optional (`-x` flag)

#### 2. Integration Tests (Second)
- **Rationale**: Service dependencies required, verify API endpoints and service interactions
- **Duration**: 15-30 minutes
- **Command**: `PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime`
- **Parallel**: Yes (where possible)
- **Prerequisites**: Docker Compose services running
- **CI (Gap #3, task 1.7):** In `.github/workflows/ci.yml`, the "Run integration tests" step sets `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and passes `--docker-compose-runtime` so integration tests that require the compose runtime are not skipped for wrong env. CI uses GitHub Actions services (postgres, redis) and docker-run microservices (datacontract, dq, compliance, semantic, worker) on localhost; tests that need full docker-compose networking may still skip or fail in CI. **Alignment with local:** For local runs use `docker-compose.test.yml` (e.g. `docker compose -f docker-compose.test.yml up -d`), then run the same command with `PYTEST_DOCKER_COMPOSE_RUNTIME=1` and `--docker-compose-runtime` so the same set of integration tests runs. See [Environment Configuration](#environment-configuration) and the variable `PYTEST_DOCKER_COMPOSE_RUNTIME` in the table there.

#### 3. E2E Tests (Third)
- **Rationale**: Full stack required, verify complete user journeys
- **Duration**: 30-60 minutes
- **Command**: `PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime`
- **Parallel**: Sequential recommended
- **Prerequisites**: All services running

#### 4. Security Tests (Fourth - Parallel with E2E)
- **Rationale**: Can run in parallel with E2E tests, independent verification
- **Duration**: 10-20 minutes
- **Command**: `pytest tests/security/ -v -m security`
- **Parallel**: Yes
- **Can Run With**: E2E tests (parallel)

#### 5. Performance Tests (Fifth)
- **Rationale**: Long-running, resource intensive, verify performance targets
- **Duration**: 60-120 minutes
- **Command**: `./tests/performance/run_performance_tests.sh`
- **Parallel**: Sequential (resource intensive)
- **Prerequisites**: API server running, test users created

#### 6. Concurrency Tests (Sixth)
- **Rationale**: Test concurrency behavior, requires sequential execution
- **Duration**: 20-40 minutes
- **Command**: `pytest hub/apps/*/tests/test_*.py tests/integration/ -v -m concurrency`
- **Parallel**: Sequential (test concurrency)
- **Note**: Integrated into other test suites

#### 7. Regression Tests (Seventh)
- **Rationale**: Verify existing functionality hasn't regressed
- **Duration**: 30-60 minutes
- **Command**: `pytest tests/regression/ -v -m regression`
- **Parallel**: Yes (where possible)
- **Run After**: All other tests pass

#### Smoke Tests (after API and services are up)
- **Rationale**: Quick health checks for API and microservices; run once the stack is up (Gap #8, task 1.4).
- **Duration**: 1-2 minutes
- **Command**: `pytest tests/smoke/ -v --tb=short --junit-xml=smoke-test-results.xml`
- **Defaults**: Aligned with `docker-compose.test.yml` host ports — `API_BASE_URL=http://localhost:8001`, `DATACONTRACT_SERVICE_URL=http://localhost:8093`, `DQ_SERVICE_URL=http://localhost:8084`, `COMPLIANCE_SERVICE_URL=http://localhost:8085`, `SEMANTIC_SERVICE_URL=http://localhost:8086`. Override in CI (API on 8000, services on 8080/8083/8082/8081).
- **CI**: In `ci.yml`, smoke runs after migrations and after the API server is started (same job as unit/integration/E2E); JUnit artifact `smoke-test-results.xml` is uploaded.
- **Local**: With `docker-compose.test.yml` up, run `pytest tests/smoke/ -v` from repo root (no env needed). See GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md §4.4.
- **Full suite (Phase 12A, task 4.1b)**: The Phase 12A full run **includes smoke**. When you run `scripts/run_phase_12a_full_suites.sh`, smoke runs after 12A.1 (backend) as step 12A.1.5; artifacts are under `test_reports_comprehensive/{date}/smoke/` (`smoke.log`, `junit.xml`). Smoke failure fails the full suite. This is the **single canonical place** that states the full suite includes smoke and where it runs.

### Execution Flow Diagram

```
┌─────────────────┐
│  Unit Tests     │ (5-10 min, parallel)
└────────┬────────┘
         │ Pass?
         ▼
┌─────────────────┐
│ Integration     │ (15-30 min, parallel where possible)
│ Tests           │
└────────┬────────┘
         │ Pass?
         ▼
┌─────────────────┐     ┌─────────────────┐
│  E2E Tests      │     │ Security Tests  │ (parallel)
│  (Sequential)   │     │  (Parallel)     │
└────────┬────────┘     └─────────────────┘
         │ Pass?
         ▼
┌─────────────────┐
│ Performance     │ (60-120 min, sequential)
│ Tests           │
└────────┬────────┘
         │ Pass?
         ▼
┌─────────────────┐
│ Concurrency     │ (20-40 min, sequential)
│ Tests           │
└────────┬────────┘
         │ Pass?
         ▼
┌─────────────────┐
│ Regression      │ (30-60 min, parallel where possible)
│ Tests           │
└─────────────────┘
```

### Phase 12A.2 — Frontend unit and E2E tests (runnable)

Phase 12A.2 runs after backend suites (Phase 12A.1). It is used by the full Phase 12A execution (e.g. `scripts/run_phase_12a_full_suites.sh`) and by gapfix1/testreview1 validation. Commands are runnable from the project root; artifacts are written under `test_reports_comprehensive/{date}/`.

#### 12A.2.1 Frontend unit tests

**Command** (interactive / watch):
```bash
cd frontend && npm test
```

**Command for scripted/CI / Phase 12A** (run once, then exit):
```bash
cd frontend && npm run test:run
```
Use this in automation (e.g. `scripts/run_phase_12a_full_suites.sh`) so Vitest does not stay in watch mode.

**With coverage** (for evidence):
```bash
cd frontend && npm run test:coverage
```

**Duration**: 2–5 minutes.  
**Artifacts**: When run via `scripts/run_phase_12a_full_suites.sh`, output is captured in `test_reports_comprehensive/{date}/frontend-unit/frontend-unit.log`. For JUnit/coverage in that layout, use `scripts/collect_test_evidence.sh` or run with Vitest reporters configured to write under that path.

**Prerequisites**: `cd frontend && npm install`. No backend required (only external HTTP mocked at axios/apiClient boundary).

#### 12A.2.2 Frontend E2E tests

**Prerequisites**:
```bash
cd frontend && npx playwright install
# Backend and frontend dev server running for full E2E (e.g. docker compose up; npm run dev)
```

**Command**:
```bash
cd frontend && npm run test:e2e
```

**Duration**: 10–60 minutes (depends on journey count and backend).  
**Artifacts**: When run via `scripts/run_phase_12a_full_suites.sh`, output is in `test_reports_comprehensive/{date}/frontend-e2e/frontend-e2e.log`. Playwright reports (screenshots, traces, videos) can be collected to `frontend-e2e/` per `docs/EVIDENCE_COLLECTION_PLAN.md`.

#### 12A.2.3 Evidence layout

| Step       | Command (scripted/CI)      | Artifact path (under `test_reports_comprehensive/{date}/`) |
|-----------|----------------------------|------------------------------------------------------------|
| 12A.2.1   | `cd frontend && npm run test:run` | `frontend-unit/` (e.g. `frontend-unit.log`)                |
| 12A.2.2   | `cd frontend && npm run test:e2e` | `frontend-e2e/` (e.g. `frontend-e2e.log`, Playwright report) |

#### Phase 12A.3 — Security, performance, concurrency, regression (runnable)

Phase 12A.3 runs after 12A.2 when the full Phase 12A script is used. It is executed **inside the api-service container** by `scripts/run_phase_12a_full_suites.sh`. If `api-service` is not running, 12A.3 is skipped and a summary is written with `"skipped": true`. Failures are not masked: each suite’s exit code is recorded and the script exits with status 1 if any suite failed.

| Step     | Suite        | Command (inside container)     | Artifact path (under `test_reports_comprehensive/{date}/`) |
|----------|--------------|---------------------------------|-------------------------------------------------------------|
| 12A.3.1  | Security     | `pytest tests/security/ -v --junit-xml=...`  | `security/` (`security.log`, `junit.xml`)   |
| 12A.3.2  | Performance  | `pytest tests/performance/ -v --junit-xml=...`| `performance/` (`performance.log`, `junit.xml`) |
| 12A.3.3  | Concurrency  | `pytest tests/concurrency/ -v --junit-xml=...`| `concurrency/` (`concurrency.log`, `junit.xml`) |
| 12A.3.4  | Regression   | `pytest tests/regression/ -v --junit-xml=...` | `regression/` (`regression.log`, `junit.xml`) |

**Summary artifact**: `test_reports_comprehensive/{date}/phase_12a_3_summary.json` — contains each suite’s `exit_code` and `artifacts` path; used so CI/ops see failures (no masking).

**Performance note**: Phase 12A.3 runs **pytest** for `tests/performance/` only. Extended performance runs (Locust, `./tests/performance/run_performance_tests.sh`) are documented in [Performance Tests](#performance-tests) and can be run separately for load/stress evidence.

**Full Phase 12A (backend + frontend + 12A.3)**: Run `scripts/run_phase_12a_full_suites.sh` to execute 12A.1 (backend), 12A.2 (frontend), and 12A.3 (security, performance, concurrency, regression) and populate the same date-based layout.

**Affected frontend features (gapfix1)**: Scheduled Export has frontend unit tests (service: `scheduledExportService.test.ts`; hooks: `useScheduledExport.test.tsx`; component: `ScheduledExportListPage.test.tsx`) and E2E (`e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts`). Only external HTTP (axios/apiClient) is mocked; hooks and services are real. Trust signals config API has no frontend UI yet; no frontend tests required until a UI is added.

---

## Parallelization Strategy

### Unit Tests

**Strategy**: Run in parallel (recommended)

**Command**:
```bash
pytest hub/apps/*/tests/test_*.py -v -n auto --cov=hub
```

**Rationale**:
- Fast execution (< 1 second per test)
- No shared state or dependencies
- Isolated components
- Maximizes CPU utilization

**Configuration**:
- Use `pytest-xdist` with `-n auto` (auto-detect CPU cores)
- Or specify worker count: `-n 4` (4 workers)

**Considerations**:
- Ensure tests are truly isolated (no shared database state)
- Use test database isolation per worker
- Monitor for race conditions (shouldn't occur in unit tests)

---

### Integration Tests

**Strategy**: Run in parallel where possible (with caution)

**Command**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v --docker-compose-runtime -n auto
```

**Rationale**:
- Moderate execution time (5-30 seconds per test)
- Some tests may share services/resources
- Can parallelize independent test suites

**Configuration**:
- Use `-n auto` for auto-detection
- Or limit workers: `-n 2` (2 workers) to reduce resource contention

**Considerations**:
- Some tests may require sequential execution due to:
  - Shared database state
  - Resource constraints (database connections, Redis)
  - Service dependencies
- Mark tests requiring isolation: `@pytest.mark.isolation`
- Run isolation tests separately: `pytest tests/integration/ -v -m isolation`

**Best Practice**:
- Group independent tests into batches
- Use markers to identify parallelizable tests: `@pytest.mark.parallel`
- Run isolation tests sequentially: `pytest tests/integration/ -v -m "not isolation" -n auto`

---

### E2E Tests

**Strategy**: Sequential recommended (full stack)

**Command**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v --docker-compose-runtime
```

**Rationale**:
- Full stack tests (30-300 seconds per test)
- Shared database state
- Resource intensive (database, Redis, services)
- Complex setup/teardown

**Alternative**: Batch Execution
- Use E2E batch markers for parallel batch execution:
```bash
# Run batches in parallel (separate processes)
pytest tests/e2e/ -v -m e2e_batch1 --docker-compose-runtime &
pytest tests/e2e/ -v -m e2e_batch2 --docker-compose-runtime &
pytest tests/e2e/ -v -m e2e_batch3 --docker-compose-runtime &
wait
```

**Considerations**:
- Database isolation per batch
- Service resource limits
- Test data cleanup between batches
- Monitor for resource exhaustion

---

### Security Tests

**Strategy**: Run in parallel

**Command**:
```bash
pytest tests/security/ -v -m security -n auto
```

**Rationale**:
- Independent security checks
- No shared state
- Can run concurrently

**Configuration**:
- Use `-n auto` for maximum parallelization
- Or limit workers: `-n 4` (4 workers)

---

### Performance Tests

**Strategy**: Sequential (resource intensive)

**Command**:
```bash
./tests/performance/run_performance_tests.sh
```

**Rationale**:
- Resource intensive (CPU, memory, network)
- Long-running (5-60 minutes per test)
- Requires dedicated resources
- Baseline comparison requires sequential execution

**Considerations**:
- Run one performance test at a time
- Ensure sufficient system resources
- Monitor system metrics during execution
- Compare against baseline metrics

---

### Concurrency Tests

**Strategy**: Sequential (test concurrency)

**Command**:
```bash
pytest hub/apps/*/tests/test_*.py tests/integration/ -v -m concurrency
```

**Rationale**:
- Tests concurrency behavior itself
- Requires controlled execution environment
- Sequential execution ensures accurate concurrency testing

**Considerations**:
- Do not parallelize concurrency tests
- Run in isolation from other tests
- Monitor for actual concurrency issues

---

### Regression Tests

**Strategy**: Run in parallel where possible

**Command**:
```bash
pytest tests/regression/ -v -m regression -n auto
```

**Rationale**:
- Moderate execution time (5-30 seconds per test)
- Independent verification tests
- Can parallelize independent test suites

**Configuration**:
- Use `-n auto` for auto-detection
- Or limit workers: `-n 2` (2 workers)

**Considerations**:
- Some regression tests may require sequential execution
- Use markers to identify parallelizable tests
- Run isolation tests separately

---

### Frontend Unit Tests

**Strategy**: Run in parallel (default)

**Command**:
```bash
cd frontend && npm test
```

**Rationale**:
- Vitest runs tests in parallel by default
- Fast execution (< 1 second per test)
- No shared state

**Configuration**:
- Vitest automatically parallelizes tests
- Configure in `vitest.config.ts` if needed

---

### Frontend E2E Tests

**Strategy**: Sequential recommended (browser-based)

**Command**:
```bash
cd frontend && npm run test:e2e
```

**Rationale**:
- Browser-based tests (30-300 seconds per test)
- Resource intensive (browser instances)
- Shared backend state

**Alternative**: Batch Execution
- Use route-based batches for parallel execution:
```bash
cd frontend && npm run test:e2e:routes:batch1 &
cd frontend && npm run test:e2e:routes:batch2 &
cd frontend && npm run test:e2e:routes:batch3 &
wait
```

**Considerations**:
- Browser resource limits
- Backend service capacity
- Test data isolation between batches

---

## CI/CD Integration

### CI/CD execution stages (gapfix1 Phase 5.1, aligned with testreview1 Phase 12)

Each stage runs commands from this document; artifacts are retained and linked from the test summary report where applicable. Canonical layout: `test_reports_comprehensive/{date}/` per [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md#directory-structure).

| Stage | Scope | Commands (from this plan) | Artifacts |
|--------|--------|---------------------------|-----------|
| **5.1.1 Pre-commit / fast** | Backend unit + frontend unit | Backend: `pytest hub/apps/*/tests/test_*.py -v -m unit -x`. Frontend: `cd frontend && npm run test:run`. | Optional JUnit/coverage; fast feedback only. |
| **5.1.2 PR** | Unit + integration (backend), frontend unit, optional E2E | Backend: unit + integration per [Pull Request](#pull-request) below (JUnit XML, coverage). Frontend: `cd frontend && npm run test:run` (or `npm run test:coverage`). Optionally E2E if fast. | Publish JUnit XML and coverage (e.g. Codecov, upload-artifact). |
| **5.1.3 Merge to main** | Full backend suite + frontend tests | Backend: `scripts/run_phase_12a_backend_suites.sh` (unit, integration, E2E). Frontend: `cd frontend && npm run test:run` and optionally `npm run test:e2e`. Or full: `scripts/run_phase_12a_full_suites.sh`. | Publish to `test_reports_comprehensive/{date}/` or CI artifact storage; retain 30 days. |
| **5.1.4 Nightly** | Full suite + security + performance | `scripts/run_phase_12a_full_suites.sh` (backend, frontend, security, performance, concurrency, regression). Then `scripts/generate_test_summary_report.sh $DATE`. | Publish test summary and evidence; retain per CI policy. |
| **5.1.5 Release (or release-prep)** | Full suite + security + performance + concurrency | Same as Nightly; full suite includes concurrency. Generate test summary report; retain evidence for sign-off per [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md). | `test_reports_comprehensive/{date}/`, summary report; retain for sign-off. |

Workflow mapping: see [.github/workflows/README.md — Workflow execution stages](../.github/workflows/README.md#workflow-execution-stages-gapfix1-phase-51).

---

### Pre-Commit Hook

**Test Type**: Unit tests (fast) — backend and frontend (5.1.1)

**Backend Command**:
```bash
pytest hub/apps/*/tests/test_*.py -v -m unit -x
```

**Frontend Command** (scripted, no watch):
```bash
cd frontend && npm run test:run
```

**Duration**: 5-10 minutes (backend); 2-5 minutes (frontend)
**Stop on Failure**: Yes (`-x` for backend)

---

### Pull Request

**Test Type**: Unit + Integration tests

**Command**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest hub/apps/*/tests/test_*.py tests/integration/ -v --docker-compose-runtime --cov=hub --cov-report=html
```

**CI/CD Command** (with XML and JUnit reports):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest hub/apps/*/tests/test_*.py tests/integration/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=pr-test-results.xml \
  --tb=short
```

**Frontend** (5.1.2): Run `cd frontend && npm run test:run` (or `npm run test:coverage` for coverage). Publish JUnit XML and coverage (e.g. `actions/upload-artifact`, Codecov).

**Duration**: 20-40 minutes
**Coverage**: Unit and integration tests (backend); frontend unit

---

### Merge to Main

**Test Type**: Full test suite (5.1.3)

**Command**:
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime --cov=hub --cov-report=html --cov-report=term
```

**CI/CD Command** (with XML and JUnit reports):
```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=merge-test-results.xml \
  --tb=short
```

**Artifacts**: Publish to `test_reports_comprehensive/{date}/` or CI artifact storage (e.g. `actions/upload-artifact`); retain 30 days. Use `scripts/run_phase_12a_backend_suites.sh` and frontend commands, or `scripts/run_phase_12a_full_suites.sh`.

**Duration**: 60-120 minutes
**Coverage**: All test types (unit, integration, E2E, security, regression)

---

### Nightly Builds

**Test Type**: Full suite + Performance + Security (5.1.4)

Performance, regression, and concurrency are **optional for the PR gate**; they run in nightly (or release) so main CI stays fast. Regression can also be run as the last batch in batched execution (`run_phase_12a_batched.sh`) or in nightly only. See [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md#ci-vs-nightly-vs-manual).

**Command**:
```bash
# Backend tests
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ tests/security/ -v --docker-compose-runtime \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=nightly-test-results.xml \
  --tb=short

# Performance tests (separate job)
./tests/performance/run_performance_tests.sh
```

**Recommended**: Run `scripts/run_phase_12a_full_suites.sh` then `scripts/generate_test_summary_report.sh $DATE`; publish test summary and evidence (e.g. workflow artifact).

**Duration**: 120-180 minutes
**Coverage**: All test types including performance and security

---

### Release Builds

**Test Type**: Full suite + Performance + Security + Concurrency (5.1.5)

**Command**:
```bash
# Backend tests
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/ tests/security/ -v --docker-compose-runtime -m "not performance" \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-report=html \
  --junit-xml=release-test-results.xml \
  --tb=short

# Performance tests (separate job)
./tests/performance/run_performance_tests.sh

# Concurrency tests (separate job)
pytest hub/apps/*/tests/test_*.py tests/integration/ -v -m concurrency \
  --cov=hub \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-append \
  --junit-xml=concurrency-test-results.xml \
  --tb=short
```

**Release (or release-prep)**: Run `scripts/run_phase_12a_full_suites.sh` (includes concurrency and regression); then `scripts/generate_test_summary_report.sh $DATE`. Retain evidence for sign-off per [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md).

**Duration**: 180-240 minutes
**Coverage**: All test types including concurrency tests

---

## Coverage Reporting

### Coverage Report Formats

**HTML Report** (for local viewing):
```bash
--cov-report=html
```
Generates `htmlcov/index.html` for interactive coverage browsing.

**XML Report** (for CI/CD integration):
```bash
--cov-report=xml
```
Generates `coverage.xml` for Codecov and other CI/CD tools.

**Terminal Report** (for console output):
```bash
--cov-report=term
--cov-report=term-missing  # Shows missing lines
```
Displays coverage summary in terminal with missing line numbers.

**Combining Coverage Reports**:
```bash
--cov-append
```
Appends coverage data to existing coverage file (useful for combining across test types).

### Coverage Threshold Checking

**Check Coverage Threshold** (example script):
```bash
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('coverage.xml')
root = tree.getroot()
line_rate = float(root.get('line-rate', 0))
coverage_percent = line_rate * 100
threshold = 80
if coverage_percent < threshold:
    print(f'❌ Coverage {coverage_percent:.2f}% is below threshold of {threshold}%')
    exit(1)
else:
    print(f'✅ Coverage {coverage_percent:.2f}% meets threshold of {threshold}%')
"
```

### JUnit XML Reports

**Generate JUnit XML Report**:
```bash
--junit-xml=test-results.xml
```
Generates JUnit XML format for CI/CD test result visualization.

**Multiple Test Types**:
```bash
# Unit tests
pytest hub/apps/*/tests/test_*.py -v --junit-xml=unit-test-results.xml

# Integration tests
pytest tests/integration/ -v --junit-xml=integration-test-results.xml

# E2E tests
pytest tests/e2e/ -v --junit-xml=e2e-test-results.xml
```

---

## Environment Configuration

### Environment Variables

**Test execution and evidence** (used by Phase 12A scripts and pytest):

| Variable | Purpose | When to set |
|----------|---------|-------------|
| `DJANGO_SETTINGS_MODULE` | Django settings module (e.g. `hub.settings`). Required for any pytest run. | Always when running pytest from the host; Phase 12A scripts set it inside the container. |
| `PYTHONPATH` | Project root so Python can import `hub`. | When running pytest from the host (e.g. `PYTHONPATH=/path/to/DataInteroperabilityHub`); Phase 12A scripts set it inside the container. |
| `PYTEST_DOCKER_COMPOSE_RUNTIME` | Set to `1` so integration/E2E tests that require the compose runtime are selected and behave correctly when using `--docker-compose-runtime`. | Always when running `pytest tests/integration/` or `pytest tests/e2e/` with `--docker-compose-runtime`. |
| `DATE` | Override date for `test_reports_comprehensive/{date}/` (default: `YYYY-MM-DD`). | When you want a specific date dir for evidence (e.g. in CI). |
| `COMPOSE_FILE` | Compose file to use (e.g. `docker-compose.test.yml`). When set to a file containing `docker-compose.test`, Phase 12A scripts use service `api-service-test`. | When using the test stack for integration/E2E. |
| `API_SERVICE_NAME` | Override the API service name used by Phase 12A scripts (default: `api-service` or `api-service-test` when `COMPOSE_FILE` contains `docker-compose.test`). | When your stack uses a different service name. |

Coverage and report paths: Phase 12A scripts write under `test_reports_comprehensive/{date}/` (unit/, integration/, e2e/, etc.). Coverage is produced via `--cov=hub`, `--cov-report=xml`, `--cov-report=html`; JUnit XML and logs go into the same subdirs. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md#directory-structure).

**Docker Compose Runtime**:
```bash
export PYTEST_DOCKER_COMPOSE_RUNTIME=1
```

**Database Configuration**:
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=hub
export POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub_test
```

**Redis Configuration**:
```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
```

**Performance Test Configuration**:
```bash
export API_HOST=http://localhost:8000
export PERF_TEST_USER_EMAIL=perf-test@example.com
export PERF_TEST_USER_PASSWORD=perf-test-password-123
export USERS=50
export SPAWN_RATE=5
export RUN_TIME=5m
```

**Frontend E2E Configuration**:
```bash
export E2E_VISIBLE=1  # For visible browser mode
export PLAYWRIGHT_BROWSERS_PATH=~/.cache/ms-playwright
```

---

## Troubleshooting

### Common Issues

#### 1. Tests Fail with "Database not found"

**Solution**:
```bash
# Create test database
createdb hub_test

# Or use Django management command
python hub/manage.py migrate --database=default
```

#### 2. Tests Fail with "Redis connection refused"

**Solution**:
```bash
# Start Redis
redis-server

# Or use Docker Compose
docker compose -f docker-compose.dev.yml up -d redis
```

#### 3. Integration/E2E Tests Fail with "Services not available"

**Solution**:
```bash
# Start Docker Compose services
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
./scripts/health-checks/health-check-all.sh

# Set environment variable
export PYTEST_DOCKER_COMPOSE_RUNTIME=1
```

#### 4. Performance Tests Fail with "API server not responding"

**Solution**:
```bash
# Start API server
python hub/manage.py runserver

# Verify API is accessible
curl http://localhost:8000/health/
```

#### 5. Frontend E2E Tests Fail with "Browser not found"

**Solution**:
```bash
# Install Playwright browsers
cd frontend && npx playwright install
```

#### 6. Parallel Tests Fail with "Database locked" or "Connection pool exhausted"

**Solution**:
- Reduce number of parallel workers: `-n 2` instead of `-n auto`
- Ensure test database isolation per worker
- Check database connection pool settings

#### 7. Tests Are Slow

**Solution**:
- Run tests in parallel: `-n auto`
- Use markers to skip slow tests: `-m "not slow"`
- Run only relevant tests: `pytest path/to/specific/test.py`

---

## Best Practices

### Test Execution Best Practices

1. **Run Unit Tests First**: Catch quick failures early
2. **Use Parallel Execution**: Maximize efficiency for unit and integration tests
3. **Stop on First Failure in CI**: Use `-x` flag for faster feedback
4. **Generate Coverage Reports**: Always include `--cov` and `--cov-report`
5. **Use Markers**: Organize tests with markers for selective execution
6. **Isolate Tests**: Ensure tests don't depend on execution order
7. **Clean Up**: Always clean up test data and resources
8. **Monitor Resources**: Watch for resource exhaustion in parallel execution
9. **Use Docker Compose Runtime**: For integration/E2E tests requiring services
10. **Document Test Dependencies**: Clearly document prerequisites for each test type

### Performance Best Practices

1. **Run Performance Tests Separately**: Don't mix with other test types
2. **Establish Baselines**: Compare against performance baselines
3. **Monitor System Resources**: Watch CPU, memory, network during execution
4. **Use Realistic Load**: Match production load patterns
5. **Document Results**: Save performance test results for comparison

### CI/CD Best Practices

1. **Fast Feedback**: Run fast tests (unit) first in CI
2. **Parallel Jobs**: Use separate CI jobs for different test types
3. **Cache Dependencies**: Cache Python packages and Node modules
4. **Artifact Storage**: Store test reports and coverage as artifacts
5. **Notification**: Notify on test failures
6. **Retry Strategy**: Retry flaky tests (but fix root cause)
7. **Coverage Reports**: Use `--cov-report=xml` for Codecov integration
8. **Coverage Append**: Use `--cov-append` to combine coverage across test types
9. **JUnit XML**: Use `--junit-xml` for test result visualization in CI/CD
10. **Traceback Format**: Use `--tb=short` for cleaner CI/CD logs
11. **Coverage Thresholds**: Check coverage thresholds in CI/CD (e.g., minimum 80%)

---

## Related Documents

- **[COMPREHENSIVE_TEST_PLAN.md](COMPREHENSIVE_TEST_PLAN.md)** - Complete test plan documentation
- **[TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md)** - Test coverage matrix
- **[TEST_TRACEABILITY.md](TEST_TRACEABILITY.md)** - Test traceability matrix
- **[FEATURES.md](FEATURES.md)** - Feature documentation
- **[USE_CASES.md](USE_CASES.md)** - Use case documentation

---

**Document Created**: 2026-02-05
**Last Updated**: 2026-02-08
**Version**: 1.1.0
**Status**: ✅ Active
