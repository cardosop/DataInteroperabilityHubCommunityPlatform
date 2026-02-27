# Test Slowness Investigation

**Purpose**: Identify root causes of slow test execution and document mitigations.

---

## Root Causes (in order of impact)

### 1. **Repeated pytest startup (25× per full run)**

With batched execution (`run_phase_12a_backend_suites.sh`), each of the 25 unit batches runs a **separate** `docker compose exec` + pytest process. Each process does:

| Step | Time | × 25 batches |
|------|------|--------------|
| Conftest load (Django imports, patches) | 2–4 s | 50–100 s |
| `pytest_sessionstart` (DB check, django.setup) | 3–8 s | 75–200 s |
| pytest-django `create_test_db` / reuse | 1–5 s* | 25–125 s |
| Collection (import test modules) | 5–30 s | 125–750 s |

\* With `--reuse-db` and pre-migrated DB: ~1 s. Without: 10–45 min first run.

**Total overhead**: ~4–12 minutes before any test runs, just from startup.

### 2. **Django app initialization (every run)**

Per [README_TEST_DB.md](../scripts/README_TEST_DB.md):

- **5–10 seconds** per pytest run for Django to load all apps, register business rules, event subscribers, validate URL patterns.
- Unavoidable per process; with 25 batches that’s 2–4 minutes.

### 3. **Test database creation / migrations (first run)**

- First run: Django creates test DB and runs **100+ migrations** → 10–45 minutes.
- Mitigation: run `./scripts/setup_test_db.sh` once, then use `--reuse-db`.

### 4. **DB connectivity check (hub/conftest)**

- `hub/conftest.py` `pytest_sessionstart` runs `django.setup()` + `psycopg2.connect()` before collection.
- Runs **once per batch** = 25×. Each check: ~2–5 s when DB is healthy.

### 5. **Collection phase**

- Importing test modules pulls in app code and triggers Django setup.
- Large batches (e.g. Integrations) can take 30+ s to collect.

### 6. **Docker volume mount**

- `.:/app` bind mount can be slow on Mac/Windows.
- On Linux with overlay2 usually fine.

---

## Mitigations (implemented or recommended)

### A. Pre-create test database (do once)

```bash
./scripts/setup_test_db.sh
```

Ensures `--reuse-db` can skip migrations. Saves 10–45 min on first run.

### B. Skip DB check for batches 2+ (implemented)

When running batched unit tests, batch 1 already verified DB. Batches 2+ can set `SKIP_DB_CONNECTIVITY_CHECK=1` to save ~2–5 s per batch.

### C. Fewer, larger batches

- Current: 25 batches → 25× startup.
- Alternative: 8–10 batches → ~8–10× startup.
- Trade-off: larger batches = more memory and longer collection per batch.

### D. Single pytest run instead of 25 batches

Run one pytest process with all paths and `-n 4`:

```bash
docker compose exec -T api-service-test bash -c "cd /app && python -m pytest hub/apps/ tests/unit/ -v -m 'not integration and not e2e' --reuse-db -n 4 ..."
```

- One Django init, one collection, one DB check.
- Collection of ~18k tests: ~2–5 min once.
- Total: ~3–6 min overhead vs 4–12 min with 25 batches.

### E. Reduce parallel workers for heavy batches

- `-n 4` spawns 4 workers; each can add memory/DB load.
- For OOM-prone batches (ODPS, ODCS, Files), use `-n 2` or `-n 0`.

---

## Diagnostic commands

### 1. Time Django setup only

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "
  cd /app && time python -c \"
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
print('Django OK')
\"
"
```

### 2. Time collection only (no tests run)

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "
  cd /app && time python -m pytest hub/apps/assets/tests/ --collect-only -q
"
```

### 3. Time full pytest (one small batch)

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "
  cd /app && time python -m pytest hub/apps/core/tests/ -v -m 'not integration and not e2e' --reuse-db -x
"
```

### 4. Check if test DB is pre-migrated

```bash
docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "
  cd /app && python -c \"
from django.conf import settings
import django
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute('SELECT COUNT(*) FROM django_migrations')
    print('Migrations:', c.fetchone()[0])
\" 2>/dev/null || echo 'DB not ready'
"
```

---

## Quick wins checklist

- [ ] Run `./scripts/setup_test_db.sh` once (if not done)
- [ ] Use `--reuse-db` (already in scripts)
- [ ] Set `SKIP_DB_CONNECTIVITY_CHECK=1` for batch 2+ (see run script)
- [ ] Consider single pytest run for unit phase instead of 25 batches
- [ ] Use `PYTEST_PARALLEL_WORKERS=4` (or 0 if OOM)
