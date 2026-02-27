# E2E Environment Requirements

**Last Updated**: 2026-02-19
**Task**: Phase 7.1.2 — Services per test group, health checks, availability detection
**Related**: [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md), [DOCKER_COMPOSE_DEPLOYMENT.md](DOCKER_COMPOSE_DEPLOYMENT.md)

---

## Overview

This document lists services required per E2E test group, how to detect their availability, and health check procedures. Use it to determine which services must be running before a test run and when tests may skip due to optional service unavailability.

---

## 1. Test Groups and Service Requirements

### 1.1 Core Test Group (Required for All E2E)

These services **must** be running. If any is unavailable, E2E tests will fail (not skip). Do not run E2E without them.

| Service | Compose Service Name | Default Host Port | Health Check | Detection |
|---------|---------------------|------------------|---------------|-----------|
| **API** | `api-service-test` | 8001 | `GET /health/` → 200 | `curl -s http://localhost:8001/health/` |
| **PostgreSQL** | `postgres-test` | 5434 | `pg_isready -U hub_test -d hub_test` | `pg_isready -h localhost -p 5434 -U hub_test -d hub_test` |
| **Redis (Cache)** | `redis-cache-test` | 6379 | `redis-cli ping` | `redis-cli -h localhost -p 6379 ping` |
| **Redis (Queue)** | `redis-queue-test` | 6380 | `redis-cli ping` | `redis-cli -h localhost -p 6380 ping` |
| **MinIO** | `minio-test` | 9010 (API), 9011 (Console) | `GET http://localhost:9010/minio/health/live` | `curl -sf http://localhost:9010/minio/health/live` |

**Environment Variables** (override defaults):

- `API_BASE_URL` / `E2E_API_BASE_URL` / `VITE_API_BASE_URL` — API base (e.g. `http://localhost:8001/api/v1` for test stack)
- `POSTGRES_TEST_PORT`, `REDIS_CACHE_TEST_PORT`, `MINIO_TEST_API_PORT` — Port overrides

**Start Command**:

```bash
docker compose -f docker-compose.test.yml up -d postgres-test redis-cache-test redis-queue-test redis-events-test redis-channels-test minio-test api-service-test
```

---

### 1.2 Optional Services (Tests May Skip If Unavailable)

Some E2E tests require additional services. If unavailable, tests skip with a clear reason (see [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md)).

| Service | Compose Service Name | Default Host Port | Health Check | Used By |
|---------|---------------------|------------------|---------------|---------|
| **Prefect** (server, db, worker, integration) | `prefect-db-test`, `prefect-server-test`, `prefect-worker-test`, `prefect-integration-service-test` | 4202 (server), 8114 (integration) | `GET http://localhost:8114/health` | `scheduled-ingestion-journey.spec.ts`, `scheduled-export-journey.spec.ts` |
| **MailHog** | `mailhog-test` | 8025 (UI/API), 1025 (SMTP) | `GET http://localhost:8025/api/v2/messages?limit=1` | `JOURNEY-AUTH-003.spec.ts`, `auth-visitor-journeys.spec.ts` (password reset) |
| **AI/ML (ODH Inference Scheduler)** | `odh-inference-scheduler-test` | 8080 | `GET http://localhost:8080/health` | `hub/apps/ml/tests/test_inference_real_integration.py` |

**Start Commands**:

```bash
# Prefect (scheduled ingestion/export)

docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test

# MailHog (password reset E2E)

docker compose -f docker-compose.test.yml up -d mailhog-test

# AI/ML (ODH Inference Scheduler)

docker compose -f docker-compose.test.yml up -d odh-inference-scheduler-test odh-training-operator-test
```

**Environment Variables**:

- `PREFECT_INTEGRATION_SERVICE_URL` — Prefect integration service URL (default: `http://localhost:8084`; host: `http://localhost:8114` when using docker-compose.test.yml)
- `MAILHOG_URL` — MailHog API URL (default: `http://localhost:8025`)
- `ODH_INFERENCE_SCHEDULER_URL` — ODH Inference Scheduler URL (default: `http://odh-inference-scheduler-test:8080` in Docker)

---

## 2. Health Checks

### 2.1 Scripted Health Checks

Use the health check scripts before running E2E:

```bash
# E2E test stack (recommended — checks core services only)

./scripts/health-checks/health-check-e2e.sh

# Or explicitly:

COMPOSE_FILE=docker-compose.test.yml ./scripts/health-checks/health-check-e2e.sh
```

**Alternative** — full stack with `health-check-all.sh` (uses main compose by default; for test stack, set `COMPOSE_FILE` or `ENVIRONMENT=test`; note: service names differ between compose files):

```bash
COMPOSE_FILE=docker-compose.test.yml ./scripts/health-checks/health-check-all.sh
```

**Note**: `health-check-e2e.sh` is designed for the test stack and checks `postgres-test`, `redis-cache-test`, `minio-test`, `api-service-test`. The `health_check_lib.sh` respects explicit `COMPOSE_FILE` and supports `ENVIRONMENT=test` → `docker-compose.test.yml`.

### 2.2 Manual Health Checks

| Service | Check Command |
|---------|---------------|
| API | `curl -s http://localhost:8001/health/` |
| PostgreSQL | `pg_isready -h localhost -p 5434 -U hub_test -d hub_test` |
| Redis | `redis-cli -h localhost -p 6379 ping` |
| MinIO | `curl -sf http://localhost:9010/minio/health/live` |
| Prefect Integration | `curl -sf http://localhost:8114/health` |
| MailHog | `curl -sf http://localhost:8025/api/v2/messages?limit=1` |
| ODH Inference Scheduler | `curl -sf http://localhost:8080/health` |

### 2.3 How to Detect Availability

**In tests** (Playwright / pytest):

- **ConnectionRefused, Timeout, ConnectTimeout**: Transient — service not running or unreachable. Skip with clear reason.
- **Wrong URL, malformed response, 4xx/5xx from health endpoint**: Non-transient — configuration or service bug. Re-raise; do not skip.
- **Health endpoint returns 200**: Service available; proceed.

**Example (Playwright)**:

```typescript
let healthOk = false;
try {
  const res = await fetch(`${PREFECT_INTEGRATION_URL}/health`, { signal: AbortSignal.timeout(5000) });
  healthOk = res.ok;
} catch (e) {
  // ConnectionRefused, Timeout, etc. → skip
  test.skip(true, `Prefect not reachable: ${e}. Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`);
}
if (!healthOk) {
  test.skip(true, `Prefect unhealthy. Start: docker compose -f docker-compose.test.yml up -d ...`);
}
```

---

## 3. Test Group → Service Mapping

| Test Group | Core Services | Optional Services |
|------------|---------------|-------------------|
| Backend E2E (pytest) | API, Postgres, Redis, MinIO | Prefect (scheduled ingestion/export), ODH (ML inference) |
| Frontend E2E (Playwright) | API, Postgres, Redis, MinIO | Prefect, MailHog |
| Auth journeys (JOURNEY-AUTH-001, JOURNEY-AUTH-004) | Core | — |
| Auth password reset (JOURNEY-AUTH-003) | Core | MailHog |
| Scheduled ingestion/export | Core | Prefect |
| ML inference integration | Core | ODH Inference Scheduler |

---

## 4. Compose File Reference

| File | Purpose | API Port |
|------|---------|----------|
| `docker-compose.yml` | Production-style full stack | 8000 |
| `docker-compose.dev.yml` | Development with hot-reload | 8000 |
| `docker-compose.test.yml` | Test stack (isolated DB) | 8001 |

---

## 5. E2E User Setup

Before running frontend E2E, ensure E2E user roles exist:

```bash
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles
```

If this is not run, tests that require TA, PA, CPO, AUD, DEV, or DMO roles may redirect to login or fail.

---

## 6. Pytest Markers (Test Requirements Discoverability)

Use these markers to discover which tests require which services. See `pytest.ini` and `tests/e2e/conftest.py`.

| Marker | Service | Behavior When Unavailable | Used By |
|--------|---------|---------------------------|---------|
| `@pytest.mark.requires_minio` | MinIO/S3 | Skip (fixture `require_minio`) | Backend E2E file upload tests |
| `@pytest.mark.requires_prefect` | Prefect (server, worker, integration) | Fail (Phase 7.4.3) | `scheduled-ingestion-journey.spec.ts`, `scheduled-export-journey.spec.ts`, backend scheduled ingestion/export |
| `@pytest.mark.requires_mailhog` | MailHog | Skip (Phase 7.4.4) | `JOURNEY-AUTH-003.spec.ts`, `auth-visitor-journeys.spec.ts` (password reset) |

**Usage**:

```bash
# Run only tests that require MinIO
pytest -m requires_minio

# Exclude tests that require Prefect (e.g. when Prefect not started)
pytest -m "not requires_prefect"

# Exclude tests that require MailHog
pytest -m "not requires_mailhog"
```

**Note**: Playwright E2E tests use runtime checks (not pytest markers). The markers above apply to backend pytest E2E. Frontend test requirements are documented in [E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md).

### 6.1 Optional: Core vs Optional CI Job Separation

For CI optimization, tests can be split into:

- **Core job** (strict, required services only): `pytest -m "not requires_prefect and not requires_mailhog"` — runs with API, Postgres, Redis, MinIO. Fails fast when core stack is down.
- **Optional job** (Prefect, MailHog): `pytest -m "requires_prefect or requires_mailhog"` — runs when optional services are started. Can be a separate CI job or run in parallel.

See [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) for current CI structure.

---

## 7. References

- [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md) — When to skip vs fail
- [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md) — Skip conventions
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution order, CI
- [frontend/e2e/README.md](../frontend/e2e/README.md) — Frontend E2E setup
- [pytest.ini](../pytest.ini) — Marker definitions
