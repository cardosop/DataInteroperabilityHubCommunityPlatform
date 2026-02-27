# Test Scenario Matrix

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-19  
**Status**: Active  
**Task**: Phase 8.2 — Scenario Coverage Matrix; openspec/changes/testsfix1 tasks 8.2.1, 8.2.2

---

## Overview

This document defines **scenario-level** test coverage per feature: **Success**, **Failure** (by HTTP status 400/401/403/404/429), and **Edge** (empty input, max length, special characters). It complements [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) (test types per feature) and [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) (feature → test file mapping). Coverage gaps visible here drive prioritization for failure and edge tests (e.g. Phase 8.4, 8.5).

**Related**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md), [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md), [FEATURES.md](FEATURES.md), [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md). Integration with traceability: [Integration with traceability report](#integration-with-traceability-report) below.

---

## Table of Contents

1. [Column definitions](#column-definitions)
2. [Failure scenarios per journey type (Phase 8.4)](#failure-scenarios-per-journey-type-phase-84)
3. [Edge scenarios per journey type (Phase 8.5)](#edge-scenarios-per-journey-type-phase-85)
4. [Scenario matrix (all features)](#scenario-matrix-all-features)
5. [Coverage gaps summary](#coverage-gaps-summary)
6. [Audit sources](#audit-sources)
7. [Integration with traceability report](#integration-with-traceability-report)

---

## Column definitions

| Column | Meaning | Criteria |
|--------|---------|----------|
| **Feature** | Product feature from [FEATURES.md](FEATURES.md) (29 features). | Same ordering as [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md). |
| **Success** | At least one test that exercises a happy path (2xx) for the feature. | Unit, integration, or E2E test that asserts success (e.g. 200, 201, 204). |
| **Failure (400/401/403/404/429)** | At least one test that asserts an error response for the feature: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, or 429 Too Many Requests. | Explicit assertion on `status_code` or equivalent; not only “may return” but “expect 4xx in this scenario”. |
| **Edge (empty/max/special chars)** | At least one test that exercises edge inputs: empty string/list, max length, or special characters. | Empty payload/field, oversized input, or special chars (e.g. Unicode, SQL-like) that could affect validation or storage. |

**Status legend**: ✅ Covered (explicit tests found in audit); ⏳ Partial (some status codes or edge types missing); ❌ Missing (no explicit scenario tests found).

---

## Failure scenarios per journey type (Phase 8.4)

Per [Phase 8.4](../openspec/changes/testsfix1/tasks.md): each journey should have explicit failure coverage. Failure scenario **types** are defined below; use them when adding or auditing failure tests (validation, auth, forbidden).

| Type | HTTP status | Description | When to use |
|------|-------------|-------------|-------------|
| **Validation** | 400 | Invalid input, missing required fields, format errors, business-rule violations. | Create/update flows (assets, contracts, marketplace, forms). Assert API returns 400 and/or UI shows validation message. |
| **Auth** | 401 | Unauthenticated access: no token, expired token, invalid credentials. | Protected routes and APIs. Assert API returns 401 and/or redirect to login. |
| **Forbidden** | 403 | Authenticated but not permitted: wrong role, missing capability, tenant isolation. | Role- or capability-gated routes (e.g. governance, developer, social). Assert 403 or redirect to /403. |
| **Not found** | 404 | Resource does not exist or not visible (e.g. cross-tenant). | Detail/edit routes with non-existent ID. Assert 404 or error UI. |
| **Rate limit** | 429 | Too many requests. | Login, high-frequency APIs. Assert 429 and optional retry-after. |

**Top 10 journeys (Phase 8.4.2)**  
For these journeys we require **≥2 failure tests** with at least one **validation** (400) and at least one **auth** (401) or **forbidden** (403):

1. JOURNEY-AUTH-001 (First-Time Visitor Registers)
2. JOURNEY-AUTH-002 (User Logs In)
3. JOURNEY-AUTH-003 (User Resets Password)
4. JOURNEY-AUTH-004 (Unauthenticated User Accesses Public Resources)
5. JOURNEY-DPO-001 (Onboard New Asset via Data-First Flow)
6. JOURNEY-DPO-002 (Publish Asset to Marketplace)
7. JOURNEY-DPO-003 (Manage Asset Lifecycle)
8. JOURNEY-DPO-004 (Monitor Asset Quality)
9. JOURNEY-DPO-005 (Configure Data Contracts)
10. JOURNEY-DPO-006 (Manage Marketplace Listings)

**Remaining journeys**: Each must have **≥1 failure test** (validation, auth, forbidden, or 404) so that every journey has explicit failure coverage.

**Implementation**: Use `verifyFailureScenario()` in `frontend/e2e/fixtures/helpers.ts` with `expectedError.status` and `expectedError.urlPattern` when asserting API status; see [TEST_GENERATION_GUIDE](../frontend/e2e/TEST_GENERATION_GUIDE.md) and [TEST_ASSERTION_CONVENTIONS](TEST_ASSERTION_CONVENTIONS.md).

---

## Edge scenarios per journey type (Phase 8.5)

Per [Phase 8.5](../openspec/changes/testsfix1/tasks.md): each journey should have explicit edge coverage. Edge scenario **types** are defined below; use them when adding or auditing edge tests (empty/null, max length, special chars). No mocks; use real backend and real UI.

| Type | Description | When to use | Example |
|------|-------------|-------------|---------|
| **Empty / null** | Empty string, empty list, optional field omitted, empty state UI. | Forms, list pages, optional fields. | Submit with empty required field (HTML5 or API validation); list with zero items shows empty state. |
| **Max length** | Input at or over maximum allowed length (field or API limit). | Text inputs, descriptions, keys. | Name/description at max chars; assert truncation, validation, or error. |
| **Special characters** | Unicode, quotes, SQL-like, HTML, newlines, control chars. | Any user-facing input. | Email with `+`; name with apostrophe; search with `%`; assert sanitization or validation. |
| **Boundary / filter** | First/last page, filter with no results, sort. | List journeys. | Pagination: next/previous, page size; filter returns empty; sort changes order. |

**Top 10 journeys (Phase 8.5.2)**  
For these journeys we require **≥2 edge tests** (from the types above):

1. JOURNEY-AUTH-001 (First-Time Visitor Registers)
2. JOURNEY-AUTH-002 (User Logs In)
3. JOURNEY-AUTH-003 (User Resets Password)
4. JOURNEY-AUTH-004 (Unauthenticated User Accesses Public Resources)
5. JOURNEY-DPO-001 (Onboard New Asset via Data-First Flow)
6. JOURNEY-DPO-002 (Publish Asset to Marketplace)
7. JOURNEY-DPO-003 (Manage Asset Lifecycle)
8. JOURNEY-DPO-004 (Monitor Asset Quality)
9. JOURNEY-DPO-005 (Configure Data Contracts)
10. JOURNEY-DPO-006 (Manage Marketplace Listings)

(Same list as Phase 8.4.)

**List journeys (pagination)**  
Journeys that show paginated lists must have **≥1 pagination test**: assert next/previous or page-size control when the list API supports pagination; or assert empty-state when there are no results. List journeys include: assets list (DPO-001, DPO-003), contracts list (DPO-005), marketplace/listings list (DPO-002, DPO-006), DQ runs list (DPO-004), and other list-based specs under `frontend/e2e/journeys/`.

**Implementation**: Prefer real data and real API; assert UI state (e.g. empty state visible, pagination controls present/disabled, validation message shown). See [TEST_ASSERTION_CONVENTIONS](TEST_ASSERTION_CONVENTIONS.md).

---

## Scenario matrix (all features)

| # | Feature | Success | Failure (400/401/403/404/429) | Edge (empty/max/special chars) |
|---|---------|---------|--------------------------------|----------------------------------|
| 1 | Auth | ✅ | ✅ (401 in test_api_error_handling, auth APIs) | ⏳ (empty token in security tests) |
| 2 | Contracts | ✅ | ✅ (400/401 in test_workflow_security, test_rest_business_rules; 404 tenant isolation) | ✅ (test_api_edge_cases partial update, validation; invalid ODPS in test_enhanced_use_cases) |
| 3 | ODPS | ✅ | ✅ (400 in test_rest_business_rules invalid ODPS) | ✅ (test_enhanced_use_cases edge cases) |
| 4 | Assets | ✅ | ✅ (401/403/404/400 in test_persona_failure_paths, test_rest_business_rules, test_idor) | ⏳ (400 missing required in persona failure) |
| 5 | Datasets | ✅ | ✅ (401/404 in test_persona_failure_paths, test_tenant_isolation; 400 in test_rest_business_rules) | ⏳ |
| 6 | DQ | ✅ | ✅ (401/404/400 in test_persona_failure_paths) | ✅ (empty payload 400 in test_persona_failure_paths) |
| 7 | Compliance | ✅ | ✅ (401/404/400 in test_persona_failure_paths) | ✅ (empty payload 400 in test_persona_failure_paths) |
| 8 | Marketplace | ✅ | ✅ (401/403/404/400/429 in test_persona_failure_paths, test_marketplace_security, test_rest_business_rules) | ✅ (empty config in test_marketplace_security; test_enhanced_use_cases edge) |
| 9 | Governance | ✅ | ✅ (400 in test_rest_business_rules) | ⏳ |
| 10 | Search | ✅ | ⏳ (no explicit 4xx scenario audit) | ⏳ |
| 11 | Observability | ✅ | ⏳ (no explicit 4xx scenario audit for Observability) | ⏳ |
| 12 | Workflows | ✅ | ✅ (401/400 in test_workflow_security) | ⏳ |
| 13 | Lineage | ✅ | ⏳ | ⏳ |
| 14 | Versioning | ✅ | ⏳ | ⏳ |
| 15 | BaaS | ✅ | ⏳ | ⏳ |
| 16 | Integrations | ✅ | ✅ (404 in test_persona_failure_paths invalid connector type) | ⏳ |
| 17 | Jobs | ✅ | ✅ (404 in test_tenant_isolation) | ⏳ |
| 18 | Files | ✅ | ✅ (201/400/404/401/204 in test_file_storage_operations_comprehensive; 400 in test_rest_business_rules) | ⏳ |
| 19 | Semantic | ✅ | ⏳ | ⏳ |
| 20 | AI | ✅ | ⏳ | ⏳ |
| 21 | ML | ✅ | ⏳ | ⏳ |
| 22 | Social | ✅ | ⏳ | ⏳ |
| 23 | Data Mesh | ✅ | ✅ (400 in test_rest_business_rules empty name) | ⏳ |
| 24 | Virtualization | ✅ | ⏳ | ⏳ |
| 25 | Scheduled Ingestion | ✅ | ⏳ (no direct 4xx for ingestion API in audit; test_rest_business_rules has 400 for contract delete when referenced by ingestion) | ⏳ |
| 26 | Scheduled Export | ✅ | ⏳ | ⏳ |
| 27 | Webhooks | ✅ | ✅ (400 in test_persona_failure_paths missing required) | ⏳ |
| 28 | Audit | ✅ | ✅ (401/404/400 in test_persona_failure_paths; 403/404 in test_idor) | ⏳ |
| 29 | Health | ✅ | ✅ (200/404/500/503 in test_health_integration) | ⏳ |

---

## Coverage gaps summary

- **Failure (400/401/403/404/429)**: Features with ⏳ or no explicit 4xx tests in the audit: Search, Observability (partial), Lineage, Versioning, BaaS, Semantic, AI, ML, Social, Virtualization, Scheduled Ingestion, Scheduled Export. **Recommendation**: Add at least one failure scenario (e.g. 401 unauthenticated, 404 not found, 400 validation) per feature; see [Phase 8.4](../openspec/changes/testsfix1/tasks.md) and [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md).
- **Edge (empty/max/special chars)**: Most features have ⏳; only Contracts, ODPS, DQ, Compliance, Marketplace have ✅ from the audit. **Recommendation**: Add edge tests (empty payload, max length, special chars) for top 10 journeys and extend to remaining features; see [Phase 8.5](../openspec/changes/testsfix1/tasks.md).

---

## Audit sources

The matrix was populated from an audit of the following (no mocks/stubs; real assertions):

| Source | Content |
|--------|---------|
| `tests/e2e/test_persona_failure_paths_comprehensive.py` | Explicit 400/401/403/404 tests for Assets, Datasets, DQ, Compliance, Marketplace, Users, Tenants, Integrations, Webhooks, Audit; empty-payload 400 for DQ, Compliance, Order, User, Tenant, Webhook, Audit. |
| `tests/integration/test_api_error_handling.py` | 404, 401, 400 generic. |
| `tests/integration/test_tenant_isolation.py` | 404 for cross-tenant Assets, Contracts, Datasets, Files, Jobs. |
| `tests/integration/test_rest_business_rules_alignment.py` | 400 for Contracts, Assets, Datasets, Marketplace, Files, Governance, Compliance, Data Mesh, Scheduled Ingestion. |
| `tests/integration/test_trust_signals_config_api_comprehensive.py` | 401, 400 for Marketplace trust signals. |
| `tests/e2e/test_workflow_security_business_rules_e2e.py` | 401, 400 for Contracts. |
| `tests/security/test_marketplace_security.py` | 403, 429; empty API key, empty config. |
| `tests/security/test_idor.py` | 403/404 for Assets, Audit. |
| `tests/integration/test_file_storage_operations_comprehensive.py` | 201/400/404/401/204 for Files. |
| `tests/integration/test_health_integration.py` | 200/404/500/503 for Health. |
| `tests/integration/test_api_edge_cases.py` | Edge: Contracts partial update, validation. |
| `tests/e2e/test_enhanced_use_cases_with_odps.py` | Edge: ODPS invalid document, existing contract, Marketplace without ODPS, multilingual. |

Backend and frontend test paths are those referenced in [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md). To refresh the matrix, re-run the audit (grep/script) over `tests/`, `hub/apps/*/tests/`, and `frontend/e2e/` for status-code assertions and edge-case patterns.

---

## Integration with traceability report

- **Traceability document**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) maps Features → Test files, Use Cases → Tests, and User Journeys → Tests. Use it to locate which test files to extend for missing Failure or Edge scenarios.
- **UC/Journey coverage report**: The script `scripts/report_uc_journey_test_coverage.py` produces a report of which use cases and journeys have at least one test and their **scenario coverage** (S/F/E). Run:
  - `python scripts/report_uc_journey_test_coverage.py` (Markdown; scenario column S/F/E)
  - `python scripts/report_uc_journey_test_coverage.py --json` (JSON; scenario_coverage)
  - `python scripts/report_uc_journey_test_coverage.py --ci-mode --output traceability-report.json` (CI artifact; includes scenario_coverage in JSON)
  The report now includes scenario coverage (S/F/E) per UC and journey (Phase 8.8); it complements this matrix (which covers scenario by feature).
- **Cross-reference**: When adding failure or edge tests for a feature, update (1) this matrix (Success/Failure/Edge columns), (2) [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) (feature → test file), and (3) docstrings or markers (e.g. `@pytest.mark.uc`) so `report_uc_journey_test_coverage.py` and traceability stay aligned.
- **Coverage matrix**: [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) remains the source for test *type* coverage (unit, integration, E2E, security, performance) per feature. This document is the source for *scenario* coverage (Success / Failure / Edge) per feature.

---

## Related documents

- [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) — Feature → Test mapping, UC/Journey traceability
- [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md) — Test type coverage per feature
- [FEATURES.md](FEATURES.md) — 29 features and supporting capabilities
- [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) — How to assert status codes and errors
- [openspec/changes/testsfix1/tasks.md](../openspec/changes/testsfix1/tasks.md) — Phase 8.2, 8.4, 8.5 tasks
