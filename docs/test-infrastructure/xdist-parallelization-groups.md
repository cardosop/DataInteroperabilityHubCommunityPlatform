# xdist Parallelization Groups

**Date:** 2026-05-22
**Phase:** 312.12.3 — Test Performance & Developer Workflow

---

## Overview

`pytest-xdist` (`-n auto`) distributes tests across CPU cores for speed. When tests share mutable state (database rows, files, Redis keys), parallel execution causes contention and flaky failures. **xdist groups** serialize tests that must not run concurrently.

---

## Group Definitions

### `xdist_group("serial")`

Tests that **must run alone**. No other test can execute concurrently.

**Use when:**
- Test manipulates global configuration (Django settings, environment variables)
- Test uses file-system state shared across tests
- Test modifies Redis keys used by other tests
- Test uses singleton resources (mock server, test client with shared state)

### `xdist_group("db_write_heavy")`

Tests that **contend on database writes**. Multiple tests in this group can run concurrently with each other but not with tests from the same app/table.

**Use when:**
- Test performs bulk INSERT/UPDATE/DELETE on a shared table
- Test uses transactions that may deadlock under concurrent write load
- Test calls management commands that touch multiple tables
- Test creates/teardown complex fixture hierarchies

### Default: `-n auto` with `--reuse-db`

Most tests are safe for parallel execution because:
- `--reuse-db` reuses the test database across workers
- Django's `TransactionTestCase` serializes DB access per test
- `pytest-django` handles database setup/teardown per worker

---

## Usage

```python
import pytest

@pytest.mark.xdist_group("serial")
def test_global_config_mutation():
    """This test changes a Django setting — must run alone."""
    ...

@pytest.mark.xdist_group("db_write_heavy")
class TestBulkAssetImport:
    """All tests in this class contend on the assets table."""
    def test_bulk_create_1000_assets(self):
        ...
    def test_bulk_update_500_assets(self):
        ...
```

---

## Known Contention Files

The following test files are known to cause contention under `-n auto` and have been annotated:

| File | Group | Reason |
|---|---|---|
| `hub/apps/assets/tests/test_bulk_operations.py` | `db_write_heavy` | Bulk INSERT on assets table |
| `hub/apps/contracts/tests/test_migration_0010.py` | `serial` | Migration state mutation |
| `hub/apps/contracts/tests/test_normalization_pipeline.py` | `db_write_heavy` | Heavy normalization writes |
| `hub/apps/compliance/tests/test_compliance_runs.py` | `db_write_heavy` | ComplianceRun bulk operations |
| `hub/apps/marketplace/tests/test_order_fulfillment.py` | `db_write_heavy` | Order/entitlement writes |
| `hub/apps/governance/tests/test_access_request_approval.py` | `db_write_heavy` | Multi-step approval writes |
| `hub/apps/mesh/tests/test_domain_topology.py` | `serial` | Global mesh topology changes |
| `hub/apps/audit/tests/test_audit_event_bulk.py` | `db_write_heavy` | Bulk audit event writes |
| `tests/concurrency/test_tenant_isolation.py` | `serial` | Cross-tenant isolation verification |
| `tests/isolation/test_rate_limit_isolation.py` | `serial` | Rate-limit state verification |

---

## CI Configuration

```bash
# Parallel-safe tests (default)
pytest -m "not serial and not db_write_heavy" -n auto --reuse-db

# Serial-only tests
pytest -m "serial" -p no:xdist --reuse-db

# DB-write-heavy tests (limited concurrency)
pytest -m "db_write_heavy" -n 2 --reuse-db
```

---

## Related Documentation
- [marker-audit.md](marker-audit.md) — Full pytest marker catalog
- [flaky-test-quarantine-policy.md](flaky-test-quarantine-policy.md) — Flaky test lifecycle
