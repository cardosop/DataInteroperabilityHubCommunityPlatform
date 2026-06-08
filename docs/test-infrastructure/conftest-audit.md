# Conftest File Audit

**Date:** 2026-05-21
**Scope:** 47 project conftest files; 6 core files audited in depth.
**Core files:** `tests/conftest.py`, `hub/conftest.py`, `tests/e2e/conftest.py`, `tests/conftest_prefect.py`, `tests/integration/conftest_test_env.py`, `tests/integration/conftest_api_client_usage.py`

---

## Summary

| File | Lines | Fixtures | Hooks | Primary Role |
|---|---|---|---|---|
| `tests/conftest.py` | 2,401 | 24 | 4 | Root conftest: Django patches, service fixtures, env validation |
| `hub/conftest.py` | 1,463 | 10 | 4 | Hub-scoped: DB connectivity, idempotent creates, teardown resilience |
| `tests/e2e/conftest.py` | 1,996 | 3 | 2 | E2E-specific: docker-compose runner, E2E test base class, CLI runner |
| `tests/prefect/conftest.py` (was `tests/conftest_prefect.py`) | 117 | 5 | 0 | Prefect service fixtures (renamed Phase 312.11.1) |
| `tests/integration/conftest_test_env.py` | 7 | 0 | 0 | Environment setup only (no fixtures) |
| `tests/integration/conftest_api_client_usage.py` | 9 | 0 | 0 | API client usage patterns (no fixtures) |
| **Total** | **~5,992** | **~43** | **10** | |

---

## 1. Duplication Analysis: `tests/conftest.py` vs `hub/conftest.py`

### 1.1 Why Two Root Conftest Files Exist

The project has a **dual root conftest** architecture:

- **`tests/conftest.py`** (2,401 lines): Loaded when pytest collects from `tests/` directory.
- **`hub/conftest.py`** (1,463 lines): Loaded when pytest collects from `hub/` directory.

When `testpaths = hub/apps tests` (as configured in `pytest.ini`), both conftest files load — but when running `pytest hub/apps/auth/tests/` directly, only `hub/conftest.py` loads. This is why `hub/conftest.py` (line 69) imports `tests.conftest` as a fallback.

### 1.2 Shared Patch Targets

Both conftest files patch **the same Django internals** at these lifecycle points:

| Django Internal | `tests/conftest.py` | `hub/conftest.py` | Duplication |
|---|---|---|---|
| `Command.sync_apps` | Patched (L64-108) | Reached via `import tests.conftest` (L69) | **Delegated** |
| `MigrationExecutor.__init__` | Patched (L114-149) | Reached via `import tests.conftest` (L69) | **Delegated** |
| `MigrationLoader.load_disk` | Patched (L149+) | Reached via `import tests.conftest` (L69) | **Delegated** |
| `sql_flush` (CASCADE) | Patched (tests/conftest.py) | **Duplicated** (L961-972) | **DUPLICATED** |
| `create_contenttypes` | Patched (tests/conftest.py L650-734) | Not patched | Tests only |
| `create_permissions` | Patched (tests/conftest.py L738-837) | Not patched | Tests only |
| `_create_test_db` (PostgreSQL) | Patched (tests/conftest.py L841+) | Not patched | Tests only |
| `setup_databases` (retry) | Not patched | **Hub-only** (L1172-1226) | Hub only |
| `_fixture_teardown` (resilience) | Not patched | **Hub-only** (L1419-1457) | Hub only |

### 1.3 Exact Duplication: `sql_flush` CASCADE Patch

The `sql_flush` CASCADE patch is the only **exact duplicate** between the two files:

**`tests/conftest.py`** (approximate location ~L1100):
```python
# Patches PostgreSQL sql_flush to use TRUNCATE ... CASCADE
# Prevents ForeignKeyViolation during transaction test case teardown
```

**`hub/conftest.py`** (L961-972):
```python
if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
    _original_sql_flush = pg_operations.DatabaseOperations.sql_flush
    def _patched_sql_flush(...):
        return _original_sql_flush(...)
    _patched_sql_flush._patched_for_cascade = True
    pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
```

This duplication exists because `hub/conftest.py` guards against the case where `tests.conftest` import fails (line 69-71: `except ImportError: pass`). The comment at L17-18 acknowledges: *"Duplicates the sql_flush CASCADE patch as a fallback in case tests/conftest.py is unreachable."*

### 1.4 Duplication Analysis — Fixtures

16 app-level conftest files at `hub/apps/*/tests/conftest.py` provide DB setup fixtures. These are **not duplicated** — each provides app-specific test data. However, they share the same pattern: `@pytest.fixture(autouse=True)` that calls `_seed_*` helpers.

### 1.5 Lines of Duplication Estimate

| Category | Approximate Lines |
|---|---|
| `sql_flush` CASCADE patch (exact duplicate) | ~15 lines |
| Shared import fallback (`import tests.conftest`) | ~5 lines |
| Shared `DJANGO_SETTINGS_MODULE` setup | ~3 lines |
| Shared `TESTING=1` env setting | ~2 lines |
| **Total duplicated logic** | **~25 lines** |

The remaining ~3,800 lines across both files are **non-duplicated**: `tests/conftest.py` specializes in migration-safety patches and service fixtures; `hub/conftest.py` specializes in DB connectivity checks, idempotent CRUD, and teardown resilience.

---

## 2. E2E Conftest: `tests/e2e/conftest.py` (1,996 lines)

### Overview

The third-largest conftest file provides the E2E test runner infrastructure:

- **`E2ETestBase`** — Base test case class for E2E tests with `complete_file_upload` support (requires MinIO/S3)
- **`pytest_addoption(parser)`** — Registers E2E CLI options: `--docker-compose-runtime`, `--reuse-db`, `--e2e-base-url`, etc.
- **`pytest_configure(config)`** — Configures E2E-specific markers and fixtures based on runtime mode
- **Session fixtures** — Docker Compose project management, API client setup, tenant provisioning
- **Django setup bridging** — Sets `DJANGO_SETTINGS_MODULE=hub.settings` and calls `django.setup()` when running inside docker-compose

### Why It's 1,996 Lines

The E2E conftest implements a complete test runtime: CLI argument parsing, docker-compose lifecycle management, shared DB coordination, API client authentication, and test data provisioning. It's effectively a mini-test-framework within the conftest.

### Consolidation Opportunity

Much of the `pytest_addoption` and docker-compose lifecycle logic could be extracted into `tests/_e2e_runner.py`, leaving only fixtures in the conftest.

---

## 3. Non-Standard Name: `tests/conftest_prefect.py`

> **RESOLVED (Phase 312.11.1):** Renamed `tests/conftest_prefect.py` → `tests/prefect/conftest.py`.
> Fixtures are now auto-discoverable for any test under `tests/prefect/`.

### Problem (historical)

`tests/conftest_prefect.py` used the non-standard name `conftest_prefect.py` instead of `conftest.py`. Pytest **does not auto-discover** files with this naming pattern — only files named exactly `conftest.py` are loaded.

### Impact (historical)

- Fixtures in this file (`prefect_server_url`, `prefect_server_health`, `prefect_server_available`, `prefect_api_key`, `prefect_work_pool`, `wait_for_prefect_server`) were **never automatically available** to tests.
- Tests had to explicitly import from this file or it had to be renamed to `conftest.py` in a `tests/prefect/` subdirectory.
- Per Phase 312.1 clean-conftest-names gate: `conftest_prefect.py → tests/prefect/conftest.py`.

### Recommendation

Rename to `tests/prefect/conftest.py` (create subdirectory) so pytest auto-discovers it.

---

## 4. App-Level Conftest Files (14)

Each app under `hub/apps/*/tests/` has its own `conftest.py`:

| App | Fixtures | Purpose |
|---|---|---|
| `assets` | 1 | Asset test data seeding |
| `auth` | 1 | Auth/user test setup |
| `compliance` | 1 | Compliance config seeding |
| `contracts` | 1 | Contract test data |
| `datasets` | 0 | (empty/near-empty) |
| `dq` | 1 | DQ rule seeding |
| `files` | 1 | File upload test setup |
| `governance` | 1 | Governance policy seeding |
| `integrations` | 1 | Integration config |
| `marketplace` | 1 | Marketplace listing data |
| `orchestration` | 1 | Orchestration fixtures |
| `semantic` | 1 | Semantic/config setup |
| `webhooks` | 1 | Webhook test setup |
| `ai` | 0 | (empty) |

These 14 app conftest files total approximately 500-700 lines and follow consistent patterns. They could be candidates for consolidation if a shared "app test data" fixture pattern emerges.

---

## 5. Other Conftest Files

| File | Purpose |
|---|---|
| `tests/e2e/conftest.py` | E2E-specific session fixtures, API client setup |
| `tests/integration/conftest_test_env.py` | Integration test environment setup |
| `tests/integration/conftest_api_client_usage.py` | API client usage patterns for integration tests |
| `tests/concurrency/conftest.py` | Concurrency test isolation |
| `tests/isolation/conftest.py` | Test isolation fixtures |
| `tests/pact/conftest.py` | Contract testing (Pact) fixtures |
| `tests/resilience/conftest.py` | Resilience/chaos testing fixtures |
| `tests/security/conftest.py` | Security test fixtures |
| `tests/smoke/conftest.py` | Smoke test fixtures |
| `tests/scripts/conftest.py` | Scripts test fixtures |
| `tests/sdk_python/conftest.py` | SDK Python test fixtures |
| `cli/tests/conftest.py` | CLI test fixtures |
| `sdk/python/tests/conftest.py` | SDK test fixtures |
| `services/*/tests/conftest.py` (7) | Microservice test fixtures |

---

## 6. Conftest Loading Order & Interaction

Pytest loads conftest files from root to leaf:

1. `tests/conftest.py` — Root-level patches, migration safety
2. `hub/conftest.py` — Imports `tests.conftest`, adds DB check + teardown
3. `tests/e2e/conftest.py` — E2E overrides
4. `hub/apps/*/tests/conftest.py` — App-level fixtures

The `import tests.conftest` fallback in `hub/conftest.py:69` means patches are applied twice when both conftests load (both files reference the same import), but the `_patched` sentinel attributes prevent double-patching.

---

## Recommendations

1. **De-duplicate `sql_flush` CASCADE patch** — move to a shared module (`tests/_patches.py`) imported by both conftest files, eliminating the `except ImportError: pass` fallback pattern.
2. **Rename `tests/conftest_prefect.py` → `tests/prefect/conftest.py`** — makes Prefect fixtures auto-discoverable.
3. **Extract `tests/e2e/conftest.py` CLI/docker-compose logic** — the 1,996-line E2E conftest contains a complete test runtime. Extract `pytest_addoption`, docker-compose lifecycle, and runner logic into `tests/_e2e_runner.py`, leaving only fixtures in the conftest.
4. **Consider extracting migration-safety patches** (sync_apps, MigrationExecutor, MigrationLoader, create_contenttypes, create_permissions, _create_test_db) from `tests/conftest.py` into `tests/_patches.py` to reduce the 2,401-line conftest to a more manageable size (~500 lines of actual fixtures).
5. **Document the dual-conftest architecture** in `CLAUDE.md` so future developers understand why there are two root conftest files.
6. **Verify `hub/apps/datasets/tests/conftest.py` and `hub/apps/ai/tests/conftest.py`** are intentionally empty or add fixtures.
