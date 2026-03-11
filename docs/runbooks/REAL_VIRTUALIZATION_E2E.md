# Real Virtualization E2E Runbook

This runbook describes how to run **real end-to-end** virtualization integration tests against **real data sources** (PostgreSQL, Jena Fuseki, HTTP). No mocks or stubs are used.

## Purpose and scope

- **Goal:** Validate virtualization query execution (SQL, SPARQL, REST) against real PostgreSQL, Jena Fuseki (via semantic-service), and public HTTP endpoints.
- **Out of scope:** Mocked or stubbed sources; unit tests that fake connections.
- **References:**
  - [Virtualization Service](../../hub/apps/virtualization/services.py) — `_execute_sql_query`, `_execute_sparql_query`, `_execute_rest_query`, `_execute_query_against_federated_asset`
  - [Real Source Integration Tests](../../hub/apps/virtualization/tests/test_real_source_integration.py) — Phase 20 tests
  - [Federated Asset E2E Tests](../../hub/apps/virtualization/tests/test_virtualization_real_federated_e2e.py) — Phase 21 tests

## Prerequisites

- **Docker Compose test stack** running with **fully migrated** databases:
  ```bash
  # Option A: Fresh start (recommended if schema errors occur)
  ./scripts/clean-test-stack.sh --volumes
  # Wait for migrate-test-db and api-service-test to complete (~3–5 min)

  # Option B: Reuse existing stack
  docker compose -f docker-compose.test.yml --env-file .env.test up -d
  ```
- **Critical:** The test DB (`hub_test_test_shared`) must have all migrations applied. If you see "relation X does not exist" or "column Y does not exist", run `./scripts/clean-test-stack.sh --volumes` for a fresh schema.
- **postgres-test** — PostgreSQL 16 (hub-test-postgres, port 5434 on host)
- **fuseki-test** — Apache Jena Fuseki (hub-test-fuseki, port 3031 on host)
- **semantic-service-test** — Semantic service (connects to fuseki-test)
- **api-service-test** — API service (runs pytest inside container)

Optional: `.env.test` (copy from `.env.test.example`) for overrides. Defaults in `docker-compose.test.yml` are sufficient.

**Pytest marker:** Tests are marked `integration` and `real_virtualization_e2e`. Run with `-m integration` or `-m real_virtualization_e2e` to select them.

## Test summary

| Test | Source | What it does |
|------|--------|--------------|
| `test_postgresql_create_table_select_assert_rows` | PostgreSQL | Creates table, inserts 3 rows, runs SELECT via VirtualizationService, asserts row count and content |
| `test_odbc_execute_against_hub_postgresql` | ODBC (psqlodbc) | Execute SQL via ODBC source (host+database) against Hub PostgreSQL; skips when pyodbc or driver not available |
| `test_odbc_execute_connection_string_mode` | ODBC (psqlodbc) | Execute SQL via ODBC source (connection_string) against Hub PostgreSQL; skips when pyodbc or driver not available |
| `test_sparql_against_fuseki` | Jena Fuseki | Runs SPARQL `SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5` via semantic-service; skips if Fuseki unavailable |
| `test_rest_against_real_http_endpoint` | jsonplaceholder.typicode.com | Runs REST GET `/posts`, asserts JSON array with `id`, `title`, `userId` |
| `test_e2e_pull_from_demo_ckan_create_federated_asset_virtual_dataset_execute_query` | demo.ckan.org | PULL → federated asset → virtual dataset → execute query (METADATA_ONLY); skips if demo.ckan.org unreachable |
| `test_ckan_package_csv_row_count` | demo.ckan.org / data.gov | Uses CKAN package with downloadable CSV; creates federated asset (DOWNLOAD_SELECTIVE), virtual dataset, executes query, asserts row count; skips if no suitable package found |

## How to run

### Inside Docker (recommended)

**CRITICAL:** Use `--reuse-db` when running against the shared test DB (api-service-test uses `TEST_DB_SUFFIX=shared`). Without it, test DB setup may fail.

**Quick run (ensures migrations first):**
```bash
./scripts/run_virtualization_real_source_tests.sh
```

**Manual run (Phase 20 + Phase 21 real E2E):**

```bash
docker compose -f docker-compose.test.yml exec api-service-test \
  pytest hub/apps/virtualization/tests/ -v -m "integration and real_virtualization_e2e" --reuse-db
```

### Run all virtualization integration tests

```bash
docker compose -f docker-compose.test.yml exec api-service-test \
  pytest hub/apps/virtualization/tests/ -v -m integration --reuse-db
```

### Run a single test

```bash
# Phase 20: PostgreSQL
docker compose -f docker-compose.test.yml exec api-service-test \
  pytest hub/apps/virtualization/tests/test_real_source_integration.py::RealPostgreSQLSourceIntegrationTest::test_postgresql_create_table_select_assert_rows -v --reuse-db

# Phase 21: Federated asset E2E
docker compose -f docker-compose.test.yml exec api-service-test \
  pytest hub/apps/virtualization/tests/test_virtualization_real_federated_e2e.py::VirtualizationFederatedAssetE2ETest::test_e2e_pull_from_demo_ckan_create_federated_asset_virtual_dataset_execute_query -v --reuse-db
```

### From host (requires services reachable)

If running pytest from the host (not inside Docker), ensure:

- PostgreSQL is reachable at `localhost:5434` (or `POSTGRES_HOST`/`POSTGRES_PORT` from env)
- Semantic service is reachable at `localhost:8086` (or `SEMANTIC_SERVICE_URL`)
- Network allows outbound HTTPS to `jsonplaceholder.typicode.com`, `demo.ckan.org`, and `data.gov`
- Use `POSTGRES_DB=hub_test_test_shared` if connecting to the same DB as api-service-test (or `hub_test` for a fresh DB)

```bash
export POSTGRES_HOST=localhost POSTGRES_PORT=5434
export POSTGRES_USER=hub_test POSTGRES_PASSWORD=hub_test POSTGRES_DB=hub_test_test_shared
export TEST_DB_SUFFIX=shared
pytest hub/apps/virtualization/tests/ -v -m "integration and real_virtualization_e2e" --reuse-db
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `POSTGRES_HOST` | PostgreSQL host (default: `postgres-test` in Docker, `localhost` on host) |
| `POSTGRES_PORT` | PostgreSQL port (default: 5432 in Docker, 5434 on host) |
| `POSTGRES_USER` | PostgreSQL user (default: `hub_test`) |
| `POSTGRES_PASSWORD` | PostgreSQL password (default: `hub_test`) |
| `POSTGRES_DB` | PostgreSQL database (`hub_test_test_shared` for api-service-test shared DB, `hub_test` otherwise) |
| `SEMANTIC_SERVICE_URL` | Semantic service URL (default: `http://semantic-service-test:8081` in Docker) |
| `FUSEKI_URL` | Fuseki URL (used by semantic-service; default: `http://fuseki-test:3030`) |

## Troubleshooting

### PostgreSQL test fails with "connection refused"

- Ensure `postgres-test` is healthy: `docker compose -f docker-compose.test.yml ps postgres-test`
- Check `migrate-test-db` completed: `docker compose -f docker-compose.test.yml logs migrate-test-db`
- If using host pytest, ensure `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5434` (host-mapped port)

### SPARQL test skipped ("SemanticService/Fuseki not available")

- Ensure `fuseki-test` and `semantic-service-test` are running and healthy
- Fuseki has a long `start_period` (120s); wait for health check to pass
- Check: `curl -s http://localhost:3031/$/ping` (Fuseki) and semantic service health

### REST test fails (timeout or connection error)

- Requires outbound HTTPS to `jsonplaceholder.typicode.com`
- If behind a proxy or firewall, ensure the endpoint is reachable
- The test uses a public, stable API; transient failures may occur

### "No sources configured" for SPARQL

- SPARQL tests use `sources=[]`; the semantic service is configured via `FUSEKI_URL`/`SEMANTIC_SERVICE_URL`, not via VirtualDataset sources

### "column plan_id of relation tenants does not exist" or similar schema errors

- Database migrations are out of sync with the codebase. Run migrations:
  ```bash
  docker compose -f docker-compose.test.yml run --rm migrate-test-db
  ```
  Then restart api-service-test and re-run tests with `--reuse-db`:
  ```bash
  docker compose -f docker-compose.test.yml up -d api-service-test
  docker compose -f docker-compose.test.yml exec api-service-test \
    pytest hub/apps/virtualization/tests/test_real_source_integration.py -v -m integration --reuse-db
  ```
- If the DB is in an inconsistent state (e.g. DuplicateTable during migrate), consider a clean reset:
  ```bash
  docker compose -f docker-compose.test.yml down -v
  docker compose -f docker-compose.test.yml up -d
  # Wait for migrate-test-db to complete, then run tests
  ```

### Phase 21: Federated asset E2E skipped ("demo.ckan.org unreachable")

- Requires outbound HTTPS to `demo.ckan.org`, `data.gov`
- If behind a proxy or firewall, ensure these endpoints are reachable
- Check: `curl -s "https://demo.ckan.org/api/3/action/status_show" | jq .success`

### Phase 21: test_ckan_package_csv_row_count skipped ("No CKAN package with downloadable CSV")

- Tries demo.ckan.org and data.gov for a package with downloadable CSV resource
- Skip occurs when no package has a CSV resource with a valid, reachable URL
- Both demo.ckan.org and data.gov are public; transient network or SSL issues may cause skip

---

## Validation table

Record one successful real E2E run per source type or a documented skip reason.

**Run command (test stack):** `./scripts/run_virtualization_real_source_tests.sh` or `docker compose -f docker-compose.test.yml exec api-service-test pytest hub/apps/virtualization/tests/ -v -m "integration and real_virtualization_e2e" --reuse-db`.

| Source type      | Last E2E run (date) | Result (OK / SKIP / FAIL) | Run command / notes |
|------------------|---------------------|---------------------------|---------------------|
| PostgreSQL       |                     | OK                        | Uses test DB; creates table, inserts rows, runs SELECT. No external credentials. |
| Jena Fuseki      |                     | OK / SKIP                 | Requires fuseki-test + semantic-service-test. Skips if Fuseki unavailable. |
| REST (HTTP)      |                     | OK                        | Uses jsonplaceholder.typicode.com (public). No credentials. |
| demo.ckan.org    |                     | OK / SKIP                 | PULL → federated asset → virtual dataset → query. Skips if demo.ckan.org unreachable. |
| data.gov         |                     | OK / SKIP                 | Fallback for test_ckan_package_csv_row_count when demo.ckan.org has no CSV. |

**Related runbooks:** [REAL_MARKETPLACE_E2E.md](REAL_MARKETPLACE_E2E.md) (marketplace connectors), [REAL_SCHEDULED_INGESTION_EXPORT_E2E.md](REAL_SCHEDULED_INGESTION_EXPORT_E2E.md) (scheduled flows).
