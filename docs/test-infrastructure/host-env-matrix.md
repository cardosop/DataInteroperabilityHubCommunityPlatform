# Host-side vs CI test environment matrix (Phase 313 closeout)

Host-side pytest runs (against `p313-pg` / `p313-redis`) deliberately
approximate the CI compose environment, but a few dimensions are
**CI-green by design** and cannot pass locally without the org's
credentials or the paid service containers. This matrix records what
each failure class needs and how CI provides it.

| Dimension | Local (host-side) state | CI (compose / secrets) | Consequence + disposition |
|---|---|---|---|
| Stripe (`billing`, `marketplace` refunds/retries) | `STRIPE_SECRET_KEY` fallback keys are dead (auth error) | `ci.yml` `test` job injects `secrets.STRIPE_SECRET_KEY` (org live test key) | Tests that hit the live Stripe API fail locally with `AuthenticationError` / open circuit breakers. **Credential-gated** — the tests' own `requires_stripe`/skip contracts gate on key *presence*; a working key is an org secret. |
| Compliance / DQ service (`assets` fail-closed, `orchestration` data-first + webhook ordering, `virtualization` services) | No `compliance-service`/`dq-service` containers → connection refused → shared circuit breaker opens → `FailClosedRejection: compliance=DEGRADED` | Compose test stack runs the service containers; breakers never open | **Host-env artifact** — the circuit state is re-created by each local run's own connectivity failures. CI-green by design. |
| ML / ODH (`ml` training, model workflow, semantic indexing) | No `odh-training-operator`/`odh-inference-scheduler` | Compose test stack runs them | Same class as above. |
| Tenants file-upload (data-exchange storage) | `AWS_DATA_EXCHANGE_ACCESS_KEY_ID` empty in `.env.test` → `InvalidAccessKeyId` on the data-exchange bucket path | Compose provides minio-test credentials | Host-env artifact. |
| GCP Marketplace connectors (`integrations` discovery/e2e/integration/security) | `.env.test` carries a **stale** `GCP_SERVICE_ACCOUNT_JSON` → gRPC `UNAUTHENTICATED` | CI does not set the var → tests skip per their contract | Fixed at root cause: every class now probes real auth in `setUpClass`/per-call and **skips on auth failure** (the files' own stated contract). Rotate or remove the stale credential in `.env.test` to skip cleanly. |
| BigQuery live (`warehouses`) | Stale `GCP_CREDENTIALS_JSON` passes the presence gate | Same var absent in CI → presence gate skips | Class-level auth probe added. |
| Marquez (openlineage) | `MARQUEZ_INTEGRATION_TEST_URL` was set in `.env.test` while the marquez stack (a **separate** compose file) is not running → `DEAD_LETTERED` | CI sets the var AND boots `docker-compose.test.marquez.yml` | The local `.env.test` line is commented out (with re-enable instructions); the test's own contract says local runs skip. |
| JWT auth suites (host-side) | RS256 without the docker JWT key env → login tests fail | Compose provides JWT keys | Pre-existing host-side limitation (round 3 note); use `JWT_ALGORITHM=HS256` for host runs. |
| MinIO storage | `AWS_S3_ENDPOINT_URL=http://minio:9000` is docker-internal | minio-test on the compose network | Host runs must override `AWS_S3_ENDPOINT_URL=http://localhost:9000` + the dev minio credentials. |
| Snowflake live connectors (`integrations` snowflake suites, `warehouses` sandbox suites) | `SNOWFLAKE_ACCOUNT`/`SNOWFLAKE_USER`/`SNOWFLAKE_TOKEN` unset → W16-governed: local runs skip, `CI=true` raises `EnvironmentFailureError` | CI's unit phase runs `-m "not integration and not e2e"` → live Snowflake tests deselected unless a job provisions the sandbox | Provisioning recipe: `docs/docs/runbooks/RB-INTEGRATIONS-002-snowflake-sandbox-provisioning.md`. The token is a **Programmatic Access Token (PAT)** used as the Snowflake *password* field — not an OAuth bearer token. |

## Canonical host-side interpreter

**Use `venv/bin/python`.** The repo tree carries two gitignored virtualenvs and
they are NOT interchangeable:

| Interpreter | State | Use for |
|---|---|---|
| `venv/bin/python` | **Canonical.** Also the one the publish runbook uses (`PYTHON=venv/bin/python bash scripts/publish_public.sh`). At FULL `requirements.txt` parity since 2026-08-22 (W4.3) — verify with `make check-env` | Everything — Django/DB suites, lint, type-check |
| `.venv/bin/python` | Partial. Was missing 41 of the 77 `requirements.txt` distributions (incl. `django-csp`); scheduled for deletion (owner action) | None — do not trust its results |

`TEST_DB_SUFFIX` is **required** for host runs — without it `hub/settings.py`
generates a random `<db>_test_<uuid8>` name and every DB test errors with
`database ... does not exist`.

Two environment guards run before any hub test (Phase Q.4 / W4):
* `scripts/check_env_provisioning.py` (`make check-env`) verifies the running
  interpreter satisfies `requirements.txt` and prints the exact `pip install`
  line for anything missing.
* `verify_lazy_settings_importable()` in `hub/conftest_lazy_settings.py`
  (invoked from `hub/conftest.py::pytest_configure`) imports every
  lazily-resolved settings entry up front — `MIDDLEWARE`,
  `AUTHENTICATION_BACKENDS`, DRF class paths, `STORAGES`, template
  backends/loaders, `LOGGING` handler classes. Django resolves all of them
  lazily (first request / first use), so before that guard a missing package
  surfaced as a `ModuleNotFoundError` a dozen frames inside the first
  `client.get()` — i.e. it looked like a product failure, not a
  half-provisioned venv. If either guard fires, install the requirements
  into *that* interpreter.

## Canonical host-side env block

```bash
export PY=venv/bin/python                       # see the interpreter table above
export POSTGRES_HOST=localhost POSTGRES_PORT=54329 POSTGRES_USER=hub POSTGRES_PASSWORD=hub
export POSTGRES_DB=hub_test_313full TEST_DB_SUFFIX=313full
export ENVIRONMENT=test JWT_ALGORITHM=HS256
export REDIS_URL=redis://127.0.0.1:63799/0 USE_PRODUCTION_DB_FOR_SDK_TESTS=1
export REDIS_CACHE_URL=redis://localhost:6479/0
export AWS_S3_ENDPOINT_URL=http://localhost:9000
# Stripe: use the compose fallback test keys (docker-compose.test.yml) —
# they are dead locally; only the org's CI secret key makes the live-API
# tests pass.
```
