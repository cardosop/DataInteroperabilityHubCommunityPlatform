# Test Environment Variable Audit

**Date:** 2026-05-21
**Scope:** 14 `SKIP_*` / `TEST_*` / `USE_*` environment variables + 5 supplementary test-infrastructure variables.
**Methodology:** Each variable was grepped across the entire codebase (`.py`, `.yml`, `.sh`, `.env*`, `Makefile`, `.toml`, `.ini`). Every occurrence was traced to its read site and set site.

---

## Primary Audit: 14 Core Variables

| # | Variable | Reads | Sets | Type | Status |
|---|---|---|---|---|---|
| 1 | `SKIP_TEST_MIGRATIONS` | 4 | 10+ (shell scripts) | Skip | Active |
| 2 | `SKIP_PROD_DB_GUARD` | 4 | 1 (test) | Guard | Active |
| 3 | `SKIP_DB_CONNECTIVITY_CHECK` | 9 | 1 (shell script) | Skip | Active |
| 4 | `SKIP_DJANGO_SETUP` | 5 | 4 | Skip | Active |
| 5 | `SKIP_TEST_ENV_VALIDATION` | 6 | 0 | Skip | Near-dead |
| 6 | `TEST_DB_SUFFIX` | 17+ | 4 (compose + scripts) | Config | Active |
| 7 | `STRICT_TEST_TEARDOWN` | 6 | 0 | Gate | Active |
| 8 | `DJANGO_PATCH_DEBUG` | 2 | 0 (dev opt-in) | Debug | Active |
| 9 | `PYTEST_DOCKER_COMPOSE_RUNTIME` | 13 | 1 (CI) | Gate | Active |
| 10 | `OPEN_SPEC_PREPROD01_GATE_ONLY` | 5 | 1 (conftest) | Gate | Active |
| 11 | `REAL_SCHEDULED_E2E` | 8 | 2 (compose + docs) | Gate | Active |
| 12 | `VALIDATE_SERVICE_CONNECTIVITY` | 1 | 0 | Skip | **Near-dead** |
| 13 | `USE_REAL_SERVICES` | 1 | 4 (Makefile + scripts) | Gate | Active |
| 14 | `DOCKER_COMPOSE_E2E_TEST` | 5 | 1 (test file auto-set) | Gate | Active |

---

## Detailed Analysis (Variables 1-14)

### 1. `SKIP_TEST_MIGRATIONS`

**Purpose:** When `=1`, skips Django migrations during test DB creation. Used with `--keepdb` to reuse existing test DBs across test runs for faster iteration.

**Read at:**
- `hub/test_runner.py` L18, L37, L105 — `NoMigrateDatabaseCreation` class
- `hub/settings.py` L704-705 — Custom test runner selection

**Set at:** 10+ shell scripts including `run_migrated_app_tests_cycle.sh`, `run_all_migrated_tests.sh`, `run_migrated_tests_sequential.sh`, phase-specific E2E scripts.

**Default:** Off (migrations run normally).

**Risk if removed:** Test DB setup would run full migrations every time. Performance optimization for iterative development.

**Status:** Active.

---

### 2. `SKIP_PROD_DB_GUARD`

**Purpose:** Bypasses the production database safety check. The test runner refuses to run if the configured database name looks like a production DB.

**Read at:**
- `hub/test_runner.py` L73, L90, L100 — Production DB name check
- `hub/tests/test_test_infrastructure.py` L124 — Test verifying guard behavior

**Set at:** Never set in CI. Only tested in unit tests with `@patch.dict`.

**Default:** Guard active (production DB access blocked).

**Risk if removed:** Would prevent any test from running against databases named like production DBs. Production safety critical.

**Status:** Active. Do not remove.

---

### 3. `SKIP_DB_CONNECTIVITY_CHECK`

**Purpose:** Skips the session-start PostgreSQL connectivity probe in `hub/conftest.py::pytest_sessionstart`. Batch test runners skip re-checking DB on batches 2+.

**Read at:**
- `hub/conftest.py` L102, L160, L170, L176, L189, L194 — Connectivity probe and error messages

**Set at:**
- `scripts/run_phase_12a_backend_suites.sh` L160 — `skip_db_check="SKIP_DB_CONNECTIVITY_CHECK=1"` for batch_num > 1

**Default:** DB check performed (72 retries, 5s interval).

**Status:** Active.

---

### 4. `SKIP_DJANGO_SETUP`

**Purpose:** Skips `django.setup()` in `tests/conftest.py`. Required for non-Django test contexts (docker-compose runtime tests, security tests, ODPS schema validation).

**Read at:**
- `tests/conftest.py` L1620-1624

**Set at:**
- `tests/ci/test_odps_schema_validation_ci.py` L17
- `tests/integration/test_docker_compose_deployment.py` L44
- `tests/integration/test_redis_service_configuration_standalone.py` L18
- `tests/security/test_production_secrets.py` L28
- `scripts/run_docker_compose_integration_tests.sh` L170

**Default:** Django setup runs.

**Status:** Active. Required for non-Django test contexts.

---

### 5. `SKIP_TEST_ENV_VALIDATION`

**Purpose:** Skips test environment validation fixture in `tests/conftest.py`.

**Read at:**
- `tests/conftest.py` L1799-1800, L1829, L2071-2082

**Set at:** **Never set in any CI workflow, shell script, or compose file.** Developer opt-in only.

**Default:** Validation runs.

**Status:** Near-dead. Never activated in automation. Can be removed or documented as developer-only.

---

### 6. `TEST_DB_SUFFIX`

**Purpose:** Appends suffix to test database name. Most commonly `"shared"` for the shared test DB (`hub_test_test_shared`). Critical for E2E tests where worker and API service must share the same DB.

**Read at:**
- `hub/settings.py` L639-640 — Fixed DB name when suffix set
- `tests/conftest.py` L650, L684, L716-717, L734, L738, L752, L754, L837, L841 — Idempotent contenttypes/permissions, DuplicateDatabase handling

**Set at:**
- `docker-compose.test.yml` L835 (api-service-test) and L1038 (worker-service-test): `TEST_DB_SUFFIX: "shared"`
- Multiple `scripts/run_migrated_*` scripts: `TEST_DB_SUFFIX=migrated_tests`

**Default:** Empty (auto-generated unique DB name per session).

**Status:** Active. Critical for shared-DB E2E pattern.

---

### 7. `STRICT_TEST_TEARDOWN`

**Purpose:** When `=1`, teardown errors (shutdown, deadlock, statement timeout, missing table, duplicate key) are raised instead of suppressed.

**Read at:**
- `hub/conftest.py` L1381, L1397, L1412, L1426, L1438 — Five teardown error suppression points
- `hub/tests/test_test_infrastructure.py` L69-117 — Comprehensive test coverage

**Set at:** Never explicitly set in CI. **Should be enabled in CI.**

**Default:** Teardown errors suppressed.

**Status:** Active. Recommended to set `STRICT_TEST_TEARDOWN=1` in CI.

---

### 8. `DJANGO_PATCH_DEBUG`

**Purpose:** When `=1`, enables DEBUG logging for Django patch diagnostics in `tests/conftest.py`.

**Read at:**
- `tests/conftest.py` L27-31 — Logger level: DEBUG if flag set, WARNING otherwise

**Set at:** Developer opt-in only.

**Default:** WARNING (quiet).

**Status:** Active. Developer debugging tool.

---

### 9. `PYTEST_DOCKER_COMPOSE_RUNTIME`

**Purpose:** Gates Docker Compose runtime tests. When `=1`, loads docker-compose runtime fixtures and runs integration tests against live containers.

**Read at:**
- `tests/conftest.py` L18-22, L1619, L1804 — Progress messages, setup gating
- `tests/integration/test_docker_compose_deployment.py` L41, L773, L777 — Test skip/runtime gating
- `tests/integration/test_docker_compose.py` L333, L355, L372, L397, L410, L413 — Docker Compose runtime gating

**Set at:**
- `.github/workflows/ci.yml` L1793: `PYTEST_DOCKER_COMPOSE_RUNTIME: "1"`
- `scripts/run_phase_12a_backend_suites.sh` L194

**Default:** Off (docker compose tests skipped).

**Status:** Active. Required for Docker Compose integration tests.

---

### 10. `OPEN_SPEC_PREPROD01_GATE_ONLY`

**Purpose:** When `=1`, restricts test collection to only OpenSpec preprod01 gate tests.

**Read at:**
- `tests/conftest.py` L1273, L1279, L1621, L1625, L1752, L1992

**Set at:** `tests/conftest.py` L1279 (auto-set during `pytest_configure`).

**Default:** Off (all tests collected).

**Status:** Active. Pre-production gating mechanism.

---

### 11. `REAL_SCHEDULED_E2E`

**Purpose:** Gates real scheduled ingestion/export E2E tests (no mocks — uses real S3/Prefect).

**Read at:**
- `tests/conftest.py` L1598-1605 — Collection-time skip
- `hub/conftest.py` L687-712 — Same for hub-only runs
- `hub/apps/scheduled_ingestion/tests/test_real_scheduled_e2e_entrypoint.py` L39-62 — Runtime verification

**Set at:**
- `docker-compose.test.yml` L857: `REAL_SCHEDULED_E2E: ${REAL_SCHEDULED_E2E:-1}` (default ON in compose)

**Default:** `1` in docker-compose.test.yml. Off otherwise.

**Status:** Active. Required for production-like scheduled ingestion testing.

---

### 12. `VALIDATE_SERVICE_CONNECTIVITY`

**Purpose:** When `=1`, enables service connectivity validation.

**Read at:**
- `tests/conftest.py` L1835 — Single check

**Set at:** **Never set in any CI workflow, shell script, or compose file.**

**Default:** Off.

**Status:** **Near-dead.** One read site, zero set sites. Safe to remove.

---

### 13. `USE_REAL_SERVICES`

**Purpose:** When `=true`, tests use real external services instead of mocks.

**Read at:**
- `hub/apps/testing/service_utils.py` L151-158

**Set at:**
- `Makefile` L161, L166 — `USE_REAL_SERVICES=true pytest`
- `scripts/run-e2e-staging.sh` L64, L96 — Staging E2E runs

**Default:** Off (mocks used).

**Status:** Active. Used for staging E2E validation.

---

### 14. `DOCKER_COMPOSE_E2E_TEST`

**Purpose:** When `=true`, signals tests are running inside docker-compose E2E environment. Disables checks that would fail in containerized context.

**Read at:**
- `hub/settings.py` L542, L570 — Disables security checks
- `tests/conftest.py` L1633 — Django setup adaptation

**Set at:**
- `tests/e2e/test_docker_compose_e2e.py` L26 — Auto-set at module level: `os.environ['DOCKER_COMPOSE_E2E_TEST'] = 'true'`

**Default:** Not set (production security checks active).

**Status:** Active. Required for Docker Compose E2E compatibility.

---

## Supplementary Variables (documented in existing partial audit)

### `RATE_LIMIT_E2E_RELAX`

**Purpose:** Relax rate limits for E2E test tenants so 4+ parallel Playwright workers do not trigger HTTP 429 cascades.

**Default:** `false` (production-safe). Set to `true` in docker-compose.test.yml and docker-compose.dev.yml.

**Throttle multipliers when enabled:**

| Throttle Scope | Production Rate | E2E Rate | Multiplier |
|---|---|---|---|
| `tenant_scoped` | 30/min | 5,000/min | ~166x |
| `anon_tenant` | 60/min | 5,000/min | ~83x |
| AUTH (60s window) | 20 req/min | 500 req/min | 25x |
| AUTH (10s burst) | 10 req/10s | 100 req/10s | 10x |
| AUTH (daily cap) | 5,000/day | 100,000/day | 20x |
| ASSET/CONTRACT (60s) | 100 req/min | 5,000 req/min | 50x |
| GENERAL/CATALOG_READ/SEARCH | 600 req/min | 2,000 req/min | ~3.3x |

**Implementation:** `TenantScopedThrottle.get_rate()` and `AnonTenantThrottle.get_rate()` in `hub/apps/core/throttles.py`.

**Throttle cache key isolation:** All throttle cache keys include `tenant_id`. Tenant A never affects tenant B.

---

### `E2E_TEST_SECRET`

**Purpose:** Shared secret for `/api/v1/test/*` endpoints. `X-E2E-Token` header must match (constant-time comparison). When unset (empty), all test endpoints return 404 — production-safe by default.

**Referenced by:**
- `hub/apps/api/e2e_gating.py` L80 — `require_e2e_token` decorator
- `hub/apps/api/views.py` L54 — `ensure_e2e_tenant_switch_setup`
- `hub/apps/api/checks.py` L51 — Django system check `hub.E002`
- `hub/apps/api/mailhog_proxy_views.py` — MailHog proxy
- `hub/apps/api/webhook_sink_views.py` — Webhook sink

---

### `TEST_POSTGRES_STATEMENT_TIMEOUT_MS`

**Purpose:** Statement timeout for test DB connections. Prevents `QueryCanceled` under xdist.

**Default:** `120000` (120 seconds).

---

### `DSAR_SKIP_HCAPTCHA_VERIFICATION`

**Purpose:** Skip hCaptcha verification on public DSAR endpoint in E2E environments.

**Default:** `false` (always verify in production).

---

### Other Test-Infrastructure Env Vars

| Variable | Purpose | Default |
|---|---|---|
| `ENVIRONMENT` | `test`/`staging`/`production`/`development` | `development` |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `hub.settings` |
| `DEBUG` | Django DEBUG mode | `false` |
| `DQ_RUN_TIMEOUT` | DQ run timeout (lower in tests) | `60` |
| `DATABASE_URL` | Postgres connection string | (varies) |
| `REDIS_URL` | Redis cache connection | (varies) |
| `MVP_MODE` | Gates MVP-specific features | (unset) |

---

## Summary

| Variable | Criticality | Auto-Set? | Dead? |
|---|---|---|---|
| `SKIP_TEST_MIGRATIONS` | High (perf) | Yes (shell scripts) | No |
| `SKIP_PROD_DB_GUARD` | Critical (safety) | No | No |
| `SKIP_DB_CONNECTIVITY_CHECK` | Medium (perf) | Yes (batch scripts) | No |
| `SKIP_DJANGO_SETUP` | High (non-Django tests) | Yes (test files) | No |
| `SKIP_TEST_ENV_VALIDATION` | Low (debug) | No | **Near-dead** |
| `TEST_DB_SUFFIX` | Critical (E2E) | Yes (compose) | No |
| `STRICT_TEST_TEARDOWN` | Medium (quality) | No | No |
| `DJANGO_PATCH_DEBUG` | Low (debug) | No | No |
| `PYTEST_DOCKER_COMPOSE_RUNTIME` | High (integration) | Yes (CI) | No |
| `OPEN_SPEC_PREPROD01_GATE_ONLY` | Medium (gating) | Yes (conftest) | No |
| `REAL_SCHEDULED_E2E` | High (real E2E) | Yes (compose) | No |
| `VALIDATE_SERVICE_CONNECTIVITY` | Low (unused) | No | **Near-dead** |
| `USE_REAL_SERVICES` | High (staging) | Yes (scripts) | No |
| `DOCKER_COMPOSE_E2E_TEST` | High (compose) | Yes (test file) | No |

---

## Recommendations

1. **Remove `VALIDATE_SERVICE_CONNECTIVITY`** — one read site, zero set sites. Dead code.
2. **Remove or document `SKIP_TEST_ENV_VALIDATION`** — never set in automation.
3. **Enable `STRICT_TEST_TEARDOWN=1` in CI** — surfaces infrastructure issues currently silently suppressed.
4. **Add CI lint rule** — every `os.getenv("SKIP_*")`/`os.getenv("TEST_*")` read must have a corresponding set site documented.
5. **Document all 14+ variables in `docs/test-infrastructure/README.md`** — this audit serves as canonical reference.
6. **Consider renaming `VALIDATE_SERVICE_CONNECTIVITY`** → `SKIP_SERVICE_CONNECTIVITY_CHECK` for consistency with other skip flags (if kept).
