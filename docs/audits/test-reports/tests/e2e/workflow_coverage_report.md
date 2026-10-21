# Workflow E2E Test Coverage Report

Generated: 2026-01-29T20:03:03.724382Z

## 1. Workflow coverage

- **Total workflow types**: 16
- **Tested in E2E**: 11
- **Coverage**: 68.8%

### Tested workflows

- **asset_creation**: test_workflow_business_rules_e2e.py, test_workflow_use_case_integration_e2e.py, test_workflow_user_journey_integration_e2e.py
- **contract_creation**: test_workflow_business_rules_e2e.py, test_workflow_error_recovery_compensation_e2e.py, test_workflow_observability_business_rules_e2e.py, test_workflow_security_business_rules_e2e.py, test_workflow_use_case_integration_e2e.py, test_workflow_user_journey_integration_e2e.py
- **marketplace_publication**: test_workflow_business_rules_e2e.py, test_workflow_use_case_integration_e2e.py, test_workflow_user_journey_integration_e2e.py
- **product_creation**: test_workflow_business_rules_e2e.py, test_workflow_performance_business_rules_e2e.py, test_workflow_user_journey_integration_e2e.py
- **dataset_creation**: test_workflow_business_rules_e2e.py
- **scheduled_ingestion**: test_workflow_business_rules_e2e.py
- **access_request**: test_workflow_user_journey_integration_e2e.py
- **compliance_reporting**: test_workflow_user_journey_integration_e2e.py, test_workflow_use_case_integration_e2e.py
- **data_quality_check**: test_workflow_user_journey_integration_e2e.py, test_workflow_use_case_integration_e2e.py
- **data_mesh**: test_workflow_user_journey_integration_e2e.py
- **version_creation**: test_workflow_use_case_integration_e2e.py

### Not covered by workflow E2E (unit/integration elsewhere)

- virtualization_query_execution
- api_key_management
- model_training
- model_inference
- marketplace_sync

## 2. Business rules coverage

Tests that validate business rules in workflow context:

- `test_workflow_business_rules_e2e.py`: Product, Contract, Asset, Marketplace, Dataset, Scheduled Ingestion BR
- `test_workflow_observability_business_rules_e2e.py`: Metrics, events, logging, tracing with BR
- `test_workflow_security_business_rules_e2e.py`: Tenant isolation, authorization, input validation, BR validation
- `test_workflow_error_recovery_compensation_e2e.py`: Retry, compensation, state recovery, validation behavior
- `test_workflow_performance_business_rules_e2e.py`: Validation overhead, throughput with BR
- `test_workflow_user_journey_integration_e2e.py`: All journey workflows with BR validation
- `test_workflow_use_case_integration_e2e.py`: All use case workflows with BR validation

## 3. Journey coverage

User journeys that include workflow E2E tests:

- **DPO-001** (Contract creation (Data Product Owner)): `TestJOURNEY_DPO_001_WorkflowIntegrationE2E`
- **DPO-002** (Marketplace publication): `TestJOURNEY_DPO_002_WorkflowIntegrationE2E`
- **DPO-015** (Product creation (ODPS product-first)): `TestJOURNEY_DPO_015_WorkflowIntegrationE2E`
- **DE-001** (Contract creation programmatic): `TestJOURNEY_DE_001_WorkflowIntegrationE2E`
- **DE-014** (Product creation via API): `TestJOURNEY_DE_014_WorkflowIntegrationE2E`
- **Compliance Officer** (Compliance reporting workflow): `TestComplianceOfficerWorkflowJourneysE2E`
- **Data Consumer** (Access request workflow): `TestDataConsumerWorkflowJourneysE2E`
- **Data Mesh Domain Owner** (Data mesh workflow): `TestDataMeshDomainOwnerWorkflowJourneysE2E`
- **Data Quality** (Data quality check workflow): `TestDataQualityWorkflowInJourneysE2E`

## 4. Use case coverage

Use cases that include workflow E2E tests:

- **UC-AM-001** (Create Asset via Data-First Flow): `TestUC_AM_001_WorkflowIntegrationE2E`
- **UC-CM-001** (Create Contract): `TestUC_CM_001_WorkflowIntegrationE2E`
- **UC-MKT-001** (Publish Asset to Marketplace): `TestUC_MKT_001_WorkflowIntegrationE2E`
- **UC-DQ-001** (Data Quality check workflow): `TestDataQualityUseCaseWorkflowE2E`
- **UC-COMP-001** (Compliance reporting workflow): `TestComplianceUseCaseWorkflowE2E`
