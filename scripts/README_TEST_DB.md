# Test Database Setup and Performance

## Why test runs can be slow

There are two main bottlenecks:

1. **Test database setup** (first run only): Django creates a test database and runs **all migrations** (100+ files across many apps). In Docker this can take 10–45+ minutes on the first run.

2. **Django app initialization** (every run): Django loads all apps, registers business rules, event subscribers, and validates URL patterns. This takes **5–10 seconds** on every pytest run and is unavoidable.

**Do not “fix” this with long timeouts** (e.g. 45-minute or 7-minute per-test timeouts). Fix the bottleneck instead.

## Pre-create Test Database (Recommended)

Run this **once** before your first test run to create and migrate the test database:

```bash
./scripts/setup_test_db.sh
```

This will:
- Create the test database
- Run all migrations (10–45 minutes first time)
- Make subsequent test runs fast

After this, all test runs with `--reuse-db` will be fast (5–10 seconds Django init + test execution time).

## Use `--reuse-db`

Always use `--reuse-db` so the test database is reused between runs:

```bash
pytest --reuse-db path/to/tests
```

- **First run with --reuse-db** (or first run ever): Can be slow — if the test DB is empty or not migrated, `migrate` runs once. After that the test DB is migrated.
- **Later runs with --reuse-db**: Fast — when the test DB already has schema (`django_migrations` has rows), `tests/conftest.py` uses a **fast path**: it **skips migrate and serialize**, so setup finishes in seconds and tests run immediately.

**Note**: Even with `--reuse-db`, Django app initialization (5–10 seconds) happens on every run. This is normal and unavoidable.

In Docker (api-service):

```bash
docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app python -m pytest --reuse-db path/to/tests -v --tb=short"
```

## CI

- Run pytest with `--reuse-db`. The first job (or first run after a clean env) will be slow; subsequent jobs that reuse the same DB will be fast.
- If your CI starts a fresh container every time, consider a dedicated “setup” step that runs migrations on the test DB once, then runs tests with `--reuse-db` in the same container/workspace.
- Keep **per-test timeouts short** (e.g. 60–120s). Use `-o timeout_func_only=true` so the timeout applies only to the test body, not to the session-scoped DB setup.

## Optional: patch logging

By default, `tests/conftest.py` sets the `django_patches` logger to **WARNING** to avoid extra I/O during DB setup. To see patch debug logs:

```bash
DJANGO_PATCH_DEBUG=1 pytest --reuse-db ...
```

## Check if Test DB Exists

To verify if the test database is already created and migrated:

```bash
docker compose exec -T api-service bash -c \
  "cd /app && python -c \"
from django.conf import settings
import django
django.setup()
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM django_migrations')
        count = cursor.fetchone()[0]
        print(f'Test DB exists: YES (migrations: {count})')
except Exception as e:
    print(f'Test DB exists: NO ({e})')
\""
```

## Expected Performance

- **First run** (DB creation + migrations): 10–45 minutes
- **Subsequent runs** (with `--reuse-db`): 5–10 seconds Django init + test execution time
  - Django app initialization: ~5–10 seconds (unavoidable, happens every run)
  - Test execution: depends on test count

## More detail

See `tests/integration/ROOT_CAUSE_ANALYSIS_TIMEOUTS.md` for root cause analysis and other improvements (squash migrations, profile slow migrations).
