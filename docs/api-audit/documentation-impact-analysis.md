# Documentation Impact Analysis

**Generated:** 2025-12-28 14:50:13

This report compiles documentation references from all audit reports and identifies documentation that needs to be updated.

---

## Summary

### Documentation Statistics

- **Total Documentation Files:** 55
- **Total Endpoint References:** 7457
- **Total Unique Endpoints:** 1114
- **Total Code Examples:** 3224
  - Valid: 3052
  - Invalid: 172
- **Total Postman Collections:** 0
  - Valid: 0
  - Invalid: 0
- **Total Postman Requests:** 0
- **Inventory Endpoints:** 0
- **Codebase Endpoints:** 0
- **Discrepancies:** 0

### Issues Identified

- **Invalid Code Examples:** 172
- **Invalid Postman Collections:** 0
- **Endpoints with Multiple Documentation Files:** 615

---

## Documentation Files

Total documentation files analyzed: **55**

### Files List

- `docs/API_BEST_PRACTICES.md`
- `docs/API_ENDPOINTS_REFERENCE.md`
- `docs/API_REFERENCE.md`
- `docs/API_STANDARDS.md`
- `docs/API_TESTING_GUIDE.md`
- `docs/API_USABILITY.md`
- `docs/API_VERSIONING_POLICY.md`
- `docs/DEVELOPER_ONBOARDING.md`
- `docs/api-audit/API_CLIENT_USAGE_SEARCH_TEST_RESULTS.md`
- `docs/api-audit/CONSOLIDATION_SUMMARY.md`
- `docs/api-audit/ENDPOINT_TESTING_SUMMARY.md`
- `docs/api-audit/GAP_ANALYSIS_SUMMARY.md`
- `docs/api-audit/GAP_DETAILS_SUMMARY.md`
- `docs/api-audit/WEBHOOK_PAYLOADS_AND_EVENTS_TEST_RESULTS.md`
- `docs/api-audit/api-dependencies.md`
- `docs/api-audit/api-development-backlog.md`
- `docs/api-audit/api-development-timeline.md`
- `docs/api-audit/api-effort-estimates-summary.md`
- `docs/api-audit/api-effort-estimation-methodology.md`
- `docs/api-audit/api-performance-requirements.md`
- `docs/api-audit/api-requirements-from-journeys.md`
- `docs/api-audit/api-requirements-from-use-cases.md`
- `docs/api-audit/api-requirements-matrix-consolidated.md`
- `docs/api-audit/api-requirements-matrix.md`
- `docs/api-audit/api-testing-plan.md`
- `docs/api-audit/codebase-endpoints-inventory.md`
- `docs/api-audit/consumer-impact-analysis.md`
- `docs/api-audit/current-api-inventory-categorized.md`
- `docs/api-audit/current-api-inventory.md`
- `docs/api-audit/endpoint-inventory-current.md`
- `docs/api-audit/endpoint-naming-audit-report.md`
- `docs/api-audit/endpoint-test-report-template.md`
- `docs/api-audit/error-responses-documentation.md`
- `docs/api-audit/error-responses-summary.md`
- `docs/api-audit/gap-analysis.md`
- `docs/api-audit/gap-categorization-by-priority.md`
- `docs/api-audit/gap-details.md`
- `docs/api-audit/gateway-config-review.md`
- `docs/api-audit/hardcoded-endpoints-impact-matrix.md`
- `docs/api-audit/integration-requirements-documentation.md`
- `docs/api-audit/integration-requirements-summary.md`
- `docs/api-audit/integration-test-requirements.md`
- `docs/api-audit/openapi-spec-discrepancies.md`
- `docs/api-audit/service-integration-impact.md`
- `docs/api-audit/test-fixtures-and-factories-report.md`
- `docs/api-audit/test-impact-analysis.md`
- `docs/api-audit/test-utilities-report.md`
- `docs/api-contracts/missing/ai-ml/natural-language-search.yaml`
- `docs/api-contracts/missing/ai-ml/schema-matching.yaml`
- `docs/api-contracts/missing/auth/me.yaml`
- `docs/api-contracts/missing/auth/register.yaml`
- `docs/api-contracts/missing/credentials/scheduled-ingestion-credentials.yaml`
- `docs/api-contracts/missing/developer/plugins-sdk.yaml`
- `docs/api-contracts/missing/marketplace-advanced/preview.yaml`
- `docs/api-contracts/missing/social/ratings-reviews-comments-communities.yaml`

---

## Endpoints

Total endpoints documented: **1114**

### Endpoints with Multiple Documentation Files

These endpoints have documentation in multiple files and may need consolidation:

- **/api/v1** (GET)
  - `docs/API_REFERENCE.md`
  - `docs/API_USABILITY.md`
  - `docs/API_VERSIONING_POLICY.md`
  - `docs/api-audit/API_CLIENT_USAGE_SEARCH_TEST_RESULTS.md`
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
  - `docs/api-audit/hardcoded-endpoints-impact-matrix.md`
  - `docs/api-audit/openapi-spec-discrepancies.md`
- **/api/v1/...** ()
  - `docs/API_VERSIONING_POLICY.md`
  - `docs/api-audit/hardcoded-endpoints-impact-matrix.md`
- **/api/v1/<drf_format_suffix:format>** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^(?!auth/|tenants/|users/|audit/|files/|datasets/|jobs/|contracts/|assets/|dq/|compliance/|semantic/|marketplace/|scheduled-ingestions/|search/|developer/|webhooks/|transformation/|mesh/|virtualization** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/freshness/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/freshness/stale/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/freshness/stale\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/freshness\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
  - `docs/api-audit/test-impact-analysis.md`
- **/api/v1/^observability/incidents/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
  - `docs/api-audit/hardcoded-endpoints-impact-matrix.md`
- **/api/v1/^observability/incidents/update/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/incidents/update\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/incidents\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
  - `docs/api-audit/hardcoded-endpoints-impact-matrix.md`
- **/api/v1/^observability/metrics/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/metrics\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/pipelines/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/pipelines\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/schema-drift/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/schema-drift/detect/$** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/schema-drift/detect\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`
- **/api/v1/^observability/schema-drift\.(?P<format>[a-z0-9]+** ()
  - `docs/api-audit/endpoint-inventory-current.md`
  - `docs/api-audit/endpoint-naming-audit-report.md`

*... and 595 more*


---

## Code Examples

### Invalid Code Examples (172)

The following code examples have errors and need to be fixed:

#### `docs/API_USABILITY.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/

#### `docs/DEVELOPMENT_GUIDE.md`

- **Errors:** 1
  - Syntax error: unexpected indent at line 2
- **Errors:** 1
  - Syntax error: unexpected indent at line 2
- **Errors:** 1
  - Syntax error: unexpected indent at line 2
- **Errors:** 1
  - Syntax error: unexpected indent at line 2

#### `docs/RUNBOOKS.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/targets/
  - Invalid endpoints: /api/v1/targets/

#### `docs/SERVICE_STARTUP_GUIDE.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/health/
  - Invalid endpoints: /api/v1/health/

#### `docs/EVENT_TYPES_REFERENCE.md`

- **Errors:** 1
  - Syntax error: invalid syntax at line 5

#### `docs/EVENT_BUS.md`

- **Errors:** 1
  - Syntax error: invalid syntax at line 4

#### `docs/API_STANDARDS.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/resources/
  - Invalid endpoints: /api/v1/resources/

#### `docs/DOCKER_COMPOSE_DEPLOYMENT.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/targets/
  - Invalid endpoints: /api/v1/targets/

#### `docs/API_BEST_PRACTICES.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v2/contracts/
  - Invalid endpoints: /api/v2/contracts/

#### `docs/API_ENDPOINTS_REFERENCE.md`

- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/contracts/products/
  - Invalid endpoints: /api/v1/contracts/products/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/contracts/{id}/export/
  - Invalid endpoints: /api/v1/contracts/{id}/export/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/contracts/{id}/download/
  - Invalid endpoints: /api/v1/contracts/{id}/download/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/contracts/{odcs-id}/link-odps/
  - Invalid endpoints: /api/v1/contracts/{odcs-id}/link-odps/
- **Errors:** 1
  - Endpoint not found in inventory: /api/v1/contracts/{odcs-id}/link-odps/
  - Invalid endpoints: /api/v1/contracts/{odcs-id}/link-odps/


*... and 52 more files with invalid examples*

---

## Postman Collections

✅ All Postman collections are valid.

---

## Recommendations

### 🔴 **HIGH Priority**: Code Examples

Fix 172 invalid code examples in documentation

**Action:** Review and update code examples with syntax errors or invalid endpoints

### 🟢 **LOW Priority**: Documentation Consolidation

Consolidate documentation for 615 endpoints with multiple documentation files

**Action:** Review and consolidate duplicate documentation


---

## Next Steps

1. Review the recommendations above
2. Prioritize fixes based on priority levels
3. Update documentation files with invalid examples
4. Fix Postman collections with invalid endpoints
5. Consolidate duplicate documentation where appropriate
6. Re-run audits to verify fixes

---

*This report was generated automatically from audit data.*
