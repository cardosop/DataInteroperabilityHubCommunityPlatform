# Gap Fix and Full Test Execution Plan

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-12  
**Status**: Active  
**Based on**: [TEST_SUITE_GAP_ANALYSIS.md](TEST_SUITE_GAP_ANALYSIS.md)  
**OpenSpec change**: [testsfix1](../openspec/changes/testsfix1/) — proposal, tasks, design, and testing-requirements delta to apply this plan (validate with `openspec validate testsfix1 --strict`).  
**Purpose**: Engineering-grade plan to implement gap fixes and execute the full test suite in small batches (100–200 tests per batch), run → fix root cause → rerun in cycles until all tests pass. No mocks/stubs; root-cause fixes only; development best practices (TDD, DRY, SOLID, clean code, Django).

---

## Table of Contents

1. [Principles and Constraints](#1-principles-and-constraints)
2. [Overview and Phases](#2-overview-and-phases)
3. [Phase 0: Prerequisites and Environment](#3-phase-0-prerequisites-and-environment)
4. [Phase 1: Gap Fixes (Pre-Execution)](#4-phase-1-gap-fixes-pre-execution)
5. [Phase 2: Batch Strategy and Tooling](#5-phase-2-batch-strategy-and-tooling)
6. [Phase 3: Batched Test Execution and Fix Cycles](#6-phase-3-batched-test-execution-and-fix-cycles)
7. [Phase 4: Full Suite Run and Sign-Off](#7-phase-4-full-suite-run-and-sign-off)
8. [Phase 5: CI and Ongoing Execution](#8-phase-5-ci-and-ongoing-execution)
9. [Artifacts, Evidence, and Reporting](#9-artifacts-evidence-and-reporting)
10. [Checklist and Acceptance Criteria](#10-checklist-and-acceptance-criteria)
11. [Appendix: Batch Definitions and Scripts](#11-appendix-batch-definitions-and-scripts)

---

## 1. Principles and Constraints

### 1.1 Mandatory Principles

| # | Principle | Application |
|---|-----------|-------------|
| 1 | **Real services only** | No mocks or stubs except at external process boundaries (e.g. third-party APIs). All tests use real DB, Redis, and services. |
| 2 | **Root-cause fixes only** | Every failure is diagnosed; fix the root cause in application or test code. No masking, no skip-if-flaky, no retries that hide failures. |
| 3 | **No quality reduction** | Do not relax assertions or simplify tests to make them pass. Fix application behavior or test environment. |
| 4 | **Development best practices** | TDD where adding tests; DRY, SOLID, clean code; Django best practices; consistent naming and structure. |
| 5 | **Batch size** | Each batch targets 100–200 tests so runs stay short enough to iterate quickly (aim &lt; 15–20 minutes per batch where possible). |
| 6 | **Fix before advance** | A batch must pass (or be explicitly deferred with a documented ticket) before starting the next batch. No “run all and fix later” without a clear batch boundary. |

### 1.2 Out of Scope for This Plan

- Introducing new mocks or stubs to make tests pass.
- Commenting out or disabling tests to achieve “all pass.”
- Performance/chaos/concurrency as part of the mandatory batched run (they can be run after sign-off as nightly or release pipeline).

---

## 2. Overview and Phases

```
Phase 0: Prerequisites & environment (stack, env vars, scripts)
    ↓
Phase 1: Gap fixes (frontend scripts, security in CI, unit phase, smoke)
    ↓
Phase 2: Batch strategy & tooling (100–200 tests/batch, runner script)
    ↓
Phase 3: Batched execution & fix cycles (run batch → fix → rerun until pass → next batch)
    ↓
Phase 4: Full suite run & sign-off (one full run, evidence, report)
    ↓
Phase 5: CI & ongoing (canonical suite in CI, nightly optional)
```

**Exit criterion**: All planned batches pass; one full suite run passes; evidence and test summary report generated; no known failing tests without a documented root-cause ticket.

---

## 3. Phase 0: Prerequisites and Environment

### 3.1 Environment

- **Docker Compose**: Use `docker-compose.test.yml` for test stack (same as Phase 12A batched execution). Ensure `COMPOSE_FILE=docker-compose.test.yml` and API service name `api-service-test`.
- **Services**: Postgres, Redis (cache, queue, events, channels), MinIO, Fuseki, datacontract-service, dq-service, compliance-service, semantic-service, api-service-test. Worker and Prefect are optional for batches that do not need them.
- **Env vars**: `DJANGO_SETTINGS_MODULE=hub.settings`, `PYTHONPATH=<repo_root>`, and for integration/e2e `PYTEST_DOCKER_COMPOSE_RUNTIME=1` when using `--docker-compose-runtime`.
- **Python**: 3.12+; install `requirements.txt` and `requirements-dev.txt`.

### 3.2 Scripts and Paths

- **Existing**: `scripts/run_phase_12a_batched.sh` (path-based batches), `scripts/run_phase_12a_backend_suites.sh`, `scripts/run_phase_12a_full_suites.sh`, `scripts/generate_test_summary_report.sh`.
- **Evidence base**: `test_reports_comprehensive/{DATE}/` with subdirs for unit, integration, e2e, security, batches, etc. (see [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md)).

### 3.3 Prerequisites Checklist

- [ ] Docker and Docker Compose installed and working.
- [ ] `docker-compose.test.yml` (or equivalent) present; stack can be brought up with `docker compose -f docker-compose.test.yml up -d`.
- [ ] All core test services healthy (health checks or manual curl).
- [ ] Repo root has `pytest.ini`, `tests/conftest.py`, and `hub/` on `PYTHONPATH`.
- [ ] No uncommitted changes that would invalidate a batch (or document branch/commit for the run).

---

## 4. Phase 1: Gap Fixes (Pre-Execution)

Implement the following **before** starting batched full-suite execution. Each item is a gate: complete it and verify before proceeding.

### 4.1 Frontend: Missing npm Scripts (Gap #4 – High)

**Problem**: `frontend-tests.yml` runs `test:component`, `test:a11y`, `test:coverage:check` which do not exist in `frontend/package.json`.

**Tasks**:

1. **test:component**  
   - Add script that runs the same Vitest scope as unit tests (e.g. `vitest run --exclude e2e` or reuse `test:run`). Example: `"test:component": "vitest run"` or a dedicated pattern for `src/**/*.component.{test,spec}.{ts,tsx}` if you introduce a convention.  
   - **Acceptance**: `cd frontend && npm run test:component` completes without error.

2. **test:a11y**  
   - Add accessibility tests (e.g. Playwright + axe-core, or Vitest + jest-axe).  
   - Script example: `"test:a11y": "playwright test --grep @a11y"` or `"test:a11y": "vitest run --config vitest.a11y.config.ts"` (if separate config).  
   - **Acceptance**: `npm run test:a11y` exists and runs; if no a11y tests yet, script can run a placeholder (e.g. vitest run with zero a11y specs) and document “a11y tests to be added.”

3. **test:coverage:check**  
   - Add script that fails if coverage is below threshold (e.g. 80% lines/functions/branches). Use Vitest coverage and a small script or `vitest run --coverage` with threshold in config.  
   - **Acceptance**: `npm run test:coverage:check` fails when below threshold and passes when above (or document threshold in plan).

4. Update `.github/workflows/frontend-tests.yml` so all three steps call the new scripts (no remove-step option unless explicitly decided).

**Verification**: Run the frontend-tests workflow (or locally the three commands) and confirm no “script not found” errors.

---

### 4.2 Security: Run Full `tests/security/` in CI (Gap #5 – High)

**Problem**: Only ODPS ref resolver and penetration tests run in CI; full `tests/security/` (IDOR, injection, AllowAny, etc.) does not.

**Tasks**:

1. Add a CI job or step that runs:  
   `pytest tests/security/ -v --tb=short --junit-xml=security-test-results.xml`  
   with DB and Redis available (same as main test job).

2. Ensure tests in `tests/security/` do not depend on services that are not present in CI (or mark and skip those with a clear reason).

3. **Acceptance**: New job/step runs and uploads `security-test-results.xml`; failures fail the job (no `continue-on-error` unless documented).

**Verification**: Push a branch and confirm the security job runs and that failures are visible.

---

### 4.3 Backend Unit Phase in CI (Gap #1 – High)

**Problem**: CI runs `pytest tests/unit/` only; app-level unit tests (`hub/apps/*/tests/`) are not explicitly part of a “unit” phase.

**Tasks**:

1. Define the unit phase as: **all unit tests** = `hub/apps/` + `tests/unit/`, with marker `-m unit` if all such tests are marked, or by path: e.g.  
   `pytest hub/apps/ tests/unit/ -v -m "unit"`  
   or  
   `pytest hub/apps/ tests/unit/ -v`  
   (and exclude integration/e2e by marker or path so unit job stays fast).

2. In CI, add or replace the unit step to run this unit phase (with coverage and JUnit XML).

3. **Acceptance**: CI unit job runs both app-level and root unit tests; duration remains acceptable (e.g. &lt; 15–20 min) or split into multiple jobs if needed.

**Verification**: CI run shows unit phase including hub app tests; no regression in total unit count.

---

### 4.4 Smoke Tests: Align Ports and Run (Gap #8 – Medium)

**Problem**: `tests/smoke/test_api_health.py` uses default `API_BASE_URL=http://localhost:8001` and service ports that may not match docker-compose/CI.

**Tasks**:

1. Align defaults or env in smoke tests with `docker-compose.test.yml` (or CI): API (e.g. 8000 or the test port), semantic, datacontract, compliance, DQ ports and service names.

2. Add smoke run to CI (after API is up) or to deploy pipeline; document in TEST_EXECUTION_PLAN.

3. **Acceptance**: `pytest tests/smoke/ -v` passes when stack is up with default env (or with env set to match compose).

**Verification**: Run smoke against the test stack; all health checks pass.

---

### 4.5 Platform App Tests or Documentation (Gap #2 – Medium)

**Problem**: `hub/apps/platform/` has no tests.

**Tasks**:

1. Either:  
   - Add minimal unit tests for platform views/behavior (TDD: write test first, then implementation), or  
   - Document in code and in TEST_COVERAGE_MATRIX that platform is a thin wrapper with no business logic and no tests by design.

2. **Acceptance**: Platform is either covered by tests or explicitly documented as out-of-scope for tests.

---

### Phase 1 Completion Gate

- [ ] All of 4.1–4.5 implemented and verified.
- [ ] No new mocks/stubs introduced; root-cause fixes only.
- [ ] CI (or local equivalent) runs: unit (app + root), security suite, smoke; frontend workflow runs component, a11y, coverage check.

---

## 5. Phase 2: Batch Strategy and Tooling

### 5.1 Batch Size and Goals

- **Target**: 100–200 tests per batch so each batch runs in a reasonable time (target &lt; 15–20 minutes per batch where feasible).
- **Goal**: Run batches in order; fix all failures in a batch before moving to the next; avoid long monolith runs until the final full run.

### 5.2 Two Complementary Approaches

**Approach A – Path-based batches (existing)**  
- Use path-based batches (e.g. by app or by `tests/unit/`, `tests/integration/`, `tests/e2e/`).  
- **Cap**: If a path-based batch exceeds 200 tests, split it into sub-batches (e.g. by file or by subdirectory) so each sub-batch is ≤ 200 tests.  
- **Pro**: Fix by domain (e.g. “all contracts tests”), easier to reason about.  
- **Con**: Batch sizes vary; some apps have &gt; 200 tests and need splitting.

**Approach B – Count-based batches (new)**  
- Collect all test node IDs:  
  `pytest hub/apps/ tests/unit/ tests/integration/ tests/e2e/ --collect-only -q`  
  (optionally exclude security/performance/concurrency/regression for the “main” run, or include them in a separate batch set).  
- Split the list into chunks of 100–200 tests (e.g. 150 per batch).  
- Run each chunk with:  
  `pytest <node_id_1> <node_id_2> ...`  
  or by writing a small script that reads a batch file of node IDs and passes them to pytest.  
- **Pro**: Strict control over batch size.  
- **Con**: Batches are arbitrary (no domain grouping); fixing may jump between areas.

**Recommended hybrid**:

1. **Backend (hub + root unit/integration/e2e)**: Use **path-based batches** (leverage and extend `run_phase_12a_batched.sh`). For any batch that currently has &gt; 200 tests, split it into sub-batches (by file or by sub-path) so each is ≤ 200. Document the final batch list and approximate counts.
2. **Optional**: Provide a **count-based batch generator** script that outputs N batch files (each with ~100–200 node IDs) for teams that prefer fixed-size runs. This can be used for a second pass or for CI splits.

### 5.3 Batch Runner Behavior

For each batch run:

1. **Invocation**: Run pytest with:  
   - `--reuse-db` to avoid repeated DB creation.  
   - `--timeout=300` (or 600 for integration/e2e) per test.  
   - `--tb=short`.  
   - `--junit-xml=<batch_dir>/junit.xml`.  
   - Optional: `--maxfail=10` during fix cycles to see multiple failures; remove for final run.  
   - No coverage for very large batches if OOM is observed (as in existing script for ODPS/Files).

2. **Output**: Log and JUnit XML under `test_reports_comprehensive/{DATE}/batches/batch_<N>/`.  
3. **Summary**: Write a small JSON per batch: exit_code, duration_seconds, passed, failed, error, skipped, log path, junit path.

### 5.4 Batch Order (Path-Based)

Suggested order (align with existing `run_phase_12a_batched.sh` where applicable):

1. Core / infra (api, health, core if present)  
2. Auth  
3. Audit  
4. Assets  
5. Contracts (split into core, ODPS, ODCS if &gt; 200 each)  
6. Datasets  
7. Marketplace  
8. Compliance  
9. Governance  
10. DQ  
11. Files  
12. Scheduled export/ingestion  
13. Orchestration  
14. Jobs  
15. Billing, BaaS, developer  
16. GDPR, notifications, webhooks  
17. AI, ML, GraphQL  
18. Observability, rate_limiting, integrations, mesh  
19. Platform, users, social  
20. Root `tests/unit/`  
21. Root `tests/integration/` (may need splitting by directory/file)  
22. Root `tests/e2e/` (may need splitting by e2e_batch1–5 or by file)  
23. Root `tests/security/`  
24. Root `tests/regression/` (optional; can be last or nightly)

Ensure each batch is ≤ 200 tests; split large path-based batches as in Section 11.

### 5.5 Deliverables for Phase 2

- [ ] Final list of batches (names and paths or node-id files) with approximate test count per batch.
- [ ] Script(s): either extended `run_phase_12a_batched.sh` with split batches, or new `scripts/run_batched_tests_by_count.sh` that uses collected node IDs and batch size 100–200.
- [ ] One-page “Batch execution runbook”: how to start stack, run one batch, run from batch N, run all, where to find logs and JUnit.

---

## 6. Phase 3: Batched Test Execution and Fix Cycles

### 6.1 Cycle Per Batch

For **each** batch (in order):

1. **Run**  
   - Start (or reuse) test stack.  
   - Run the batch (path-based or count-based).  
   - Capture log, JUnit XML, and summary JSON under `test_reports_comprehensive/{DATE}/batches/batch_<N>/`.

2. **Evaluate**  
   - If exit code 0 and no failures in JUnit: **pass** → go to next batch.  
   - If exit code ≠ 0 or failures present: **fail** → enter fix cycle.

3. **Fix cycle (no mocks/stubs)**  
   - From JUnit and log, list failing tests and errors.  
   - For each failure:  
     - Reproduce locally (run the same test or batch).  
     - Diagnose root cause (application bug, test bug, environment, flakiness).  
     - Fix root cause:  
       - Application bug → fix in application code.  
       - Test bug → fix test (assertion, setup, or environment).  
       - Environment → fix compose, env vars, or test isolation.  
       - Flakiness → fix ordering, timeouts, or isolation (no “skip if flaky”).  
     - Do not introduce mocks/stubs to make the test pass; do not comment out or relax assertions without a documented reason.

4. **Rerun same batch**  
   - After applying fixes, rerun **only that batch**.  
   - Repeat fix → rerun until the batch passes (or the failure is deferred with a ticket and documented).

5. **Next batch**  
   - Only when the current batch is green (or deferred with ticket), proceed to the next batch.

### 6.2 Recording Progress

- Maintain a simple **batch status** file or table: batch number, name, status (pass/fail/deferred), last run time, link to log/junit.  
- **Implemented**: `scripts/generate_batch_status.sh` (invoked by `run_phase_12a_batched.sh` after each batch and at end) writes `test_reports_comprehensive/{DATE}/batches/batch_status.json` and `batches/README.md` with the table. See [RUNBOOKS.md — Batch status and fix cycle](RUNBOOKS.md#batch-status-and-fix-cycle-phase-3).

### 6.3 Deferred Failures

- If a failure cannot be fixed in the current cycle (e.g. external dependency, large refactor):  
  - Open a ticket (or doc section) with: batch, test id, error summary, root cause, and plan.  
  - Mark batch as “deferred” and document in batch status.  
  - Continue to next batch; do not block the rest of the run on one deferred item.  
- Before sign-off, review all deferred items and either fix or accept for a later sprint.

### 6.4 Principles During Fixes

- **One batch at a time**: No “run all batches and collect failures” as the primary loop; the primary loop is “batch N → fix → rerun batch N until pass → N+1.”
- **Root cause only**: Every fix must address the underlying cause; no masking or skipping without a ticket.
- **Regression**: After fixing a batch, if time permits, rerun the previous batch once to ensure no regression (optional but recommended for critical domains).

---

## 7. Phase 4: Full Suite Run and Sign-Off

### 7.1 When to Run Full Suite

- After **all batches** have passed (or been deferred with tickets) in Phase 3.

### 7.2 Full Suite Run

- **Command**: Use the canonical full suite (e.g. `scripts/run_phase_12a_backend_suites.sh` or `scripts/run_phase_12a_full_suites.sh`), or run unit + integration + e2e + security in sequence with the same env and options as in CI.  
- **Environment**: Same as batched runs (docker-compose.test.yml, api-service-test, same env vars).  
- **Artifacts**: All outputs under `test_reports_comprehensive/{DATE}/` (unit, integration, e2e, security, and optionally performance/concurrency/regression if part of full suite).  
- **Duration**: Expect longer (e.g. 1–2+ hours for full backend); run once for sign-off.

### 7.3 Success Criteria

- Full suite exit code 0.  
- No failing tests in JUnit reports (or only documented deferred failures with tickets).  
- Test summary report generated (e.g. `scripts/generate_test_summary_report.sh`).

### 7.4 Sign-Off

- **Document**: Date, commit/branch, “Full suite run passed” and path to evidence (e.g. `test_reports_comprehensive/{DATE}/` and summary report).  
- **Optional**: Update TEST_COVERAGE_MATRIX or TEST_TRACEABILITY with “Last full run” date and link.  
- **Deferred**: List of deferred failures with tickets; plan for addressing in next cycle.

---

## 8. Phase 5: CI and Ongoing Execution

### 8.1 Canonical Suite in CI

- After gap fixes (Phase 1), CI should run:  
  - Unit (app + root),  
  - Integration,  
  - E2E,  
  - Security (`tests/security/`),  
  - Smoke (after API up).  
- **Canonical definition**: [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md) — run order, commands, and which steps are CI vs nightly/manual. Implemented in `.github/workflows/ci.yml` (test job: smoke → unit → integration → e2e; test-security job: `tests/security/`). Optionally: a single job that invokes `run_phase_12a_backend_suites.sh` so local and CI use the same commands (see TEST_EXECUTION_PLAN).

### 8.2 Nightly or Release Pipeline

- Performance, concurrency, regression can run in a separate workflow (e.g. nightly or on release) so main CI stays fast.  
- Documented in runbooks, [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) (Nightly Builds, Release Builds), and [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md). Regression can be run as the last batch in batched execution or in nightly only.

### 8.3 Batched Runs in CI (Optional)

- For CI, running 20+ batches sequentially may be too slow. Options:  
  - Run “full suite” in CI (single job or a few jobs: unit, integration, e2e, security) as the gate; use batched execution locally for incremental fixing.  
  - Or run a subset of batches in CI (e.g. batches 1–5 on every PR, full set on merge to main or nightly).

---

## 9. Artifacts, Evidence, and Reporting

### 9.1 Per-Batch Artifacts

- Directory: `test_reports_comprehensive/{DATE}/batches/batch_<N>/`.  
- Contents: `batch_<N>.log`, `junit.xml`, `summary.json` (exit_code, duration_seconds, passed, failed, errors, skipped, paths to log/junit).  
- Optional: coverage XML for that batch if not disabled for OOM.

### 9.2 Full Suite Artifacts

- As per EVIDENCE_COLLECTION_PLAN: `unit/`, `integration/`, `e2e/`, `security/`, and optionally `performance/`, `concurrency/`, `regression/`, `frontend-unit/`, `frontend-e2e/`.  
- Summary JSON: `phase_12a_1_summary.json` (and `phase_12a_3_summary.json` if 12A.3 run).  
- Test summary report: output of `scripts/generate_test_summary_report.sh`.

### 9.3 Retention

- Keep evidence for at least 14 days (or per CI retention).  
- Do not commit `test_reports_comprehensive/` (already in .gitignore); upload as CI artifacts or store in a shared location if needed.

---

## 10. Checklist and Acceptance Criteria

### 10.1 Phase 1 (Gap Fixes) – Done When

- [ ] Frontend: `test:component`, `test:a11y`, `test:coverage:check` exist and run; frontend-tests workflow succeeds.  
- [ ] Security: `pytest tests/security/` runs in CI and fails the job on failure.  
- [ ] Backend unit phase in CI includes hub app + root unit tests.  
- [ ] Smoke tests use correct ports/env and pass against test stack; smoke run in CI or deploy.  
- [ ] Platform app: tests added or documented as no-logic.

### 10.2 Phase 2 (Batching) – Done When

- [ ] Batch list is defined with ≤ 200 tests per batch (path-based and optionally count-based).  
- [ ] Runner script(s) can run a single batch, run from batch N, and run all batches.  
- [ ] Batch runbook is written (how to run, where logs are).

### 10.3 Phase 3 (Fix Cycles) – Done When

- [ ] Every batch has been run and has passed (or is deferred with a ticket).  
- [ ] All fixes are root-cause; no mocks/stubs introduced to pass tests.  
- [ ] Batch status (pass/fail/deferred) is recorded.

### 10.4 Phase 4 (Sign-Off) – Done When

- [ ] One full suite run has been executed and passed.  
- [ ] Test summary report generated and stored.  
- [ ] Sign-off documented (date, commit, evidence path, deferred list if any).

### 10.5 Phase 5 (CI) – Done When

- [ ] CI runs unit (app + root), integration, e2e, security, smoke per this plan.  
- [ ] Optional: nightly or release runs performance/regression/concurrency; runbooks updated.

---

## 11. Appendix: Batch Definitions and Scripts

### 11.1 Auditing and Splitting Large Path-Based Batches

**Audit script** (`scripts/audit_batch_sizes.sh`): Run with test stack up to get test count per batch. Output is a Markdown table; batches over 200 are marked **SPLIT**. Use `--no-up` if the stack is already up.

**Split script** (`scripts/split_batches_to_cap.py`): With stack up, run to generate `scripts/batch_definitions.txt` so every batch has ≤200 tests (path-based splits, then per-file grouping). The batched runner loads this file when present. Generation can take 30+ minutes.

If a path-based batch has &gt; 200 tests and no generated file is used:

- **By file**: List test files under that path; group into sub-batches of ~100–200 tests (e.g. by counting with `pytest path/ --collect-only -q` per file and summing).  
- **By subdirectory**: If the app has `tests/subdir1/`, `tests/subdir2/`, use one batch per subdir or combine small subdirs.  
- **By marker**: If tests are marked (e.g. `e2e_batch1`–`e2e_batch5`), use one batch per marker and cap each at 200.

### 11.2 Count-Based Batch Generator Script

Use the provided script to generate batch files with a fixed number of tests per batch (e.g. 150):

```bash
# From repo root, with venv and DJANGO_SETTINGS_MODULE=hub.settings (or run inside api-service-test)
python scripts/generate_test_batches_by_count.py --size=150 --output-dir=test_batches

# Dry run (only print total and batch count)
python scripts/generate_test_batches_by_count.py --size=150 --dry-run

# Run one batch (after generation)
pytest $(cat test_batches/batch_001.txt) -v --reuse-db --timeout=300 --tb=short
```

Script: `scripts/generate_test_batches_by_count.py`. It runs `pytest --collect-only` on the given paths (default: `hub/apps/`, `tests/unit/`, `tests/integration/`, `tests/e2e/`), parses node IDs, and writes `batch_NNN.txt` files with one node id per line. For full collection, use the same environment as the path-based batched run (e.g. inside the test container).

### 11.3 References

- **Gap analysis**: [TEST_SUITE_GAP_ANALYSIS.md](TEST_SUITE_GAP_ANALYSIS.md)  
- **Test execution**: [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md)  
- **Evidence**: [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md)  
- **Batched script**: `scripts/run_phase_12a_batched.sh` (supports `--batch=N`, `--start-from=N`, `--list-batches`; loads `scripts/batch_definitions.txt` when present)  
- **Audit/split**: `scripts/audit_batch_sizes.sh`, `scripts/split_batches_to_cap.py`  
- **Runbooks**: [RUNBOOKS.md](RUNBOOKS.md) — [Batch execution (Phase 12A path-based batches)](RUNBOOKS.md#batch-execution-phase-12a-path-based-batches), full test suite, Phase 12A

---

*This plan should be updated when gap fixes are completed, batch definitions change, or the test strategy is revised.*
