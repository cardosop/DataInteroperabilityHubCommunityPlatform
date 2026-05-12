# Fixture Audit — Phase 274.14 (BR20)

## Audit Date: 2026-05-12

### Current State

15 conftest.py files found under `hub/apps/*/tests/`:
- Most contain only `pytest_collection_modifyitems` for MVP marker
- 0 conftest files define `@pytest.fixture` functions (no `_raw_*` or `*_via_service` patterns exist)

### tests/fixtures/ directory contents:
- `contracts/` — contract test data
- `marketplace/` — marketplace test data
- `odps/` — ODPS test data
- `email_service_fixtures.py`
- `external_service_fixtures.py`
- `prefect_fixtures.py`
- `test_data_factories.py`

### Categorization

No `_raw_*` vs `*_via_service` naming convention exists today.
All fixtures are unnamed/unclassified.

### PR-B Plan (Phase D follow-up per 274.14.4)

1. Rename fixtures that bypass services to `_raw_*`
2. Update test imports across all affected test files
3. Flip conformance test from warn-only to hard-gate

### Decision

274.14.4 — **Defer to Phase D.** The rename sweep touches
potentially hundreds of test imports and carries non-trivial
merge-conflict risk. Phase D provides a dedicated window for
this controlled sweep.
