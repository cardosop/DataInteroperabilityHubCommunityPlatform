# Test Infrastructure Audit — Index

**Date:** 2026-05-21
**Phase:** 312.2 — Test Infrastructure Audit
**Scope:** 11 audit documents covering all aspects of the Meshant test infrastructure.

---

## Audit Documents

| # | Document | Description | Lines |
|---|---|---|---|
| 1 | [script-audit.md](script-audit.md) | Audit of 607 scripts in `scripts/`: 48 Active, 30 Legacy, 8 Duplicate, 52 Dead, 62 Utility | ~200 |
| 2 | [marker-audit.md](marker-audit.md) | Audit of 60 pytest markers: 32 zero-use (53%), 3 high-use (100+), 3 built-in markers used but unregistered | ~160 |
| 3 | [conftest-audit.md](conftest-audit.md) | Audit of 47 conftest files (5,992 lines in 6 core files): duplication analysis, `conftest_prefect.py` non-standard name, `tests/e2e/conftest.py` (1,996 lines) extraction opportunity | ~180 |
| 4 | [factory-audit.md](factory-audit.md) | Audit of 9 factory files (1,892 lines): duplication map, cross-app dependencies, consolidation candidates | ~220 |
| 5 | [ci-workflow-audit.md](ci-workflow-audit.md) | Audit of 25 CI test workflows: triggers, job catalog, overlap analysis, DJANGO_SETTINGS_MODULE references | ~260 |
| 6 | [settings-audit.md](settings-audit.md) | Audit of 3 test settings modules + 157 DJANGO_SETTINGS_MODULE references; `test_settings_phase11.py` is legacy+unsafe | ~190 |
| 7 | [docker-compose-audit.md](docker-compose-audit.md) | Audit of `docker-compose.test.yml` (63 services): dependency graph, 3 API variants analysis, startup time; **all images properly pinned** | ~280 |
| 8 | [env-var-audit.md](env-var-audit.md) | Audit of 14 `SKIP_*`/`TEST_*`/`USE_*` env vars + 5 supplementary vars: usage, defaults, dead flags | ~370 |
| 9 | [ci-scripts-audit.md](ci-scripts-audit.md) | Audit of 52 CI quality scripts: categorized by phase and functional area, 9 dead scripts identified | ~140 |
| 10 | [existing-infra-inventory.md](existing-infra-inventory.md) | Comprehensive inventory: backend tests, E2E, frontend, security, performance, microservices, CI gates | ~230 |
| 11 | [README.md](README.md) | This index (you are here) | ~50 |

**Total:** ~1,730 lines of audit documentation.

---

## Key Findings at a Glance

### Critical Issues
- **53% of pytest markers are dead** (32/60) — clean up `pytest.ini`
- **`VALIDATE_SERVICE_CONNECTIVITY` is dead** — one read site, zero set sites
- **`test_settings_phase11.py` can corrupt test DB** if accidentally imported — delete it
- **`conftest_prefect.py` is undiscoverable** — non-standard name, pytest ignores it
- **`tests/e2e/conftest.py` is 1,996 lines** — third-largest conftest, needs extraction

### Consolidation Opportunities
- **8 app factory files** duplicate central `tests/factories.py` — consolidate
- **7 E2E workflows** have overlapping coverage — merge into parameterized workflow
- **3 mutmut workflows** — merge with matrix strategy
- **5 migrated-test shell scripts** — consolidate into one parameterized script
- **10 duplicate E2E batch markers** (e2e1-5 + e2e_batch1-5) — pick one convention

### Dead Code
- **52 unreferenced scripts** in `scripts/` — one-shot audits never run again
- **30 legacy phase-specific scripts** — completed development phases
- **9 dead CI quality scripts** — no CI/Makefile/pre-commit references
- **`hub/test_settings_phase11.py`** — not referenced in any CI workflow
- **32 zero-use pytest markers** — registered but never applied

### Strengths
- **Single `DJANGO_SETTINGS_MODULE`** — only `hub.settings` used everywhere (no settings proliferation)
- **All Docker images properly pinned** — zero external `:latest` tags in docker-compose.test.yml
- **Consistent throttle key isolation** — all throttle cache keys include `tenant_id`
- **Comprehensive CI quality gates** — 52 scripts covering 13 functional categories
- **3 API variants with `extends:`** — clean compose inheritance pattern for MVP/non-MVP testing
- **Production guard tests** — 37+ tests protecting production safety

---

## Cross-Cutting Impact Analysis

### Frontend
- **No direct impact** from this audit (documentation only).
- **Indirect benefit:** Frontend tests (vitest, a11y, Playwright, Chromatic, visual regression) are catalogued and CI workflows mapped — easier to debug frontend CI failures.
- **Risk identified:** `frontend-test` compose service is broken (TS build errors), under `--profile frontend`. Frontend devs should use `docker-compose.dev.yml` instead.

### Backend
- **No runtime impact.** All backend test paths, conftest patches, factory patterns, and marker taxonomy are documented.
- **Settings risk:** `test_settings_phase11.py` poses a silent DB corruption risk for developers running tests from an IDE that auto-imports it.
- **Anti-pattern found:** Production code in `hub/apps/contracts/views.py`, `views_refactored.py`, `views_base.py`, `urls.py`, and `hub/apps/auth/middleware.py` checks `DJANGO_SETTINGS_MODULE.endswith("test")` instead of using the `TESTING` env flag.

### Infrastructure
- **Docker Compose:** 63 services with 14 volume mounts. All images properly pinned. Startup is 8-15 minutes due to `postgres-test` 900s healthcheck start_period.
- **CI runners:** `ci.yml` at 116KB with 50+ jobs causes runner queue contention. Recommended to split.
- **No `:latest` tags risk** — confirmed all external images are version-pinned.

### Tests
- **Test discovery gap:** `testpaths = hub/apps tests` in `pytest.ini` excludes `cli/tests`, `sdk/python/tests`, and `services/*/tests` (~5,000 test functions).
- **Marker hygiene:** 32/60 markers are dead. No formal marker taxonomy (unit/integration/e2e) is enforced.
- **Factory fragmentation:** Two incompatible factory patterns (factory_boy vs static methods).
- **Conftest size:** Three conftest files exceed 1,400 lines each. Extraction to `hub/testing/` is planned (312.3).

### Operations
- **`STRICT_TEST_TEARDOWN` should be enabled in CI** — currently teardown errors are silently suppressed.
- **`VALIDATE_SERVICE_CONNECTIVITY` is dead code** — safe to remove from `tests/conftest.py`.
- **Monitoring test stack** (Prometheus/Grafana/Alertmanager) is heavyweight for CI — profile-guard for nightly only.

### CI/CD
- **Workflow overlap:** 7 E2E workflows for the same test surface. Consolidation would reduce CI complexity.
- **`release/mvp-v1` branch trigger** in `ci.yml` may be dead if MVP-v1 is shipped.
- **`chromatic.yml`** references `master` branch that may not exist.
- **openlineage-f4-dod.yml** trigger is correct (`push: tags: [f4-*]`) — no fix needed.
- **test-results-reporting.yml** meta-aggregator depends on artifacts from 10+ upstream workflows.

---

## Recommended Priority Actions

1. **Week 1:** ✅ Delete `test_settings_phase11.py`, ✅ rename `conftest_prefect.py` → `tests/prefect/conftest.py` (Phase 312.11.1), remove `VALIDATE_SERVICE_CONNECTIVITY`, fix `DJANGO_SETTINGS_MODULE.endswith("test")` anti-pattern
2. **Week 2:** ✅ Clean up 32 zero-use markers from `pytest.ini` (Phase 312.5), consolidate 9 factory files, extract `tests/e2e/conftest.py` runner logic
3. **Week 3:** ✅ Delete 52 dead scripts (Phase 312.7.8: 9 workflows archived), consolidate E2E workflows (Phase 312.7), enable `STRICT_TEST_TEARDOWN=1` in CI
4. **Week 4:** Add flaky quarantine, fix `testpaths` to include all test dirs, split `ci.yml` monolith

---

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) — Project instructions and conventions
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — System architecture
- [docs/API_STANDARDS.md](../../docs/API_STANDARDS.md) — API design standards
- [openspec/changes/preprod01/tasks.md](../../openspec/changes/preprod01/tasks.md) — Pre-prod phase tasks
