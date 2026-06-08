# Pytest Marker Audit

**Date:** 2026-05-21
**Scope:** 60 registered markers in `pytest.ini` + built-in markers found in code.
**Methodology:** Marker registration extracted from `pytest.ini`; usage counts from `grep -rn "@pytest.mark"` across `hub/` and `tests/`.

## Summary

| Metric | Count |
|---|---|
| Total registered markers | 60 |
| Markers with **zero** uses | 32 (53%) |
| Markers with **1-10** uses | 20 (33%) |
| Markers with **11-100** uses | 5 (8%) |
| Markers with **100+** uses | 3 (5%) |
| Built-in markers found in code (not in registry) | 3 (`skipif`=91, `parametrize`=65, `timeout`=32) |

---

## Marker Usage — Full Census

### Top Usage (100+)

| Marker | Uses | Notes |
|---|---|---|
| `django_db` | 306 | pytest-django DB access marker |
| `asyncio` | 118 | pytest-asyncio async test marker |
| `integration` | 87 | Integration tests |

### Moderate Usage (11-99)

| Marker | Uses |
|---|---|
| `journey` | 15 |
| `e2e` | 12 |
| `docker_compose_runtime` | 11 |
| `real_virtualization_e2e` | 10 |

### Low Usage (1-10)

| Marker | Uses | Notes |
|---|---|---|
| `spec` | 9 | Spec traceability |
| `requires_database` | 7 | |
| `performance` | 7 | |
| `isolation` | 6 | |
| `scheduled_ingestion_integration` | 5 | |
| `uc` | 4 | Use case traceability |
| `requires_aws_test_dataset` | 4 | |
| `tabletop_rehearsal` | 3 | |
| `benchmark` | 3 | |
| `allow_server_errors` | 3 | |
| `snowflake_integration` | 2 | |
| `slow` | 2 | |
| `requires_aws_role_arn` | 2 | |
| `e2e_batch2` | 2 | |
| `aws_integration` | 2 | |
| `xfail` | 1 | Built-in, but registered? |
| `uses_admin_role` | 1 | |
| `stripe_connect` | 1 | |
| `snowflake_e2e` | 1 | |
| `smoke_mvp_mode` | 1 | |
| `security` | 1 | |
| `requires_redis` | 1 | |
| `requires_file_virus_scan_e2e` | 1 | |
| `requires_clamav_live` | 1 | |
| `requires_aws_session_token` | 1 | |
| `gcp_integration` | 1 | |
| `filterwarnings` | 1 | |

### Zero Usage — Dead Markers (32)

These markers are registered in `pytest.ini` but **never used** in any test file:

| Marker | Registered Purpose |
|---|---|
| `unit` | Unit tests |
| `e2e1` | E2E sub-batch 1 — Core API, Contracts, Assets, Datasets, Files, Schema |
| `e2e2` | E2E sub-batch 2 — Worker, Jobs, DQ, Compliance |
| `e2e3` | E2E sub-batch 3 — Email, Rate Limiting |
| `e2e4` | E2E sub-batch 4 — Auth, Personas, Tenants, CLI |
| `e2e5` | E2E sub-batch 5 — Marketplace, Semantic, Monitoring, Edge Cases, Journeys |
| `e2e_batch1` | E2E Batch 1 — Core API, Contracts, Assets |
| `e2e_batch3` | E2E Batch 3 — Email, Notifications, Rate Limiting |
| `e2e_batch4` | E2E Batch 4 — Tenant Config, Personas, CLI |
| `e2e_batch5` | E2E Batch 5 — Marketplace, Semantic, Monitoring, Edge Cases |
| `requires_services` | Tests that require external services |
| `requires_test_env` | Tests that require test environment validation |
| `requires_services_connectivity` | Tests that require service connectivity validation |
| `requires_gcp_service_account` | GCP integration tests (skip when unset) |
| `saas_platform` | SaaS platform feature tests |
| `cli_sdk` | CLI and SDK tests |
| `regression` | Regression tests |
| `odh_inference` | Tests that require ODH Inference Scheduler |
| `requires_minio` | Tests that require MinIO/S3 |
| `requires_prefect` | Tests that require Prefect |
| `requires_mailhog` | Tests that require MailHog |
| `requires_stripe` | Stripe-dependent tests |
| `workflow_e2e` | Workflow engine E2E tests |
| `marketplace` | Marketplace-specific tests |
| `serial` | Tests that must run sequentially |
| `mvp` | Tests for MVP features |
| `rls` | Row-level security tests |
| `openspec_gate` | OpenSpec CLI validation only |
| `uc_journey_persona` | UC/journey/persona E2E tests |
| `persona` | Persona name marker |
| `scheduled_export` | Scheduled export feature tests |
| `real_scheduled_e2e` | Real scheduled ingestion/export E2E |

Note: `e2e_batch2` has 2 uses (the only partially-used e2e_batch marker). `real_scheduled_e2e` is registered but its tests use the env var gate pattern instead of the marker. `persona` is marked as "Persona name" but no tests use it with `@pytest.mark.persona`.

### Built-in Markers Found in Code (not in registry)

These are used in test code but are pytest built-ins (no registration needed):

| Marker | Uses | Origin |
|---|---|---|
| `skipif` | 91 | pytest built-in |
| `parametrize` | 65 | pytest built-in |
| `timeout` | 32 | `pytest-timeout` plugin — **should be registered** to avoid `--strict-markers` warnings |

No unregistered non-built-in markers found — all custom markers used in code are properly registered.

---

## Analysis

### Dead Marker Rate: 53%

Over half (32/60) of registered markers have zero uses. This creates confusion about which markers to use for test selection/filtering.

### Duplicate Marker Sets

The `e2e1`-`e2e5` set and `e2e_batch1`-`e2e_batch5` set serve the **same purpose** (E2E batching) with different naming conventions. Only `e2e_batch2` has any usage (2). This is a clear consolidation opportunity.

### Marker Naming Inconsistency

- `e2e1`-`e2e5` (no underscore) vs `e2e_batch1`-`e2e_batch5` (underscore + "batch")
- `requires_*` prefix used for 14 markers, but `snowflake_e2e` and `snowflake_integration` don't follow the pattern
- `real_scheduled_e2e` uses env var gating, not marker gating — registration is misleading

### Built-in Confusion

`unit` is registered but never used. The `integration` marker (87 uses) functions as the de facto primary categorization, with `e2e` (12 uses) as secondary. This suggests the test taxonomy was designed for a `unit`/`integration`/`e2e` split that was never implemented.

---

## Recommendations

1. **Remove 32 zero-use markers** from `pytest.ini` — cleans up `--markers` output and reduces confusion.
2. **Consolidate E2E batch markers** — pick ONE naming convention (`e2e_batch1`-`e2e_batch5` or `e2e1`-`e2e5`) and remove the other set (10 markers total).
3. **Either implement `unit` marker or remove it** — if unit tests exist, tag them; otherwise delete the marker.
4. **Register `timeout` marker explicitly** — `pytest-timeout` is used (32 occurrences) but the marker isn't registered in `pytest.ini`, causing strict-marker warnings.
5. **Run `scripts/add_e2e_batch_markers.py`** (dead script now) to actually apply batch markers to E2E tests, so the batching markers become functional.
6. **Audit marker usage in CI selectors** — check that `-m` flags in CI workflows reference markers that actually have uses.
