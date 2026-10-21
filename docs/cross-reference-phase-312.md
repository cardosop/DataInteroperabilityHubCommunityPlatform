# Cross-Reference: Phase 312 — Sibling Change Coverage

**Date:** 2026-05-22
**Phase:** 312.18.3 — OpenSpec Integration
**Scope:** Cross-reference `openspec/changes/testreview1/` and `openspec/changes/testsfix1/` against Phase 312 tasks.

---

## Summary

Phase 312 (this phase) covers test infrastructure across 18 subphases. Many tasks from sibling changes (`testreview1/` and `testsfix1/`) are now superseded or covered.

---

## `openspec/changes/testreview1/` — Coverage Map

| Sibling File | Content | Covered By Phase 312? |
|---|---|---|
| `design.md` | Test infrastructure design review | **Superseded** — 312.2 audit covers this in detail |
| `tasks.md` | 16 phases of test review tasks | See detailed table below |
| `E2E_TEST_GAP_ANALYSIS.md` | E2E test coverage gaps | **Covered** — 312.2.5 (CI workflow audit), 312.8.3 (E2E batch strategy) |
| `DOCKER_COMPOSE_TEST_GAP_ANALYSIS.md` | Docker Compose test gaps | **Covered** — 312.2.7 (docker-compose audit) |
| `DOCKER_COMPOSE_IMPROVEMENT_PLAN_BEST_PRACTICES.md` | Docker Compose best practices | **Covered** — 312.2.7 recommendations |
| `DOCKER_COMPOSE_UPDATE_PLAN_COVERAGE.md` | Docker Compose coverage plan | **Superseded** — 312.2.7 covers this |
| `DOCKER_COMPOSE_FIX_PLAN_FLAKY.md` | Docker Compose flaky test fixes | **Complementary** — 312.12.5 (flaky quarantine policy) |
| `E2E_TEST_UPDATE_PLAN.md` | E2E test update plan | **Covered** — 312.8 (frontend test infrastructure) |
| `E2E_REVIEW_PHASE_4_1.md` | E2E review phase | **Covered** — 312.2.5 (CI workflow audit) |
| `FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md` | Frontend/backend gap fixes | **Complementary** — 312.8 addresses specific gaps |
| `CONCURRENCY_TEST_PLAN.md` | Concurrency test plan | **Covered** — 312.13 (concurrency & idempotency) |
| `COMPREHENSIVE_UPDATE_PLAN_11_2.md` | Update plan | **Superseded** — absorbed into Phase 312 |

### `testreview1/tasks.md` — Phase-by-Phase Coverage

| Testreview1 Phase | Phase 312 Equivalent | Status |
|---|---|---|
| Phase 1 (Test Discovery) | 312.4.1 (testpaths fix) | **Done** |
| Phase 2 (Marker Audit) | 312.2.2 (marker audit) | **Done** |
| Phase 3 (Conftest Consolidation) | 312.3 (conftest consolidation) | **Done** |
| Phase 4 (CI Unification) | 312.7 (CI unification) | **Done** |
| Phase 5 (Factory Consolidation) | 312.2.4 (factory audit) | **Done** |
| Phase 6 (Smoke Tests) | 312.15 (smoke tests) | **Done** |
| Phase 7 (Performance Baseline) | 312.17 (performance baseline) | **Done** |
| Phase 8 (Service Tests) | 312.10 (service-level tests) | **Done** |
| Phase 9 (Frontend Tests) | 312.8 (frontend test infrastructure) | **Done** |
| Phase 10 (CLI/SDK Tests) | 312.9 (CLI & SDK test integration) | **Done** |
| Phase 11 (E2E Tests) | 312.8.3 (E2E batch strategy) | **Done** |
| Phase 12 (Security Tests) | 312.6 (code quality gates) + 312.8.6 (security E2E) | **Done** |
| Phase 13 (Migration Tests) | 312.6 (GATE-10/11/12) | **Done** |
| Phase 14 (i18n Tests) | 312.4 partial (pre-commit checks) | **Complementary** |
| Phase 15 (a11y Tests) | 312.8.1 (a11y config) | **Done** |
| Phase 16 (Documentation) | 312.18 (this subphase) | **In Progress** |

---

## `openspec/changes/testsfix1/` — Coverage Map

| Sibling File | Content | Covered By Phase 312? |
|---|---|---|
| `tasks.md` | Test gap fixes | See below |
| `design.md` | Gap fix design | **Superseded** — Phase 312 provides comprehensive approach |
| `proposal.md` | Fix proposal | **Superseded** — Phase 312 implements the proposals |
| `specs/` | BDD specs | **Complementary** — 312.5 (spec coverage) references these |
| `E2E_FIX_VALIDATION_REPORT.md` | E2E fix validation | **Covered** — 312.8 fixes validated |
| `FRONTEND_BACKEND_GAP_REMEDIATION_PLAN.md` | Frontend/backend gaps | **Covered** — 312.8 addresses |
| `ODH_INFERENCE_SKIP_ROOT_CAUSE_AND_FIX.md` | ODH inference skip fix | **Complementary** — not specifically covered by 312 |

---

## Superseded vs Complementary

### Superseded (13 tasks)
Tasks fully replaced by Phase 312 implementation:
- Test infrastructure audits (testreview1 phases 1-5) → 312.2/3/4
- Docker Compose plans (3 files) → 312.2.7
- E2E coverage plans (2 files) → 312.2.5 / 312.8
- Update plans (2 files) → absorbed

### Complementary (4 tasks)
Tasks that enhance Phase 312 but are not fully replaced:
- i18n tests (testreview1 phase 14) — 312.4 covers pre-commit checks; additional i18n hardening not done
- ODH inference fix (testsfix1) — infrastructure-specific, not covered by 312
- Flaky test fixes (testsfix1) — 312.12.5 provides policy; specific fixes may need additional work
- BDD specs (testsfix1/specs/) — referenced by 312.5 but not implemented

---

## Recommended Actions

1. **Add note to testreview1/tasks.md**: "Phase 312 covers test infrastructure. See docs/test-infrastructure/ for audit documents."
2. **Add note to testsfix1/tasks.md**: "Gap fixes addressed by Phase 312 subphases. See docs/cross-reference-phase-312.md."
3. **Preserve complementary tasks** — i18n, ODH, and specific flaky fixes remain as future work.
