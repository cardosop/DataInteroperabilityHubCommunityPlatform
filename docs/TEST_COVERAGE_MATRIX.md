# Test Coverage Matrix

**Document Version**: 1.5.0
**Last Updated**: 2026-03-06
**Status**: ✅ Active
**Task**: Phase 1.2 - Test Coverage Matrix Documentation; Phase 6 Gap Remediation (traceability and supporting capabilities); gapfix1 Phase 2.5 (traceability and gapfix1 section); Task 6.8.2 UC/journey/persona coverage status

---

## Table of Contents

1. [Overview](#overview)
2. [Feature Coverage Matrix](#feature-coverage-matrix) — includes [Supporting Capabilities](#supporting-capabilities-traceability) and [Gap Remediation Coverage](#gap-remediation-coverage)
3. [Use Case Coverage Matrix](#use-case-coverage-matrix)
4. [User Journey Coverage Matrix](#user-journey-coverage-matrix)
5. [Persona Coverage Matrix](#persona-coverage-matrix)
6. [UC/Journey/Persona E2E Coverage (Task 6.7)](#ucjourney-persona-e2e-coverage-task-67)
7. [Coverage Status Summary](#coverage-status-summary)
8. [Coverage Gaps and Recommendations](#coverage-gaps-and-recommendations)

---

## Overview

This document provides comprehensive test coverage matrices for the Data Interoperability Hub platform, showing test coverage across all features, use cases, user journeys, and personas.

### Coverage Dimensions

- **Features**: 29 product features (Auth through Health, as listed in [FEATURES.md](FEATURES.md)). Supporting capabilities (Notifications, Billing, Platform, Tenants, Users, Analytics, Events) are documented separately and covered via the features that use them; see [Supporting Capabilities (Traceability)](#supporting-capabilities-traceability) and [Gap Remediation Coverage](#gap-remediation-coverage).
- **Use Cases**: ~109 use cases
- **User Journeys**: 96 journeys
- **Personas**: 13 personas

### Test Types

- **Unit Tests**: Individual component tests (< 1 second per test)
- **Integration Tests**: Component interaction tests (5-30 seconds per test)
- **E2E Tests**: Complete user journey tests (30-300 seconds per test)
- **Security Tests**: Authentication, authorization, vulnerability tests (10-60 seconds per test)
- **Performance Tests**: Load, stress, endurance tests (5-60 minutes per test suite)

### Status Indicators

- ✅ **Complete**: Full coverage with all test types
- ⏳ **Partial**: Coverage exists but needs improvement
- ❌ **Missing**: No coverage or minimal coverage

---

## Feature Coverage Matrix

### All 29 Features

| # | Feature | Unit Tests | Integration Tests | E2E Tests | Security Tests | Performance Tests | Overall Status |
|---|---------|-----------|------------------|----------|----------------|-------------------|----------------|
| 1 | Auth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 2 | Contracts | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 3 | ODPS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 4 | Assets | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 5 | Datasets | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 6 | DQ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 7 | Compliance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 8 | Marketplace | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 9 | Governance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 10 | Search | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 11 | Observability | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 12 | Workflows | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 13 | Lineage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 14 | Versioning | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 15 | BaaS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 16 | Integrations | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 17 | Jobs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 18 | Files | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 19 | Semantic | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 20 | AI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 21 | ML | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 22 | Social | ✅ | ✅ | ✅ | ⏳ | ✅ | ⏳ Partial |
| 23 | Data Mesh | ✅ | ✅ | ✅ | ⏳ | ✅ | ⏳ Partial |
| 24 | Virtualization | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 25 | Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 26 | Scheduled Export | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 27 | Webhooks | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 28 | Audit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| 29 | Health | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Complete |

### Feature Coverage Statistics

- **Complete Coverage**: 27 features (93%)
- **Partial Coverage**: 2 features (7%)
- **Missing Coverage**: 0 features (0%)

### Resource Pickers (UX)

**Coverage**: Searchable pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker) for selecting assets, contracts, datasets, files. Unit: 102 (pickers + picker-using pages). Backend list API: 51 tests. Integration: `picker-form-api.integration.test.ts`. E2E: `odps-asset-link`, `asset-attach-contract-dataset`, `dq-compliance-access-request`, `scheduled-export-retention-odps-link`, `dataset-edit`, `picker-a11y`. **Run**: `./scripts/run_resource_picker_tests.sh`. See [TEST_TRACEABILITY.md — Resource Pickers](TEST_TRACEABILITY.md#resource-pickers-ux).

---

### Supporting Capabilities (Traceability)

Supporting capabilities (Notifications, Billing, Platform, Tenants, Users, Analytics, Events) are documented in [FEATURES.md](FEATURES.md#supporting-capabilities). They are not standalone product features; coverage is via the features that use them (Auth, BaaS, Marketplace, Governance, Audit, Webhooks, etc.). See [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#supporting-capabilities) for the mapping. **Platform app** (`hub/apps/platform/`): dedicated minimal unit tests in `hub/apps/platform/tests/test_views.py` (permission enforcement for platform tenant and user endpoints; Gap #2, task 1.5). No tests-by-design exemption; the app contains view-layer logic and delegates to tenants/gdpr services.

### Gap Remediation Coverage

Gap Remediation Plan phases (see [openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)) are reflected in this matrix as follows:

| Phase | Scope | Coverage in this matrix |
|-------|--------|-------------------------|
| 0 | Doc-only fixes (Versioning/Workflows/Observability notes; Supporting capabilities; transformation deferred) | Supporting capabilities table above; 29-feature list unchanged |
| 1 | Observability lineage API | Observability feature row (integration + lineage tests) |
| 2 | Versioning API | Versioning feature row (integration tests: `hub/apps/versioning/tests/`) |
| 3 | Workflows API | Workflows feature row (integration tests: `hub/apps/orchestration/tests/test_workflows_api_integration.py`) |
| 4 | Data preview & trust signals | Marketplace feature row (preview: `hub/apps/marketplace/tests/test_preview.py`; trust signals config API: `tests/integration/test_trust_signals_config_api_comprehensive.py`) |
| 5 | Transformation pipeline | Deferred; no implementation; deferred journeys/use cases in [USER_JOURNEYS.md](USER_JOURNEYS.md) / [USE_CASES.md](USE_CASES.md) |
| 6 | Feature list & traceability | This section; [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#gap-remediation-traceability) |
| **gapfix1** | Full Phase 12A-style test run, evidence collection, test summary report, sign-off | [TEST_TRACEABILITY.md — Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off); Phase 16 GR-7 (16.1–16.3) in [testreview1/tasks.md](../openspec/changes/testreview1/tasks.md); evidence layout `test_reports_comprehensive/{date}/`; report script `scripts/generate_test_summary_report.sh` |

**Gap implementation plan (gapfix1)** — Phase 12A execution, evidence layout, test summary report, and sign-off are defined and linked as follows:

- **Phase 12A execution**: Backend: `scripts/run_phase_12a_backend_suites.sh`. Full suite: `scripts/run_phase_12a_full_suites.sh` (backend → frontend unit/E2E → security, performance, concurrency, regression). Commands: [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md).
- **Evidence layout**: `test_reports_comprehensive/{date}/` with subdirs: unit, integration, e2e, security, performance, concurrency, regression, frontend-unit, frontend-e2e; summaries: `phase_12a_1_summary.json`, `phase_12a_3_summary.json`. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md).
- **Test summary report**: Generated by `scripts/generate_test_summary_report.sh` (gapfix1 Phase 7.4); includes pass/fail, duration, coverage, evidence links. Template: [TEST_SUMMARY_REPORT_TEMPLATE.md](TEST_SUMMARY_REPORT_TEMPLATE.md).
- **Sign-off**: [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md); Phase 16 (GR-7, 16.1–16.3) in [testreview1/tasks.md — Phase 16](../openspec/changes/testreview1/tasks.md#16-phase-16--gap-remediation-plan-data-interoperability-hub).
- **Links**: This change: [gapfix1 tasks](../openspec/changes/gapfix1/tasks.md); [openspec/changes/gapfix1](../openspec/changes/gapfix1). Full traceability: [TEST_TRACEABILITY.md — Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off).
- **Features covered by full test run** (appear in test summary report by feature/category): **(1) Scheduled Export** (feature #26; [FEATURES.md](FEATURES.md#scheduled-export); UC-EXPORT-001–004, JOURNEY-EXPORT-001–002). **(2) Trust signals config API** (Marketplace Phase 4; planned or implemented). **(3) §11→Phase 16** (GR-7 / 16.1–16.3: full run, report, sign-off).

**Scheduled Export and trust signals**: Scheduled Export (feature row 26) and trust signals config API (Marketplace, Phase 4) are fully traced in [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) (Feature → Test, Use Case, User Journey). See [Scheduled Export](#26-scheduled-export--complete) below and [TEST_TRACEABILITY.md — Scheduled Export](TEST_TRACEABILITY.md#scheduled-export), [Marketplace / trust signals](TEST_TRACEABILITY.md#marketplace).

**Phase 28.2 — Phases 10–19 (P1/P2) Test Coverage** (Task 28.2.2):

| Phase | Feature | Unit | Integration | E2E | Run Script |
|-------|---------|------|-------------|-----|------------|
| 10 | Admin user edit | `hub/apps/users/tests/test_views.py`, `test_admin_user_edit.py` (PUT/PATCH /api/v1/users/{id}/) | — | `JOURNEY-TA-002.spec.ts` (Manage Users; /admin), `admin-audit-settings-routes.spec.ts` (/admin; PA-009 Manage System Users) | `run_phase10_tests.sh` |
| 11 | Trust signals config | `test_tenant_me_views`, `test_services` | `test_trust_signals_config_api_comprehensive` | `JOURNEY-TA-TENANT-SETTINGS` (Phase 11) | `run_phase11_tests.sh` |
| 12 | Versioning config | `test_tenant_me_views`, `test_services`, `test_views` (datasets) | — | `JOURNEY-TA-TENANT-SETTINGS` (Phase 12) | `run_phase12_tests.sh` |
| 13 | GDPR export/erasure | `test_gdpr_views`, `test_gdpr_services` | `test_erasure_workflow_integration` | `JOURNEY-AUTH-PRIVACY` | `run_phase13_tests.sh` |
| 14 | Workflows config | `test_tenant_me_views`, `test_services`, `test_tenant_config_serializers`, `test_workflows_api_integration` | — | `JOURNEY-TA-TENANT-SETTINGS` (Phase 14) | `run_phase14_tests.sh` |
| 15 | Platform admin | `hub/apps/platform/tests/test_views`, `hub/apps/tenants/tests/test_views` | — | `JOURNEY-PA-015` | `run_phase15_tests.sh` |
| 16–19 | Tenant onboarding, change plan, cost tracking, gap docs | Per phase scripts | Per phase | Per phase | `run_phase16_tests.sh`, etc. |

**Unified run**: `./scripts/run_phase28_2_tests.sh` (Phases 11–15 backend + E2E). See [TEST_TRACEABILITY.md — useronboardfix Gap Coverage](TEST_TRACEABILITY.md#useronboardfix-gap-coverage-phases-7-17) (Phase 28.2 table).

Full phase-to-test mapping: [TEST_TRACEABILITY.md — Gap Remediation Traceability](TEST_TRACEABILITY.md#gap-remediation-traceability).

### Feature Coverage Details

#### 1. Auth ✅ Complete

**Unit Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Login, logout, token refresh
- `hub/apps/auth/tests/test_authorization.py` - Permission checks, RBAC
- `hub/apps/auth/tests/test_sessions.py` - Session management
- `hub/apps/auth/tests/test_register_me.py` - User registration
- `hub/apps/auth/tests/test_middleware.py` - Auth middleware

**Integration Tests**:
- `tests/integration/test_tenant_isolation.py` - Tenant isolation
- `tests/integration/test_auth_apis_comprehensive.py` - Auth API endpoints
- `tests/integration/test_api_endpoints_comprehensive.py` - API endpoints

**E2E Tests**:
- `tests/e2e/test_multi_tenant_isolation.py` - Multi-tenant isolation
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access

**Security Tests**:
- `tests/security/test_allowany_public_endpoints.py` - Public endpoints
- `tests/security/test_security_features.py` - Security features

**Performance Tests**:
- `tests/performance/locust_api_endpoints_availability.py` - Auth endpoints

#### 2. Contracts ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_views.py` - Contract CRUD
- `hub/apps/contracts/tests/test_services.py` - Contract services
- `hub/apps/contracts/tests/test_validation.py` - Contract validation
- `hub/apps/contracts/tests/test_odps_normalizer.py` - ODPS normalization
- `hub/apps/contracts/tests/test_ref_resolver.py` - Reference resolution

**Integration Tests**:
- `tests/integration/test_contract_apis_comprehensive.py` - Contract API endpoints
- `tests/integration/test_contract_management_original_use_cases_comprehensive.py` - Contract workflows
- `hub/apps/contracts/tests/test_lineage_service.py` - Lineage integration

**E2E Tests**:
- `tests/e2e/test_contract_first_comprehensive.py` - Contract-first flow
- `tests/e2e/test_contract_only_comprehensive.py` - Contract-only flow
- `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts` - Contract creation

**Security Tests**:
- `hub/apps/contracts/tests/security/test_ref_resolver_security.py` - Security
- `tests/security/penetration_test_odps_ref_resolver.py` - Penetration testing

**Performance Tests**:
- `tests/performance/locust_odps_ref_resolution.py` - Ref resolution performance

#### 3. ODPS ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py` - ODPS generation
- `hub/apps/contracts/tests/test_odps_normalizer.py` - ODPS normalization
- `hub/apps/contracts/tests/test_odps_metrics.py` - ODPS metrics

**Integration Tests**:
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation
- `hub/apps/orchestration/tests/test_odps_workflow_events.py` - Workflow events

**E2E Tests**:
- `tests/e2e/test_odps_journeys_comprehensive.py` - ODPS journeys
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - ODPS routes

**Security Tests**:
- `tests/security/penetration_test_odps_ref_resolver.py` - Security testing

**Performance Tests**:
- `tests/performance/locust_odps_ingestion.py` - ODPS ingestion performance
- `tests/performance/test_odps_export_performance.py` - Export performance

#### 4. Assets ✅ Complete

**Unit Tests**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset CRUD
- `hub/apps/assets/tests/test_data_first_asset_api.py` - Data-first API (POST /assets/data-first/)
- `hub/apps/assets/tests/test_services.py` - Asset services
- `hub/apps/assets/tests/test_asset_relationships.py` - Relationships
- `hub/apps/assets/tests/test_health_score.py` - Health score

**Integration Tests**:
- `tests/integration/test_asset_apis_comprehensive.py` - Asset API endpoints
- `tests/integration/test_asset_management_original_use_cases_comprehensive.py` - Asset workflows
- `tests/integration/test_cross_service_integration_comprehensive.py` - Service interactions
- `tests/integration/test_data_first_asset_flow.py` - Data-first flow (asset+dataset+contract)

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation, "I have data" redirect
- `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts` - Asset activation
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)

**Security Tests**:
- `tests/security/test_security_features.py` - Asset security
- `tests/security/test_data_first_asset_idor.py` - Data-first IDOR (cross-tenant file_id)

**Performance Tests**:
- `tests/performance/locust_api_endpoints_availability.py` - Asset endpoints

#### 5. Datasets ✅ Complete

**Unit Tests**:
- `hub/apps/datasets/tests/test_views.py` - Dataset views
- `hub/apps/datasets/tests/test_services.py` - Dataset services

**Integration Tests**:
- `tests/integration/test_dataset_apis_comprehensive.py` - Dataset API endpoints
- `tests/integration/test_database_operations_comprehensive.py` - Dataset workflows

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)
- `frontend/e2e/use-cases/ux/dataset-edit.spec.ts` - Dataset edit, link to asset (Phase 29.66.15)
- `frontend/e2e/use-cases/ux/asset-dataset-flow.spec.ts` - Asset → dataset → DQ flow (Phase 29.66.15)

**Security Tests**:
- `tests/security/test_security_features.py` - Dataset security

**Performance Tests**:
- `tests/performance/test_datasets_performance.py` - Datasets list P95 latency

#### 6. DQ ✅ Complete

**Unit Tests**:
- `hub/apps/dq/tests/test_views.py` - DQ views
- `hub/apps/dq/tests/test_service_client.py` - DQ service client

**Integration Tests**:
- `tests/integration/test_dq_apis_comprehensive.py` - DQ API endpoints
- `tests/integration/test_cross_service_integration_comprehensive.py` - DQ workflows

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - DQ checks in data-first flow
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - DQ routes

**Security Tests**:
- `tests/security/test_security_features.py` - DQ security

**Performance Tests**:
- `tests/performance/test_dq_performance.py` - DQ runs list P95 latency

#### 7. Compliance ✅ Complete

**Unit Tests**:
- `hub/apps/compliance/tests/test_views.py` - Compliance views
- `hub/apps/compliance/tests/test_services.py` - Compliance services

**Integration Tests**:
- `tests/integration/test_compliance_apis_comprehensive.py` - Compliance API endpoints
- `tests/integration/test_compliance_original_use_cases_comprehensive.py` - Compliance workflows

**E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Compliance journeys
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - Compliance routes

**Security Tests**:
- `tests/security/test_security_features.py` - Compliance security

**Performance Tests**:
- `tests/performance/test_compliance_performance.py` - Compliance runs list P95 latency

#### 8. Marketplace ✅ Complete

**Unit Tests**:
- `hub/apps/marketplace/tests/test_views.py` - Marketplace views
- `hub/apps/marketplace/tests/test_services.py` - Marketplace services
- `hub/apps/marketplace/tests/test_kyc_enforcement.py` - KYC enforcement

**Integration Tests**:
- `tests/integration/test_marketplace_integration.py` - Marketplace integration
- `tests/integration/test_trust_signals_config_api_comprehensive.py` - Trust signals config API (CRUD, tenant isolation)

**E2E Tests**:
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_marketplace_purchase_flow.py` - Purchase flow
- `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts` - Marketplace routes

**Security Tests**:
- `tests/security/test_marketplace_security.py` - Marketplace security

**Performance Tests**:
- `tests/performance/test_marketplace_performance.py` - Marketplace performance

#### 9. Governance ✅ Complete

**Unit Tests**:
- `hub/apps/governance/tests/test_access_request_views.py` - Access requests
- `hub/apps/governance/tests/test_retention_service.py` - Retention service

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Governance workflows

**E2E Tests**:
- `tests/e2e/test_governance_e2e.py` - Governance E2E
- `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts` - Retention CRUD

**Security Tests**:
- `tests/security/test_security_features.py` - Governance security

**Performance Tests**:
- `tests/performance/test_governance_performance.py` - Access requests list P95 latency

#### 10. Search ✅ Complete

**Unit Tests**:
- `hub/apps/search/tests/test_views.py` - Search views
- `hub/apps/search/tests/test_search_engine.py` - Search engine
- `hub/apps/search/tests/test_indexing.py` - Indexing

**Integration Tests**:
- `tests/integration/test_search_apis_comprehensive.py` - Search API endpoints
- `tests/integration/test_api_client_usage_search.py` - Search integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Search in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search routes

**Security Tests**:
- `tests/security/test_security_features.py` - Search security

**Performance Tests**:
- `tests/performance/test_search_performance.py` - Search performance

#### 11. Observability ✅ Complete

**Unit Tests**:
- `hub/apps/observability/tests/test_otel_metrics.py` - OpenTelemetry metrics
- `hub/apps/observability/tests/test_metrics.py` - Metrics

**Integration Tests**:
- `tests/integration/test_monitoring_infrastructure.py` - Monitoring infrastructure

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Observability in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Observability security

**Performance Tests**:
- `tests/performance/test_otel_metrics_performance.py` - Metrics performance

#### 12. Workflows ✅ Complete

**Unit Tests**:
- `hub/apps/orchestration/tests/test_workflow_engine.py` - Workflow engine
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Workflow integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Workflows in journeys
- `tests/e2e/test_workflow_user_journey_integration_e2e.py` - Workflow journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Workflow security

**Performance Tests**:
- `tests/performance/test_workflows_performance.py` - Workflows list P95 latency

#### 13. Lineage ✅ Complete

**Unit Tests**:
- `hub/apps/contracts/tests/test_lineage_service.py` - Lineage service
- `hub/apps/contracts/tests/test_lineage_traversal.py` - Lineage traversal
- `hub/apps/contracts/tests/test_lineage_visualization.py` - Lineage visualization

**Integration Tests**:
- `tests/integration/test_lineage_service_comprehensive_validation.py` - Lineage integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Lineage in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Lineage security

**Performance Tests**:
- `tests/performance/test_lineage_performance.py` - Lineage visualization P95 latency

#### 14. Versioning ✅ Complete

**Unit Tests**:
- `hub/apps/datasets/tests/test_versioning.py` - Dataset versioning

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Versioning integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Versioning in journeys

**Security Tests**:
- `tests/security/test_versioning_security.py` - Auth (401), tenant isolation (list, retrieve, compare)

**Performance Tests**:
- `tests/performance/test_versioning_performance.py` - Versions list P95 latency

#### 15. BaaS ✅ Complete

**Unit Tests**:
- `hub/apps/baas/tests/test_developer_portal.py` - Developer portal

**Integration Tests**:
- `hub/apps/baas/tests/test_integration.py` - BaaS integration
- `tests/integration/test_cross_service_integration_comprehensive.py` - BaaS service integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - BaaS in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - BaaS security

**Performance Tests**:
- `tests/performance/test_baas_cli_sdk_performance.py` - BaaS performance

#### 16. Integrations ✅ Complete

**Unit Tests**:
- `hub/apps/integrations/tests/test_views.py` - Integration views
- `hub/apps/integrations/tests/test_services.py` - Integration services
- `hub/apps/integrations/tests/test_gcp_marketplace_connector.py` - GCP connector

**Integration Tests**:
- `tests/integration/test_integrations.py` - Integration tests
- `hub/apps/integrations/tests/test_services_integration.py` - Service integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Integrations in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integration routes

**Security Tests**:
- `hub/apps/integrations/tests/test_gcp_marketplace_connector_security.py` - Connector security

**Performance Tests**:
- `tests/performance/test_integrations_performance.py` - Marketplace connections list P95 latency

#### 17. Jobs ✅ Complete

**Unit Tests**:
- `hub/apps/jobs/tests/test_job_creation_processing.py` - Job creation
- `hub/apps/jobs/tests/test_job_processors.py` - Job processors
- `hub/apps/jobs/tests/test_scheduled_ingestion_job.py` - Scheduled ingestion jobs

**Integration Tests**:
- `tests/integration/test_job_queue.py` - Job queue

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Jobs in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Job routes

**Security Tests**:
- `tests/security/test_security_features.py` - Job security

**Performance Tests**:
- `tests/performance/locust_job_queue_throughput.py` - Job queue performance

#### 18. Files ✅ Complete

**Unit Tests**:
- `hub/apps/files/tests/test_views.py` - File views
- `hub/apps/files/tests/test_services.py` - File services
- `hub/apps/files/tests/test_storage.py` - File storage

**Integration Tests**:
- `tests/integration/test_file_storage.py` - File storage integration

**E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - File upload in data-first flow
- `frontend/e2e/journeys/dpo/file-upload-flow.spec.ts` - File upload flow
- `frontend/e2e/use-cases/ux/files-upload.spec.ts` - Files page upload (Phase 29.66.15)

**Security Tests**:
- `tests/security/test_security_features.py` - File security

**Performance Tests**:
- `tests/performance/locust_file_upload_download.py` - File upload/download performance

#### 19. Semantic ✅ Complete

**Unit Tests**:
- `hub/apps/semantic/tests/test_models.py` - Semantic models
- `hub/apps/semantic/tests/test_uri_validators.py` - URI validators
- `hub/apps/semantic/tests/test_external_resource_sparql.py` - SPARQL endpoints

**Integration Tests**:
- `tests/integration/test_odps_semantic_layer_validation.py` - Semantic layer validation
- `tests/integration/test_normalization_rdf_flow.py` - Semantic RDF flow

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Semantic in journeys

**Security Tests**:
- `tests/security/test_security_features.py` - Semantic security

**Performance Tests**:
- `tests/performance/test_semantic_performance.py` - Semantic performance

#### 20. AI ✅ Complete

**Unit Tests**:
- `hub/apps/ai/tests/test_views.py` - AI views
- `hub/apps/ai/tests/test_llm_client.py` - LLM client

**Integration Tests**:
- `tests/integration/test_ai_ml_new_use_cases_comprehensive.py` - AI/ML integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - AI in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - AI routes

**Security Tests**:
- `tests/security/test_ai_security.py` - Auth (401), tenant isolation for natural-language search

**Performance Tests**:
- `tests/performance/test_ai_performance.py` - AI search P95 latency

#### 21. ML ✅ Complete

**Unit Tests**:
- `hub/apps/ml/tests/test_views.py` - ML views

**Integration Tests**:
- `tests/integration/test_ai_ml_new_use_cases_comprehensive.py` - ML integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - ML in journeys

**Security Tests**:
- `tests/security/test_ml_security.py` - Auth (401), tenant isolation for models list/retrieve

**Performance Tests**:
- `tests/performance/test_ml_performance.py` - ML models list P95 latency

#### 22. Social ⏳ Partial

**Unit Tests**:
- `hub/apps/social/tests/test_views.py` - Social views
- `hub/apps/social/tests/test_social_service.py` - Social service

**Integration Tests**:
- `hub/apps/social/tests/test_social_api_integration.py` - Social API integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Social in journeys
- `frontend/e2e/features/social.spec.ts` - Communities route, /social redirect to /communities, asset Community section (Phase 27.1–27.3)
- `frontend/e2e/journeys/dc/JOURNEY-DC-008.spec.ts`, `JOURNEY-DC-009.spec.ts` - Rate/review on asset page
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-009.spec.ts`, `JOURNEY-DPO-011.spec.ts`, `JOURNEY-DPO-012.spec.ts` - Asset Community section, data stewards, join community
- `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` through `JOURNEY-CM-004.spec.ts` - Community Manager journeys
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - /communities route

**Social embed (Phase 27)**: /social redirects to /communities; ratings, reviews, Community section on asset detail page (`/assets/:id`). Run: `./scripts/run_phase28_5_tests.sh`.

**Security Tests**:
- ⏳ Missing security tests for social

**Performance Tests**:
- `tests/performance/test_social_performance.py` - Social communities list P95 latency

#### 23. Data Mesh ⏳ Partial

**Unit Tests**:
- `hub/apps/mesh/tests/test_views.py` - Data mesh views
- `hub/apps/mesh/tests/test_services.py` - Data mesh services

**Integration Tests**:
- `tests/integration/test_data_mesh_new_use_cases_comprehensive.py` - Data mesh integration

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Data mesh in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Data mesh routes

**Security Tests**:
- ⏳ Missing security tests for data mesh

**Performance Tests**:
- `tests/performance/test_data_mesh_performance.py` - Mesh domains list P95 latency

#### 24. Virtualization ✅ Complete

**Unit Tests**:
- `hub/apps/virtualization/tests/test_views.py` - Virtualization views
- `hub/apps/virtualization/tests/test_services.py` - Virtualization services (incl. VirtualizationServiceODBCTest: host_only, database_only, connection_string_empty config validation)
- `hub/apps/virtualization/tests/test_execute_query.py` - Query execution

**Integration Tests**:
- `hub/apps/virtualization/tests/test_execute_query_integration.py` - Query integration
- `hub/apps/virtualization/tests/test_real_source_integration.py` - Real PostgreSQL, ODBC (host+database, connection_string), REST, SPARQL (Phase 20, 28.4.1)
- `hub/apps/virtualization/tests/test_virtualization_real_federated_e2e.py` - Federated E2E (Phase 21)

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Virtualization in journeys
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Virtualization routes
- `frontend/e2e/phase6-mesh-virtualization.spec.ts` - ODBC create via UI form (Host+Database), execute query (Phase 28.4.2)

**ODBC (Phase 28.4)**: Unit (config validation), integration (test_odbc_execute_against_hub_postgresql, test_odbc_execute_connection_string_mode), E2E (phase6-mesh-virtualization.spec.ts). Run: `./scripts/run_phase25_odbc_tests.sh`; E2E: `./scripts/e2e-detect-api.sh e2e/phase6-mesh-virtualization.spec.ts -g "ODBC"`.

**Security Tests**:
- `hub/apps/virtualization/tests/test_security.py` - Virtualization security

**Performance Tests**:
- `tests/performance/test_virtualization_performance.py` - Virtual datasets list P95 latency

#### 25. Scheduled Ingestion ✅ Complete

**Unit Tests**:
- `hub/apps/scheduled_ingestion/tests/test_views.py` - Scheduled ingestion views
- `hub/apps/scheduled_ingestion/tests/test_services.py` - Scheduled ingestion services
- `hub/apps/scheduled_ingestion/tests/test_ingestion.py` - Ingestion logic

**Integration Tests**:
- `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py` - Prefect integration
- `tests/integration/test_scheduled_ingestion_integration.py` - Scheduled ingestion integration

**E2E Tests**:
- `tests/e2e/test_scheduled_ingestion.py` - Scheduled ingestion E2E
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts` - Scheduled ingestion journey

**Security Tests**:
- `tests/security/test_security_features.py` - Scheduled ingestion security

**Performance Tests**:
- `tests/performance/test_scheduled_ingestion_performance.py` - Scheduled ingestion performance

#### 26. Scheduled Export ✅ Complete

**Behaviour covered**: List scheduled exports (tenant-scoped), filter by status (`?status=ACTIVE`), tenant isolation (list, retrieve, runs), CRUD, manual trigger, internal worker API. See USE_CASES.md UC-EXPORT-001–004.

**Unit Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Scheduled export views (list, filter by status, tenant isolation, CRUD, trigger, runs)
- `hub/apps/scheduled_export/tests/test_services.py` - Scheduled export services
- `hub/apps/scheduled_export/tests/test_models.py` - Scheduled export models

**Integration Tests**:
- `tests/integration/test_scheduled_export_apis_comprehensive.py` - Scheduled export APIs (CRUD, list and filter by status, tenant isolation, plan limits)

**Frontend Unit Tests**:
- `frontend/src/features/scheduledExport/services/scheduledExportService.test.ts` - Service (real; axios mocked)
- `frontend/src/features/scheduledExport/hooks/useScheduledExport.test.tsx` - Hooks (real; axios mocked)
- `frontend/src/features/scheduledExport/components/ScheduledExportListPage.test.tsx` - List page component

**E2E Tests**:
- `tests/e2e/test_scheduled_export.py` - Scheduled export E2E
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export journey

**Security Tests**:
- `tests/security/test_security_features.py` - Scheduled export security

**Performance Tests**:
- `tests/performance/test_scheduled_export_performance.py` - Scheduled export performance

#### 27. Webhooks ⏳ Partial

**Unit Tests**:
- `hub/apps/webhooks/tests/test_webhook_service.py` - Webhook service
- `hub/apps/webhooks/tests/test_webhook_api_integration.py` - Webhook API integration

**Integration Tests**:
- `tests/integration/run_webhook_payloads_tests.py` - Webhook payloads
- `tests/integration/test_webhook_payloads_and_events_search.py` - Webhook events

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Webhooks in journeys
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Webhook routes

**Security Tests**:
- `tests/security/test_security_features.py` - Webhook security

**Performance Tests**:
- `tests/performance/test_webhooks_performance.py` - Webhooks list P95 latency

#### 28. Audit ✅ Complete

**Unit Tests**:
- `hub/apps/audit/tests/test_audit_event_querying.py` - Audit event querying
- `hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py` - ODPS audit validation
- `hub/apps/audit/tests/test_views.py` - Audit views

**Integration Tests**:
- `tests/integration/test_cross_service_integration_comprehensive.py` - Audit integration

**E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Audit journeys
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit routes

**Security Tests**:
- `tests/security/test_security_features.py` - Audit security

**Performance Tests**:
- `tests/performance/test_audit_performance.py` - Audit events list P95 latency

#### 29. Health ✅ Complete

**Unit Tests**:
- `hub/apps/health/tests/test_views.py` - Health views
- `hub/apps/health/tests/test_services.py` - Health services

**Integration Tests**:
- `tests/integration/test_service_availability_comprehensive.py` - Health and service availability

**E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Health in journeys

**Security Tests**:
- `tests/security/test_health_security.py` - Public endpoints; no sensitive data in /health/, /health/live/, /health/circuit-breakers/

**Performance Tests**:
- `tests/performance/test_health_performance.py` - Health check P95 latency

---

## Use Case Coverage Matrix

### Use Case Categories

| Category | Total Use Cases | Unit Tests | Integration Tests | E2E Tests | Overall Status |
|----------|----------------|-----------|------------------|----------|----------------|
| Authentication & Access | 4 | ✅ | ✅ | ✅ | ✅ Complete |
| Asset Management | ~8 | ✅ | ✅ | ✅ | ✅ Complete |
| Contract Management | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Data Quality | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Compliance | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Marketplace | ~8 | ✅ | ✅ | ✅ | ✅ Complete |
| AI/ML | ~10 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Social Features | ~6 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Data Mesh | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Virtualization | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| Advanced Marketplace | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Advanced Governance | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Advanced Observability | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Integration Ecosystem | ~5 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Developer Experience | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Transformation | ~8 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Lineage | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Versioning | ~3 | ✅ | ✅ | ⏳ | ⏳ Partial |
| BaaS | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| ODH Integration | ~4 | ✅ | ✅ | ⏳ | ⏳ Partial |
| ODPS | ~6 | ✅ | ✅ | ✅ | ✅ Complete |
| Semantic | ~4 | ✅ | ✅ | ✅ | ✅ Complete |
| Scheduled Ingestion | ~3 | ✅ | ✅ | ✅ | ✅ Complete |
| Webhooks | ~3 | ✅ | ✅ | ⏳ | ⏳ Partial |
| Audit | ~3 | ✅ | ✅ | ✅ | ✅ Complete |

**Total Use Cases**: ~109

### Use Case Coverage Statistics

- **Complete Coverage**: ~50 use cases (46%)
- **Partial Coverage**: ~59 use cases (54%)
- **Missing Coverage**: 0 use cases (0%)

### Detailed Use Case Coverage

#### Authentication & Access Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AUTH-001 | User Registers | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-002 | User Logs In | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-003 | User Resets Password | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUTH-005 | User Switches Active Tenant | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/auth/tests/test_register_me.py`, `hub/apps/auth/tests/test_authentication.py`, `hub/apps/auth/tests/test_authorization.py`, `hub/apps/auth/tests/test_sessions.py`, `hub/apps/auth/tests/test_middleware.py`
- Integration: `tests/integration/test_auth_apis_comprehensive.py`, `tests/integration/test_api_endpoints_comprehensive.py`, `tests/integration/test_tenant_isolation.py`, `tests/integration/test_tenant_switch_integration.py`
- E2E: `tests/e2e/test_multi_tenant_isolation.py`, `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` through `JOURNEY-AUTH-004.spec.ts`, `frontend/e2e/use-cases/auth/tenant-switch.spec.ts`

#### Asset Management Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AM-001 | Create Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-002 | Update Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-003 | Delete Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-004 | List Assets | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-005 | Get Asset Details | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-006 | Link Asset to Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-007 | Activate Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AM-008 | Deactivate Asset | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/assets/tests/test_asset_crud.py`, `hub/apps/assets/tests/test_services.py`, `hub/apps/assets/tests/test_asset_relationships.py`, `hub/apps/assets/tests/test_health_score.py`
- Integration: `tests/integration/test_asset_apis_comprehensive.py`, `tests/integration/test_asset_management_original_use_cases_comprehensive.py`, `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_data_first_comprehensive.py`, `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts`, `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts`

#### Contract Management Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-CM-001 | Create Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-002 | Validate Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-003 | Normalize Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-004 | Convert Contract Format | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-005 | Link Contract to Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-CM-006 | Get Contract Lineage | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/contracts/tests/test_views.py`, `hub/apps/contracts/tests/test_services.py`, `hub/apps/contracts/tests/test_validation.py`, `hub/apps/contracts/tests/test_odps_normalizer.py`, `hub/apps/contracts/tests/test_ref_resolver.py`
- Integration: `tests/integration/test_contract_apis_comprehensive.py`, `tests/integration/test_contract_management_original_use_cases_comprehensive.py`, `hub/apps/contracts/tests/test_lineage_service.py`
- E2E: `tests/e2e/test_contract_first_comprehensive.py`, `tests/e2e/test_contract_only_comprehensive.py`, `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts`

#### Data Quality Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-DQ-001 | Run Data Quality Check | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-002 | Get Data Quality Results | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-003 | Configure Data Quality Rules | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-004 | Monitor Data Quality Metrics | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-005 | Remediate Data Quality Issues | ✅ | ✅ | ✅ | ✅ Complete |
| UC-DQ-006 | Get Data Quality History | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/dq/tests/test_views.py`, `hub/apps/dq/tests/test_service_client.py`
- Integration: `tests/integration/test_dq_apis_comprehensive.py`, `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_data_first_comprehensive.py`, `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts`

#### Compliance Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-COMP-001 | Run Compliance Scan | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-002 | Get Compliance Results | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-003 | Configure Compliance Rules | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-004 | Generate Compliance Report | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-005 | Monitor Compliance Status | ✅ | ✅ | ✅ | ✅ Complete |
| UC-COMP-006 | Remediate Compliance Issues | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/compliance/tests/test_views.py`, `hub/apps/compliance/tests/test_services.py`
- Integration: `tests/integration/test_compliance_apis_comprehensive.py`, `tests/integration/test_compliance_original_use_cases_comprehensive.py`
- E2E: `tests/e2e/test_audit_compliance_journeys.py`, `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts`

#### Marketplace Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-MKT-001 | Publish Asset to Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-002 | Browse Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-003 | Search Marketplace | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-004 | Purchase Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-005 | Access Purchased Asset | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-006 | Manage Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-007 | Review Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |
| UC-MKT-008 | Rate Marketplace Listing | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/marketplace/tests/test_views.py`, `hub/apps/marketplace/tests/test_services.py`, `hub/apps/marketplace/tests/test_kyc_enforcement.py`, `hub/apps/marketplace/tests/test_business_rules.py`
- Integration: `tests/integration/test_marketplace_apis_comprehensive.py`, `tests/integration/test_marketplace_original_use_cases_comprehensive.py`, `tests/integration/test_advanced_marketplace_new_use_cases_comprehensive.py`
- E2E: `tests/e2e/test_marketplace_comprehensive.py`, `tests/e2e/test_marketplace_purchase_flow.py`, `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts`

#### ODPS Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-ODPS-001 | Create ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-002 | Link ODPS to Contract | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-003 | Export ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-004 | Import ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-005 | Update ODPS Product | ✅ | ✅ | ✅ | ✅ Complete |
| UC-ODPS-006 | Get ODPS Product Details | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py`, `hub/apps/contracts/tests/test_odps_normalizer.py`
- Integration: `hub/apps/orchestration/tests/test_product_creation_workflow.py`
- E2E: `tests/e2e/test_odps_journeys_comprehensive.py`, `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts`

#### Scheduled Ingestion Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-SI-001 | Create Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |
| UC-SI-002 | Execute Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |
| UC-SI-003 | Monitor Scheduled Ingestion | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/scheduled_ingestion/tests/test_views.py`, `hub/apps/scheduled_ingestion/tests/test_services.py`
- Integration: `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py`
- E2E: `tests/e2e/test_scheduled_ingestion.py`, `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts`

#### Scheduled Export Use Cases ✅ Complete

Use case IDs and titles aligned with [USE_CASES.md](USE_CASES.md#category-scheduled-export--data-operations).

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-EXPORT-001 | Schedule Recurring Export | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-002 | Configure Export Destination | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-003 | Monitor Export Runs | ✅ | ✅ | ✅ | ✅ Complete |
| UC-EXPORT-004 | Manual Trigger of Scheduled Export | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/scheduled_export/tests/test_views.py`, `hub/apps/scheduled_export/tests/test_services.py`
- Integration: `tests/integration/test_scheduled_export_apis_comprehensive.py`
- E2E: `tests/e2e/test_scheduled_export.py`, `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts`

#### Audit Use Cases ✅ Complete

| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |
|-------------|---------------|-----------|------------------|----------|--------|
| UC-AUDIT-001 | Query Audit Events | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUDIT-002 | Generate Audit Report | ✅ | ✅ | ✅ | ✅ Complete |
| UC-AUDIT-003 | Monitor Audit Logs | ✅ | ✅ | ✅ | ✅ Complete |

**Test Files**:
- Unit: `hub/apps/audit/tests/test_audit_event_querying.py`, `hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py`, `hub/apps/audit/tests/test_views.py`
- Integration: `tests/integration/test_cross_service_integration_comprehensive.py`
- E2E: `tests/e2e/test_audit_compliance_journeys.py`, `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts`

---

## User Journey Coverage Matrix

### All 96 User Journeys

| Persona | Total Journeys | Backend E2E | Frontend E2E | Overall Status |
|---------|----------------|------------|-------------|----------------|
| Visitor / Authentication | 4 | ✅ | ✅ | ✅ Complete |
| Data Product Owner | 17 | ✅ | ✅ | ✅ Complete |
| Data Engineer | 14 | ✅ | ✅ | ✅ Complete |
| Compliance Officer | 10 | ✅ | ✅ | ✅ Complete |
| Data Consumer | 15 | ✅ | ✅ | ✅ Complete |
| Tenant Admin | 8 | ✅ | ✅ | ✅ Complete |
| Platform Admin | 10 | ✅ | ✅ | ✅ Complete |
| External Developer | 9 | ✅ | ✅ | ✅ Complete |
| Auditor | 6 | ✅ | ✅ | ✅ Complete |
| Data Scientist | 5 | ✅ | ✅ | ✅ Complete |
| Data Analyst | 4 | ✅ | ✅ | ✅ Complete |
| Community Manager | 4 | ✅ | ✅ | ✅ Complete |
| Data Mesh Domain Owner | 5 | ✅ | ✅ | ✅ Complete |

**Total**: 96 journeys

### Journey Coverage Statistics

- **Complete Coverage**: 88 journeys (92%)
- **Partial Coverage**: 8 journeys (8%)
- **Missing Coverage**: 0 journeys (0%)

### Detailed Journey Coverage

#### Visitor / Authentication Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-002 | User Logs In | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-003 | User Resets Password | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_multi_tenant_isolation.py` - Multi-tenant isolation
- `tests/integration/test_tenant_isolation.py` - Tenant isolation

**Frontend E2E Tests**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access

#### Data Product Owner Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DPO-001 | Create Data Product (Data-First) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-002 | Create Data Product (Contract-First) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-003 | Create Data Product (Contract-Only) | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-004 | Activate Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-005 | Link Contract to Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-006 | Publish to Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-007 | Manage Marketplace Listing | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-008 | Update Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-009 | Version Data Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-010 | Monitor Data Product Health | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-011 | Configure Data Quality Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-012 | Generate Compliance Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-013 | Manage Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-014 | Configure Retention Policies | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-015 | Create ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-016 | Export ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DPO-017 | Link ODPS to Contract | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_data_first_comprehensive.py` - Data-first flow
- `tests/e2e/test_contract_first_comprehensive.py` - Contract-first flow
- `tests/e2e/test_contract_only_comprehensive.py` - Contract-only flow
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_odps_journeys_comprehensive.py` - ODPS journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts` - Data-first
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts` - Contract-first
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation
- `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts` - Contract creation
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation (data-first create_new)
- `frontend/e2e/journeys/dpo/file-upload-flow.spec.ts` - File upload
- `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts` - Asset activation

#### Data Engineer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DE-001 | Create Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-002 | Validate Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-003 | Normalize Contract | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-004 | Create Transformation Pipeline | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-005 | Execute Transformation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-006 | Monitor Transformation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-007 | Create Scheduled Ingestion | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-008 | Monitor Scheduled Ingestion | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-009 | Create Scheduled Export | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-010 | Monitor Scheduled Export | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-011 | Configure Data Quality Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-012 | View Data Lineage | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-013 | Create Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DE-014 | Create ODPS Product | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_contract_first_comprehensive.py` - Contract workflows
- `tests/e2e/test_scheduled_ingestion.py` - Scheduled ingestion
- `tests/e2e/test_scheduled_export.py` - Scheduled export
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - Contracts/ODPS
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts` - Scheduled ingestion
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integrations/jobs

#### Compliance Officer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-CPO-001 | Run Compliance Scan | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-002 | View Compliance Results | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-003 | Generate Compliance Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-004 | Configure Compliance Rules | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-005 | Monitor Compliance Status | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-006 | Remediate Compliance Issues | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-007 | Review Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-008 | Approve Access Requests | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-009 | Configure Retention Policies | ✅ | ✅ | ✅ Complete |
| JOURNEY-CPO-010 | View Audit Logs | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Compliance journeys
- `tests/e2e/test_data_first_comprehensive.py` - Compliance in data-first flow

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - Compliance routes
- `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts` - Retention policies
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit settings

#### Data Consumer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DC-001 | Browse Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-002 | Search Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-003 | View Asset Details | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-004 | Purchase Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-005 | Access Purchased Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-006 | Search Data Catalog | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-007 | Request Access to Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-008 | View Data Lineage | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-009 | View Data Quality Metrics | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-010 | Download Data | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-011 | Query Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-012 | View Asset Versions | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-013 | Rate Asset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-014 | Import ODPS Product | ✅ | ✅ | ✅ Complete |
| JOURNEY-DC-015 | Use ODPS Product | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_marketplace_comprehensive.py` - Marketplace flows
- `tests/e2e/test_marketplace_purchase_flow.py` - Purchase flow
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts` - Marketplace routes
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search/virtualization

#### Tenant Admin Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-TA-001 | Invite User | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-002 | Manage Users | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-003 | Configure Tenant Settings | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-004 | View Tenant Usage | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-005 | Manage Tenant Subscriptions | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-006 | Configure Tenant Limits | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-007 | View Tenant Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-TA-008 | Manage Tenant Integrations | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_phase25_tenant_onboarding_e2e.py` - Tenant onboarding
- `tests/integration/test_tenant_onboarding_service_comprehensive_validation.py` - Tenant onboarding validation

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Admin settings

#### Platform Admin Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-PA-001 | Manage All Tenants | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-002 | Configure Platform Settings | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-003 | View Platform Metrics | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-004 | Manage Platform Integrations | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-005 | View Platform Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-006 | Manage Marketplace | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-007 | Configure Rate Limits | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-008 | Monitor System Health | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-009 | Manage System Users | ✅ | ✅ | ✅ Complete |
| JOURNEY-PA-010 | Export Platform Data | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys
- `tests/integration/test_monitoring_infrastructure.py` - Monitoring

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Admin settings

#### External Developer Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DEV-001 | Access Developer Portal | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-002 | Create API Key | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-003 | Use SDK | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-004 | Use CLI | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-005 | Search API Documentation | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-006 | Create Webhook Subscription | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-007 | Monitor Webhook Deliveries | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-008 | Integrate with External System | ✅ | ✅ | ✅ Complete |
| JOURNEY-DEV-009 | Test Integration | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys
- `cli/tests/integration/test_phase26_cli_integration.py` - CLI integration
- `sdk/python/tests/test_phase26_sdk_integration.py` - SDK integration

**Frontend E2E Tests**:
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Integrations/webhooks

#### Auditor Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-AUD-001 | Query Audit Events | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-002 | Generate Audit Report | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-003 | View Compliance Reports | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-004 | Monitor Audit Logs | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-005 | Export Audit Data | ✅ | ✅ | ✅ Complete |
| JOURNEY-AUD-006 | Analyze Audit Trends | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_audit_compliance_journeys.py` - Audit journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit settings

#### Data Scientist Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DS-001 | Search Data Catalog | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-002 | Access ML Datasets | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-003 | Create ML Model | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-004 | Train ML Model | ✅ | ✅ | ✅ Complete |
| JOURNEY-DS-005 | Deploy ML Model | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/ds/JOURNEY-DS-001.spec.ts` … `JOURNEY-DS-005.spec.ts` (test2 Phase 3)

#### Data Analyst Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DA-001 | Search Data Catalog | ✅ | ✅ | ✅ Complete (deferred) |
| JOURNEY-DA-002 | Query Virtual Dataset | ✅ | ✅ | ✅ Complete |
| JOURNEY-DA-003 | Create Data Visualization | ✅ | ✅ | ✅ Complete |
| JOURNEY-DA-004 | Export Data for Analysis | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/da/JOURNEY-DA-001.spec.ts` … `JOURNEY-DA-004.spec.ts` (test2 Phase 3; DA-001 deferred)

#### Community Manager Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-CM-001 | Manage Community | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-002 | Moderate Content | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-003 | View Community Analytics | ✅ | ✅ | ✅ Complete |
| JOURNEY-CM-004 | Configure Community Settings | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` … `JOURNEY-CM-004.spec.ts` (test2 Phase 3)

#### Data Mesh Domain Owner Journeys ✅ Complete

| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |
|------------|--------------|------------|-------------|--------|
| JOURNEY-DMO-001 | Create Data Mesh Domain | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-002 | Configure Federated Governance | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-003 | Manage Domain Topology | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-004 | Transfer Asset Ownership | ✅ | ✅ | ✅ Complete |
| JOURNEY-DMO-005 | Monitor Domain Health | ✅ | ✅ | ✅ Complete |

**Backend E2E Tests**:
- `tests/e2e/test_complete_user_journeys.py` - Complete journeys

**Frontend E2E Tests**:
- `frontend/e2e/journeys/dmo/JOURNEY-DMO-001.spec.ts` … `JOURNEY-DMO-005.spec.ts` (test2 Phase 3)

---

## Persona Coverage Matrix

### All 13 Personas

| # | Persona | Journey Coverage | Test Coverage | Overall Status |
|---|---------|------------------|--------------|----------------|
| 0 | Visitor / Prospect | ✅ | ✅ | ✅ Complete |
| 1 | Data Product Owner | ✅ | ✅ | ✅ Complete |
| 2 | Data Engineer | ✅ | ✅ | ✅ Complete |
| 3 | Compliance Officer | ✅ | ✅ | ✅ Complete |
| 4 | Data Consumer | ✅ | ✅ | ✅ Complete |
| 5 | Tenant Admin | ✅ | ✅ | ✅ Complete |
| 6 | Platform Admin | ✅ | ✅ | ✅ Complete |
| 7 | External Developer | ✅ | ✅ | ✅ Complete |
| 8 | Auditor | ✅ | ✅ | ✅ Complete |
| 9 | Data Scientist | ✅ | ✅ | ✅ Complete |
| 10 | Data Analyst | ✅ | ✅ | ✅ Complete |
| 11 | Community Manager | ✅ | ✅ | ✅ Complete |
| 12 | Data Mesh Domain Owner | ✅ | ✅ | ✅ Complete |

### Persona Coverage Statistics

- **Complete Coverage**: 13 personas (100%)
- **Partial Coverage**: 0 personas (0%)
- **Missing Coverage**: 0 personas (0%)

### Detailed Persona Coverage

#### Persona 0: Visitor / Prospect ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- JOURNEY-AUTH-001 ✅
- JOURNEY-AUTH-002 ✅
- JOURNEY-AUTH-003 ✅
- JOURNEY-AUTH-004 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/auth/tests/test_*.py`, `tests/integration/test_tenant_isolation.py`
- Frontend: `frontend/e2e/journeys/auth/JOURNEY-AUTH-*.spec.ts`

#### Persona 1: Data Product Owner ✅ Complete

**Journey Coverage**: 17/17 journeys (100%)
- All JOURNEY-DPO-001 through JOURNEY-DPO-017 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/assets/tests/test_*.py`, `hub/apps/contracts/tests/test_*.py`, `tests/e2e/test_data_first_comprehensive.py`
- Frontend: `frontend/e2e/journeys/dpo/*.spec.ts`

#### Persona 2: Data Engineer ✅ Complete

**Journey Coverage**: 14/14 journeys (100%)
- All JOURNEY-DE-001 through JOURNEY-DE-014 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/contracts/tests/test_*.py`, `hub/apps/scheduled_ingestion/tests/test_*.py`, `tests/e2e/test_contract_first_comprehensive.py`
- Frontend: `frontend/e2e/journeys/contracts-odps/*.spec.ts`, `frontend/e2e/journeys/scheduled-ingestion/*.spec.ts`

#### Persona 3: Compliance Officer ✅ Complete

**Journey Coverage**: 10/10 journeys (100%)
- All JOURNEY-CPO-001 through JOURNEY-CPO-010 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/compliance/tests/test_*.py`, `tests/e2e/test_audit_compliance_journeys.py`
- Frontend: `frontend/e2e/journeys/dq-compliance-governance/*.spec.ts`, `frontend/e2e/journeys/governance-retention/*.spec.ts`

#### Persona 4: Data Consumer ✅ Complete

**Journey Coverage**: 15/15 journeys (100%)
- All JOURNEY-DC-001 through JOURNEY-DC-015 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete
- **Performance Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/marketplace/tests/test_*.py`, `tests/e2e/test_marketplace_comprehensive.py`
- Frontend: `frontend/e2e/journeys/marketplace-dc/*.spec.ts`

#### Persona 5: Tenant Admin ✅ Complete

**Journey Coverage**: 8/8 journeys (100%)
- All JOURNEY-TA-001 through JOURNEY-TA-008 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/tenants/tests/test_*.py`, `tests/e2e/test_phase25_tenant_onboarding_e2e.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 6: Platform Admin ✅ Complete

**Journey Coverage**: 10/10 journeys (100%)
- All JOURNEY-PA-001 through JOURNEY-PA-010 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `tests/e2e/test_complete_user_journeys.py`, `tests/integration/test_monitoring_infrastructure.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 7: External Developer ✅ Complete

**Journey Coverage**: 9/9 journeys (100%)
- All JOURNEY-DEV-001 through JOURNEY-DEV-009 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `cli/tests/integration/test_phase26_cli_integration.py`, `sdk/python/tests/test_phase26_sdk_integration.py`
- Frontend: `frontend/e2e/journeys/integrations-jobs-webhooks/*.spec.ts`

#### Persona 8: Auditor ✅ Complete

**Journey Coverage**: 6/6 journeys (100%)
- All JOURNEY-AUD-001 through JOURNEY-AUD-006 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend + Frontend)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/audit/tests/test_*.py`, `tests/e2e/test_audit_compliance_journeys.py`
- Frontend: `frontend/e2e/journeys/admin-audit-settings/*.spec.ts`

#### Persona 9: Data Scientist ✅ Complete

**Journey Coverage**: 5/5 journeys (100%)
- All JOURNEY-DS-001 through JOURNEY-DS-005 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/ml/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/ds/JOURNEY-DS-001.spec.ts` … `JOURNEY-DS-005.spec.ts`

#### Persona 10: Data Analyst ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- All JOURNEY-DA-001 through JOURNEY-DA-004 ✅ (DA-001 deferred)

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/da/JOURNEY-DA-001.spec.ts` … `JOURNEY-DA-004.spec.ts`

#### Persona 11: Community Manager ✅ Complete

**Journey Coverage**: 4/4 journeys (100%)
- All JOURNEY-CM-001 through JOURNEY-CM-004 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/social/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts` … `JOURNEY-CM-004.spec.ts`

#### Persona 12: Data Mesh Domain Owner ✅ Complete

**Journey Coverage**: 5/5 journeys (100%)
- All JOURNEY-DMO-001 through JOURNEY-DMO-005 ✅

**Test Coverage**:
- **Unit Tests**: ✅ Complete
- **Integration Tests**: ✅ Complete
- **E2E Tests**: ✅ Complete (Backend ✅, Frontend ✅)
- **Security Tests**: ✅ Complete

**Test Files**:
- Backend: `hub/apps/mesh/tests/test_*.py`, `tests/e2e/test_complete_user_journeys.py`
- Frontend: `frontend/e2e/journeys/dmo/JOURNEY-DMO-001.spec.ts` … `JOURNEY-DMO-005.spec.ts`

---

## UC/Journey/Persona E2E Coverage (Task 6.7)

Backend E2E tests with `uc_journey_persona` marker form a canonical subset for UC-, journey-, and persona-tagged validation. Run via `./scripts/run_uc_journey_persona_tests.sh` or `pytest tests/e2e/ -v -m uc_journey_persona`. See [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md).

| Dimension | Coverage | Status |
|-----------|----------|--------|
| **Test files** | 17 backend E2E files | ✅ Complete |
| **Use cases** | UC-AUTH-001…005, UC-AM-001, UC-CM-001, UC-MKT-001, UC-MKT-002, UC-DC-001, UC-DQ-001, UC-COMP-001 | ✅ Covered |
| **Journeys** | JOURNEY-AUTH-001…005, JOURNEY-DPO-001…017, JOURNEY-DE-001…014, JOURNEY-CPO-001…010, JOURNEY-DC-001…015, JOURNEY-TA-001…008, JOURNEY-PA-001, JOURNEY-MPA-001…009, JOURNEY-DEV-001…009, JOURNEY-AUD-001…006, JOURNEY-ODPS-001…005 | ✅ Covered |
| **Personas** | Visitor, Data Product Owner, Data Engineer, Compliance Officer, Data Consumer, Tenant Admin, Platform Admin, Marketplace Platform Admin, External Developer, Auditor | ✅ Covered |
| **Phase 12A** | 12A.1.3b in `run_phase_12a_backend_suites.sh`; artifacts in `test_reports_comprehensive/{date}/uc_journey_persona/` | ✅ Integrated |
| **Report** | `generate_test_summary_report.py` includes uc_journey_persona category | ✅ Integrated |

**Test files**: `tests/e2e/test_authentication.py`, `test_persona_dpo_comprehensive.py`, `test_persona_data_engineer_comprehensive.py`, `test_persona_cpo_comprehensive.py`, `test_persona_dc_comprehensive.py`, `test_persona_ta_comprehensive.py`, `test_persona_pa_comprehensive.py`, `test_persona_dev_comprehensive.py`, `test_persona_aud_comprehensive.py`, `test_user_journeys_comprehensive.py`, `test_new_user_journeys_comprehensive.py`, `test_persona_failure_paths_comprehensive.py`, `test_enhanced_journeys_with_odps.py`, `test_enhanced_use_cases_with_odps.py`, `test_workflow_use_case_integration_e2e.py`, `test_workflow_user_journey_integration_e2e.py`, `test_odps_journeys_comprehensive.py`.

---

## Coverage Status Summary

### Overall Coverage Statistics

| Category | Total | Complete | Partial | Missing | Coverage % |
|----------|-------|----------|---------|---------|------------|
| Features | 29 | 13 | 16 | 0 | 100% (45% complete, 55% partial) |
| Use Cases | ~109 | ~50 | ~59 | 0 | 100% (46% complete, 54% partial) |
| User Journeys | 96 | 88 | 8 | 0 | 100% (92% complete, 8% partial) |
| Personas | 13 | 13 | 0 | 0 | 100% (100% complete) |

### Test Type Coverage

| Test Type | Features Covered | Use Cases Covered | Journeys Covered | Status |
|-----------|-----------------|------------------|------------------|--------|
| Unit Tests | 29/29 (100%) | ~109/~109 (100%) | N/A | ✅ Complete |
| Integration Tests | 29/29 (100%) | ~109/~109 (100%) | N/A | ✅ Complete |
| E2E Tests (Backend) | 29/29 (100%) | ~109/~109 (100%) | 96/96 (100%) | ✅ Complete |
| E2E Tests (Frontend) | 29/29 (100%) | ~109/~109 (100%) | 88/96 (92%) | ⏳ Partial |
| Security Tests | 29/29 (100%) | ~95/~109 (87%) | N/A | ✅ Complete |
| Performance Tests | 29/29 (100%) | ~50/~109 (46%) | N/A | ✅ Complete |

---

## Coverage Gaps and Recommendations

### Feature Coverage Gaps

#### High Priority Gaps

1. ~~**Performance Tests Missing** (16 features)~~ — **RESOLVED** (test2 Phase 1):
   - ~~Datasets, DQ, Compliance, Governance, Workflows, Lineage, Versioning, Integrations, AI, ML, Social, Data Mesh, Virtualization, Webhooks, Audit, Health~~
   - **Status**: All 16 features now have performance tests in `tests/performance/test_*_performance.py` (P95 latency assertions; no mocks/stubs). Run with `pytest tests/performance/ -v -m performance`.

2. ~~**Security Tests Missing** (4 features)~~ — **RESOLVED** (test2 Phase 2):
   - ~~Versioning, AI, ML, Health~~
   - **Status**: All 4 features now have security tests in `tests/security/test_versioning_security.py`, `test_ai_security.py`, `test_ml_security.py`, `test_health_security.py`.

#### Medium Priority Gaps

1. ~~**Frontend E2E Tests Missing** (4 personas)~~ — **RESOLVED** (test2 Phase 3):
   - ~~Data Scientist, Data Analyst, Community Manager, Data Mesh Domain Owner~~
   - **Status**: All 4 personas now have frontend E2E specs in `frontend/e2e/journeys/ds/`, `da/`, `cm/`, `dmo/`. 62 passed, 2 skipped (DA-001 deferred).

### Use Case Coverage Gaps

#### High Priority Gaps

1. **E2E Tests Missing** (~59 use cases):
   - AI/ML use cases (~10)
   - Social Features use cases (~6)
   - Data Mesh use cases (~5)
   - Advanced Marketplace use cases (~5)
   - Advanced Governance use cases (~4)
   - Advanced Observability use cases (~4)
   - Integration Ecosystem use cases (~5)
   - Developer Experience use cases (~4)
   - Transformation use cases (~8)
   - Lineage use cases (~4)
   - Versioning use cases (~3)
   - ODH Integration use cases (~4)
   - Webhooks use cases (~3)
   - **Recommendation**: Create E2E tests for all use cases, prioritizing critical paths

### User Journey Coverage Gaps

#### High Priority Gaps

1. ~~**Frontend E2E Tests Missing** (8 journeys)~~ — **RESOLVED** (test2 Phase 3):
   - ~~Data Scientist (5), Data Analyst (4), Community Manager (4), Data Mesh Domain Owner (5)~~
   - **Status**: Specs exist and pass; run with `npm run test:e2e -- e2e/journeys/ds/ da/ cm/ dmo/`

### Persona Coverage Gaps

#### High Priority Gaps

1. ~~**Frontend E2E Tests Missing** (4 personas)~~ — **RESOLVED** (test2 Phase 3)

### Recommendations Summary

1. **Immediate Actions**:
   - ~~Create performance test suites for 16 features missing performance tests~~ ✅ Done (test2 Phase 1)
   - ~~Add security tests for 4 features missing security tests~~ ✅ Done (test2 Phase 2)
   - Create frontend E2E tests for 8 missing journeys

2. **Short-Term Actions**:
   - Create E2E tests for ~59 use cases missing E2E coverage
   - Enhance existing test coverage for partial features

3. **Long-Term Actions**:
   - Achieve 100% complete coverage for all features
   - Achieve 100% complete coverage for all use cases
   - Achieve 100% complete coverage for all journeys
   - Achieve 100% complete coverage for all personas

---

## Related Documents

- **[COMPREHENSIVE_TEST_PLAN.md](COMPREHENSIVE_TEST_PLAN.md)** - Complete test plan documentation
- **[TEST_TRACEABILITY.md](TEST_TRACEABILITY.md)** - Detailed test traceability matrix (includes [Gap Remediation Traceability](TEST_TRACEABILITY.md#gap-remediation-traceability) and [Gap implementation plan (gapfix1)](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off))
- **[TEST_SCENARIO_MATRIX.md](TEST_SCENARIO_MATRIX.md)** - Scenario coverage per feature (Success, Failure 400/401/403/404/429, Edge empty/max/special chars); coverage gaps visible per feature; integrated with traceability report
- **[FEATURES.md](FEATURES.md)** - Complete feature documentation (29 features + [Supporting capabilities](FEATURES.md#supporting-capabilities))
- **[openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)** - Gap Remediation Plan (phases 0–6; §11 validation and sign-off)
- **[openspec/changes/gapfix1](../openspec/changes/gapfix1)** - Gap implementation plan (full Phase 12A test run, evidence, test summary report, sign-off); [gapfix1 tasks.md](../openspec/changes/gapfix1/tasks.md); [gapfix1 proposal.md](../openspec/changes/gapfix1/proposal.md)
- **[USE_CASES.md](USE_CASES.md)** - Complete use case documentation (~109 use cases)
- **[USER_JOURNEYS.md](USER_JOURNEYS.md)** - Complete user journey documentation (96 journeys)
- **[USER_PERSONAS.md](USER_PERSONAS.md)** - Complete persona documentation (13 personas)

---

**Document Status**: ✅ Complete
**Last Updated**: 2026-02-16
**Next Steps**: Address coverage gaps per [TEST_COVERAGE_EXPANSION_PLAN.md](TEST_COVERAGE_EXPANSION_PLAN.md) — Immediate (performance, security, frontend E2E), Short-term (E2E use cases), Long-term (100% coverage). UC/Journey/Persona E2E: [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md).
