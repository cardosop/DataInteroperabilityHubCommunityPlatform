# Test Coverage Expansion Plan

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-22  
**Status**: Draft  
**Purpose**: Phased plan to expand test coverage per [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) gaps — Immediate (performance, security, frontend E2E), Short-term (E2E use cases), Long-term (100% coverage).

**Related**: [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md), [UC_JOURNEY_COVERAGE_GAP_REPORT.md](UC_JOURNEY_COVERAGE_GAP_REPORT.md), [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Immediate Phase](#immediate-phase)
3. [Short-Term Phase](#short-term-phase)
4. [Long-Term Phase](#long-term-phase)
5. [Execution Strategy](#execution-strategy)
6. [Success Criteria](#success-criteria)

---

## Overview

| Phase | Scope | Est. Effort | Target |
|-------|-------|--------------|--------|
| **Immediate** | Performance (16 features), Security (4 features), Frontend E2E (4 personas) | 4–6 weeks | 100% coverage for identified gaps |
| **Short-Term** | E2E tests for ~59 use cases | 8–12 weeks | All use cases have E2E coverage |
| **Long-Term** | 100% feature, use case, journey, persona coverage | Ongoing | Continuous improvement |

**Principles** (from [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md)):
- Real services only (no mocks/stubs except at external boundaries)
- Root-cause fixes only
- TDD, DRY, SOLID, clean code, Django best practices

---

## Immediate Phase

### 1. Performance Tests (16 Features)

**Target**: Add performance test suites for features missing them.

| # | Feature | Location | Critical Endpoints | Notes |
|---|---------|----------|--------------------|-------|
| 1 | Datasets | `hub/apps/datasets/` | List, create, retrieve, update | Follow `tests/performance/test_marketplace_performance.py` pattern |
| 2 | DQ | `hub/apps/dq/` | Runs, profiles, rules | |
| 3 | Compliance | `hub/apps/compliance/` | Runs, policies | |
| 4 | Governance | `hub/apps/governance/` | Policies, retention | |
| 5 | Workflows | `hub/apps/orchestration/` | Flow runs, triggers | |
| 6 | Lineage | `hub/apps/lineage/` or lineage API | Graph queries | |
| 7 | Versioning | `hub/apps/versioning/` | Version list, diff | |
| 8 | Integrations | `hub/apps/integrations/` | Connector CRUD | |
| 9 | AI | `hub/apps/ai/` | Search, schema matching | |
| 10 | ML | `hub/apps/ml/` | Model serving, inference | |
| 11 | Social | `hub/apps/social/` | Communities, feeds, reviews | |
| 12 | Data Mesh | `hub/apps/mesh/` | Domains, topology | |
| 13 | Virtualization | `hub/apps/virtualization/` | Virtual datasets, queries | |
| 14 | Webhooks | `hub/apps/webhooks/` | Webhook delivery | |
| 15 | Audit | `hub/apps/audit/` | Event queries | |
| 16 | Health | `hub/apps/health/` | Health checks | |

**Tasks**:
- [x] Create `tests/performance/test_datasets_performance.py`
- [x] Create `tests/performance/test_dq_performance.py`
- [x] Create `tests/performance/test_compliance_performance.py`
- [x] Create `tests/performance/test_governance_performance.py`
- [x] Create `tests/performance/test_workflows_performance.py`
- [x] Create `tests/performance/test_lineage_performance.py`
- [x] Create `tests/performance/test_versioning_performance.py`
- [x] Create `tests/performance/test_integrations_performance.py`
- [x] Create `tests/performance/test_ai_performance.py`
- [x] Create `tests/performance/test_ml_performance.py`
- [x] Create `tests/performance/test_social_performance.py`
- [x] Create `tests/performance/test_data_mesh_performance.py`
- [x] Create `tests/performance/test_virtualization_performance.py`
- [x] Create `tests/performance/test_webhooks_performance.py`
- [x] Create `tests/performance/test_audit_performance.py`
- [x] Create `tests/performance/test_health_performance.py`
- [x] Add `-m performance` marker to all new tests
- [x] Update [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) Performance column

**Reference**: `tests/performance/test_marketplace_performance.py`, `tests/performance/run_performance_tests.sh`, [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md#performance-tests).

**Phase 1 Status**: ✅ Complete (2026-02-22). All 16 tests pass; run with `pytest tests/performance/ -v -m performance`.

---

### 2. Security Tests (4 Features)

**Target**: Add security coverage for Versioning, AI, ML, Health.

| # | Feature | Location | Scope | Notes |
|---|---------|----------|-------|-------|
| 1 | Versioning | `hub/apps/versioning/` | Auth, tenant isolation, authz | `test_versioning_security.py` exists; validate/expand |
| 2 | AI | `hub/apps/ai/` | Auth, tenant isolation, injection | `test_ai_security.py` exists; validate/expand |
| 3 | ML | `hub/apps/ml/` | Auth, tenant isolation | `test_ml_security.py` exists; validate/expand |
| 4 | Health | `hub/apps/health/` | Public vs protected endpoints | New file |

**Tasks**:
- [x] Audit `tests/security/test_versioning_security.py` — ensure auth, tenant isolation, authz
- [x] Audit `tests/security/test_ai_security.py` — ensure auth, tenant isolation, injection
- [x] Audit `tests/security/test_ml_security.py` — ensure auth, tenant isolation
- [x] Create `tests/security/test_health_security.py` — public endpoints, no sensitive data leakage
- [x] Add `-m security` marker where missing
- [x] Update [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) Security column

**Phase 2 Status**: ✅ Complete (2026-02-22). All 18 tests pass; run with `pytest tests/security/test_versioning_security.py test_ai_security.py test_ml_security.py test_health_security.py -v`.

**Reference**: [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md), [test_security_features.py](tests/security/test_security_features.py).

---

### 3. Frontend E2E (4 Personas)

**Target**: Ensure frontend E2E coverage for Data Scientist, Data Analyst, Community Manager, Data Mesh Domain Owner.

**Current state**: Frontend specs exist under `frontend/e2e/journeys/`:
- `ds/` — JOURNEY-DS-001 … JOURNEY-DS-005
- `da/` — JOURNEY-DA-001 … JOURNEY-DA-004
- `cm/` — JOURNEY-CM-001 … JOURNEY-CM-004
- `dmo/` — JOURNEY-DMO-001 … JOURNEY-DMO-005

**Tasks**:
- [x] Validate all 18 journey specs run and pass (Data Scientist: 5, Data Analyst: 4, Community Manager: 4, Data Mesh Domain Owner: 5)
- [x] Fix any failing or skipped specs
- [ ] Add missing persona-specific routes (e.g. mesh-virtualization-search-ai for DS/DA/DMO)
- [ ] Ensure `npm run test:e2e` includes these personas
- [ ] Update [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) Frontend E2E column for these 4 personas

**Reference**: [frontend/e2e/journeys/](../frontend/e2e/journeys/), [USER_JOURNEYS.md](USER_JOURNEYS.md), [ManualTest/Front/](../ManualTest/Front/).

---

## Short-Term Phase

### E2E Tests for ~59 Use Cases

**Target**: Add backend E2E tests for use cases that lack E2E coverage.

**Use cases without E2E** (from [UC_JOURNEY_COVERAGE_GAP_REPORT.md](UC_JOURNEY_COVERAGE_GAP_REPORT.md)):

| Category | Use Cases | Est. Tests |
|----------|-----------|------------|
| Compliance Officer | UC-CPO-006, UC-CPO-007, UC-CPO-008, UC-CPO-009, UC-CPO-010 | 5 |
| Data Analyst | UC-DA-003, UC-DA-004 | 2 |
| Data Consumer | UC-DC-006, UC-DC-008, UC-DC-011, UC-DC-012, UC-DC-013 | 5 |
| Data Engineer | UC-DE-005, UC-DE-009, UC-DE-010, UC-DE-011, UC-DE-012 | 5 |
| Data Mesh Domain Owner | UC-DMO-001, UC-DMO-002, UC-DMO-003, UC-DMO-005 | 4 |
| Data Product Owner | UC-DPO-002, UC-DPO-010, UC-DPO-014 | 3 |
| Scheduled Export | UC-EXPORT-001, UC-EXPORT-002, UC-EXPORT-003, UC-EXPORT-004 | 4 |
| Governance Advanced | UC-GOV-ADV-002A | 1 |
| Tenant Admin | UC-TA-007, UC-TA-008 | 2 |
| Data Consumer (journeys) | JOURNEY-DC-014, JOURNEY-DC-015 | 2 |

**Prioritization**:
1. **High**: Critical paths (Scheduled Export, Data Consumer, Data Engineer)
2. **Medium**: Compliance Officer, Data Mesh Domain Owner, Data Product Owner
3. **Lower**: Governance Advanced, Tenant Admin

**Tasks**:
- [ ] Create `tests/e2e/test_persona_cpo_use_cases_e2e.py` (UC-CPO-006 … UC-CPO-010)
- [ ] Add UC-DA-003, UC-DA-004 to `tests/e2e/test_persona_da_comprehensive.py` or new file
- [ ] Add UC-DC-006, UC-DC-008, UC-DC-011, UC-DC-012, UC-DC-013 to Data Consumer E2E
- [ ] Add UC-DE-005, UC-DE-009 … UC-DE-012 to Data Engineer E2E
- [ ] Add UC-DMO-001 … UC-DMO-005 to Data Mesh Domain Owner E2E (if not covered)
- [ ] Add UC-DPO-002, UC-DPO-010, UC-DPO-014 to Data Product Owner E2E
- [ ] Create `tests/e2e/test_scheduled_export_use_cases_e2e.py` (UC-EXPORT-001 … 004)
- [ ] Add UC-GOV-ADV-002A, UC-TA-007, UC-TA-008
- [ ] Add JOURNEY-DC-014, JOURNEY-DC-015
- [ ] Update [UC_JOURNEY_COVERAGE_GAP_REPORT.md](UC_JOURNEY_COVERAGE_GAP_REPORT.md) as tests are added

**Reference**: [USE_CASES.md](USE_CASES.md), [tests/e2e/test_persona_*_comprehensive.py](tests/e2e/), [test_new_user_journeys_comprehensive.py](tests/e2e/test_new_user_journeys_comprehensive.py).

---

## Long-Term Phase

### 100% Coverage

**Target**: Achieve complete coverage for all features, use cases, journeys, and personas.

| Dimension | Current | Target | Actions |
|-----------|---------|--------|---------|
| **Features** | 13 complete, 16 partial | 29 complete | Complete performance + security for all partial features |
| **Use Cases** | ~50 with E2E | ~109 with E2E | Complete short-term phase |
| **User Journeys** | 92/96 (4 deferred) | 96/96 when implemented | Un-defer transformation pipeline journeys when API exists |
| **Personas** | 9 complete, 4 partial | 13 complete | Complete frontend E2E for 4 personas |

**Ongoing**:
- [ ] Run full suite regularly; fix failures at root cause
- [ ] Update TEST_COVERAGE_MATRIX after each phase
- [ ] Add CI gates for new test types when stable
- [ ] Document transformation pipeline backlog; un-defer when implemented

---

## Execution Strategy

1. **Batch size**: 2–4 features per sprint for immediate phase; 5–10 use cases per sprint for short-term.
2. **Order**: Performance → Security → Frontend E2E (immediate); then use cases by priority.
3. **Validation**: Run `./scripts/run_phase_12a_backend_suites.sh` (or full suite) after each batch.
4. **Evidence**: Keep `test_reports_comprehensive/{date}/`; update `phase_12a_*_summary.json`.

---

## Success Criteria

| Phase | Done When |
|-------|-----------|
| **Immediate** | All 16 performance suites created and passing; all 4 security gaps addressed; all 4 personas frontend E2E passing |
| **Short-Term** | All ~59 use cases have E2E tests; UC_JOURNEY_COVERAGE_GAP_REPORT shows ✅ for previously ⚠️ items |
| **Long-Term** | TEST_COVERAGE_MATRIX shows 29/29 complete; 109/109 use cases; 96/96 journeys (minus deferred); 13/13 personas |

---

## Related Documents

- [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) — Feature/UC/Journey/Persona matrices
- [UC_JOURNEY_COVERAGE_GAP_REPORT.md](UC_JOURNEY_COVERAGE_GAP_REPORT.md) — Use case → test file mapping
- [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) — Principles and batch strategy
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Commands and run order
- [USER_JOURNEYS.md](USER_JOURNEYS.md) — Journey definitions
- [USE_CASES.md](USE_CASES.md) — Use case definitions
