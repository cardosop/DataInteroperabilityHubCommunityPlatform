# BaaS Infrastructure (Dedicated Postgres and Redis)

Runbook for optional dedicated Postgres and Redis instances for BaaS (Backend-as-a-Service) usage tracking and quota. Design: [openspec/changes/feat1/design.md](../../openspec/changes/feat1/design.md) D1b.

## When to use dedicated BaaS instances

- **Staging / production:** Set `BAAS_DATABASE_URL` and `BAAS_REDIS_URL` so BaaS usage and quota use dedicated instances (isolated from main app DB and cache).
- **Dev / test / CI:** Leave both unset to use main `DATABASE_URL` and `REDIS_URL` (no extra services required).

## Docker Compose

### Main stack (docker-compose.yml)

- **postgres-baas:** Port `5433` (host). DB `baas`, user `hub_baas` (override with `BAAS_POSTGRES_DB`, `BAAS_POSTGRES_USER`, `BAAS_POSTGRES_PASSWORD`).
- **redis-baas:** Port `6383` (host). No auth by default.

To use them from the API service:

1. Set in `.env.dev` or environment:
   - `BAAS_DATABASE_URL=postgresql://hub_baas:hub_baas@postgres-baas:5432/baas`
   - `BAAS_REDIS_URL=redis://redis-baas:6379/0`
2. Optional: add `depends_on` for `postgres-baas` and `redis-baas` to `api-service` (e.g. in an override) so the API waits for BaaS services.

Without these variables, the API uses the main Postgres and Redis for BaaS; the BaaS containers can stay stopped.

### Test stack (docker-compose.test.yml)

- **postgres-baas-test:** Host port `5435` (default; use `BAAS_POSTGRES_TEST_PORT` to override). Same credentials as above (or `BAAS_POSTGRES_*`). Avoids conflict with main test Postgres on 5434.
- **redis-baas-test:** Host port `6384`.

To run tests with dedicated BaaS storage:

1. Start BaaS test services:  
   `docker compose -f docker-compose.test.yml up -d postgres-baas-test redis-baas-test`
2. Set for `api-service-test` (e.g. in `.env.test`):
   - `BAAS_DATABASE_URL=postgresql://hub_baas:hub_baas@postgres-baas-test:5432/baas`
   - `BAAS_REDIS_URL=redis://redis-baas-test:6379/0`
3. Run migrations on the BaaS DB:  
   `docker compose -f docker-compose.test.yml exec api-service-test python hub/manage.py migrate --database=baas`
4. Run tests as usual.

## Settings (hub/settings.py)

- **BAAS_DATABASE_URL** (optional): Postgres URL for BaaS. When set, a Django DB alias `baas` is configured and BaaS usage can be stored there (see design D1b). Used by Postgres usage backend.
- **BAAS_REDIS_URL** (optional): Redis URL for BaaS. When set, the Redis usage backend uses this; otherwise it uses `REDIS_URL`.
- **BAAS_USAGE_STORAGE_BACKEND** (optional): `"postgres"` or `"redis"`. Default `"postgres"`. Selects which backend stores usage and serves quota counts (feat1 1.3). Use `postgres` for default or dedicated BaaS DB; use `redis` for high-throughput recording with time-window quota.

Production/staging **MUST** set both `BAAS_DATABASE_URL` and `BAAS_REDIS_URL` when using dedicated BaaS instances. Dev/test **MAY** leave them unset to use the main DB and Redis.

## Health / connectivity

When `BAAS_DATABASE_URL` or `BAAS_REDIS_URL` is set, the app may perform health or startup checks against those instances (see optional task 1.0.5). If the BaaS services are down and the URLs are set, BaaS usage recording or quota checks can fail until the instances are reachable.

## Runbook index

See [RUNBOOKS.md](../RUNBOOKS.md) for the full list; [BaaS Platform Troubleshooting](../RUNBOOKS.md#baas-platform-troubleshooting) for general BaaS issues.
