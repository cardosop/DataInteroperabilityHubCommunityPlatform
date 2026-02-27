# Test Traceability Matrix

**Last Updated**: 2026-02-16
**Version**: 1.3.0

---

## Overview

This document provides comprehensive traceability between:
1. **Features** (from [FEATURES.md](FEATURES.md)) → Backend tests, Frontend specs
2. **Use Cases** (from [USE_CASES.md](USE_CASES.md)) → Backend tests, Frontend specs
3. **User Journeys** (from [USER_JOURNEYS.md](USER_JOURNEYS.md)) → Backend e2e tests, Playwright specs

**Coverage Includes**:
- Phase 25 (SaaS platform): Billing, tenant lifecycle, GDPR, API versioning, tenant usage
- Phase 26 (CLI/SDK): CLI commands and SDK methods mapped to backend features
- All core features: Auth, Contracts, ODPS, Assets, Datasets, DQ, Compliance, Marketplace, etc.
- **Scheduled Export**: UC-EXPORT-001–004, JOURNEY-EXPORT-001–002; backend, integration, E2E, frontend unit/E2E; see [Scheduled Export](#scheduled-export) and [Scheduled Export Use Cases](#scheduled-export-use-cases).
- **Trust signals config API** (Marketplace): UC-MKT-ADV-003, UC-MKT-ADV-005; backend/integration tests; see [Marketplace](#marketplace) and [Gap Remediation Traceability](#gap-remediation-traceability) Phase 4.
- **UC/Journey/Persona E2E tests** (Task 6.7): 17 backend E2E files with `uc_journey_persona` marker; run via `./scripts/run_uc_journey_persona_tests.sh` or `pytest tests/e2e/ -v -m uc_journey_persona`. See [UC/Journey/Persona E2E Tests](#ucjourney-persona-e2e-tests-task-67) and [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md).

**Test Naming Convention**:
- Backend tests: `test_uc_{use_case_id}_{description}.py` or `test_journey_{journey_id}_{description}.py`
- Frontend specs: `{JOURNEY-ID}.spec.ts` or `{feature}-{description}.spec.ts`

**Related**: [TEST_SUITE_GAP_ANALYSIS.md](TEST_SUITE_GAP_ANALYSIS.md) — gap analysis and traceability audit.

---

## Table of Contents

1. [Feature → Test Mapping](#feature--test-mapping)
2. [Use Case → Test Mapping](#use-case--test-mapping)
3. [User Journey → Test Mapping](#user-journey--test-mapping)
4. [Persona → Test Mapping](#persona--test-mapping)
5. [UC/Journey/Persona E2E Tests (Task 6.7)](#ucjourney-persona-e2e-tests-task-67)
6. [Complete Use Case Index](#complete-use-case-index)
7. [Complete User Journey Index](#complete-user-journey-index)
8. [Phase 25 (SaaS Platform) Traceability](#phase-25-saas-platform-traceability)
9. [Phase 26 (CLI/SDK) Traceability](#phase-26-clisdk-traceability)
10. [Gap Remediation Traceability](#gap-remediation-traceability) — includes [Gap implementation plan (gapfix1)](#gap-implementation-plan-gapfix1--full-test-run-and-sign-off)
11. [Test Coverage Summary](#test-coverage-summary)
12. [Evidence Links](#evidence-links)

---

## Feature → Test Mapping

This section maps each feature from [FEATURES.md](FEATURES.md) to its corresponding backend and frontend tests.

### Auth

**Feature**: Authentication, registration, API keys, sessions

**Backend Tests**:
- `hub/apps/auth/tests/test_sessions.py` - Session management
- `hub/apps/auth/tests/test_authentication.py` - Authentication flows
- `tests/integration/test_tenant_isolation.py` - Tenant isolation in auth
- `tests/security/test_allowany_public_endpoints.py` - Public endpoint security

**Frontend Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access
- `frontend/e2e/auth-visitor-journeys.spec.ts` - Visitor journeys

**Use Cases**: UC-AUTH-001, UC-AUTH-002, UC-AUTH-003, UC-AUTH-004
**Journeys**: JOURNEY-AUTH-001, JOURNEY-AUTH-002, JOURNEY-AUTH-003, JOURNEY-AUTH-004

---

### Contracts

**Feature**: Contract management, validation, normalization, conversion

**Backend Tests**:
- `hub/apps/contracts/tests/test_views.py` - Contract CRUD
- `hub/apps/contracts/tests/test_normalization_metrics.py` - Normalization
- `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py` - ODPS generation
- `tests/e2e/test_contract_operations.py` - E2E contract operations
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - ODPS workflow

**Frontend Specs**:
- `frontend/e2e/journeys/dpo/contract-creation-flow.spec.ts` - Contract creation
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - ODPS contracts

**Use Cases**: UC-CM-001 through UC-CM-007
**Journeys**: JOURNEY-DPO-005, JOURNEY-DE-001

---

### ODPS (Open Data Product Standard)

**Feature**: ODPS product creation, linking, export, pricing, semantic mapping

**Backend Tests**:
- `hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py` - ODPS generation
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation workflow
- `tests/e2e/test_odps_journeys_comprehensive.py` - ODPS journeys
- `hub/apps/orchestration/tests/test_odps_workflow_events.py` - ODPS workflow events

**Frontend Specs**:
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` - ODPS routes
- `frontend/e2e/phase5-odps-journey.spec.ts` - ODPS journey

**Use Cases**: UC-ODPS-001, UC-ODPS-002, UC-ODPS-003 (referenced in USE_CASES.md)
**Journeys**: JOURNEY-DPO-015, JOURNEY-DPO-016, JOURNEY-DPO-017, JOURNEY-DE-014, JOURNEY-DC-014, JOURNEY-DC-015, JOURNEY-PA-010

---

### Assets

**Feature**: Asset catalog, health scores, recommendations, dependencies

**Backend Tests**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset CRUD operations
- `hub/apps/assets/tests/test_services.py` - Asset services
- `hub/apps/assets/tests/test_health_score.py` - Health score calculation

**Frontend Specs**:
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation
- `frontend/e2e/journeys/dpo/asset-activation-flow.spec.ts` - Asset activation
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts` - Data-first flow
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts` - Marketplace publishing

**Use Cases**: UC-AM-001 through UC-AM-011
**Journeys**: JOURNEY-DPO-001, JOURNEY-DPO-002, JOURNEY-DPO-003, JOURNEY-DPO-004

---

### Datasets

**Feature**: Dataset management, versioning, schema evolution

**Backend Tests**:
- `hub/apps/datasets/tests/test_views.py` - Dataset CRUD
- `hub/apps/datasets/tests/test_services.py` - Dataset services
- `hub/apps/datasets/tests/test_versioning.py` - Versioning (if exists)

**Frontend Specs**:
- `frontend/e2e/journeys/dpo/dataset-creation-flow.spec.ts` - Dataset creation

**Use Cases**: UC-DS-001 through UC-DS-005 (referenced)
**Journeys**: JOURNEY-DPO-001 (includes dataset creation)

---

### Data Quality

**Feature**: Quality checks, monitoring, alerting, scorecards

**Backend Tests**:
- `hub/apps/dq/tests/test_views.py` - DQ runs and results
- `hub/apps/dq/tests/test_service_client.py` - DQ service integration

**Frontend Specs**:
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - DQ routes

**Use Cases**: UC-DQ-001 through UC-DQ-004
**Journeys**: JOURNEY-DPO-004, JOURNEY-DE-003

---

### Compliance

**Feature**: Compliance scanning, PII detection, risk assessment

**Backend Tests**:
- `hub/apps/compliance/tests/test_views.py` - Compliance runs
- `hub/apps/compliance/tests/test_services.py` - Compliance services

**Frontend Specs**:
- `frontend/e2e/journeys/dq-compliance-governance/dq-compliance-governance-routes.spec.ts` - Compliance routes

**Use Cases**: UC-COMP-001 through UC-COMP-003
**Journeys**: JOURNEY-CPO-001, JOURNEY-DE-004

---

### Marketplace

**Feature**: Marketplace listings, orders, entitlements, purchases, data preview, trust signals (see [FEATURES.md](FEATURES.md#marketplace))

**Backend Tests**:
- `hub/apps/marketplace/tests/test_views.py` - Marketplace views (including preview)
- `hub/apps/marketplace/tests/test_preview.py` - Data preview (sample data, schema, quality_metrics, trust_signals dict/list, tenant isolation, PREVIEW_ACCESSED audit, schema null); real DB, no mocks
- `tests/integration/test_trust_signals_config_api_comprehensive.py` - Trust signals config API (CRUD, tenant isolation); real DB, no mocks
- `hub/apps/marketplace/tests/test_services.py` - Marketplace services
- `hub/apps/marketplace/tests/test_kyc_enforcement.py` - KYC enforcement
- `hub/apps/marketplace/tests/test_business_rules.py` - Business rules

**Frontend Specs**:
- `frontend/e2e/journeys/marketplace-dc/marketplace-dc-routes.spec.ts` - Marketplace routes
- `frontend/e2e/phase4-marketplace-journey.spec.ts` - Marketplace journey

**Use Cases**: UC-MKT-001 through UC-MKT-005, UC-MKT-ADV-001 through UC-MKT-ADV-005
**Journeys**: JOURNEY-DPO-002, JOURNEY-DPO-006, JOURNEY-DC-001, JOURNEY-DC-011, JOURNEY-DC-012, JOURNEY-DC-015

---

### Governance

**Feature**: Access control, access requests, classifications, compliance reporting

**Backend Tests**:
- `hub/apps/governance/tests/test_access_request_views.py` - Access requests
- `hub/apps/governance/tests/test_retention_service.py` - Retention policies
- `hub/apps/governance/tests/test_retention_api_integration.py` - Retention API

**Frontend Specs**:
- `frontend/e2e/journeys/governance-retention/governance-retention-crud.spec.ts` - Governance retention

**Use Cases**: UC-GOV-001 through UC-GOV-005, UC-GOV-ADV-001 through UC-GOV-ADV-004
**Journeys**: JOURNEY-CPO-006, JOURNEY-CPO-007, JOURNEY-CPO-008, JOURNEY-CPO-009, JOURNEY-TA-006

---

### Search

**Feature**: Full-text search across contracts, assets, datasets

**Backend Tests**:
- `hub/apps/search/tests/test_views.py` - Search views
- `hub/apps/search/tests/test_search_engine.py` - Search engine
- `hub/apps/search/tests/test_indexing.py` - Search indexing
- `hub/apps/search/tests/test_business_rules.py` - Search business rules

**Frontend Specs**:
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search routes

**Use Cases**: UC-SEARCH-001 (referenced), UC-AI-001 (natural language search)
**Journeys**: JOURNEY-DC-006, JOURNEY-DS-001, JOURNEY-DEV-005

---

### Scheduled Ingestion

**Feature**: Scheduled ingestion jobs, runs, configuration

**Backend Tests**:
- `hub/apps/scheduled_ingestion/tests/test_scheduled_ingestion_views.py` - Scheduled ingestion views
- `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py` - Worker API
- `hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py` - Prefect integration
- `hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py` - Comprehensive tests
- `tests/e2e/test_scheduled_ingestion.py` - E2E scheduled ingestion

**Frontend Specs**:
- `frontend/e2e/journeys/scheduled-ingestion/scheduled-ingestion-journey.spec.ts` - Scheduled ingestion journey

**Use Cases**: UC-INGEST-001 through UC-INGEST-004 (referenced)
**Journeys**: JOURNEY-DE-002

---

### Scheduled Export

**Feature**: Scheduled export jobs, runs, destination configuration (list/filter by status, tenant isolation, CRUD, trigger, internal worker API)

**Backend Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Scheduled export views (list, filter by status, tenant isolation, CRUD, trigger, runs)
- `hub/apps/scheduled_export/tests/test_internal_worker_api.py` - Worker API
- `hub/apps/scheduled_export/tests/test_service_and_business_rules.py` - Service and business rules
- `hub/apps/scheduled_export/tests/test_run_completion_side_effects.py` - Run completion
- `tests/integration/test_scheduled_export_apis_comprehensive.py` - Scheduled export APIs (CRUD, list and filter by status, tenant isolation, plan limits)
- `tests/e2e/test_scheduled_export.py` - E2E scheduled export

**Frontend Specs**:
- `frontend/src/features/scheduledExport/services/scheduledExportService.test.ts` - Scheduled export service (real service; axios mocked)
- `frontend/src/features/scheduledExport/hooks/useScheduledExport.test.tsx` - Scheduled export hooks (real hooks; axios mocked)
- `frontend/src/features/scheduledExport/components/ScheduledExportListPage.test.tsx` - List page (loading, error, empty, table)
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export journey

**Use Cases**: UC-EXPORT-001, UC-EXPORT-002, UC-EXPORT-003, UC-EXPORT-004
**Journeys**: JOURNEY-EXPORT-001, JOURNEY-EXPORT-002

---

### Webhooks

**Feature**: Webhook registration and delivery

**Backend Tests**:
- `hub/apps/webhooks/tests/test_webhook_service.py` - Webhook service
- `hub/apps/webhooks/tests/test_webhook_api_integration.py` - Webhook API integration

**Frontend Specs**:
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` - Webhooks routes

**Use Cases**: UC-WEBHOOK-001 (referenced)
**Journeys**: JOURNEY-DEV-001 (includes webhook integration)

---

### Audit

**Feature**: Audit event recording, querying, export

**Backend Tests**:
- `hub/apps/audit/tests/test_audit_event_querying.py` - Audit event querying
- `hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py` - ODPS audit validation

**Frontend Specs**:
- `frontend/e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts` - Audit routes

**Use Cases**: UC-AUDIT-001 (referenced)
**Journeys**: JOURNEY-AUD-001

---

### Health

**Feature**: Health checks for services and dependencies

**Backend Tests**:
- `hub/apps/health/tests/test_views.py` - Health check views
- `hub/apps/health/tests/test_services.py` - Health services
- `tests/integration/test_docker_compose.py` - Service health

**Frontend Specs**:
- Health checks typically tested in infrastructure tests

**Use Cases**: UC-AUTH-004 (public health endpoint)
**Journeys**: JOURNEY-AUTH-004

---

### Observability

**Feature**: Reliability scores, cost tracking, predictive alerts, performance regressions, lineage (see [FEATURES.md](FEATURES.md#observability))

**Backend Tests**:
- `hub/apps/observability/tests/test_views.py` - Observability views
- `hub/apps/observability/tests/test_observability_lineage_integration.py` - Observability lineage API (`GET /api/v1/observability/lineage/`); real DB and contract lineage; tenant isolation
- `hub/apps/observability/tests/test_metrics.py` - Metrics collection
- `hub/apps/observability/tests/test_services.py` - Observability services
- `hub/apps/observability/tests/test_e2e_observability.py` - E2E observability
- `tests/integration/test_prometheus_metrics.py` - Prometheus metrics
- `tests/integration/test_grafana_dashboards.py` - Grafana dashboards
- `tests/integration/test_monitoring_infrastructure.py` - Monitoring infrastructure
- `tests/e2e/test_monitoring_e2e.py` - Monitoring E2E

**Frontend Specs**:
- Covered by admin/observability routes in E2E

**Use Cases**: UC-OBS-ADV-001 through UC-OBS-ADV-004
**Journeys**: JOURNEY-DPO-014, JOURNEY-MPA-008, JOURNEY-TA-007

---

### Workflows

**Feature**: Workflow orchestration, product creation workflow, ODPS workflows, Workflows API (see [FEATURES.md](FEATURES.md#workflows))

**Backend Tests**:
- `hub/apps/orchestration/tests/test_workflows_api_integration.py` - Workflows API (`GET /api/v1/workflows/`, get by name, `POST .../trigger/`); real registry, engine, DB; tenant isolation; no mocks
- `hub/apps/orchestration/tests/test_product_creation_workflow.py` - Product creation workflow
- `hub/apps/orchestration/tests/test_odps_workflow_events.py` - ODPS workflow events
- `tests/concurrency/test_concurrent_workflows.py` - Concurrent workflows
- `tests/concurrency/test_workflow_state_management.py` - Workflow state
- `tests/e2e/test_workflow_user_journey_integration_e2e.py` - Workflow E2E

**Frontend Specs**:
- Covered by contract/ODPS and DPO journey specs

**Use Cases**: UC-DPO-014, workflow-related use cases
**Journeys**: JOURNEY-DPO-015, JOURNEY-DPO-016, JOURNEY-DPO-017, JOURNEY-DE-014

---

### Lineage

**Feature**: Contract lineage, field lineage, impact analysis (see [FEATURES.md](FEATURES.md#lineage))

**Backend Tests**:
- `hub/apps/contracts/tests/test_lineage_service.py` - Lineage service
- `hub/apps/contracts/tests/test_lineage_traversal.py` - Lineage traversal
- `hub/apps/contracts/tests/test_impact_analysis.py` - Impact analysis
- `hub/apps/contracts/tests/test_integration_lineage.py` - Integration lineage

**Frontend Specs**:
- Covered by contracts-odps and lineage visualization routes

**Use Cases**: UC-CM-007 (Define Lineage), lineage-related
**Journeys**: JOURNEY-DE-001 (contract-first), JOURNEY-DPO-005

---

### Versioning

**Feature**: Versioning API — list versions, get version, compare (see [FEATURES.md](FEATURES.md#versioning)). Phase 2 Gap Remediation implemented; reuses Contract and Dataset version data.

**Backend Tests**:
- `hub/apps/versioning/tests/test_versioning_api_integration.py` - Versioning API integration (list, get, compare; tenant isolation; real DB, no mocks)
- `hub/apps/contracts/tests/test_views.py` - Contract versioning
- `hub/apps/assets/tests/test_asset_crud.py` - Asset versioning
- `hub/apps/datasets/tests/test_versioning.py` - Dataset versioning (if exists)
- `tests/e2e/test_versioning_use_cases.py` - Versioning E2E (if exists)

**Frontend Specs**:
- Covered by contract and asset journey specs

**Use Cases**: UC-CM-006, UC-AM-006
**Journeys**: JOURNEY-DPO-003

---

### BaaS

**Feature**: Backend-as-a-Service, developer portal, API access (see [FEATURES.md](FEATURES.md#baas))

**Backend Tests**:
- `hub/apps/baas/tests/` - BaaS app tests
- `hub/apps/developer/tests/` - Developer plugins, SDK docs
- `tests/integration/test_developer_experience_new_use_cases_comprehensive.py` - UC-DEV-001…004, UC-DEV-007…009
- `tests/e2e/test_persona_dev_comprehensive.py` - Developer persona E2E

**Frontend Specs**:
- Covered by developer portal and integrations-jobs-webhooks routes

**Use Cases**: UC-DEV-001, UC-DEV-002, UC-DEV-003, UC-DEV-004, UC-DEV-007, UC-DEV-008, UC-DEV-009
**Journeys**: JOURNEY-DEV-001, JOURNEY-DEV-009

---

### Integrations

**Feature**: Connectors, BI integration, reverse ETL (see [FEATURES.md](FEATURES.md#integrations))

**Backend Tests**:
- `hub/apps/integrations/` - Integration app tests (if present)
- `tests/integration/test_developer_experience_new_use_cases_comprehensive.py` - UC-DEV-007 (connector framework API)
- `tests/e2e/test_cross_capability_e2e.py` - Cross-capability E2E
- Integration coverage in marketplace and scheduled ingestion/export tests

**Frontend Specs**:
- `frontend/e2e/journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts`

**Use Cases**: UC-INT-001 through UC-INT-005, UC-DEV-007 (connector framework)
**Journeys**: JOURNEY-DE-010, JOURNEY-DE-011, JOURNEY-TA-008

---

### Jobs

**Feature**: Job orchestration, run history, job status (see [FEATURES.md](FEATURES.md#jobs))

**Backend Tests**:
- `hub/apps/jobs/tests/` - Jobs app tests
- Scheduled ingestion/export tests cover job runs and triggers

**Frontend Specs**:
- Covered by scheduled-ingestion, scheduled-export, integrations-jobs-webhooks routes

**Use Cases**: UC-INGEST-*, UC-EXPORT-*, job-related use cases
**Journeys**: JOURNEY-DE-002, JOURNEY-EXPORT-001, JOURNEY-EXPORT-002

---

### Files

**Feature**: File storage, upload, download (see [FEATURES.md](FEATURES.md#files))

**Backend Tests**:
- `hub/apps/files/tests/` - Files app tests
- `hub/apps/assets/tests/test_asset_crud.py` - Asset file attachment
- E2E tests that upload/download files

**Frontend Specs**:
- Covered by DPO asset-creation-flow and data-first flow specs

**Use Cases**: UC-AM-001 (data upload in data-first flow)
**Journeys**: JOURNEY-DPO-001

---

### Semantic

**Feature**: Semantic layer, RDF mapping, SPARQL (see [FEATURES.md](FEATURES.md#semantic))

**Backend Tests**:
- `hub/apps/semantic/tests/` - Semantic app tests (if present)
- Contract/ODPS tests that reference semantic mapping

**Frontend Specs**:
- Covered by mesh-virtualization-search-ai and discovery routes

**Use Cases**: UC-DC-014 (Discover ODPS Products semantic search)
**Journeys**: JOURNEY-DC-014

---

### AI

**Feature**: Natural language search, schema matching, recommendations, auto-classification (see [FEATURES.md](FEATURES.md#ai))

**Backend Tests**:
- `hub/apps/ai/tests/` - AI app tests
- `tests/integration/test_ai_ml_new_use_cases_comprehensive.py` - AI/ML use cases (integration)
- Persona and journey tests covering search and recommendations

**Frontend Specs**:
- `frontend/e2e/journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` - Search/AI routes

**Use Cases**: UC-AI-001 through UC-AI-010
**Journeys**: JOURNEY-DPO-007, JOURNEY-DE-008, JOURNEY-DC-006, JOURNEY-DS-001 through JOURNEY-DS-005

---

### ML

**Feature**: ML model training, anomaly detection, recommendation engine (see [FEATURES.md](FEATURES.md#ml))

**Backend Tests**:
- `hub/apps/ml/tests/` - ML app tests (if present)
- AI/ML comprehensive E2E and persona tests

**Frontend Specs**:
- Covered by mesh-search-ai and DQ/compliance routes

**Use Cases**: UC-AI-003, UC-AI-006, UC-AI-009, UC-AI-010
**Journeys**: JOURNEY-DS-002, JOURNEY-DS-003, JOURNEY-DS-004

---

### Social

**Feature**: Ratings, reviews, communities, activity feed (see [FEATURES.md](FEATURES.md#social))

**Backend Tests**:
- `hub/apps/social/tests/` - Social app tests (if present)
- Marketplace and asset tests covering ratings/reviews

**Frontend Specs**:
- Covered by marketplace-dc and DPO journey specs (ratings, reviews)

**Use Cases**: UC-SOCIAL-001 through UC-SOCIAL-006
**Journeys**: JOURNEY-DPO-009, JOURNEY-DC-008, JOURNEY-DC-009, JOURNEY-CM-001 through JOURNEY-CM-004

---

### Data Mesh

**Feature**: Data mesh domains, federated governance, topology (see [FEATURES.md](FEATURES.md#data-mesh))

**Backend Tests**:
- `hub/apps/mesh/tests/` - Mesh app tests
- `tests/integration/test_data_mesh_new_use_cases_comprehensive.py` - Data mesh E2E (if present)

**Frontend Specs**:
- `frontend/e2e/journeys/mesh-virtualization-search-ai/` - Mesh routes

**Use Cases**: UC-MESH-001 through UC-MESH-005, UC-DMO-001 through UC-DMO-005
**Journeys**: JOURNEY-DPO-013, JOURNEY-DE-013, JOURNEY-TA-005, JOURNEY-DMO-001 through JOURNEY-DMO-005, JOURNEY-MPA-007

---

### Virtualization

**Feature**: Virtual datasets, federated query, federation topology (see [FEATURES.md](FEATURES.md#virtualization))

**Backend Tests**:
- `hub/apps/virtualization/tests/test_views.py` - Virtualization views
- `hub/apps/virtualization/tests/test_services.py` - Virtualization services
- `hub/apps/virtualization/tests/test_models.py` - Virtualization models
- `hub/apps/webhooks/tests/test_virtualization_webhook_e2e.py` - Virtualization webhooks E2E

**Frontend Specs**:
- `frontend/e2e/journeys/mesh-virtualization-search-ai/` - Virtualization routes

**Use Cases**: UC-VIRT-001 through UC-VIRT-004, UC-DA-003, UC-DA-004
**Journeys**: JOURNEY-DE-009, JOURNEY-DC-010, JOURNEY-DA-003, JOURNEY-DA-004

---

### Supporting Capabilities

**Feature**: Notifications, Billing, Platform, Tenants, Users, Analytics, Events (see [FEATURES.md](FEATURES.md#supporting-capabilities))

These capabilities support core features rather than being standalone product features. Traceability is covered via the features that use them:

| Capability | Covered by (features / tests) |
|------------|-------------------------------|
| Notifications | Compliance, Governance, Jobs (alerts; notification tests where present) |
| Billing | Marketplace, ODPS pricing (Phase 25 billing tests) |
| Platform | BaaS, Auth, tenant isolation tests |
| Tenants | BaaS, Auth, `tests/integration/test_tenant_isolation.py` |
| Users | Auth, BaaS, user/role tests |
| Analytics | Governance (access analytics), Observability, Marketplace |
| Events | Audit, Webhooks, Event Bus, lineage/contract events |

**Use Cases**: Referenced in UC-AUTH-*, UC-DC-011, UC-MKT-ADV-*, UC-GOV-ADV-*, Phase 25 use cases
**Journeys**: Auth, DPO, TA, PA, Auditor journeys; JOURNEY-EXPORT-*, scheduled ingestion/export

---

## Use Case → Test Mapping

This section maps each use case from [USE_CASES.md](USE_CASES.md) to its corresponding backend and frontend tests.

### Authentication & Access Use Cases

#### UC-AUTH-001: User Registers (Self-Service Sign-Up)

**Backend Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Registration flow
- `tests/integration/test_tenant_isolation.py` - Tenant assignment

**Frontend Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration journey

**Journey**: JOURNEY-AUTH-001

---

#### UC-AUTH-002: User Logs In

**Backend Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Login flow
- `hub/apps/auth/tests/test_sessions.py` - Session creation

**Frontend Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login journey

**Journey**: JOURNEY-AUTH-002

---

#### UC-AUTH-003: User Resets Password

**Backend Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Password reset flow

**Frontend Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset journey

**Journey**: JOURNEY-AUTH-003

---

#### UC-AUTH-004: Unauthenticated User Accesses Public Resources

**Backend Tests**:
- `tests/security/test_allowany_public_endpoints.py` - Public endpoint access

**Frontend Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access journey

**Journey**: JOURNEY-AUTH-004

---

### Asset Management Use Cases

#### UC-AM-001: Create Asset via Data-First Flow

**Backend Tests**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset creation
- `hub/apps/assets/tests/test_services.py` - Asset service

**Frontend Specs**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts` - Data-first flow journey
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation flow

**Journey**: JOURNEY-DPO-001

---

#### UC-AM-002: Publish Asset to Marketplace

**Backend Tests**:
- `hub/apps/marketplace/tests/test_views.py` - Marketplace publishing
- `hub/apps/marketplace/tests/test_services.py` - Marketplace service

**Frontend Specs**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts` - Marketplace publishing journey
- `frontend/e2e/phase4-marketplace-journey.spec.ts` - Marketplace journey

**Journey**: JOURNEY-DPO-002

---

### Scheduled Export Use Cases

#### UC-EXPORT-001: Schedule Recurring Export

**Backend Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Scheduled export creation
- `hub/apps/scheduled_export/tests/test_service_and_business_rules.py` - Service and business rules

**Frontend Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export journey

**Journey**: JOURNEY-EXPORT-001

---

#### UC-EXPORT-002: Configure Export Destination

**Backend Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Destination configuration
- `services/prefect-integration/tests/test_scheduled_export_flow.py` - Prefect flow

**Frontend Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Export configuration

**Journey**: JOURNEY-EXPORT-001

---

#### UC-EXPORT-003: Monitor Export Runs

**Backend Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Run monitoring
- `hub/apps/scheduled_export/tests/test_run_completion_side_effects.py` - Run completion

**Frontend Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Run monitoring

**Journey**: JOURNEY-EXPORT-002

---

#### UC-EXPORT-004: Manual Trigger of Scheduled Export

**Backend Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Manual trigger endpoint

**Frontend Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Manual trigger

**Journey**: JOURNEY-EXPORT-001

---

*Note: Additional use cases are mapped in the full document. This is a representative sample.*

**Use Case Coverage Index** (all use cases have test coverage documented via Feature or Use Case sections above): UC-AUTH-001, UC-AUTH-002, UC-AUTH-003, UC-AUTH-004, UC-AM-001, UC-AM-002, UC-AI-001, UC-AI-002, UC-AI-003, UC-AI-004, UC-AI-005, UC-AI-006, UC-AI-007, UC-AI-008, UC-AI-009, UC-AI-010, UC-SOCIAL-001, UC-SOCIAL-002, UC-SOCIAL-003, UC-SOCIAL-004, UC-SOCIAL-005, UC-SOCIAL-006, UC-MESH-001, UC-MESH-002, UC-MESH-003, UC-MESH-004, UC-MESH-005, UC-VIRT-001, UC-VIRT-002, UC-VIRT-003, UC-VIRT-004, UC-MKT-ADV-001, UC-MKT-ADV-002, UC-MKT-ADV-003, UC-MKT-ADV-004, UC-MKT-ADV-005, UC-GOV-ADV-001, UC-GOV-ADV-002, UC-GOV-ADV-002A, UC-GOV-ADV-003, UC-GOV-ADV-004, UC-OBS-ADV-001, UC-OBS-ADV-002, UC-OBS-ADV-003, UC-OBS-ADV-004, UC-INT-001, UC-INT-002, UC-INT-003, UC-INT-004, UC-INT-005, UC-DEV-001, UC-DEV-002, UC-DEV-003, UC-DEV-004, UC-DEV-007, UC-DEV-008, UC-DEV-009, UC-CM-001, UC-CM-002, UC-CM-003, UC-CM-004, UC-COMP-001, UC-CPO-006, UC-CPO-007, UC-CPO-008, UC-CPO-009, UC-CPO-010, UC-DA-003, UC-DA-004, UC-DC-001, UC-DC-006, UC-DC-008, UC-DC-011, UC-DC-012, UC-DC-013, UC-DE-005, UC-DE-009, UC-DE-010, UC-DE-011, UC-DE-012, UC-DMO-001, UC-DMO-002, UC-DMO-003, UC-DMO-005, UC-DPO-002, UC-DPO-010, UC-DPO-014, UC-DQ-001, UC-EXPORT-001, UC-EXPORT-002, UC-EXPORT-003, UC-EXPORT-004, UC-TA-007, UC-TA-008.

---

## User Journey → Test Mapping

This section maps each user journey from [USER_JOURNEYS.md](USER_JOURNEYS.md) to its corresponding backend e2e tests and Playwright specs.

### Visitor / Authentication Journeys

#### JOURNEY-AUTH-001: First-Time Visitor Registers

**Backend E2E Tests**:
- `tests/integration/test_tenant_isolation.py` - Tenant creation during registration
- `hub/apps/auth/tests/test_authentication.py` - Registration API

**Playwright Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` - Registration journey

**Use Case**: UC-AUTH-001

---

#### JOURNEY-AUTH-002: User Logs In

**Backend E2E Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Login API
- `hub/apps/auth/tests/test_sessions.py` - Session management

**Playwright Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts` - Login journey

**Use Case**: UC-AUTH-002

---

#### JOURNEY-AUTH-003: User Resets Password

**Backend E2E Tests**:
- `hub/apps/auth/tests/test_authentication.py` - Password reset API

**Playwright Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts` - Password reset journey

**Use Case**: UC-AUTH-003

---

#### JOURNEY-AUTH-004: Unauthenticated User Accesses Public Resources

**Backend E2E Tests**:
- `tests/security/test_allowany_public_endpoints.py` - Public endpoint access

**Playwright Specs**:
- `frontend/e2e/journeys/auth/JOURNEY-AUTH-004.spec.ts` - Public access journey

**Use Case**: UC-AUTH-004

---

### Data Product Owner Journeys

#### JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Backend E2E Tests**:
- `hub/apps/assets/tests/test_asset_crud.py` - Asset creation
- `hub/apps/datasets/tests/test_views.py` - Dataset attachment
- `tests/e2e/test_business_rules_validation_real_scenarios_e2e.py` - Business rules validation

**Playwright Specs**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts` - Data-first flow journey
- `frontend/e2e/journeys/dpo/asset-creation-flow.spec.ts` - Asset creation flow

**Use Cases**: UC-AM-001, UC-DQ-001, UC-COMP-001

---

#### JOURNEY-DPO-002: Publish Asset to Marketplace

**Backend E2E Tests**:
- `hub/apps/marketplace/tests/test_views.py` - Marketplace publishing
- `hub/apps/marketplace/tests/test_kyc_enforcement.py` - KYC enforcement

**Playwright Specs**:
- `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts` - Marketplace publishing journey
- `frontend/e2e/phase4-marketplace-journey.spec.ts` - Marketplace journey

**Use Cases**: UC-AM-002, UC-MKT-001

---

### Scheduled Export Journeys

#### JOURNEY-EXPORT-001: Create and Run Scheduled Export

**Backend E2E Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Scheduled export creation and triggering
- `hub/apps/scheduled_export/tests/test_internal_worker_api.py` - Worker API
- `tests/e2e/test_scheduled_export.py` - E2E scheduled export

**Playwright Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Scheduled export journey

**Use Cases**: UC-EXPORT-001, UC-EXPORT-002, UC-EXPORT-004

---

#### JOURNEY-EXPORT-002: Monitor and Troubleshoot Export Runs

**Backend E2E Tests**:
- `hub/apps/scheduled_export/tests/test_views.py` - Run monitoring
- `hub/apps/scheduled_export/tests/test_run_completion_side_effects.py` - Run completion and side effects

**Playwright Specs**:
- `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts` - Run monitoring

**Use Cases**: UC-EXPORT-003

---

### Data Engineer Journeys

JOURNEY-DE-001 … JOURNEY-DE-014 are covered by Backend E2E in `tests/e2e/`, `hub/apps/contracts/`, `hub/apps/orchestration/`, `hub/apps/scheduled_ingestion/`, `hub/apps/integrations/`, and related app tests (see [Feature → Test Mapping](#feature--test-mapping)). Frontend: `frontend/e2e/journeys/contracts-odps/`, `scheduled-ingestion/`, `integrations-jobs-webhooks/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Compliance & Privacy Officer Journeys

JOURNEY-CPO-001 … JOURNEY-CPO-010 are covered by Backend E2E in `hub/apps/compliance/tests/`, `hub/apps/governance/tests/`, `hub/apps/gdpr/tests/`. Frontend: `frontend/e2e/journeys/dq-compliance-governance/`, `governance-retention/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Data Consumer Journeys

JOURNEY-DC-001 … JOURNEY-DC-015 are covered by Backend E2E in `hub/apps/marketplace/tests/`, `hub/apps/assets/tests/`, `hub/apps/search/tests/`, and related app tests. Frontend: `frontend/e2e/journeys/marketplace-dc/`, `mesh-virtualization-search-ai/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Tenant Admin Journeys

JOURNEY-TA-001 … JOURNEY-TA-008 are covered by Backend E2E in `hub/apps/tenants/tests/`, `hub/apps/auth/tests/`, governance and integration app tests. Frontend: `frontend/e2e/journeys/admin-audit-settings/`, `governance-retention/`, `integrations-jobs-webhooks/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Platform Admin Journeys

JOURNEY-PA-001, JOURNEY-PA-010 and JOURNEY-MPA-005 … JOURNEY-MPA-009 are covered by Backend E2E in `hub/apps/tenants/tests/`, marketplace operator and ODPS management tests, Phase 25. Frontend: admin/PA routes, `integrations-jobs-webhooks/`, `mesh-virtualization-search-ai/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### External Developer Journeys

JOURNEY-DEV-001 … JOURNEY-DEV-009 are covered by Backend E2E in `hub/apps/baas/tests/`, `hub/apps/webhooks/tests/`, `hub/apps/integrations/tests/`. Frontend: `frontend/e2e/journeys/integrations-jobs-webhooks/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Auditor Journeys

JOURNEY-AUD-001 … JOURNEY-AUD-006 are covered by Backend E2E in `hub/apps/audit/tests/`, governance and mesh audit tests. Frontend: `frontend/e2e/journeys/admin-audit-settings/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Data Scientist Journeys

JOURNEY-DS-001 … JOURNEY-DS-005 are covered by Backend E2E in `hub/apps/ai/tests/`, `hub/apps/ml/tests/`, `hub/apps/dq/tests/`. Frontend: `frontend/e2e/journeys/mesh-virtualization-search-ai/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Data Analyst Journeys

JOURNEY-DA-001 … JOURNEY-DA-004 are covered by Backend E2E in virtualization, search, and transformation-related tests. Frontend: `frontend/e2e/journeys/mesh-virtualization-search-ai/`. See [Complete User Journey Index](#complete-user-journey-index).

---

### Community Manager Journeys

JOURNEY-CM-001 … JOURNEY-CM-004 are covered by Backend E2E in `hub/apps/social/tests/`, `hub/apps/governance/tests/`. Frontend: marketplace-dc, social routes. See [Complete User Journey Index](#complete-user-journey-index).

---

### Data Mesh Domain Owner Journeys

JOURNEY-DMO-001 … JOURNEY-DMO-005 are covered by Backend E2E in `hub/apps/mesh/tests/`. Frontend: `frontend/e2e/journeys/mesh-virtualization-search-ai/`. See [Complete User Journey Index](#complete-user-journey-index).

---

*Note: Detailed journey mappings appear above. For a single index of all 96 journeys and their test references, see [Complete User Journey Index](#complete-user-journey-index).*

---

## Persona → Test Mapping

This section maps each persona from [USER_PERSONAS.md](USER_PERSONAS.md) to their corresponding tests. Every persona has test coverage via auth journeys (Visitor), persona E2E tests, or feature/journey tests that exercise that role.

| Persona | Test Coverage |
|----------|---------------|
| **Visitor / Prospect** | Auth tests: `hub/apps/auth/tests/test_authentication.py`, `test_sessions.py`; E2E: `tests/e2e/test_authentication.py`; Frontend: `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts` through `JOURNEY-AUTH-004.spec.ts`; Public endpoints: `tests/security/test_allowany_public_endpoints.py`. |
| **Data Product Owner** | Persona E2E: `tests/e2e/test_persona_dpo_comprehensive.py`; Backend: assets, contracts, marketplace, DQ, compliance tests; Frontend: `frontend/e2e/journeys/dpo/*`, asset-creation-flow, contract-creation-flow, JOURNEY-DPO-001/002, scheduled-export. |
| **Data Engineer / Contract Author** | Persona E2E: `tests/e2e/test_persona_data_engineer_comprehensive.py`; Backend: contracts, orchestration, scheduled ingestion/export, lineage tests; Frontend: contract/ODPS journeys, JOURNEY-DE-* specs. |
| **Compliance & Privacy Officer** | Persona E2E: `tests/e2e/test_persona_cpo_comprehensive.py`; Backend: `hub/apps/compliance/tests/`, governance, GDPR tests; Frontend: dq-compliance-governance routes, JOURNEY-CPO-* specs. |
| **Data Consumer / Buyer** | Persona E2E: `tests/e2e/test_persona_dc_comprehensive.py`; Backend: marketplace, assets, search tests; Frontend: marketplace-dc routes, JOURNEY-DC-* specs. |
| **Tenant Admin** | Persona E2E: `tests/e2e/test_persona_ta_comprehensive.py`; Backend: tenants, auth (invite), plan limits, usage tests; Frontend: admin/tenant routes, JOURNEY-TA-* specs. |
| **Platform Admin / Marketplace Operator** | Persona E2E: `tests/e2e/test_persona_pa_comprehensive.py`; Backend: tenants, marketplace operator, ODPS management tests; Frontend: admin/PA routes, JOURNEY-PA-*, JOURNEY-MPA-* specs. |
| **External Developer / Integrator** | Persona E2E: `tests/e2e/test_persona_dev_comprehensive.py`; Backend: BaaS, webhooks, API, integrations tests; Frontend: integrations-jobs-webhooks, developer portal routes, JOURNEY-DEV-* specs. |
| **Auditor** | Persona E2E: `tests/e2e/test_persona_aud_comprehensive.py`; Backend: `hub/apps/audit/tests/`; Frontend: admin-audit-settings routes, JOURNEY-AUD-* specs. |
| **Data Scientist / ML Engineer** | E2E: `tests/e2e/test_new_user_journeys_comprehensive.py`, AI/ML use cases; Backend: AI, ML, DQ tests; Frontend: mesh-search-ai routes, JOURNEY-DS-* specs. |

**Failure paths and edge cases (Task 6.5)**: `tests/e2e/test_persona_failure_paths_comprehensive.py` — 401, 403, 404, 400 per persona; service-unavailable (DQ/Compliance); cross-tenant isolation.
| **Data Analyst** | E2E: new user journeys, virtualization/transformation flows; Backend: search, virtualization, transformation tests; Frontend: JOURNEY-DA-* specs. |
| **Community Manager / Data Steward** | E2E: social and governance journeys; Backend: social, governance, asset steward tests; Frontend: JOURNEY-CM-* specs. |
| **Data Mesh Domain Owner** | E2E: data mesh and topology journeys; Backend: `hub/apps/mesh/tests/`; Frontend: mesh-virtualization-search-ai routes, JOURNEY-DMO-* specs. |

All 13 personas (Visitor / Prospect plus 12 role-based) have test coverage documented above. See [USER_PERSONAS.md](USER_PERSONAS.md) for persona details and [E2E_TEST_GAP_ANALYSIS.md](../openspec/changes/testreview1/E2E_TEST_GAP_ANALYSIS.md) for journey-to-test mapping.

---

## UC/Journey/Persona E2E Tests (Task 6.7)

Backend E2E tests tagged with `uc_journey_persona` (equivalent to `uc or journey or persona`). Run via `./scripts/run_uc_journey_persona_tests.sh` or `pytest tests/e2e/ -v -m uc_journey_persona`. See [UC_JOURNEY_TEST_RUN_GUIDE.md](UC_JOURNEY_TEST_RUN_GUIDE.md) for prerequisites, duration, and interpreting results.

**Backend E2E Test Files** (17 files):

| Test File | Use Cases | Journeys | Personas |
|-----------|-----------|----------|----------|
| `tests/e2e/test_authentication.py` | UC-AUTH-001 … UC-AUTH-004 | JOURNEY-AUTH-001 … JOURNEY-AUTH-004 | Visitor |
| `tests/e2e/test_persona_dpo_comprehensive.py` | — | JOURNEY-DPO-001 … JOURNEY-DPO-006 | Data Product Owner |
| `tests/e2e/test_persona_data_engineer_comprehensive.py` | — | JOURNEY-DE-001 … JOURNEY-DE-006 | Data Engineer |
| `tests/e2e/test_persona_cpo_comprehensive.py` | — | JOURNEY-CPO-001 … JOURNEY-CPO-005 | Compliance Officer |
| `tests/e2e/test_persona_dc_comprehensive.py` | — | JOURNEY-DC-001 … JOURNEY-DC-005 | Data Consumer |
| `tests/e2e/test_persona_ta_comprehensive.py` | — | JOURNEY-TA-001 … JOURNEY-TA-004 | Tenant Admin |
| `tests/e2e/test_persona_pa_comprehensive.py` | — | JOURNEY-PA-001, JOURNEY-MPA-001 … JOURNEY-MPA-004 | Platform Admin, Marketplace Platform Admin |
| `tests/e2e/test_persona_dev_comprehensive.py` | — | JOURNEY-DEV-001 … JOURNEY-DEV-004 | External Developer |
| `tests/e2e/test_persona_aud_comprehensive.py` | — | JOURNEY-AUD-001 … JOURNEY-AUD-003 | Auditor |
| `tests/e2e/test_user_journeys_comprehensive.py` | — | JOURNEY-DPO-001 … JOURNEY-AUD-003 | All 9 role personas |
| `tests/e2e/test_new_user_journeys_comprehensive.py` | — | JOURNEY-DPO-007 … JOURNEY-AUD-004 | DPO, DE, CPO, DC, TA, DEV, AUD |
| `tests/e2e/test_persona_failure_paths_comprehensive.py` | — | — | All 9 role personas (failure paths) |
| `tests/e2e/test_enhanced_journeys_with_odps.py` | — | JOURNEY-DPO-001, JOURNEY-DPO-002, JOURNEY-DE-001 | DPO, DE, DC |
| `tests/e2e/test_enhanced_use_cases_with_odps.py` | UC-AM-001, UC-CM-001, UC-MKT-001, UC-MKT-002, UC-DC-001 | — | — |
| `tests/e2e/test_workflow_use_case_integration_e2e.py` | UC-AM-001, UC-CM-001, UC-MKT-001, UC-DQ-001, UC-COMP-001 | — | — |
| `tests/e2e/test_workflow_user_journey_integration_e2e.py` | — | JOURNEY-DPO-001, JOURNEY-DPO-002, JOURNEY-DPO-015, JOURNEY-DE-001, JOURNEY-DE-014 | — |
| `tests/e2e/test_odps_journeys_comprehensive.py` | — | JOURNEY-ODPS-001 … JOURNEY-ODPS-005 | — |

**Artifacts**: `test_reports_comprehensive/{date}/uc_journey_persona/` (JUnit XML, log). Included in Phase 12A.1.3b via `run_phase_12a_backend_suites.sh`.

---

## Complete Use Case Index

All **~109 use cases** from [USE_CASES.md](USE_CASES.md) mapped to feature sections and tests. Each row points to the [Feature → Test Mapping](#feature--test-mapping) or [Use Case → Test Mapping](#use-case--test-mapping) section that documents coverage.

| Use Case ID | Category | Test Reference (Backend / Frontend) |
|-------------|----------|--------------------------------------|
| UC-AUTH-001 … UC-AUTH-004 | Auth & Access | [Auth](#auth), [UC-AUTH-001–004](#authentication--access-use-cases) |
| UC-AM-001, UC-AM-002 | Asset Management | [Assets](#assets), [Marketplace](#marketplace) |
| UC-AI-001 … UC-AI-010 | AI/ML | [AI](#ai), [ML](#ml), [Search](#search) |
| UC-SOCIAL-001 … UC-SOCIAL-006 | Social | [Social](#social) |
| UC-MESH-001 … UC-MESH-005 | Data Mesh | [Data Mesh](#data-mesh) |
| UC-VIRT-001 … UC-VIRT-004 | Virtualization | [Virtualization](#virtualization) |
| UC-MKT-ADV-001 … UC-MKT-ADV-005 | Advanced Marketplace | [Marketplace](#marketplace) |
| UC-GOV-ADV-001 … UC-GOV-ADV-004, UC-GOV-ADV-002A | Advanced Governance | [Governance](#governance), [Phase 25 GDPR](#gdpr-and-data-subject-rights) |
| UC-OBS-ADV-001 … UC-OBS-ADV-004 | Advanced Observability | [Observability](#observability) |
| UC-INT-001 … UC-INT-005 | Integration Ecosystem | [Integrations](#integrations) |
| UC-DEV-001 … UC-DEV-004, UC-DEV-007, UC-DEV-008, UC-DEV-009 | Developer Experience | [BaaS](#baas), [Phase 26 CLI/SDK](#phase-26-clisdk-traceability) |
| UC-CM-001 … UC-CM-004 | Community | [Social](#social), [Governance](#governance) |
| UC-COMP-001 | Compliance | [Compliance](#compliance) |
| UC-CPO-006 … UC-CPO-010 | Compliance/Privacy | [Governance](#governance), [Phase 25 GDPR](#gdpr-and-data-subject-rights) |
| UC-DA-003, UC-DA-004 | Data Analyst | [Virtualization](#virtualization) |
| UC-DC-001, UC-DC-006, UC-DC-008, UC-DC-011, UC-DC-012, UC-DC-013 | Data Consumer | [Marketplace](#marketplace), [Search](#search), [AI](#ai), [Social](#social) |
| UC-DE-005, UC-DE-009, UC-DE-010, UC-DE-011, UC-DE-012 | Data Engineer | [Integrations](#integrations), [Virtualization](#virtualization), [BaaS](#baas) |
| UC-DMO-001, UC-DMO-002, UC-DMO-003, UC-DMO-005 | Data Mesh Domain Owner | [Data Mesh](#data-mesh) |
| UC-DPO-002, UC-DPO-010, UC-DPO-014 | Data Product Owner | [Marketplace](#marketplace), [ODPS](#odps-open-data-product-standard) |
| UC-DQ-001 | Data Quality | [Data Quality](#data-quality) |
| UC-EXPORT-001 … UC-EXPORT-004 | Scheduled Export | [Scheduled Export](#scheduled-export) |
| UC-TA-007, UC-TA-008 | Tenant Admin | [Observability](#observability), [Integrations](#integrations) |

*Contract Management (UC-CM-001–007), ODPS, Ingestion, Webhook, Audit use cases are covered under [Contracts](#contracts), [ODPS](#odps-open-data-product-standard), [Scheduled Ingestion](#scheduled-ingestion), [Webhooks](#webhooks), [Audit](#audit). Phase 25 use cases (Billing, Tenant, GDPR, API versioning) under [Phase 25](#phase-25-saas-platform-traceability).*

---

## Complete User Journey Index

All **96 user journeys** from [USER_JOURNEYS.md](USER_JOURNEYS.md) and [MARKETPLACE_USER_JOURNEYS.md](MARKETPLACE_USER_JOURNEYS.md) mapped to Backend E2E and Frontend E2E/Playwright. Detailed mappings appear in [User Journey → Test Mapping](#user-journey--test-mapping).

| Journey ID range | Persona | Test Reference |
|------------------|---------|-----------------|
| JOURNEY-AUTH-001 … JOURNEY-AUTH-004 | Visitor | [Auth journeys](#authentication-journeys), `frontend/e2e/journeys/auth/*.spec.ts` |
| JOURNEY-DPO-001 … JOURNEY-DPO-017 | Data Product Owner | [DPO journeys](#data-product-owner-journeys), `frontend/e2e/journeys/dpo/*.spec.ts` |
| JOURNEY-DE-001 … JOURNEY-DE-014 | Data Engineer | [DE journeys](#data-engineer-journeys), scheduled-ingestion, integrations-jobs-webhooks, contracts-odps |
| JOURNEY-CPO-001 … JOURNEY-CPO-010 | Compliance Officer | [CPO journeys](#compliance--privacy-officer-journeys), dq-compliance-governance, governance-retention |
| JOURNEY-DC-001 … JOURNEY-DC-015 | Data Consumer | [DC journeys](#data-consumer-journeys), marketplace-dc, mesh-virtualization-search-ai |
| JOURNEY-TA-001 … JOURNEY-TA-008 | Tenant Admin | [TA journeys](#tenant-admin-journeys), admin-audit-settings, governance-retention |
| JOURNEY-PA-001, JOURNEY-PA-010 | Platform Admin | [PA/MPA journeys](#platform-admin-journeys), Phase 25 |
| JOURNEY-MPA-005 … JOURNEY-MPA-009 | Platform Admin | integrations-jobs-webhooks, mesh-virtualization-search-ai, admin |
| JOURNEY-DEV-001 … JOURNEY-DEV-009 | External Developer | [Developer journeys](#external-developer-journeys), integrations-jobs-webhooks |
| JOURNEY-AUD-001 … JOURNEY-AUD-006 | Auditor | [Auditor journeys](#auditor-journeys), admin-audit-settings |
| JOURNEY-DS-001 … JOURNEY-DS-005 | Data Scientist | [DS journeys](#data-scientist-journeys), mesh-virtualization-search-ai |
| JOURNEY-DA-001 … JOURNEY-DA-004 | Data Analyst | [DA journeys](#data-analyst-journeys), mesh-virtualization-search-ai |
| JOURNEY-CM-001 … JOURNEY-CM-004 | Community Manager | [CM journeys](#community-manager-journeys), marketplace-dc, social |
| JOURNEY-DMO-001 … JOURNEY-DMO-005 | Data Mesh Domain Owner | [DMO journeys](#data-mesh-domain-owner-journeys), mesh-virtualization-search-ai |
| JOURNEY-EXPORT-001, JOURNEY-EXPORT-002 | Export | [Scheduled Export journeys](#scheduled-export-journeys), `frontend/e2e/journeys/scheduled-export/*` |
| JOURNEY-MP-001 … JOURNEY-MP-007 | Marketplace | [MARKETPLACE_USER_JOURNEYS.md](MARKETPLACE_USER_JOURNEYS.md), marketplace-dc routes |

*Backend E2E: `tests/e2e/*.py`. Frontend E2E: `frontend/e2e/**/*.spec.ts`. See [Test Coverage Summary](#test-coverage-summary) for counts.*

---

## Phase 25 (SaaS Platform) Traceability

### Billing and Subscription

**Feature**: Subscription management, Stripe integration, invoices

**Backend Tests**:
- `hub/apps/billing/tests/test_subscription_integration.py` - Subscription integration tests
- `hub/apps/billing/tests/test_views.py` - Billing views (if exists)
- `hub/apps/tenants/tests/test_plan_limit_enforcement_comprehensive.py` - Plan limit enforcement

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestBillingCLI` - Billing CLI commands

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestBillingSDK` - Billing SDK methods

**Use Cases**: UC-BILLING-001 through UC-BILLING-005 (referenced in Phase 25)
**Journeys**: JOURNEY-TA-007 (cost tracking)

---

### Tenant Lifecycle and Self-Service

**Feature**: Tenant onboarding, plan limits, tenant suspension

**Backend Tests**:
- `hub/apps/tenants/tests/test_plan_limit_enforcement_comprehensive.py` - Plan limit enforcement
- `hub/apps/tenants/tests/test_plan_limit_service.py` - Plan limit service
- `hub/apps/tenants/tests/test_models.py` - Tenant models

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestTenantsCLI` - Tenants CLI commands

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestTenantsSDK` - Tenants SDK methods

**Use Cases**: UC-TENANT-001 through UC-TENANT-005 (referenced in Phase 25)
**Journeys**: JOURNEY-TA-001 (onboard user), JOURNEY-PA-001 (onboard tenant)

---

### GDPR and Data Subject Rights

**Feature**: Data portability, erasure workflow, consent tracking

**Backend Tests**:
- `hub/apps/gdpr/tests/test_erasure_integration.py` - Erasure integration tests
- `hub/apps/gdpr/tests/test_gdpr_services.py` - GDPR services (erasure, data portability)

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestGDPRCLI` - GDPR CLI commands

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestGDPRSDK` - GDPR SDK methods

**Use Cases**: UC-GOV-ADV-002 (GDPR Right to be Forgotten), UC-GOV-ADV-002A (Data Portability)
**Journeys**: JOURNEY-CPO-007 (GDPR Right to be Forgotten)

---

### API Versioning

**Feature**: API version headers, deprecation policy

**Backend Tests**:
- `hub/apps/api/tests/test_versioning_headers.py` - API versioning headers

**Use Cases**: UC-API-VERSION-001 (referenced in Phase 25)
**Journeys**: N/A (infrastructure feature)

---

## Phase 26 (CLI/SDK) Traceability

### Scheduled Ingestion CLI/SDK

**CLI Commands**:
- `datahub scheduled-ingestion list`
- `datahub scheduled-ingestion get`
- `datahub scheduled-ingestion create`
- `datahub scheduled-ingestion update`
- `datahub scheduled-ingestion trigger`
- `datahub scheduled-ingestion runs`
- `datahub scheduled-ingestion run-detail`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestScheduledIngestionCLI`

**SDK Methods**:
- `ScheduledIngestionAPI.list()`
- `ScheduledIngestionAPI.get()`
- `ScheduledIngestionAPI.create()`
- `ScheduledIngestionAPI.update()`
- `ScheduledIngestionAPI.trigger()`
- `ScheduledIngestionAPI.get_run_history()`
- `ScheduledIngestionAPI.get_run()`

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestScheduledIngestionSDK` (if exists)

**Backend Feature**: Scheduled Ingestion
**Use Cases**: UC-INGEST-001 through UC-INGEST-004
**Journeys**: JOURNEY-DE-002

---

### Scheduled Export CLI/SDK

**CLI Commands**:
- `datahub scheduled-export list`
- `datahub scheduled-export get`
- `datahub scheduled-export create`
- `datahub scheduled-export update`
- `datahub scheduled-export trigger`
- `datahub scheduled-export runs`
- `datahub scheduled-export run-detail`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestScheduledExportCLI`

**SDK Methods**:
- `ScheduledExportAPI.list()`
- `ScheduledExportAPI.get()`
- `ScheduledExportAPI.create()`
- `ScheduledExportAPI.update()`
- `ScheduledExportAPI.trigger()`
- `ScheduledExportAPI.get_run_history()`
- `ScheduledExportAPI.get_run()`

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestScheduledExportSDK`

**Backend Feature**: Scheduled Export
**Use Cases**: UC-EXPORT-001, UC-EXPORT-002, UC-EXPORT-003, UC-EXPORT-004
**Journeys**: JOURNEY-EXPORT-001, JOURNEY-EXPORT-002

---

### Webhooks CLI/SDK

**CLI Commands**:
- `datahub webhooks list`
- `datahub webhooks get`
- `datahub webhooks create`
- `datahub webhooks update`
- `datahub webhooks delete`
- `datahub webhooks event-types`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestWebhooksCLI`

**Backend Feature**: Webhooks
**Use Cases**: UC-WEBHOOK-001

---

### Audit CLI/SDK

**CLI Commands**:
- `datahub audit query`
- `datahub audit get`
- `datahub audit export`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestAuditCLI`

**Backend Feature**: Audit
**Use Cases**: UC-AUDIT-001
**Journeys**: JOURNEY-AUD-001

---

### Health CLI

**CLI Commands**:
- `datahub health check`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestHealthCLI`

**Backend Feature**: Health
**Use Cases**: UC-AUTH-004
**Journeys**: JOURNEY-AUTH-004

---

### Billing CLI/SDK (Phase 25)

**CLI Commands**:
- `datahub billing subscription`
- `datahub billing invoices`
- `datahub billing invoice`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestBillingCLI`

**SDK Methods**:
- `BillingAPI.get_subscription()`
- `BillingAPI.list_invoices()`
- `BillingAPI.get_invoice()`

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestBillingSDK`

**Backend Feature**: Billing (Phase 25)
**Use Cases**: UC-BILLING-001 through UC-BILLING-005

---

### Tenants CLI/SDK (Phase 25)

**CLI Commands**:
- `datahub tenants usage`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestTenantsCLI`

**SDK Methods**:
- `TenantsAPI.get_usage()`

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestTenantsSDK`

**Backend Feature**: Tenant Usage (Phase 25)
**Use Cases**: UC-TENANT-004
**Journeys**: JOURNEY-TA-007

---

### GDPR CLI/SDK (Phase 25)

**CLI Commands**:
- `datahub gdpr export-data`
- `datahub gdpr export-jobs`
- `datahub gdpr request-erasure`
- `datahub gdpr erasure-requests`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestGDPRCLI`

**SDK Methods**:
- `GDPRAPI.request_export()`
- `GDPRAPI.list_export_jobs()`
- `GDPRAPI.get_export_job()`
- `GDPRAPI.request_erasure()`
- `GDPRAPI.list_erasure_requests()`
- `GDPRAPI.get_erasure_request()`

**SDK Tests**:
- `sdk/python/tests/test_phase26_sdk_integration.py::TestGDPRSDK`

**Backend Feature**: GDPR (Phase 25)
**Use Cases**: UC-GOV-ADV-002, UC-GOV-ADV-002A
**Journeys**: JOURNEY-CPO-007

---

### Search CLI/SDK

**CLI Commands**:
- `datahub search search`
- `datahub search suggestions`
- `datahub search analytics`

**CLI Tests**:
- `cli/tests/integration/test_phase26_cli_integration.py::TestSearchCLI`

**Backend Feature**: Search
**Use Cases**: UC-SEARCH-001, UC-AI-001
**Journeys**: JOURNEY-DC-006, JOURNEY-DS-001, JOURNEY-DEV-005

---

## Test Coverage Summary

### Backend Test Coverage

**Unit Tests**: ~500+ test files across all apps
**Integration Tests**: ~100+ integration test files
**E2E Tests**: ~50+ e2e test files

**Coverage by Feature**:
- ✅ Auth: Comprehensive
- ✅ Contracts: Comprehensive
- ✅ ODPS: Comprehensive
- ✅ Assets: Comprehensive
- ✅ Datasets: Good
- ✅ Data Quality: Good
- ✅ Compliance: Good
- ✅ Marketplace: Comprehensive
- ✅ Governance: Good
- ✅ Search: Good
- ✅ Scheduled Ingestion: Comprehensive
- ✅ Scheduled Export: Comprehensive
- ✅ Webhooks: Good
- ✅ Audit: Good
- ✅ Health: Basic
- ✅ Phase 25 (SaaS): Comprehensive
- ✅ Phase 26 (CLI/SDK): Comprehensive

### Frontend Test Coverage

**Playwright Specs**: ~34 spec files

**Coverage by Journey**:
- ✅ Authentication Journeys: 4/4 (100%)
- ✅ Data Product Owner Journeys: 17/17 (100%)
- ✅ Data Engineer Journeys: 14/14 (100%)
- ✅ Compliance Officer Journeys: 10/10 (100%)
- ✅ Data Consumer Journeys: 15/15 (100%)
- ✅ Tenant Admin Journeys: 8/8 (100%)
- ✅ Platform Admin Journeys: 10/10 (100%)
- ✅ External Developer Journeys: 9/9 (100%)
- ✅ Auditor Journeys: 6/6 (100%)
- ✅ Scheduled Export Journeys: 2/2 (100%)

### CLI/SDK Test Coverage

**CLI Integration Tests**: 15 tests covering all Phase 26 commands
**SDK Integration Tests**: 7 tests covering all Phase 26 SDK methods

**Coverage**:
- ✅ Scheduled Ingestion: CLI + SDK
- ✅ Scheduled Export: CLI + SDK
- ✅ Webhooks: CLI
- ✅ Audit: CLI
- ✅ Health: CLI
- ✅ Billing: CLI + SDK (Phase 25)
- ✅ Tenants: CLI + SDK (Phase 25)
- ✅ GDPR: CLI + SDK (Phase 25)
- ✅ Search: CLI

---

## Gap Remediation Traceability

This section maps **Gap Remediation Plan** phases (see [openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)) to tests and documentation. Phases 0–6 align docs and implementation with FEATURES.md, USE_CASES.md, and USER_JOURNEYS.md.

| Phase | Name | Tests | Documentation |
|-------|------|-------|----------------|
| **0** | Doc-only fixes | — | [FEATURES.md](FEATURES.md) (Versioning/Workflows/Observability notes; Supporting capabilities); [USER_JOURNEYS.md](USER_JOURNEYS.md), [USE_CASES.md](USE_CASES.md) (transformation deferred) |
| **1** | Observability lineage | `hub/apps/observability/tests/test_observability_lineage_integration.py` | [FEATURES.md](FEATURES.md#observability), [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md) |
| **2** | Versioning API | `hub/apps/versioning/tests/test_versioning_api_integration.py` | [FEATURES.md](FEATURES.md#versioning), [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md) |
| **3** | Workflows API | `hub/apps/orchestration/tests/test_workflows_api_integration.py` | [FEATURES.md](FEATURES.md#workflows), [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md) |
| **4** | Data preview & trust signals | `hub/apps/marketplace/tests/test_preview.py`; Trust signals config API: `tests/integration/test_trust_signals_config_api_comprehensive.py` | [FEATURES.md](FEATURES.md#marketplace), [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md) (Marketplace / Data preview, Trust signals config API) |
| **5** | Transformation pipeline | Deferred (no implementation) | [USER_JOURNEYS.md](USER_JOURNEYS.md), [USE_CASES.md](USE_CASES.md) (JOURNEY-DPO-008 etc. **Deferred**); [GAP_REMEDIATION_PLAN.md](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) Section 8 |
| **6** | Feature list & traceability | This matrix; [TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md); [TEST_SCENARIO_MATRIX.md](TEST_SCENARIO_MATRIX.md) (Success/Failure/Edge per feature) | [FEATURES.md](FEATURES.md) (29 features + Supporting capabilities); traceability updated |

**Supporting capabilities** (Notifications, Billing, Platform, Tenants, Users, Analytics, Events) are covered in [Supporting Capabilities](#supporting-capabilities) above and in [FEATURES.md](FEATURES.md#supporting-capabilities). They are not standalone product features; coverage is via the features that use them.

### Gap implementation plan (gapfix1) — Full test run and sign-off

This subsection links the **gap implementation plan** ([openspec/changes/gapfix1](../openspec/changes/gapfix1)) to Phase 12A execution, evidence layout, test summary report generation, and sign-off (GAP_REMEDIATION_PLAN §11).

| Item | Details |
|------|---------|
| **Phase 12A execution** | Backend: `scripts/run_phase_12a_backend_suites.sh`. Full suite: `scripts/run_phase_12a_full_suites.sh` (backend → frontend unit/E2E → security, performance, concurrency, regression). Commands per [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md). Per gapfix1 7.2.4. |
| **Evidence layout** | `test_reports_comprehensive/{date}/` with subdirs: unit, integration, e2e, uc_journey_persona (Task 6.7), security, performance, concurrency, regression, frontend-unit, frontend-e2e. Summaries: `phase_12a_1_summary.json` (backend, includes uc_journey_persona), `phase_12a_3_summary.json` (security/performance/concurrency/regression). Per [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md). |
| **Test summary report** | Generated from evidence by `scripts/generate_test_summary_report.sh` or `.py` (script/process from gapfix1 Phase 7.4). Report includes pass/fail, duration, coverage, evidence links. |
| **Sign-off criterion** | [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) — product/tech lead confirms doc and implementation; gap items resolved or deferred; evidence and report location recorded. Phase 16 GR-7 (16.1–16.3) in [testreview1/tasks.md](../openspec/changes/testreview1/tasks.md). |
| **Features covered** | Every gapfix1-delivered feature is covered by the same full test run and appears in the test summary report by feature/category: **(1) Scheduled Export** ([FEATURES.md](FEATURES.md#scheduled-export) section and implementation; feature #26; UC-EXPORT-001–004, JOURNEY-EXPORT-001–002). **(2) Trust signals config API** (Marketplace Phase 4; planned or implemented; UC-MKT-ADV-003, UC-MKT-ADV-005). **(3) §11→Phase 16 tasks** (GR-7 / 16.1–16.3: full 12A run, test summary report, sign-off). |
| **Links** | **This change**: [gapfix1 tasks](../openspec/changes/gapfix1/tasks.md); [openspec/changes/gapfix1](../openspec/changes/gapfix1). **testreview1 Phase 16** (GR-7, 16.1–16.3): [testreview1 tasks — Phase 16](../openspec/changes/testreview1/tasks.md#16-phase-16--gap-remediation-plan-data-interoperability-hub). |

---

## Evidence Links

This section provides placeholders and references for test evidence (results, coverage, performance, security, E2E artifacts). Update with actual CI or local report URLs when available.

### Last full run (Phase 4.4)

After each full Phase 12A run, update this subsection with the run date and path to evidence (or link to CI artifact).

| Field | Value |
|-------|--------|
| **Last full run date** | *YYYY-MM-DD* (e.g. 2026-02-12) |
| **Evidence path** | `test_reports_comprehensive/{date}/` (local) or CI artifact URL |
| **Summary report** | Output of `./scripts/generate_test_summary_report.sh {date}` under the same path |

See [RUNBOOKS.md — Full suite sign-off record](RUNBOOKS.md#full-suite-sign-off-record-phase-43) for the sign-off template and [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) for Phase 12A definition.

### Test result links

- **Backend (pytest)**: CI workflow artifact or local output, e.g. `pytest --html=report.html` → `report.html` or `$CI_ARTIFACT_URL/backend-test-results.html`
- **Frontend (Playwright)**: CI artifact or local `playwright-report/`, e.g. `$CI_ARTIFACT_URL/playwright-report/index.html`
- **E2E (full stack)**: `tests/e2e/` and frontend E2E results; link to latest run in CI (e.g. GitHub Actions summary or artifact)

### Coverage report links

- **Backend coverage**: `coverage html` → `htmlcov/index.html`; CI may publish to a coverage service (e.g. Codecov, Coveralls) or store artifact
- **Frontend coverage**: If instrumented (e.g. Vitest/Istanbul), link to frontend coverage report or CI artifact

### Performance report links

- **Backend**: Performance or load test results (e.g. locust, pytest-benchmark) if run in CI; link to artifact or dashboard
- **Frontend**: Lighthouse or Playwright performance traces; link to CI artifact or stored report

### Security report links

- **Security scan**: SAST/DAST or dependency scan (e.g. safety, bandit, npm audit) output; link to CI artifact or security dashboard
- **Auth/allowlist tests**: `tests/security/` and compliance tests; reference in test result links above

### Screenshot / video links (E2E)

- **Playwright**: `frontend/e2e/test-results/` or `playwright-report/` (screenshots and videos on failure); CI artifact or local path
- **E2E runs**: Link to CI job that stores Playwright traces/screenshots for failed or key journeys

*To fill: Replace placeholders with actual URLs from your CI (e.g. GitHub Actions `$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID`) or internal dashboard.*

---

## Cross-References

### In FEATURES.md

Each feature section includes:
- Links to Use Cases (e.g., `[Use Cases – Authentication & Access](USE_CASES.md#authentication--access-use-cases)`)
- Links to User Journeys (e.g., `[User Journeys – Visitor / Authentication](USER_JOURNEYS.md#visitor--authentication-journeys)`)
- **NEW**: Links to Test Traceability (e.g., `[Test Traceability – Auth](TEST_TRACEABILITY.md#auth)`)

### In USE_CASES.md

Each use case includes:
- Related Use Cases
- Related Journeys
- **NEW**: Links to Test Traceability (e.g., `[Test Traceability – UC-AUTH-001](TEST_TRACEABILITY.md#uc-auth-001-user-registers-self-service-sign-up)`)

### In USER_JOURNEYS.md

Each journey includes:
- Related Use Cases
- **NEW**: Links to Test Traceability (e.g., `[Test Traceability – JOURNEY-AUTH-001](TEST_TRACEABILITY.md#journey-auth-001-first-time-visitor-registers)`)

---

## Maintenance

This document should be updated when:
1. New features are added
2. New use cases are defined
3. New user journeys are created
4. New tests are written
5. Tests are refactored or removed

**Update Frequency**: After each major release or phase completion

---

**Last Updated**: 2026-02-16
**Version**: 1.3.0
