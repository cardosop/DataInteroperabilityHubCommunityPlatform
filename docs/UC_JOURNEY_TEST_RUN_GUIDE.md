# UC/Journey/Persona Test Run Guide

**Last Updated**: 2026-02-16
**Task**: 6.8.3 — How to run, prerequisites, duration, interpreting results

---

## Overview

The UC/Journey/Persona E2E test suite is a canonical subset of backend E2E tests that validate use cases, user journeys, and personas defined in [USE_CASES.md](USE_CASES.md), [USER_JOURNEYS.md](USER_JOURNEYS.md), and [USER_PERSONAS.md](USER_PERSONAS.md). Tests are tagged with `uc_journey_persona` (equivalent to `uc or journey or persona`).

**Scope**: 17 backend E2E test files, ~400+ tests (419 selected as of 2026-02-16), covering authentication, all 9 role personas, ODPS journeys, workflow integration, and failure paths.

---

## Prerequisites

### 1. Test stack running

Start the test Docker Compose stack (use `--env-file .env.test` so Postgres initializes with `hub_test` credentials):

```bash
docker compose -f docker-compose.test.yml --env-file .env.test up -d
```

**Verify**:
- API healthy: `curl -sf http://localhost:8001/health/`
- MailHog: `curl -sf http://localhost:8025/`
- Or run: `./scripts/verify_test_stack.sh`
- API port: 8001 (default; override with `API_TEST_PORT` if needed)

### 2. Environment

- `COMPOSE_FILE=docker-compose.test.yml` (default when using the script)
- `API_SERVICE_NAME=api-service-test` (default for test compose)
- `DATE` (optional): Override report date; defaults to `$(date +%Y-%m-%d)`

### 3. Dependencies

- Docker and Docker Compose
- Python 3.x (for non-Docker fallback; Django/settings must be configured)

---

## How to Run

### Option 1: Script (recommended)

```bash
./scripts/run_uc_journey_persona_tests.sh
```

- Uses Docker if `api-service-test` is running; otherwise falls back to local pytest
- Writes artifacts to `test_reports_comprehensive/{DATE}/uc_journey_persona/`
- Exit code reflects pytest result (0 = pass, non-zero = fail)

### Option 2: Direct pytest (Docker)

```bash
COMPOSE_FILE=docker-compose.test.yml docker compose exec -T api-service-test bash -c \
  "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v -m uc_journey_persona --reuse-db --timeout=900 --tb=short"
```

### Option 3: Direct pytest (local)

```bash
PYTEST_DOCKER_COMPOSE_RUNTIME=1 python -m pytest tests/e2e/ -v -m uc_journey_persona --reuse-db --timeout=900 --tb=short
```

Requires Django settings and PYTHONPATH configured (e.g. from project root with `hub` on path).

---

## Duration

| Context | Typical duration |
|---------|------------------|
| **Docker (recommended)** | 5–15 minutes (depends on DB state, `--reuse-db`) |
| **First run (no reuse)** | 10–20 minutes |
| **Incremental (reuse-db)** | 5–10 minutes |

Individual tests: 30–300 seconds each. Timeout per test: 900 seconds (15 min).

---

## Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| **Log** | `test_reports_comprehensive/{DATE}/uc_journey_persona/uc_journey_persona.log` | Full pytest output |
| **JUnit XML** | `test_reports_comprehensive/{DATE}/uc_journey_persona/junit.xml` | Machine-readable results |
| **Exit/duration** | Appended to log | `UC_JOURNEY_PERSONA_EXIT`, `UC_JOURNEY_PERSONA_DURATION` |

---

## Interpreting Results

### Exit codes

- **0**: All selected tests passed
- **1**: One or more tests failed
- **2**: Pytest usage/collection error
- **5**: No tests collected (e.g. marker mismatch)

### Log output

- `PASSED` / `FAILED` / `SKIPPED` / `ERROR` per test
- Tracebacks for failures (`--tb=short` keeps them concise)
- Summary at end: `X passed, Y failed, Z skipped in Ns`

### JUnit XML

- Parse with CI or `generate_test_summary_report.py`
- Contains `tests`, `failures`, `errors`, `skipped`, `time`

### Test summary report

After running, generate the full report:

```bash
./scripts/generate_test_summary_report.sh
```

The report includes `uc_journey_persona` as a category with pass/fail counts and evidence links.

---

## Phase 12A Integration

The UC/journey/persona suite runs as **12A.1.3b** in the full Phase 12A backend run:

```bash
./scripts/run_phase_12a_backend_suites.sh
```

Or via the full suite:

```bash
./scripts/run_phase_12a_full_suites.sh
```

Results are recorded in `phase_12a_1_summary.json` under the `uc_journey_persona` key.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `no tests ran` / all deselected | Marker mismatch or collection errors | Ensure `uc_journey_persona` marker in pytest.ini; check Django/settings for collection errors |
| `Connection refused` to API | Test stack not up | `docker compose -f docker-compose.test.yml --env-file .env.test up -d` |
| Timeouts | Slow DB or network | Increase `--timeout`; use `--reuse-db` |
| Import errors | PYTHONPATH or Django not configured | Run inside container or set `PYTHONPATH`, `DJANGO_SETTINGS_MODULE` |

---

## Sign-Off Record (Task 6.8.4)

When documenting a UC/journey/persona suite run sign-off, record:

| Field | Description |
|-------|-------------|
| **Date** | Date of the run (YYYY-MM-DD). |
| **Commit** | Git commit hash (e.g. `git rev-parse --short HEAD`). |
| **Evidence path** | `test_reports_comprehensive/{date}/uc_journey_persona/` |
| **Result** | passed / failed (exit code 0 / non-zero). |
| **Summary** | X passed, Y failed, Z skipped (from log or JUnit). |

**Example (2026-02-16)**:
- **Date**: 2026-02-16
- **Commit**: 6ba447c
- **Evidence path**: `test_reports_comprehensive/2026-02-16/uc_journey_persona/`
- **Result**: failed (exit 1)
- **Summary**: 320 passed, 73 failed, 26 skipped (419 selected)
- **Artifacts**: `uc_journey_persona.log` (full output)

---

## Related Documents

- [RUNBOOKS.md — UC/Journey/Persona E2E tests](RUNBOOKS.md#ucjourney-persona-e2e-tests-task-67)
- [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md) (step 4b)
- [TEST_TRACEABILITY.md — UC/Journey/Persona E2E Tests](TEST_TRACEABILITY.md#ucjourney-persona-e2e-tests-task-67)
- [TEST_COVERAGE_MATRIX.md — UC/Journey/Persona E2E Coverage](TEST_COVERAGE_MATRIX.md#ucjourney-persona-e2e-coverage-task-67)
