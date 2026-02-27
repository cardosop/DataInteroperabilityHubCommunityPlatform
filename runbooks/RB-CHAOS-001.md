# RB-CHAOS-001: Chaos Test Execution (Manual Only)

**Runbook ID:** `RB-CHAOS-001`  
**Title:** Chaos Test Execution (Manual Only)  
**Last Updated:** 2026-02-19  
**Version:** 1.0

---

## Scope

This runbook covers how and when to run the chaos test suite (`tests/chaos/`). Chaos tests validate system resilience (e.g. ODPS workflow behavior under failure injection) using real services (no mocks/stubs).

**In Scope:**

- When to run chaos tests (pre-release, incident investigation)
- How to run (`pytest tests/chaos/`)
- Required environment (Docker Compose, services)
- Clarification that chaos tests are **manual only** — not in CI or nightly

**Out of Scope:**

- Writing or modifying chaos tests (see `tests/chaos/` and [TEST_EXECUTION_PLAN.md](../docs/TEST_EXECUTION_PLAN.md))
- Other test suites (unit, integration, E2E, security — see [RUNBOOKS.md](../docs/RUNBOOKS.md))

---

## Audience & Prerequisites

**Audience:** Release engineers, SRE, developers validating resilience before release or during incident investigation.

**Prerequisites:**

- Repository checked out; Python env with project dependencies (`pip install -r requirements.txt requirements-dev.txt`)
- Docker Compose available; test stack can be started (`docker-compose.test.yml`, `.env.test`)
- `DJANGO_SETTINGS_MODULE=hub.settings` (set by commands below)

---

## When to Run

- **Pre-release**: Before cutting a release candidate or major version.
- **After major changes**: After significant orchestration or workflow changes (ODPS, Prefect, compensation logic).
- **Incident investigation**: When validating resilience or reproducing failure scenarios (e.g. ODPS workflow under service/network/DB failures).

Chaos tests are **manual only**. They are **not** run in CI (`ci.yml`) or in nightly (`phase-12a-nightly.yml`) or release (`phase-12a-release.yml`) workflows. Run them on demand only.

---

## Required Environment

- **Docker Compose**: Use `docker-compose.test.yml` (or `docker-compose.dev.yml`) so Postgres, Redis, and the API service are available.
- **Services**: PostgreSQL (database), Redis (if tests use cache/queue), API service. Minimal set matches integration/E2E; see [TEST_EXECUTION_PLAN — Docker Compose and test runtime](../docs/TEST_EXECUTION_PLAN.md#docker-compose-and-test-runtime-integration-and-e2e).
- **Settings**: `DJANGO_SETTINGS_MODULE=hub.settings`; test DB is used under pytest.

---

## Procedure: How to Run

### Option A — From repo root (stack already up)

```bash
pytest tests/chaos/ -v --tb=short
```

Or with env explicit:

```bash
PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/chaos/ -v --tb=short
```

### Option B — Using test compose stack (recommended for parity with Phase 12A)

1. Start the test stack:

   ```bash
   docker compose -f docker-compose.test.yml --env-file .env.test up -d
   ```

2. Wait until `api-service-test` is healthy (e.g. `docker compose -f docker-compose.test.yml ps`).
3. Run chaos tests inside the API container:

   ```bash
   docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/chaos/ -v --tb=short"
   ```

### Optional: JUnit artifacts

To write results under the Phase 12A layout:

```bash
mkdir -p test_reports_comprehensive/$(date +%Y-%m-%d)/chaos
pytest tests/chaos/ -v --tb=short --junit-xml=test_reports_comprehensive/$(date +%Y-%m-%d)/chaos/junit.xml
```

---

## What the Suite Covers

- **ODPS workflow chaos** (`tests/chaos/test_odps_workflow_chaos.py`): resilience under service/network/DB failures, compensation logic, event replay. Uses `tests/chaos/framework.py` (ChaosEngine, ChaosScenario, FailureType).

**Note:** `scripts/run_phase_10_5_tests.sh` runs chaos as one of its load/stress/chaos suites when executed manually; it is not in CI or nightly. Use `pytest tests/chaos/` to run only the chaos suite.

---

## Fixing Failures

- Fix failures at **root cause** (no mocks/stubs, no skip-if-flaky). Chaos tests use real services; any failure indicates a real resilience or environment issue.
- Re-run the suite after fixes to confirm green.

---

## Related Documentation

- [RUNBOOKS.md — Chaos tests (manual only)](../docs/RUNBOOKS.md#chaos-tests-manual-only) — main runbook section with same content and links
- [TEST_EXECUTION_PLAN.md — Chaos tests (manual only)](../docs/TEST_EXECUTION_PLAN.md#chaos-tests-manual-only) — execution plan entry
- [FULL_TEST_SUITE_DEFINITION.md — Optional / Extended Suites](../docs/FULL_TEST_SUITE_DEFINITION.md#optional--extended-suites-nightly-or-manual) — canonical suite definition (chaos = manual only)
