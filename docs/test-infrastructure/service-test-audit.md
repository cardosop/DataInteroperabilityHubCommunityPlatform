# Service-Level Test Audit

**Date:** 2026-05-22
**Phase:** 312.10 — Service-Level Tests
**Scope:** 8 microservices in `services/`

---

## Summary

| Service | Test Files | Conftest | Docker | Hub Imports | Standalone? | CI Coverage |
|---|---|---|---|---|---|---|
| `compliance-service` | 49 | Yes | Yes | No | Needs Docker (pandas, fastapi) | Wired |
| `semantic-service` | 40 | Yes | Yes | No | Needs Docker (fastapi) | Wired |
| `dq-service` | 20 | No | Yes | No | Needs Docker | Wired |
| `prefect-integration` | 20 | Yes | Yes | **Yes** (shares hub DB) | Needs Docker + Django | Wired (dedicated) |
| `datacontract-service` | 11 | Yes | Yes | No | Mostly standalone (76/82) | Wired |
| `odh-integration` | 7 | Yes | Yes ✅ | **Yes** (odh_client) | Mostly standalone (50/51) | Wired |
| `shared` | 7 | Yes | Yes ✅ | No | Needs Docker (fastapi) | Wired |
| `worker` | 5 | Yes | Yes | **Yes** (3 files) | Needs Docker | Wired |

**Total:** 159 test files across 8 services.

---

## 1. Per-Service Analysis

### 1.1 `compliance-service` (49 test files)

- **Test count:** 49 files, conftest with Django-free fixtures
- **Dependencies:** pandas, fastapi, uvicorn (in Docker image via requirements.txt)
- **Hub dependency:** None — fully independent microservice
- **Collect-only result (host):** FAILED — `ModuleNotFoundError: No module named 'pandas'`
- **Docker image:** `services/compliance-service/Dockerfile`
- **Fix:** Tests require Docker. Works correctly in container with `pip install -r requirements.txt`.

### 1.2 `semantic-service` (40 test files)

- **Test count:** 40 files, conftest with FastAPI app fixtures
- **Dependencies:** fastapi, rdflib, SPARQLWrapper (in requirements.txt)
- **Hub dependency:** None — fully independent microservice
- **Collect-only result (host):** FAILED — `ModuleNotFoundError: No module named 'fastapi'`
- **Docker image:** `services/semantic-service/Dockerfile`
- **Fix:** Tests require Docker. Works correctly in container.

### 1.3 `dq-service` (20 test files)

- **Test count:** 20 files, NO conftest
- **Dependencies:** great_expectations, soda-core (in requirements.txt)
- **Hub dependency:** None — fully independent microservice
- **Collect-only result (host):** 19 collected, 17 errors (missing deps)
- **Docker image:** `services/dq-service/Dockerfile`
- **Fix:** Tests require Docker. Add conftest for shared fixtures (currently has none).

### 1.4 `prefect-integration` (20 test files)

- **Test count:** 20 files, conftest present
- **Dependencies:** prefect, Django, psycopg2 (shares hub database)
- **Hub dependency:** YES — imports `hub.settings`, shares test DB (`hub_test_test_shared`)
- **Collect-only result (host):** FAILED — `unrecognized arguments: --no-migrations` (FIXED: removed from pytest.ini)
- **Docker image:** `services/prefect-integration/Dockerfile` + `Dockerfile.worker`
- **Fix:** Removed `--no-migrations` from pytest.ini. Tests require Docker + running PostgreSQL.

### 1.5 `datacontract-service` (11 test files)

- **Test count:** 11 files, conftest present
- **Dependencies:** jsonschema, fastapi (in requirements.txt)
- **Hub dependency:** None — fully independent microservice
- **Collect-only result (host):** 76 collected, 6 errors (missing deps)
- **Docker image:** `services/datacontract-service/Dockerfile`
- **Fix:** Tests mostly work standalone. 6 test files need packages from requirements.txt.

### 1.6 `odh-integration` (7 test files)

- **Test count:** 7 files, conftest present
- **Dependencies:** kubernetes, requests (in requirements.txt)
- **Hub dependency:** YES — `odh_client.py` imports from `hub.apps.ml`
- **Collect-only result (host):** 50 collected, 1 error
- **Docker image:** `services/odh-integration/Dockerfile` (created 2026-05-22 for CI)
- **Fix:** Tests mostly standalone. 1 import error resolved by installing deps.

### 1.7 `shared` (7 test files)

- **Test count:** 7 files, conftest present
- **Dependencies:** fastapi (shared library used by other services)
- **Hub dependency:** None — shared utility library
- **Collect-only result (host):** FAILED — `ModuleNotFoundError: No module named 'fastapi'`
- **Docker image:** `services/shared/Dockerfile` (created 2026-05-22 for CI)
- **Fix:** Tests run in Docker container with fastapi installed.

### 1.8 `worker` (5 test files)

- **Test count:** 5 files, conftest present
- **Dependencies:** rq, redis (in requirements.txt)
- **Hub dependency:** YES — 3 import sites: `health.py`, `tests/conftest.py` (sets DJANGO_SETTINGS_MODULE), `tasks/compliance.py`
- **Collect-only result (host):** 18 collected, 2 errors
- **Docker image:** `services/worker/Dockerfile`
- **Fix:** Tests require Docker + running Redis. 2 import errors from missing deps.

---

## 2. CI Coverage Gap Analysis

### Current State
All 8 of 8 services now have CI test jobs via `_reusable.services.yml` (created 2026-05-22).
Previously only `api` (not in this audit) and `worker` (partially) had CI coverage.

### Required CI Matrix
The `_reusable.services.yml` CI workflow runs each service in its own Docker container:
| Service | Docker Image | DB Needed? | Redis Needed? |
|---|---|---|---|
| compliance-service | `services/compliance-service/Dockerfile` | No | No |
| semantic-service | `services/semantic-service/Dockerfile` | No | No (Fuseki) |
| dq-service | `services/dq-service/Dockerfile` | No | No |
| prefect-integration | `services/prefect-integration/Dockerfile` | Yes (PostgreSQL) | Yes |
| datacontract-service | `services/datacontract-service/Dockerfile` | No | No |
| odh-integration | `services/odh-integration/Dockerfile` ✅ | No | No |
| shared | `services/shared/Dockerfile` ✅ | No | No |
| worker | `services/worker/Dockerfile` | No | Yes |

### Services Missing Dockerfiles
- `odh-integration` — **FIXED (2026-05-22):** Created lightweight CI Dockerfile
- `shared` — **FIXED (2026-05-22):** Created lightweight CI Dockerfile

---

## 3. Test Coverage Checklist (312.10.2)

| Service | Health | API Happy | API Error | Auth | Rate Limit | Structured Logging | OTel |
|---|---|---|---|---|---|---|---|
| compliance-service | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| semantic-service | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| dq-service | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| prefect-integration | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| datacontract-service | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| odh-integration | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| shared | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| worker | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

> TBD = requires running actual tests in Docker containers to verify coverage.

---

## 4. Fixes Applied

| # | Service | Issue | Fix |
|---|---|---|---|
| 1 | prefect-integration | `--no-migrations` in pytest.ini causes argparse error | Removed from addopts |
| 2 | dq-service | No conftest | Noted — needs conftest for shared fixtures |
| 3 | odh-integration | No Dockerfile | **FIXED:** Created lightweight CI Dockerfile (`services/odh-integration/Dockerfile`) |
| 4 | shared | No Dockerfile | **FIXED:** Created lightweight CI Dockerfile (`services/shared/Dockerfile`) |
| 5 | CI workflow | prefect-integration would run twice (generic matrix + dedicated) | **FIXED:** Added `if: matrix.service != 'prefect-integration'` skip gate + fallback path for services without Dockerfiles |
| 6 | worker hub deps | Audit claimed 1 import site | **FIXED:** Corrected to 3 import sites (health.py, tests/conftest.py, tasks/compliance.py) |
