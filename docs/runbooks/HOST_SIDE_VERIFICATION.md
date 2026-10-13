# Host-Side Verification Runbook

The exact environment recipe for running the backend suites directly on a
developer machine (instead of inside the compose stack). Canonical source:
`docs/test-infrastructure/host-env-matrix.md` — this runbook is the
step-by-step form.

## Required containers

All of these must be `Up` before a DB-backed run:

| Container | Purpose |
|---|---|
| `p313-pg` | Main test PostgreSQL (port `54329`) |
| `p313-redis` | The redis the host-side suites USE (`REDIS_URL=redis://127.0.0.1:63799/0`) |
| `hub-test-redis-cache` | Cache role for host-side runs (`REDIS_CACHE_URL=redis://localhost:6479/0` — the test stack's cache published on the host; contracts Redis tests skip without it) |
| `hub-test-minio` | S3-compatible storage for file-upload tests (host port `9010`) |
| `hub-redis-queue` | RQ queue — dev-stack only (port `6380`) |
| `hub-redis-cache` | Cache — dev-stack only (port `6379`) |
| `hub-redis-events` | Event bus — dev-stack only (port `6381`) |
| `hub-redis-channels` | Channels layer — dev-stack only (port `6382`) |

Check: `docker ps --format '{{.Names}}' | grep -E 'p313-pg|hub-redis|hub-minio'`

## The env block

```bash
export PY=venv/bin/python                       # canonical interpreter
export POSTGRES_HOST=localhost POSTGRES_PORT=54329
export POSTGRES_USER=hub POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub_test_313full TEST_DB_SUFFIX=313full
export ENVIRONMENT=test JWT_ALGORITHM=HS256
export REDIS_URL=redis://127.0.0.1:63799/0
export REDIS_CACHE_URL=redis://localhost:6479/0
export AWS_S3_ENDPOINT_URL=http://localhost:9010
export AWS_ACCESS_KEY_ID=minio
export AWS_SECRET_ACCESS_KEY=<minio root password — see below>
# Snowflake live-connector tests (optional). Unset = W16-governed: local
# runs skip, CI raises EnvironmentFailureError. Provisioning recipe:
# docs/docs/runbooks/RB-INTEGRATIONS-002-snowflake-sandbox-provisioning.md
export SNOWFLAKE_ACCOUNT=<orgname-accountname or account locator>
export SNOWFLAKE_USER=<service user, e.g. HUB_TEST_READER>
export SNOWFLAKE_TOKEN=<programmatic access token (PAT, password-equivalent)>
export SNOWFLAKE_WAREHOUSE=<optional warehouse>
export SNOWFLAKE_ROLE=<optional role>
export SNOWFLAKE_DATABASE=<optional database>
```

`TEST_DB_SUFFIX` is **required**: without it `hub/settings.py` generates a
random `<db>_test_<uuid8>` name and every DB test errors with
`database ... does not exist`.

### MinIO root secret

The test compose defaults the root password to `minio123`
(`docker-compose.test.yml`, `MINIO_ROOT_PASSWORD`). If the running
container was started with a different value, extract it:

```bash
docker inspect hub-minio --format '{{range .Config.Env}}{{println .}}{{end}}' | grep MINIO_ROOT_PASSWORD
```

## Known env-bucket symptoms and their fingerprints

| Symptom | Fingerprint | Cause |
|---|---|---|
| Compliance / DQ failures with `FailClosedRejection: compliance=DEGRADED` | circuit breaker OPEN after `connection refused` | `compliance-service`/`dq-service` containers not running (host-side runs cannot reach compose DNS names) |
| RQ / search failures | Redis connection errors on port `6380` | Pointing at the compose-internal Redis port instead of `127.0.0.1:63799` (the `p313-redis` host mapping) |
| ODH / ML failures | `odh-training-operator`/`odh-inference-scheduler` connection refused | Those compose services are not running host-side; CI-green by design |
| `pyodbc` import/runtime errors | driver manager errors | ODBC driver not installed on the host — install the distro driver or run those tests in the compose stack |
| Stripe 4xx | `Stripe API key not configured` / auth errors | Fallback keys are dead locally; only the org's CI secret key works — credential-gated |
| 60+ tests error with `database ... does not exist` | UUID-suffixed DB names | `TEST_DB_SUFFIX` missing from the env block |

## The canonical run

```bash
set -a; source <(cat <<'EOF'
POSTGRES_HOST=localhost POSTGRES_PORT=54329 POSTGRES_USER=hub POSTGRES_PASSWORD=hub
POSTGRES_DB=hub_test_313full TEST_DB_SUFFIX=313full ENVIRONMENT=test JWT_ALGORITHM=HS256
REDIS_URL=redis://127.0.0.1:63799/0
# Per-pool overrides: suites that use hub.apps.core.redis_pools (M2M token
# cache, OBO access-token cache) read REDIS_CACHE_URL — REDIS_URL alone
# leaves them on localhost:6379 (connection refused).
# MUST be db 13: the OBO/M2M test fixtures (conftest redis_13) seed and
# flush db 13 — a db-0 value makes every OBO-cache-dependent test fail
# closed pre-network (masked 502 DATABRICKS_AUTH_FAILED, zero requests).
REDIS_CACHE_URL=redis://127.0.0.1:63799/13
# RQ/django-rq suites (job creation/enqueue) read REDIS_QUEUE_URL — without
# it the settings fallback picks localhost:6380 whenever staging detection
# sees hub-test-api:8001 responding (the "Redis on 6380" symptom row).
REDIS_QUEUE_URL=redis://127.0.0.1:63799/0
AWS_S3_ENDPOINT_URL=http://localhost:9010
EOF
); set +a
venv/bin/python -m pytest <paths> --reuse-db
```

And the fast pre-flight: `venv/bin/python scripts/check_core_boundary.py`
plus `bash scripts/validate_openspec_changes.sh` (no DB needed).

### Contracts Redis recipe (close-test-coverage-gaps 7.2)

The contracts caching suites (`hub/apps/contracts/tests/test_caching_enhanced.py`,
`hub/apps/contracts/tests/test_caching_behavior_validation.py`,
`hub/apps/contracts/tests/test_ref_resolver_caching.py`) self-skip
with "Redis not available" when their skip gate — a `ping()` on
`settings.REDIS_URL` — cannot reach an instance. Host-side, `REDIS_URL` defaults
to `redis://localhost:<port>/0` with nothing listening → **33/33 skipped**
(measured 2026-09-28). BOTH variables must point at the SANCTIONED instance
(the test stack's cache, host port 6479 — the same instance in-container
batches use):

```bash
export REDIS_URL=redis://localhost:6479/0
export REDIS_CACHE_URL=redis://localhost:6479/0
```

`REDIS_CACHE_URL` alone is NOT enough — the skip gate reads `REDIS_URL`, and a
cache-only recipe is a proven 33-skip state. The two serve different layers:
`REDIS_URL` backs the tests' raw client (tag indexing), `REDIS_CACHE_URL` the
django cache layer (`cache_contract`). Verified: the recipe above runs the
three files **82 passed / 0 skipped** host-side (`--reuse-db`).

The canonical block above keeps `REDIS_CACHE_URL=redis://127.0.0.1:63799/13`
for the OBO/M2M token-cache fixtures (db 13, per the 0.3 databricks work) —
override it with the 6479 recipe when running the contracts caching suites,
and restore it for databricks_admin OBO/M2M runs. In-container batches need
nothing: the compose env already points at `redis-cache-test` (compose
:139 etc.).
