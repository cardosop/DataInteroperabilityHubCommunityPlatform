# Staging Secrets Registry — Owner + Rotation

**Environment:** compose-path staging (`docker compose -f docker-compose.staging.yml --env-file .env.staging`).
**Scope:** every secret in `.env.staging` (gitignored). Coverage is enforced by
`scripts/tests/test_staging_env_contract.py` — a secret removed from this table
(or added to the env file without one) fails the contract suite.
**Owner default:** `admin` (per `docs/operations/triage-owners.md`).

## Rotation policy

- Cadence column applies while the internal beta runs on the compose path;
  the EKS migration ticket (210.29, owner `admin`, expiry 2026-09-30) moves
  this file's lifecycle to AWS Secrets Manager.
- Every rotation: update `.env.staging`, run `make staging-up` (the stack
  re-reads env), verify `make staging-post-deploy`, then record the rotation
  date in the `Last rotated` column of this file.
- Stripe keys come from the Stripe test-mode dashboard; webhook secrets must
  match the endpoint configuration in Stripe.

| Secret (env var) | Purpose | Owner | Cadence | Rotation procedure |
|---|---|---|---|---|
| `POSTGRES_PASSWORD` | Main staging Postgres superuser/app password | admin | Quarterly or on credential exposure | `docker compose -f docker-compose.staging.yml --env-file .env.staging exec postgres psql -U hub_staging -c "ALTER USER hub_staging WITH PASSWORD '<new>'"` then update `.env.staging` + `make staging-up`. See `RB-SEC-001-credential-rotation.md`. |
| `PGBOUNCER_AUTH_PASSWORD` | PgBouncer `auth_query` user (postgres side + userlist) | admin | Quarterly (same event as Postgres) | Update `03-pgbouncer-user.sh`-managed role via psql, then `.env.staging`; userlist.txt is regenerated from env on every container start. |
| `PGBOUNCER_ADMIN_PASSWORD` | PgBouncer admin console | admin | Quarterly | Update `.env.staging` only; userlist regenerated on restart. |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO root credentials (server bootstrap) | admin | Quarterly | `docker compose ... exec minio mc admin user ...` — see `docs/runbooks/kms-rotation.md` pattern; rotate app creds in the same window. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | MinIO **app** user (bucket-scoped policy created by `minio-init`) — NOT the root credentials | admin | Quarterly or on exposure | `mc admin user add` fails on an existing name: `mc admin user rm local <old> && mc admin user add local <new-id> <new-secret> && mc admin policy attach local hub-app-policy --user <new-id>` inside the `minio` container, then update `.env.staging` and re-run `minio-init` (`docker compose ... run --rm minio-init`). |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket created by `minio-init` for staging file storage (identifier — listed because the compose file fails fast on it) | admin | Never | Recreate the bucket via `mc mb --ignore-existing` if removed; rename requires a data migration of the bucket contents. |
| `FUSEKI_ADMIN_PASSWORD` | Jena Fuseki admin (shiro.ini resynced on boot via `fuseki_password_sync.sh`) | admin | Quarterly | Update `.env.staging`; restart fuseki (the entrypoint re-syncs shiro.ini on every start). |
| `STRIPE_SECRET_KEY` | Stripe test-mode secret key (billing + checkout) | admin | On Stripe key rollover | Rotate in the Stripe test dashboard, update `.env.staging` + `make staging-up`. |
| `STRIPE_WEBHOOK_SECRET` / `STRIPE_MARKETPLACE_WEBHOOK_SECRET` | Webhook signature verification | admin | On Stripe key rollover | Rotate alongside the secret key; update the Stripe webhook endpoint config and `.env.staging` atomically, then re-verify with a Stripe CLI `listen` replay (see `RB-MKT-001-stripe-connect-onboarding-failure.md` for the verification loop). |
| `SECRET_KEY` | Django signing/session secret | admin | Quarterly or on exposure | Update `.env.staging` + `make staging-up`. Invalidation of existing sessions/refresh tokens on rotation is accepted in staging. |
| `INTERNAL_API_KEY` | Inter-service shared auth (compliance/dq RQ workers) | admin | Quarterly | Update `.env.staging` + `make staging-up`; rotate in the same window as the services' env (see `RB-AUTH-004-internal-api-key-rotation.md`). |
| `BAAS_DATABASE_URL` | BaaS usage/quota storage URL — embeds the `POSTGRES_PASSWORD` (dedicated `baas` database on the staging postgres instance) | admin | Rides the `POSTGRES_PASSWORD` rotation event | Rebuild the URL string in `.env.staging` with the new password + `make staging-up`; the `baas` database itself is re-created idempotently by `make staging-post-deploy`. |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin login | admin | Quarterly | Update `.env.staging` + `make staging-up` (the compose consumes it fail-fast — no `:-admin` default since W0.7). |
| `REDIS_CACHE_PASSWORD` / `REDIS_QUEUE_PASSWORD` / `REDIS_EVENTS_PASSWORD` / `REDIS_CHANNELS_PASSWORD` | Redis `requirepass` x4 (cache/queue/events/channels instances — the production-compose precedent, W0.7) | admin | Quarterly | Update `.env.staging` (all four, one event) + `make staging-up`; the compose URLs + healthchecks read them fail-fast. `BAAS_REDIS_URL` rides the cache password. |
| `BAAS_REDIS_URL` | BaaS usage/quota Redis URL — embeds the `REDIS_CACHE_PASSWORD` (db 1 on the staging redis-cache) | admin | Rides the `REDIS_CACHE_PASSWORD` rotation event | Rebuild the URL string in `.env.staging` (`redis://:<cache-password>@redis-cache:6379/1`) + `make staging-up`. |
| `HUB_WORKER_API_KEY` | Scheduled-ingestion/export internal-auth key (worker-service + prefect-worker, W0.7) | admin | Quarterly or on exposure | Update `.env.staging` + `make staging-up`; rotate in the same window as `INTERNAL_API_KEY`. |
| `PREFECT_DB_PASSWORD` | Prefect server database (prefect-db) | admin | Quarterly (same event as Postgres) | Update `.env.staging` + `make staging-up` (the W0.7 evidence boot found the ``:-prefect`` default — now fail-fast). |
| `POSTGRES_USER` | Postgres role name (identifier, not a secret — listed for ownership) | admin | Never (rename requires dump/reload) | — |
| `POSTGRES_ADMIN_PASSWORD` | `meshant_admin` BYPASSRLS role (settings' `admin` DB alias, B-RLS-0.5) — init-db.sql creates the role WITHOUT a password; the post-deploy bootstrap syncs it from this var | admin | Quarterly (same event as Postgres) | Update `.env.staging` + `make staging-up`; `make staging-post-deploy` re-syncs the role (`ALTER ROLE meshant_admin WITH PASSWORD`) idempotently. |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | RS256 JWT signing keypair (login/refresh tokens) | admin | Quarterly or on exposure | Generate via `openssl genrsa 2048` + `openssl rsa -pubout` (see `infrastructure/scripts/generate-jwt-keys.sh` for the Vault production variant); update `.env.staging` as JSON-escaped single lines + `make staging-up`. Rotation invalidates all staging sessions (accepted). |

## Verification

```bash
# contract suite (no Django/DB needed)
venv/bin/python -m pytest -c /dev/null -p no:django scripts/tests/test_staging_env_contract.py -q

# the stack resolves every ${VAR:?} at parse time
docker compose -f docker-compose.staging.yml --env-file .env.staging config --quiet
```
