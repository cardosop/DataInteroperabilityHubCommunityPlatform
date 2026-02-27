# Startup Configuration Validation Design

**Document Version**: 1.0  
**Last Updated**: 2026-02-19  
**Task**: Phase 10 — Startup Configuration Validation (openspec/changes/testsfix1 tasks 10.1–10.4)

---

## 1. Overview

Configuration validation runs at startup so misconfiguration fails fast with a clear error instead of failing later in request handling or with opaque backend errors. This document defines required environment variables, format checks, and where validation runs.

**Principles**: No mocks; validation uses real settings and env; failures raise `django.core.exceptions.ImproperlyConfigured` with a clear message.

---

## 2. Required Environment Variables and Format Checks

### 2.1 Always validated (all environments)

| Variable | Check | Error if |
|----------|--------|----------|
| **Database** | `DATABASES['default']` present and has `ENGINE`, `NAME`, `HOST`, `PORT` (from `POSTGRES_*` or equivalent in settings). | Missing or empty required key. |
| **Redis** | At least one of `REDIS_URL` or `REDIS_CACHE_URL` (from settings) is set and matches `redis://[host][:port]/[db]`. | In production/staging: no Redis URL or invalid scheme. In development: warn only if missing. |
| **ALLOWED_HOSTS** | When `ENVIRONMENT` is `production`: list non-empty. | Production and ALLOWED_HOSTS is empty. |

### 2.2 Production-only (when `ENVIRONMENT=production`)

| Variable | Check | Error if |
|----------|--------|----------|
| **SECRET_KEY** | Set via env and not the dev default (`dev-secret-key-not-for-production`). | Missing, empty, or dev default. |
| **JWT_SECRET_KEY** | Set via env and not the dev default (`dev-jwt-secret-key-not-for-production`). | Missing, empty, or dev default. |

### 2.3 Optional / not validated at startup

- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — optional; validated when billing is used.
- `HUB_WORKER_API_KEY` — optional for worker auth.
- Feature flags, logging level, timeouts — no fail-fast validation.

### 2.4 Format rules

- **Redis URL**: Must start with `redis://` or `rediss://`; may contain host, port, path (db number). No strict regex; we check prefix and non-empty.
- **Database**: Validated via Django’s `DATABASES` structure; we do not parse `DATABASE_URL` if the project uses `POSTGRES_*` in settings.
- **ALLOWED_HOSTS**: Comma-separated list or list; in production must have at least one entry.

---

## 3. Where Validation Runs

### 3.1 Management command (primary)

```bash
python hub/manage.py validate_config
```

- **When**: Before starting the server in deployment (e.g. in container entrypoint or init step).
- **Behavior**: Loads Django settings, runs all checks, exits 0 if valid, exits 1 and prints `ImproperlyConfigured` message if invalid.
- **Use in containers**: Run this before `gunicorn` or `runserver` so the process fails fast and the orchestrator can restart or alert.

### 3.2 AppConfig.ready() (fail-fast on server start)

- **When**: During Django startup when the core app’s `ready()` runs.
- **Behavior**: Runs validation only when:
  - Not running management commands that skip it (`migrate`, `makemigrations`, `test`, `validate_config` itself), and
  - Not under pytest (so test runs do not require production env).
- **Purpose**: If someone starts the server without having run `validate_config` in the entrypoint, the process still fails fast on bad config (e.g. production with dev secrets).

### 3.3 Container entrypoint (recommended for production)

In production, run validation before starting the app server:

```bash
python hub/manage.py validate_config && exec gunicorn hub.wsgi:application ...
```

Or use an entrypoint script:

```bash
#!/bin/sh
set -e
python hub/manage.py validate_config
exec "$@"
```

See [RUNBOOKS.md](RUNBOOKS.md) and deployment docs for the exact command per environment.

### 3.4 When validation is skipped

- **Tests**: Pytest and `manage.py test` do not run validation in `ready()` so test env (e.g. SQLite, mock Redis) is not required to pass production checks.
- **Migrations**: `migrate` and `makemigrations` do not run validation in `ready()` so DB bootstrap does not depend on Redis or production secrets.
- **validate_config command**: The command itself runs validation; it is not skipped.

---

## 4. Implementation Layout

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Validation logic | `hub/apps/core/config_validation.py` | Functions that read `django.conf.settings` and raise `ImproperlyConfigured` on failure. |
| Management command | `hub/apps/core/management/commands/validate_config.py` | Calls validation, handles exit code. |
| AppConfig hook | `hub.apps/core/apps.py` | Calls validation in `ready()` when not in test/migrate. |
| Design and runbook | `docs/CONFIG_VALIDATION_DESIGN.md`, `docs/RUNBOOKS.md` | Document variables, checks, and where to run. |

---

## 5. Error Messages

Validation raises `ImproperlyConfigured` with messages that:

- Identify the variable or check that failed.
- State what is required (e.g. "SECRET_KEY must be set via environment in production").
- Point to this document or RUNBOOKS when useful.

Example:

```
django.core.exceptions.ImproperlyConfigured: In production, SECRET_KEY must be set via
environment and must not be the dev default. Set SECRET_KEY in env or use a secret manager.
See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md.
```

---

## 6. Optional: Connectivity Checks

By default, validation does **not** open connections to the database or Redis (so it works in environments where the network is not yet available). Optionally, a future flag such as `--check-connectivity` could:

- Open a DB connection and run a trivial query.
- Ping Redis.

That would be documented here and in the command help. Phase 10 does not require connectivity checks; format and presence are sufficient for fail-fast startup.
