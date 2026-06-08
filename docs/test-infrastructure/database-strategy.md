# Test Database Strategy

> Phase 312.11.2 — Documents shared vs private test databases, `TEST_DB_SUFFIX`,
> database roles, pytest DB options, xdist semantics.

## Overview

The test infrastructure supports two database modes:

| Mode | DB Name | When | Isolation |
|---|---|---|---|
| **Private** | `hub_test_<random>` | Default (no env var set) | Full — each pytest session gets its own DB |
| **Shared** | `hub_test_test_<suffix>` | `TEST_DB_SUFFIX=shared` | Transactional — multiple workers share one DB |

## TEST_DB_SUFFIX

**Purpose:** Appends a suffix to the test database name so multiple test runners
(API service, worker, Prefect integration) can share a single pre-migrated
database.

**Read at (12 code references):**
- `hub/settings.py:639-640` — Sets fixed DB name when `TEST_DB_SUFFIX` is set
- `tests/conftest.py` (originally, now `hub/testing/patches.py`) — Idempotent
  `create_contenttypes` / `create_permissions` use `ignore_conflicts=True` when
  `TEST_DB_SUFFIX` is set
- `hub/testing/patches.py:_patch_create_test_db_duplicate()` — Treats
  `DuplicateDatabase` as success when suffix is set
- `hub/testing/patches.py:_patch_setup_databases()` — Forces `keepdb=True`
  when suffix is set
- `hub/testing/patches.py:_patch_teardown_databases()` — Forces `keepdb=True`
  when suffix is set

**Set at:**
- `docker-compose.test.yml` (api-service-test, worker-service-test): `TEST_DB_SUFFIX: "shared"`
- Multiple `scripts/run_migrated_*` scripts: `TEST_DB_SUFFIX=migrated_tests`

**Default:** Empty string (private DB — auto-generated unique name per session).

### How TEST_DB_SUFFIX works

```
TEST_DB_SUFFIX not set:
  DB name = hub_test_<random_8_chars>   (e.g., hub_test_a3f8c2b1)
  django.test.utils creates a new DB per session
  teardown drops the DB

TEST_DB_SUFFIX=shared:
  DB name = hub_test_test_shared
  Django reuses the existing DB (keepdb=True forced)
  Multiple services connect to the same DB
  Writes from one service are visible to all others
  FLUSH (TRUNCATE CASCADE) runs between test classes
```

## SKIP_TEST_MIGRATIONS

**Purpose:** When `=1` (and `--keepdb`), skips the `migrate` step entirely.
The test runner (`NoMigrateTestRunner` in `hub/testing/test_runner.py`)
reuses the existing test database as-is.

**Read at (37 references):**
- `hub/testing/test_runner.py` — `NoMigrateDatabaseCreation` class
- `hub/settings.py` — Custom test runner selection
- Multiple shell scripts (`run_migrated_*.sh`)

**Default:** Off (migrations run normally).

**Risk:** Skipping migrations means schema changes aren't applied. Use only
when the DB is known to be at the correct migration level.

## Database Roles

| Role/Alias | User | Purpose | RLS |
|---|---|---|---|
| `default` | `hub_test` | Primary test database — all app tables | RLS enabled |
| `admin` | `hub_test` | Admin bypass route (BYPASSRLS in prod, same user in test) | Same physical DB |
| `meshant_app` | `meshant_app` | App-level role for RLS baseline tests | RLS enforced |
| `meshant_admin` | `meshant_admin` | Admin-level role for BYPASSRLS tests | RLS bypassed |
| `baas` | `hub_test` | BaaS usage records (separate alias, same physical DB in test) | n/a |

In test mode, `default` and `admin` point to the SAME physical database
(with different aliases). The `_patch_dedup_databases_names()` patch in
`hub/testing/patches.py` deduplicates these so `TransactionTestCase`
only flushes once per physical backend, preventing deadlocks.

## pytest DB Options

### `--reuse-db` / `--keepdb`

Reuses the test database across pytest sessions. The database is NOT dropped
at the end of the session. Required when:
- Running with xdist (`-n auto`) — each worker shares the same test DB
- Iterating on a specific test — avoids the 30-60s create+migrate startup
- Running multiple test batches against the same database

### `--database <role>`

Selects a specific database role for role-aware integration suites:
```
pytest --database=meshant_app  # Run as app-level user (RLS enforced)
pytest --database=meshant_admin # Run as admin-level user (RLS bypassed)
pytest --database=default       # Default role
```

Registered in `tests/conftest.py:pytest_addoption()`.

### `--create-db`

Forces creation of a fresh test database (ignores `--reuse-db`).
Used in CI for clean-slate runs.

## xdist + Django

When running with `pytest -n auto`:
- All workers share the same test database
- `--reuse-db` is REQUIRED (otherwise each worker tries to create its own DB)
- Transactional isolation: each worker's tests run in separate transactions
- `xdist_group("serial")`: tests that must run alone (no concurrent workers)
- `xdist_group("db_write_heavy")`: tests contending on DB writes

The dedup patch (`_patch_dedup_databases_names`) reduces the per-physical-DB
flushes from N (one per alias) to 1, preventing deadlocks under xdist.

## Database Creation Flow

1. pytest-django calls `setup_databases()`
2. `_patch_setup_databases()` forces `keepdb=True` when `TEST_DB_SUFFIX` is set
3. `_patch_create_test_db_keepdb()` provides fast path when DB already migrated
4. `_patch_create_test_db_duplicate()` catches `DuplicateDatabase` as success
5. Migrations run (or skipped if `SKIP_TEST_MIGRATIONS=1`)
6. `create_contenttypes` / `create_permissions` run idempotently
7. Tests execute
8. `_patch_teardown_databases()` forces `keepdb=True` for shared DBs
9. `_patch_sql_flush_cascade()` uses `TRUNCATE ... CASCADE` for FK-safe cleanup
10. `_patch_post_flush_reseed()` re-seeds `TenantPlan` rows after TRUNCATE

## Connection Management

- **Statement timeout**: 120s in test mode (`hub/settings.py`). Reduced to
  10s during seed operations and 60s during teardown flush.
- **Lock timeout**: 60s default, reduced to 5s during flush.
- **synchronous_commit**: Set to `off` during teardown for faster TRUNCATE
  (test data has no durability requirement).
- **Connection recovery**: `pytest_runtest_setup` in `hub/conftest.py`
  verifies connections are alive before each test, rolling back aborted
  transactions and reconnecting as needed.
