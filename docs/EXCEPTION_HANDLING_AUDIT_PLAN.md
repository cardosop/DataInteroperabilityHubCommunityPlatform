# Exception Handling Audit Plan

This document defines the process, categories, and fix patterns for the production exception-handling audit. It aligns with **DEVELOPMENT_GUIDE Phase 24.1** and ensures no bare `except:` or silent `except Exception: pass` in production code.

## 1. Scope

- **In scope:** `hub/apps/`, `services/` (excluding `**/tests/**`), production scripts under `scripts/` (excluding test helpers).
- **Out of scope:** `**/tests/**`, `**/migrations/**`, docs examples, backup folders.

## 2. Inventory Process

1. **Search:** Run for broad and bare catches in production code:
   - `except:` (bare except — catches everything including `SystemExit`/`KeyboardInterrupt`)
   - `except Exception` (broad — hides specific failure modes)
2. **List:** For each occurrence, record file path, line number, and surrounding 2–3 lines.
3. **Categorize:** Assign one of the categories below.
4. **Fix:** Apply the fix pattern for that category.

## 3. Categories

| Category | Description | When to use |
|----------|-------------|-------------|
| **Re-raise** | Catch a specific exception, log with context, then re-raise. | When the caller must handle the failure (e.g. API view, job runner). |
| **Specific catch** | Catch one or more specific types (e.g. `ConnectionError`, `TimeoutError`, `ValidationError`), handle or map to API error, log. | When the failure mode is known and can be handled or translated. |
| **Log-and-continue** | Catch a specific (or narrow) set of exceptions for non-critical operations (e.g. audit event, metrics, cache, optional feature), log with structured context, do not re-raise. | When failure must not break the main flow (e.g. event publish, cache set). |

**Rules:**

- **Never** use bare `except:`.
- **Never** use `except Exception: pass` (or any `... pass` without logging).
- **Always** log with context: use `logger.warning()` or `logger.exception()` with `extra={"error_type": type(e).__name__, "error": str(e), ...}` (or equivalent structured fields).
- Prefer **specific exception types** where possible; use `except Exception as e` only as a final fallback and always log.

## 4. Fix Patterns (from DEVELOPMENT_GUIDE Phase 24.1)

### 4.1 Replace bare `except:`

**Wrong:**
```python
try:
    do_something()
except:
    pass
```

**Correct:** Use at least `Exception` and log:
```python
try:
    do_something()
except Exception as e:
    logger.warning(
        "operation_failed",
        extra={"error_type": type(e).__name__, "error": str(e), "context": "do_something"},
        exc_info=True,
    )
```

### 4.2 Replace `except Exception: pass`

**Wrong:**
```python
try:
    publish_audit_event(...)
except Exception:
    pass
```

**Correct:** Log with context, then continue:
```python
try:
    publish_audit_event(...)
except Exception as e:
    logger.warning(
        "audit_event_publish_failed",
        extra={"error_type": type(e).__name__, "error": str(e), "resource_id": resource_id},
        exc_info=True,
    )
```

### 4.3 Non-critical operations (cache, metrics, events)

Catch specific exceptions when known (e.g. Redis `ConnectionError`, `TimeoutError`); keep a single broad fallback that **logs**:

```python
try:
    cache.set(key, value)
except (ConnectionError, TimeoutError, RuntimeError) as e:
    logger.warning(
        "cache_set_failed",
        extra={"error_type": type(e).__name__, "error": str(e), "key": key},
        exc_info=True,
    )
except Exception as e:
    logger.exception(
        "cache_set_unexpected_error",
        extra={"error_type": type(e).__name__, "key": key},
    )
```

### 4.4 Service / API layer

Catch domain exceptions first, then a single broad catch that logs and returns a structured error (e.g. 500):

```python
try:
    result = service.create_resource(...)
except ValidationError as e:
    return handle_service_exception(e)
except NotFoundError as e:
    return handle_service_exception(e)
except Exception as e:
    logger.exception(
        "create_resource_unexpected_error",
        extra={"error_type": type(e).__name__},
    )
    return api_error_response(
        message="An unexpected error occurred",
        status_code=500,
        code="INTERNAL_ERROR",
    )
```

## 5. High-Priority Files (Phase 9.3)

These files were fixed first:

| File | Notes |
|------|--------|
| `hub/apps/integrations/services.py` | Replace bare `except:` with `except Exception as e` + structured log; ensure all broad catches log with `extra`. |
| `hub/apps/jobs/tasks_odps.py` | Replace `except Exception: pass` with log-and-continue (event publish, etc.); replace bare `except:` with logged catch. |
| `hub/apps/marketplace/services.py` | Audit-event blocks: replace `except Exception: pass` with log-and-continue. |
| `hub/apps/contracts/services.py` | Same pattern: specific exceptions where possible, broad catch only with logging. |
| `hub/apps/contracts/odps_rate_limiting.py` | Replace bare `except:` and `except Exception: pass` with structured logging; fail-open behavior preserved. |
| `hub/apps/websocket/middleware/auth.py` | Remove debug file logging; replace bare `except Exception: pass` with structured log (e.g. logger.debug) or specific exception. |

## 6. Ruff and CI

- **Ruff rule E722** (bare `except`) is enabled in `pyproject.toml` (see [ERROR_HANDLING.md](./ERROR_HANDLING.md#ruff-e722-bare-except)).
- CI runs `ruff check`; E722 violations fail the build.

## 7. Inventory Summary (Production Code Only)

The following locations were audited (excluding `**/tests/**`). High-priority files are fixed in Phase 9.3; remaining production files are fixed in Phase 9.4 and in the Phase 9 review pass.

- **hub/apps/** — High-priority files (9.3) and additional production files fixed in review: `integrations/encryption.py`, `integrations/connectors/aws_data_exchange_connector.py`, `datasets/services.py`, `observability/services.py`, `orchestration/workflows/marketplace_sync.py`, `ml/business_rules.py`, `contracts/views_export.py`, `contracts/odcs_generator.py`. All `except Exception: pass` in these files now use structured logging (log-and-continue). Test directories excluded.
- **services/** — Production bare `except:` fixed in `dq-service/gx_adapter.py`; test directories excluded.
- **scripts/** — Production scripts only; test files excluded.

Run the following to regenerate the list (from repo root):

```bash
rg -n 'except\s*:|except\s+Exception' --type py hub/apps services scripts \
  --glob '!**/tests/**' --glob '!**/migrations/**' --glob '!**/backups/**'
```
