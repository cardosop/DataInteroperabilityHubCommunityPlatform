# Test Settings Module Audit

**Date:** 2026-05-21
**Scope:** 3 test settings modules + all `DJANGO_SETTINGS_MODULE` references across the codebase.
**Methodology:** Every `DJANGO_SETTINGS_MODULE` reference was located via grep; every settings file was read for content and import chain.

---

## Summary

| Settings Module | Lines | Status | Used In CI? |
|---|---|---|---|
| `hub/settings.py` | ~2,000+ | **Active** — primary settings | Yes (all workflows) |
| `hub/test_settings_phase11.py` | 12 | **Legacy** — Phase 11 only | **No** |
| `hub/tests/test_settings_admin_alias.py` | — | **Active** — tests admin alias | Yes (via test discovery) |

---

## 1. `hub/settings.py` — Primary Settings Module

### Overview

The single settings module used for ALL environments: development, test, staging, and production. Environment differentiation is handled via `ENVIRONMENT` env var (`development`/`staging`/`production`) and feature toggles.

### Test-Specific Configuration

Key test-related settings in `hub/settings.py`:

| Setting | Line | Behavior |
|---|---|---|
| `SKIP_TEST_MIGRATIONS` check | L704-705 | When `SKIP_TEST_MIGRATIONS=1`, uses `NoMigrateDatabaseCreation` custom runner |
| `TEST_DB_SUFFIX` | L639-640 | When set, uses fixed DB name for shared test DB (`hub_test_test_shared`) |
| `DOCKER_COMPOSE_E2E_TEST` | L542, L570 | Disables certain checks during Docker Compose E2E runs |
| `TESTING` env detection | (multiple) | Detects test runs via `PYTEST_CURRENT_TEST` or `DJANGO_SETTINGS_MODULE` ending with `test` |

### Admin URL Hardening (Phase 306.2)

```python
ADMIN_URL = env("ADMIN_URL", default="admin/")
```

This is tested via `hub/tests/test_settings_admin_alias.py`.

---

## 2. `hub/test_settings_phase11.py` — Legacy Settings

**Full contents (12 lines):**

```python
"""
Test settings for Phase 11 workflow tests.
Uses a fixed test database to avoid migration timeouts.
"""

from hub.settings import *

# Override database name for tests
DATABASES["default"]["NAME"] = "hub_test_phase11"
if "TEST" not in DATABASES["default"]:
    DATABASES["default"]["TEST"] = {}
DATABASES["default"]["TEST"]["NAME"] = "hub_test_phase11"
```

### Status: LEGACY — Safe to Delete

- **Not referenced in any CI workflow** — all CI workflows use `DJANGO_SETTINGS_MODULE=hub.settings`.
- **Not importable as pytest conftest** — `hub/conftest.py` (L45) explicitly ignores it: `collect_ignore = ["test_settings_phase11.py"]`.
- **Phase 11 is complete** — this file was for a specific development phase's workflow tests.
- **Risk if kept:** If accidentally imported (e.g., by an IDE or test collector), `from hub.settings import *` followed by `DATABASES["default"]["NAME"] = "hub_test_phase11"` would silently switch the test database for all subsequent tests.

---

## 3. `hub/tests/test_settings_admin_alias.py` — Active Test

This is a **test file** (not a settings module). It tests the `ADMIN_URL` configuration from `hub/settings.py`. It is properly discovered by pytest and included in CI test runs.

---

## 4. `DJANGO_SETTINGS_MODULE` — Full Reference Catalog

### 4.1 All Unique Values Found

Only **one** value is used across the entire codebase:

```
hub.settings
```

That's it. There are zero references to `hub.test_settings_phase11` or any other settings module.

### 4.2 Reference Locations

**Python files (setdefault pattern):**

| File | Line | Pattern |
|---|---|---|
| `hub/manage.py` | 13 | `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')` |
| `hub/wsgi.py` | 14 | `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')` |
| `hub/asgi.py` | 16 | `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')` |
| `hub/conftest.py` | 55 | `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")` |
| `services/prefect-integration/main.py` | 25 | `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")` |
| `services/prefect-integration/status_sync.py` | 20 | `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")` |
| `services/worker/main.py` | 30 | `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")` |
| `tests/e2e/conftest.py` | 62-63 | Conditional setdefault |
| `tests/performance/setup_test_users.py` | 18 | setdefault |

**Docker Compose files:**

| File | Service | Line |
|---|---|---|
| `docker-compose.yml` | Various | L990 |
| `docker-compose.test.yml` | `api-service-test` | L130 |
| `docker-compose.test.yml` | `api-service-test-mvp` | L837 |
| `docker-compose.test.yml` | `api-service-test-full` | L1059 |
| `docker-compose.test.yml` | `worker-service-test` | L1296 |
| `docker-compose.test.mvp.yml` | Various | L41, L58 |
| `docker-compose.production.yml` | Various | L401 |

**CI Workflows:**

| Workflow | Occurrences |
|---|---|
| `ci.yml` | 9 |
| `lineage-snapshots-f5-dod.yml` | 2 |
| `lineage-snapshots-f5-soak.yml` | 1 |
| `api-naming-validation.yml` | 1 |

**Kubernetes/Helm:**

| File | Occurrences |
|---|---|
| `helm/values.yaml` | 1 |
| `helm/templates/prefect/integration-service-deployment.yaml` | 1 |
| `k8s/api-service/base/deployment.yaml` | 2 |
| `k8s/api-service/base/configmap.yaml` | 1 |

**Environment files:**

| File | Occurrences |
|---|---|
| `.env.example` | 1 |
| `.env.dev` | 1 |
| `.env.dev.template` | 1 |
| `.env.staging` | 1 |
| `.env.test.example` | 1 |
| `.env.production.template` | 1 |

**Test files (runtime detection):**

Multiple test files check `DJANGO_SETTINGS_MODULE` at runtime:
- `hub/apps/contracts/views.py` (L397, L445, L448) — 3 occurrences
- `hub/apps/contracts/views_refactored.py` (L323, L358, L360, L392, L395, L425, L428) — 7 occurrences
- `hub/apps/contracts/views_base.py` (L214) — 1 occurrence
- `hub/apps/contracts/urls.py` (L268) — 1 occurrence
- `hub/apps/auth/middleware.py` (L407) — 1 occurrence

These runtime checks follow the pattern:
```python
os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test")
```
This is an anti-pattern — production code checking for test environment by string-matching a settings module name.

---

## 5. Import Chain

```
hub/settings.py
  └── from hub.aws_secrets_loader import load_from_aws  (conditional: AWS_SECRETS_ENABLED=true)
  └── import environ, sentry_sdk, django.*

hub/test_settings_phase11.py
  └── from hub.settings import *   (LEGACY — mutates DATABASES)
```

There is no circular import risk. The only dangerous import is `test_settings_phase11.py` doing `from hub.settings import *` followed by mutation.

---

## Recommendations

1. **Delete `hub/test_settings_phase11.py`** — legacy Phase 11 settings, not referenced anywhere, actively ignored by conftest, and dangerous if accidentally imported.
2. **Remove runtime `DJANGO_SETTINGS_MODULE` checks in production code** — `hub/apps/contracts/views.py`, `views_refactored.py`, `views_base.py`, `urls.py`, and `hub/apps/auth/middleware.py` should use a proper `TESTING` flag (already set by both conftest files) instead of string-matching `DJANGO_SETTINGS_MODULE.endswith("test")`.
3. **Consider `hub/test_settings.py` for test-specific overrides** — a cleaner pattern than scattering `if os.getenv("TEST_DB_SUFFIX")` throughout `hub/settings.py` (L639-640, L704-705). However, this is low-priority since the current approach works.
4. **Document `hub.settings` as the single settings module** — the fact that only ONE `DJANGO_SETTINGS_MODULE` value exists is a design strength worth documenting.
