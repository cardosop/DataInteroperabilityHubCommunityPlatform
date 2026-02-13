# API Gateway Tests

All tests have been rewritten to use **real services** - no mocks or stubs are used.

## Test Structure

- **test_routing.py**: Unit and integration tests for routing config (Phase 7: deployment-aligned routing; Phase 8: `TestHealthUrlContract` — health URL contract per backend)
- **test_rate_limiter.py**: Unit tests for rate limiter using real Redis
- **test_api_key_manager.py**: Unit tests for API key manager using real database
- **test_middleware.py**: Unit tests for middleware using real services
- **test_integration.py**: Integration tests with real Redis and database (Phase 7: `TestGatewayProxiesToApiService`; Phase 8: `TestAggregateHealthWithRealBackend` — gateway `GET /api/v1/health` with real api-service)
- **test_e2e.py**: End-to-end tests for complete request flows
- **test_performance.py**: Performance tests for rate limiting operations
- **test_security.py**: Security tests for API Gateway

## Running Tests

### Option 1: Run via run_tests.sh (Recommended)

From project root; inherits DB/Redis env from compose (use same `.env` as the rest of the stack):

```bash
# From project root: starts postgres, redis-cache, api-service, api-gateway if needed
./services/api-gateway/run_tests.sh

# Run only Phase 8 (health check standardization) tests
./services/api-gateway/run_tests.sh phase8

# Run only Phase 7 (routing alignment) tests
./services/api-gateway/run_tests.sh services/api-gateway/tests/test_routing.py services/api-gateway/tests/test_integration.py::TestGatewayProxiesToApiService -v --tb=short
```

If you see "password authentication failed", ensure `POSTGRES_PASSWORD` in `.env` matches the running postgres.

### Option 2: Run in Docker Container

Since all services run in Docker Compose, run tests inside the API Gateway container (paths from `/app`):

```bash
# Ensure services are running (api-service needed for Phase 7 gateway proxy test)
docker compose up -d postgres redis-cache api-service api-gateway

# Run all tests (inherits env from service; use USE_PRODUCTION_DB_FOR_SDK_TESTS=1 for hub DB)
docker compose run --rm --no-deps -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 api-gateway python -m pytest services/api-gateway/tests/ -v --tb=short

# Run Phase 8 tests only (health contract + aggregate health with real api-service)
docker compose run --rm --no-deps -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 api-gateway python -m pytest services/api-gateway/tests/test_routing.py services/api-gateway/tests/test_integration.py::TestAggregateHealthWithRealBackend -v --tb=short

# Run Phase 7 tests only (routing + gateway proxy to api-service)
docker compose run --rm --no-deps -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 api-gateway python -m pytest services/api-gateway/tests/test_routing.py services/api-gateway/tests/test_integration.py::TestGatewayProxiesToApiService -v --tb=short

# Run specific test categories (from inside running container)
docker compose exec api-gateway python -m pytest services/api-gateway/tests/ -m unit -v
docker compose exec api-gateway python -m pytest services/api-gateway/tests/ -m integration -v
docker compose exec api-gateway python -m pytest services/api-gateway/tests/ -m e2e -v
docker compose exec api-gateway python -m pytest services/api-gateway/tests/ -m performance -v
docker compose exec api-gateway python -m pytest services/api-gateway/tests/ -m security -v

# Run with coverage
docker compose run --rm --no-deps -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 api-gateway python -m pytest services/api-gateway/tests/ --cov=. --cov-report=html
```

### Option 2: Run Locally (Requires Services)

If running locally, ensure:
- Redis is available at `REDIS_CACHE_URL` or `REDIS_URL`
- Database is configured and migrations are applied
- Django settings are properly configured

```bash
cd services/api-gateway
export REDIS_CACHE_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
export DJANGO_SETTINGS_MODULE=hub.settings

python -m pytest tests/ -v --tb=short
```

## Test Requirements

### Prerequisites
- Redis server (for rate limiter tests)
- PostgreSQL database (for API key manager tests)
- Django migrations applied
- All dependencies installed

### Environment Variables
- `REDIS_CACHE_URL` or `REDIS_URL`: Redis connection URL
- `DATABASE_URL`: PostgreSQL connection URL
- `DJANGO_SETTINGS_MODULE`: Django settings module (default: `hub.settings`)

## Test Behavior

### Skipping Tests
Tests will automatically skip if:
- Redis is not available (for rate limiter tests)
- Database is not available (for API key manager tests)
- Required services are not running

### Test Data
- Tests create real test data (tenants, users, API keys)
- Test data is cleaned up after tests complete
- Each test uses unique identifiers to avoid conflicts

### No Mocks or Stubs
All tests use real services:
- Real Redis connections for rate limiting
- Real database operations for API key validation
- Real middleware processing
- Real HTTP requests for E2E tests

## Troubleshooting

### Tests Skip with "Redis not available"
- Ensure Redis is running: `docker compose ps redis-cache`
- Check Redis connection: `docker compose exec redis-cache redis-cli ping`
- Verify `REDIS_CACHE_URL` environment variable

### Tests Skip with "Database not available"
- Ensure PostgreSQL is running: `docker compose ps postgres`
- Check database connection
- Verify migrations are applied: `docker compose exec api-service python manage.py migrate`

### "password authentication failed for user hub"
- Ensure `POSTGRES_PASSWORD` in `.env` (and in `.env.dev` for api-service) matches the running postgres.
- `run_tests.sh` uses `--env-file .env` and unsets host `POSTGRES_*` so the test container gets credentials from `.env`.
- If the stack was started with different credentials (e.g. `.env.dev` had `hub_secure`), either:
  - Align `.env` and `.env.dev` with the same `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, or
  - Reset postgres: stop postgres, remove volume `datainteroperabilityhub_pgdata`, start postgres with `docker compose --env-file .env up -d postgres`, then run Django migrations (`docker compose exec api-service python hub/manage.py migrate --noinput`). All DB data will be lost.

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that Django is properly set up
- Verify Python path includes the service directory

## Test Coverage

All test categories are covered:
- ✅ Unit tests (100% coverage target)
- ✅ Integration tests (real Redis and database)
- ✅ E2E tests (complete request flows)
- ✅ Performance tests (rate limiting performance)
- ✅ Security tests (authentication and validation)
