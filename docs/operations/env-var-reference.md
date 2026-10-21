# Environment Variable Reference

**Version**: 1.0 | **Owner**: Platform Engineering

## Database

| Variable | Required | Default | Valid Values |
|----------|----------|---------|--------------|
| `POSTGRES_HOST` | Yes | `postgres` | Hostname or IP |
| `POSTGRES_PORT` | Yes | `5432` | 1–65535 |
| `POSTGRES_DB` | Yes | `hub` | Database name |
| `POSTGRES_USER` | Yes | `hub` | Username |
| `POSTGRES_PASSWORD` | Yes | — | Strong password |
| `PGBOUNCER_ENABLED` | No | `false` | `true` / `false` |
| `DATABASE_REPLICA_URL` | No | — | Full connection URL |

## Redis

| Variable | Required | Default | Valid Values |
|----------|----------|---------|--------------|
| `REDIS_URL` | Yes | `redis://redis:6379/0` | Connection URL |
| `REDIS_CACHE_URL` | No | — | Connection URL |
| `REDIS_QUEUE_URL` | No | — | Connection URL |
| `REDIS_EVENTS_URL` | No | — | Connection URL |
| `REDIS_CHANNELS_URL` | No | — | Connection URL |

## Django Core

| Variable | Required | Default | Valid Values |
|----------|----------|---------|--------------|
| `SECRET_KEY` | Production | Dev default | 50+ char random string |
| `DEBUG` | No | `false` | `true` / `false` |
| `ENVIRONMENT` | Yes | `development` | `production` / `staging` / `development` / `test` |
| `ALLOWED_HOSTS` | Production | `localhost,127.0.0.1,...` | Comma-separated hostnames |
| `ADMIN_URL` | No | `admin/` | Non-guessable path |
| `APP_NAME` | No | `Meshant` | String |

## JWT

| Variable | Required | Default | Valid Values |
|----------|----------|---------|--------------|
| `JWT_SECRET_KEY` | Production | Dev default | 50+ char random string |
| `JWT_ALGORITHM` | No | `RS256` | `RS256` / `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRY` | No | `900` | Seconds (15 min) |
| `JWT_REFRESH_TOKEN_EXPIRY` | No | `604800` | Seconds (7 days) |

## Stripe / Billing

| Variable | Required | Default | Valid Values |
|----------|----------|---------|--------------|
| `STRIPE_SECRET_KEY` | Production | — | `sk_live_...` or `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Production | — | `whsec_...` |
| `STRIPE_TAX_ENABLED` | No | `false` | `true` / `false` |
| `STRIPE_CONNECT_ENABLED` | No | `false` | `true` / `false` |
| `MARKETPLACE_PLATFORM_FEE_BPS` | No | `1000` | 0–10000 |

## Service URLs

| Variable | Required | Default |
|----------|----------|---------|
| `DATACONTRACT_SERVICE_URL` | No | `http://datacontract-service:8080` |
| `DQ_SERVICE_URL` | No | `http://dq-service:8083` |
| `COMPLIANCE_SERVICE_URL` | No | `http://compliance-service:8082` |
| `SEMANTIC_SERVICE_URL` | No | `http://semantic-service:8081` |
| `FUSEKI_URL` | No | `http://fuseki:3030` |
| `PREFECT_INTEGRATION_SERVICE_URL` | No | `http://prefect-integration-service:8084` |

## Cost Rates (285.13.4)

| Variable | Required | Default | Unit |
|----------|----------|---------|------|
| `COST_PER_1K_API_CALLS` | No | `1` | Cents |
| `COST_PER_GB_STORAGE` | No | `10` | Cents |
| `COST_PER_COMPUTE_HOUR` | No | `50` | Cents |
| `COST_PER_ENGINEERING_HOUR` | No | `8000` | Cents |
| `COST_PER_SUPPORT_TICKET` | No | `500` | Cents |
| `COST_PLATFORM_BASE_MONTHLY` | No | `5000` | Cents |
