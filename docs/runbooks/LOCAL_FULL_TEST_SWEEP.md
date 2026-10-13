# Local Full Test Sweep — Step-by-Step (backend + frontend, all batches)

**Purpose:** run EVERY local test batch of every kind (unit, integration, E2E,
security, performance, regression, services, CLI/SDK, frontend vitest +
Playwright) against this machine, in iterate-and-fix order.
**Audience:** the preprod01 branch author before/after landing the
add-databricks-control-plane change.
**Authoritative sources:** `Makefile` batch targets (561–2660), `pytest.ini`
markers, `docs/runbooks/HOST_SIDE_VERIFICATION.md`, `frontend/scripts/e2e-batches.sh`.

---

## 0. The map — every batch, one table

| # | Target | Scope | Size | Runs where |
|---|---|---|---|---|
| — | `make ci-lint-local` | lint/format/mypy/bandit gates (the 12.9 battery) | ~2 min | host |
| — | GATE-01–09 checkers | test-quality family (9 scripts) | ~1 min | host |
| B1 | `make test-batch-1` | assets + files + datasets (9 sub-batches) | ~2,076 | container |
| B2 | `make test-batch-2` | contracts (10 sub-batches) | ~5,488 | container |
| B3 | `make test-batch-3` | compliance + marketplace + billing (11 subs) | ~2,000 | container |
| B4 | `make test-batch-4` | dq + governance + gdpr (6 subs) | ~2,000 | container |
| B5 | `make test-batch-5` | auth/tenants/semantic/search/social/users/scheduled/rate_limiting/notifications (5 subs) | ~2,000 | container |
| B6 | `make test-batch-6-1-all` + 6-2…6-6 | connectors (CKAN/AWS/Snowflake/Dados/GCP/Marketplace) | ~1,100 | container |
| B7 | `make test-batch-7` | ML/AI/BaaS/Transformation/Mesh/API (9 subs) | ~2,200 | container |
| B8 | `make test-batch-8` | GraphQL/Datasets D1-D3/GDPR-DSAR/health/data_movement/consent/RoPA/warehouses (7 subs) | ~2,050 | container |
| B9 | `make test-batch-9-1` + 9-2 + 9-3 | `hub/tests/` + CLI unit + security/use-case E2E (needs API :8001) | ~1,900 | container |
| B10 | `make test-batch-10` | `tests/unit`(3), `tests/integration`(9), `tests/e2e`(5), `tests/security`(273), `performance`(184), `regression`(225), smoke/resilience/uat(163), concurrency/pact/contract/property/load/chaos/migrations(156), scripts/docs/i18n/utils(291), infrastructure/ci/chains/prefect/benchmarks/dr(284), sdk_python/isolation/preprod01/observability/schema/fixtures/gdpr(294) | ~3,900 | container |
| B12 | `make test-batch-12-1…12-5` | compliance/semantic/dq/datacontract services (host) + prefect/worker (container) + odh/shared (host) | ~1,100 | both |
| EST | estate direct run (NOT in any batch — the change's own scope) | `databricks_admin` + `data_movement` + `scheduled_export` + `scheduled_ingestion` + `warehouses` | ~1,500 | container or host |
| F1 | `cd frontend && npm run test:run` + `test:component` | vitest unit + component | ~15 min | host |
| F2 | `make test-frontend-e2e-batch1a/1b/1c` then 2…8 | Playwright (auth, a11y/UX, security, routes, 13 persona journey groups, UX flows) | ~1,885 | host (needs API :8001 + Vite) |
| F3 | `npm run test:a11y` | Playwright axe audits (a11y config) | ~10 min | host |
| SWEEP | `make test-batch-all` | B1…B10 + B12, continues on failure | hours | container |
| CI | `make test-ci` | lint + `hub/apps` full in-container + vitest (CI parity) | ~1 h | both |

**Known reds (not this change's debt, do not chase):** frontend
fragile-selector ratchet (+1.14pp, peer-owned) and mutation-coverage
(~625 EXPIRED allowlist entries, owning workstream). Connector batches
SKIP without credentials. Live-Databricks/`real_scheduled_e2e` legs are
W16-gated locally (CI raises).

---

## Phase 0 — One-time setup (~15 min)

### 0.1 Test stack up (container batches + Playwright API)

```bash
docker compose -f docker-compose.test.yml ps          # health check
make test-stack-up                                     # only if down: build + start + --wait
# tear-down when finished:  make test-stack-down  (removes volumes!)
```

The stack exposes: API `:8001` (api-service-test), worker, prefect,
compliance, dq, semantic, datacontract services, postgres, redis, minio,
fuseki. Playwright's `e2e-detect-api.sh` auto-detects `:8001` and can
auto-start the stack; batch targets expect it to be running already.

### 0.2 Host-side env block (for EST host-side runs, 12-1…12-4, scripts/tests)

From `docs/runbooks/HOST_SIDE_VERIFICATION.md` — paste into every
host-side shell:

```bash
export PY=venv/bin/python
export POSTGRES_HOST=localhost POSTGRES_PORT=54329
export POSTGRES_USER=hub POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub_test_313full TEST_DB_SUFFIX=313full
export ENVIRONMENT=test JWT_ALGORITHM=HS256
export REDIS_URL=redis://127.0.0.1:63799/0
# The cache role points at the TEST STACK's cache (hub-test-redis-cache,
# host port 6479) — the same instance in-container batches use. Contracts
# Redis tests skip when their skip gate — a ping() on settings.REDIS_URL
# (NOT REDIS_CACHE_URL) — cannot reach an instance; both variables must
# point at a reachable instance. The dedicated contracts recipe lives in
# HOST_SIDE_VERIFICATION.md (both vars at 6479 → 82 passed / 0 skipped).
export REDIS_CACHE_URL=redis://localhost:6479/0
export REDIS_QUEUE_URL=redis://127.0.0.1:63799/0
export AWS_S3_ENDPOINT_URL=http://localhost:9010
export AWS_ACCESS_KEY_ID=minio
export AWS_SECRET_ACCESS_KEY=minio123   # or: docker inspect hub-minio --format '{{range .Config.Env}}{{println .}}{{end}}' | grep MINIO_ROOT_PASSWORD
```

`TEST_DB_SUFFIX` is REQUIRED (without it settings.py invents a UUID DB
name and every DB test errors).

### 0.3 Host-side database — migrate + optional isolated clone

```bash
# migrate the canonical host-side DB to HEAD
$PY hub/manage.py migrate --noinput   # with the 0.2 env exported

# OPTIONAL — dedicated review DB so parallel sessions never contend
# (the multi-session sqlflush deadlock class):
docker exec p313-pg psql -U hub -d postgres -c \
  "CREATE DATABASE hub_test_review TEMPLATE hub_test_313full OWNER hub;"
# then use:  export POSTGRES_DB=hub_test_review TEST_DB_SUFFIX=review
# drop afterwards: DROP DATABASE hub_test_review WITH (FORCE);
```

p313-pg listens on `:54329`; there is also `pg-rls-fast` (`:54391`, tmpfs —
the 12.13 coverage-session DB) and `hub-test-postgres` (`:5434`).

### 0.4 Frontend one-time setup

```bash
cd frontend
npm ci                                  # if lockfile changed
npx playwright install --with-deps      # browsers (first time only)
npm run test:run                        # quick vitest smoke — must pass
cd ..
```

Playwright prerequisites: the API reachable at `http://127.0.0.1:8001`
(container stack, Phase 0.1) and the frontend dev server (the batch
script auto-starts Vite; `E2E_RESTART_FRONTEND=1` restarts it between
batches; `E2E_SKIP_API_RESTART=1` avoids API restarts between batches).

### 0.5 Sanity sweep

```bash
make verify-deps
make wait-for-services
docker compose -f docker-compose.test.yml ps
```

---

## Phase 1 — Static gates (~5 min, re-run after EVERY fix wave)

```bash
make ci-lint-local        # lint ratchet, format, mypy, bandit-parity, GATE-39/40, SSRF/import bans, SDK/parity ratchets, in-container makemigrations + throttle
make quality-gates        # GATE-01..09 + spec coverage + markers + docs sync
make audit-docs
```

---

## Phase 2 — Change-scope estate first (~15 min, fastest signal on THIS change)

No batch covers `databricks_admin` — run it directly, container or host:

```bash
# in-container (preferred — every dependency pre-wired):
docker compose -f docker-compose.test.yml exec -T api-service-test \
  python -u -m pytest \
  hub/apps/databricks_admin hub/apps/warehouses \
  hub/data_movement \
  hub/apps/scheduled_export hub/apps/scheduled_ingestion \
  --reuse-db -q --timeout=300

# host-side alternative (runbook env from 0.2 exported):
$PY -m pytest hub/apps/databricks_admin hub/apps/warehouses \
  hub/data_movement hub/apps/scheduled_export hub/apps/scheduled_ingestion -q
```

Iterate: single file, then single sub-batch:

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test \
  python -u -m pytest hub/apps/databricks_admin/tests/test_cost_sync.py -x -q --reuse-db
```

---

## Phase 3 — Backend batches, in order

All batch targets run inside `api-service-test` with `--reuse-db -q
--timeout=300`. Run them sequentially — parallel pytest sessions on one
DB deadlock on `sqlflush` (the multi-session contention class).

```bash
# B1  assets/files/datasets
make test-batch-1        # or per sub-batch: test-batch-1-1 … 1-9

# B2  contracts (the giant — 5,488 tests; best left running while you
#     review other output, or run last)
make test-batch-2        # or: test-batch-2-1 … 2-10

# B3  compliance + marketplace + billing
make test-batch-3        # or: test-batch-3-1 … 3-11

# B4  dq + governance + gdpr
make test-batch-4        # or: test-batch-4-1 … 4-6

# B5  auth/tenants/semantic/search/social/users/scheduled/rate_limiting/notifications
make test-batch-5        # or: test-batch-5-1 … 5-5

# B6  connectors (SKIPS without credentials — env-gated)
make test-batch-6-1-all  # CKAN ~220 + AWS ~200 + Snowflake ~90 + Dados/E2E ~45
make test-batch-6-2      # GCP Marketplace ~240
make test-batch-6-3      # Marketplace (non-GCP) + federated import ~280
make test-batch-6-4
make test-batch-6-5
make test-batch-6-6

# B7  ML / AI / BaaS / Transformation / Mesh / API
make test-batch-7        # or: test-batch-7-1 … 7-9

# B8  GraphQL / Datasets D1-D3 / GDPR-DSAR / health+data_movement /
#     RoPA+warehouses+DPIA+processor agreements
make test-batch-8        # or: test-batch-8-1 … 8-7

# B9  hub/tests/ + CLI unit + E2E slices
make test-batch-9-1      # hub/tests/ ~56 files, ~300 tests
make test-batch-9-2      # 9-2-a..f: fixtures/SDK/MVP, API units, security,
                         # mesh/perf/integration, use-case+journey (~5 min),
                         # 9-2-f comprehensive integration (~40 min)
make test-batch-9-3a     # meta/guard ~200 (~5s, no API)
make test-batch-9-3b     # fixtures + unit config ~200 (~10s, no API)
make test-batch-9-3c     # CLI command units ~400 (~30s, no API)
make test-batch-9-3d     # unit auth/token/persona ~100 (~5s, no API)
make test-batch-9-3e     # security E2E ~70  — REQUIRES API on :8001
make test-batch-9-3f     # use-cases E2E ~200 — REQUIRES API on :8001

# B10  tests/unit + integration + e2e + security + performance +
#      regression + concurrency/pact/contract + sdk_python + fixtures
make test-batch-10       # 26 sub-targets; or slice by kind:
make test-batch-10-1a    # unit: contracts/semantic/ODPS/business rules/DPO
make test-batch-10-1b    # unit: monitoring/rate limiting/redis/virtualization/jobs
make test-batch-10-1c    # unit: worker/tenant config/CLI/event bus
make test-batch-10-2a … 10-2i   # integration ×9 (~307 each)
make test-batch-10-3a … 10-3e   # e2e ×5 (~339 each)
make test-batch-10-4a    # security/ ~273
make test-batch-10-4b    # performance/ ~184
make test-batch-10-5a    # regression/ ~225
make test-batch-10-5b    # smoke + resilience + uat ~163
make test-batch-10-5c    # concurrency/pact/contract/property/load/chaos/migrations ~156
make test-batch-10-6a    # scripts/docs/i18n/utils ~291
make test-batch-10-6b    # infrastructure/ci/chains/prefect/benchmarks/dr ~284
make test-batch-10-6c    # sdk_python/isolation/preprod01/observability/schema/fixtures/gdpr ~294

# B12  microservices
make test-batch-12-1     # compliance-service (host, -p no:django)
make test-batch-12-2     # semantic-service   (host)
make test-batch-12-3     # dq-service         (host)
make test-batch-12-4     # datacontract-service (~135, host, REDIS_CACHE_URL=localhost)
make test-batch-12-5     # prefect (container) + worker (container) + odh/shared (host)
                         # → per-service logs in /tmp/batch-12-5-*.log
```

Single-file iteration inside a failing batch:

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test \
  python -u -m pytest <path/to/test_file.py> -x -q --reuse-db --timeout=300
```

Host-side services iteration: `(cd services/dq-service && python3 -m pytest tests/test_x.py -q -p no:django)`.

---

## Phase 4 — Frontend

### 4.1 Vitest (fast, no servers needed)

```bash
cd frontend
npm run test:run            # all unit tests
npm run test:component      # features + shared chunks (heap-boosted)
npm run test:coverage:check # coverage gate
# ratchet pins:
node ../scripts/tests/test_check_test_baseline.cjs   # failure-baseline 8/8
node ../scripts/check_fragile_selectors_ratchet.cjs  # KNOWN rc 1 (peer-owned)
node ../scripts/assert_mutation_coverage.cjs         # KNOWN rc 1 (EXPIRED allowlist)
node ../scripts/tag_critical_specs.cjs               # @critical tagging
cd ..
```

### 4.2 Playwright E2E batches (needs API :8001 + Vite)

```bash
make test-frontend-e2e-batch1a   # auth core ~35 tests, ~5 min
make test-frontend-e2e-batch1b   # a11y + UX ~100, ~12 min
make test-frontend-e2e-batch1c   # cross-cutting + security ~65, ~6 min
make test-frontend-e2e-batch2    # route smokes ~115
make test-frontend-e2e-batch3    # DPO journeys + asset/contract/ODPS ~275
make test-frontend-e2e-batch4    # auth/DC/DE journeys + integrations ~385
make test-frontend-e2e-batch5    # TA/PA/Dev/Aud + cross-persona + webhooks ~375
make test-frontend-e2e-batch6    # CPO/DS/DMO/DA/CM/marketplace ~390
make test-frontend-e2e-batch7    # features/phase7.5/8/governance/scheduled ~220
make test-frontend-e2e-batch8    # UX flows ~25
# or via npm directly (same runners):
#   cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch3
```

Fast single-spec iteration:

```bash
cd frontend
E2E_SKIP_API_RESTART=1 npm run test:e2e -- e2e/journeys/dpo/asset-fail-closed.spec.ts
# or the visible/headed variants:  npm run test:e2e:visible -- <spec>  /  test:e2e:headed -- <spec>
```

A11y suite: `cd frontend && npm run test:a11y` (playwright.a11y.config.ts).
MVP-mode E2E: `npm run test:e2e:mvp`.

### 4.3 Manually-excluded sets (not in the CI batches)

```bash
cd frontend
npm run test:e2e -- e2e/dimensions/    # network-failure/rate-limit — flaky by design
npm run test:e2e -- e2e/personas/      # full persona suites — very long
npm run test:e2e:batch9                # deprecated phase specs (pre-deletion regression)
cd ..
```

---

## Phase 5 — Final sweep + CI parity

```bash
make test-batch-all   # B1..B10 + B12 sequentially, continues on failure
make test-ci          # CI parity: lint + full hub/apps in-container + vitest
```

Optional extras: `make test-go-nogo` (U.8), `make test-rehearsal-migration`
(U.7), `make staging-smoke` (needs staging stack + credentials).

---

## Supporting commands appendix

**Stack control**

```bash
docker compose -f docker-compose.test.yml ps
docker compose -f docker-compose.test.yml logs -f --tail=100 api-service-test worker-service-test
make test-stack-down      # stop + DELETE volumes (full clean slate)
make wait-for-services
```

**DB access / contention**

```bash
docker exec p313-pg psql -U hub -d hub_test_313full -c '\dt' | head
docker exec p313-pg psql -U hub -d postgres -c "DROP DATABASE hub_test_review WITH (FORCE);"
```

Sequential batches only — never two pytest sessions against the same DB
concurrently. Host-side and container suites use DIFFERENT databases and
can run in parallel.

**E2E seeding**: `make _seed-e2e-data` (internal; the frontend batches seed
their own fixtures through the API).

**Credential-gated suites** (skip gracefully without env): SNOWFLAKE_ACCOUNT/
USER/TOKEN (B6 snowflake), GCP_PROJECT_ID (B6 GCP), DADOS_GOV_BR_API_KEY,
AWS role/session/dataset (B6 AWS). Live suites: `REAL_SCHEDULED_E2E=1`
+ `REAL_VIRTUALIZATION_E2E=1` + `DATABRICKS_E2E=1` (W16: local-skip,
CI-raise). Connector E2E with real credentials: `make test-connectors-e2e`.

**Failure fingerprints (host-side)** — from HOST_SIDE_VERIFICATION.md:

| Symptom | Cause | Fix |
|---|---|---|
| `database … does not exist` / UUID DB names | `TEST_DB_SUFFIX` missing | export the 0.2 block |
| compliance/DQ `FailClosedRejection: DEGRADED` | breaker OPEN — service containers down | start the test stack |
| RQ/search connection errors on :6380 | pointing at dev Redis | use `127.0.0.1:63799` |
| ODH/ML connection refused | odh containers not running host-side | run those in-container (B7) |
| pyodbc driver errors | no ODBC driver on host | run in-container |
| Stripe 4xx | dead local fallback keys | CI-only; expect skips |
| Frontend E2E "Backend API is not reachable" | API not on :8001 | `make test-stack-up` |

**Estimated wall-clock** (sequential): Phase 1 ~5 min, Phase 2 ~15 min,
B1–B12 ~3–4 h (B2 dominates), Frontend ~2 h, final sweep ~2–3 h.
Iterate-and-fix keeps every re-run to one file or one sub-batch.
