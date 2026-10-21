# Testing Guide

How to run and write tests for the Meshant platform.

## Frameworks

| Layer | Framework | Config |
|-------|-----------|--------|
| Backend | pytest + Django test runner | `pytest.ini`, `DJANGO_SETTINGS_MODULE=hub.settings_test` |
| Frontend | Vitest (unit), Playwright (E2E) | `vitest.config.ts`, `playwright.config.ts` |
| CLI | pytest | `cli/pytest.ini` |
| SDK (Python) | pytest | `sdk/python/pytest.ini` |
| SDK (JavaScript) | Jest | `sdk/js/jest.config.ts` |

## Running Tests

### Backend

```bash
# All tests
pytest hub/

# Specific app
pytest hub/apps/contracts/tests/

# With coverage
pytest hub/ --cov=hub --cov-report=html

# Specific test
pytest hub/apps/audit/tests/test_archive_command.py -v
```

### Frontend

```bash
cd frontend

# Unit tests
npm run test

# E2E tests (requires running backend)
npx playwright test

# E2E with UI
npx playwright test --ui
```

### CLI and SDK

```bash
# CLI tests
cd cli && pytest

# Python SDK tests
cd sdk/python && pytest

# JavaScript SDK tests
cd sdk/js && npm test
```

## Test Database

Tests use a separate database to avoid polluting development data:

```bash
TEST_DATABASE_URL=postgresql://hub:hub@localhost:5432/hub_test
```

Set `DJANGO_SETTINGS_MODULE=hub.settings_test` for test-specific settings
(in-memory caching, console email backend, disabled rate limiting).

## Test Structure

```
hub/apps/<app>/tests/
  test_models.py        — Model creation, validation, constraints
  test_views.py         — API endpoint behavior
  test_services.py      — Business logic
  test_serializers.py   — Input/output serialization

frontend/e2e/
  journeys/             — End-to-end user journey tests
  use-cases/            — Use case validation tests
```

## Writing Tests

- Use `pytest.mark.django_db(transaction=True)` for database tests
- Use unique identifiers (`uuid.uuid4().hex[:8]`) in fixtures to avoid collisions
- Prefer `APIClient` for endpoint tests (handles auth, content type)
- Test both success and error paths
- For audit tests, use `all_objects` manager (default manager excludes archived events)

## CI Integration

Tests run automatically in GitHub Actions on every push and PR:

- `.github/workflows/ci.yml` — Backend unit + integration tests
- `.github/workflows/frontend-tests.yml` — Frontend unit tests
- `.github/workflows/e2e.yml` — End-to-end Playwright tests

## Related

- [Local Development](local-dev.md) -- dev environment setup
- [Configuration Reference](configuration-reference.md) -- test environment variables
