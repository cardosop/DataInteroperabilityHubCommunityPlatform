# Workflow E2E Test Organization (Phase 6.10)

## Overview

Workflow E2E tests are organized by **theme** (one file per theme), **scenario** (one test class per scenario or workflow type), and **test case** (one test method per case). All tests use real services (no mocks/stubs) and extend `WorkflowE2ETestBase` or `E2ETestBase` from `workflow_e2e_base.py` and `conftest.py`.

## Structure

- **File** = theme (error recovery, observability, security, user journey, use case, business rules, performance)
- **Class** = scenario or workflow type (e.g. retry after failure, contract_creation, DPO-001)
- **Method** = individual test case

## Test Files by Theme

| Theme | File | Description |
|-------|------|-------------|
| Error recovery & compensation | `test_workflow_error_recovery_compensation_e2e.py` | Retry, compensation, state recovery, validation behavior under service/network/DB/timeout failures |
| Observability & business rules | `test_workflow_observability_business_rules_e2e.py` | Metrics, events, structured logging, distributed tracing with business rules |
| Security & business rules | `test_workflow_security_business_rules_e2e.py` | Tenant isolation, authorization, input validation, business rules validation |
| User journey integration | `test_workflow_user_journey_integration_e2e.py` | Workflows in Data Product Owner, Data Engineer, Compliance, Data Consumer, Data Mesh, Data Quality journeys |
| Use case integration | `test_workflow_use_case_integration_e2e.py` | Workflows in Asset Management, Contract, Marketplace, Data Quality, Compliance use cases |
| Business rules (core) | `test_workflow_business_rules_e2e.py` | Business rules validation for product, contract, asset, marketplace, dataset, scheduled ingestion workflows |
| Performance & business rules | `test_workflow_performance_business_rules_e2e.py` | Validation overhead and performance with business rules |

## Workflow Type → Test Coverage

| Workflow type (WORKFLOW_NAME) | Test file(s) / class(es) |
|------------------------------|---------------------------|
| `asset_creation` | test_workflow_business_rules_e2e (TestAssetCreationWorkflowBusinessRulesE2E), test_workflow_use_case_integration_e2e (TestUC_AM_001), test_workflow_user_journey_integration_e2e (DPO-015 product_creation) |
| `contract_creation` | test_workflow_business_rules_e2e (TestContractCreationWorkflowBusinessRulesE2E), test_workflow_error_recovery_compensation_e2e (retry/compensation), test_workflow_use_case_integration_e2e (TestUC_CM_001), test_workflow_user_journey_integration_e2e (DPO-001, DE-001) |
| `marketplace_publication` | test_workflow_business_rules_e2e (TestMarketplacePublicationWorkflowBusinessRulesE2E), test_workflow_use_case_integration_e2e (TestUC_MKT_001), test_workflow_user_journey_integration_e2e (DPO-002) |
| `product_creation` | test_workflow_business_rules_e2e (TestProductCreationWorkflowBusinessRulesE2E), test_workflow_user_journey_integration_e2e (DPO-015, DE-014) |
| `dataset_creation` | test_workflow_business_rules_e2e (TestDatasetCreationWorkflowBusinessRulesE2E) |
| `scheduled_ingestion` | test_workflow_business_rules_e2e (TestScheduledIngestionWorkflowBusinessRulesE2E) |
| `access_request` | test_workflow_user_journey_integration_e2e (TestDataConsumerWorkflowJourneysE2E) |
| `compliance_reporting` | test_workflow_user_journey_integration_e2e (TestComplianceOfficerWorkflowJourneysE2E), test_workflow_use_case_integration_e2e (TestComplianceUseCaseWorkflowE2E) |
| `data_quality_check` | test_workflow_user_journey_integration_e2e (TestDataQualityWorkflowInJourneysE2E), test_workflow_use_case_integration_e2e (TestDataQualityUseCaseWorkflowE2E) |
| `data_mesh` | test_workflow_user_journey_integration_e2e (TestDataMeshDomainOwnerWorkflowJourneysE2E) |
| `version_creation` | (covered via asset/version flows in other tests) |
| `virtualization_query_execution` | (unit/integration in hub/apps/orchestration/workflows/tests/) |
| `api_key_management` | (unit in hub/apps/orchestration/workflows/tests/) |
| `model_training` / `model_inference` | (unit in hub/apps/orchestration/workflows/tests/) |
| `marketplace_sync` | (unit in hub/apps/orchestration/workflows/tests/) |

## Selective Execution

- Run all workflow E2E tests: `pytest tests/e2e/ -m workflow_e2e -v`
- Run by file: `pytest tests/e2e/test_workflow_error_recovery_compensation_e2e.py -v`
- Run by class: `pytest tests/e2e/test_workflow_use_case_integration_e2e.py::TestUC_AM_001_WorkflowIntegrationE2E -v`

## How to Run (Docker Compose)

Phase 6.6–6.9 scripts reuse the same test DB (`TEST_DB_SUFFIX=phase66`, `--keepdb` by default):

- Phase 6.6 observability: `./scripts/run_phase66_workflow_observability_e2e_tests.sh`
- Phase 6.7 error recovery: `./scripts/run_phase67_workflow_error_recovery_e2e_tests.sh`
- Phase 6.8 user journey: `./scripts/run_phase68_workflow_user_journey_e2e_tests.sh`
- Phase 6.9 use case: `./scripts/run_phase69_workflow_use_case_e2e_tests.sh`

Full workflow E2E from repo root (with services up):
`pytest tests/e2e/ -m workflow_e2e -v --tb=short`

## Troubleshooting (Docker Compose)

- **relation "search_index" or "semantic_resources" does not exist**: The test DB (e.g. `hub_test_phase66`) may have been created before those migrations. Recreate it with full migrations by running once with `--no-keepdb`, e.g. `./scripts/run_phase69_workflow_use_case_e2e_tests.sh --no-keepdb`.
- **api-service not running**: Start with `docker compose up -d` and wait for api-service to be healthy.
