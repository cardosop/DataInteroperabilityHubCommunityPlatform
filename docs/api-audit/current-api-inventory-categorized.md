# Current API Inventory - Categorized

**Generated:** 2025-12-13 18:09:25
**Total Endpoints:** 148

## Summary Statistics

- **Total Endpoints:** 148
- **With Schema:** 139 (93%)
- **With Tests:** 139 (93%)
- **Deprecated:** 0

### By Feature Type

| Type | Count | Percentage |
|------|-------|------------|
| **Core** | 92 | 62% |
| **Feature** | 54 | 36% |
| **New Feature** | 2 | 1% |

### By Status

| Status | Count | Percentage |
|--------|-------|------------|
| **Working** | 139 | 93% |
| **Broken** | 0 | 0% |
| **Deprecated** | 0 | 0% |
| **Unknown** | 9 | 6% |

### By Completeness

| Completeness | Count | Percentage |
|--------------|-------|------------|
| **Complete** | 0 | 0% |
| **Incomplete** | 148 | 100% |

## Detailed Categorization

### Core Features

#### Working

- **DELETE** `/api/v1/assets/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/auth/api-keys/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/contracts/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/files/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/marketplace/listings/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/tenants/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/users/roles/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **DELETE** `/api/v1/users/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/assets/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/assets/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/assets/{id}/dependencies/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/assets/{id}/health-score/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/audit/audit-events/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/audit/audit-events/export/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/audit/audit-events/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/accept-invitation`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/api-keys/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/api-keys/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/login`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/logout`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/password-reset`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/password-reset/confirm`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/auth/refresh`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/compliance/compliance-runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/compliance/compliance-runs/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/compliance/runs/<uuid:id>`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/{id}/impact-analysis/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/{id}/lineage/contracts/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/{id}/lineage/full/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/contracts/{id}/lineage/visualization/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/datasets/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/datasets/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/datasets/{id}/versions/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/datasets/{id}/versions/compare/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/dq/dq-runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/dq/dq-runs/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/dq/runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/dq/runs/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/files/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/files/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/files/{id}/download/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/jobs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/jobs/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/marketplace/listings/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/tenants/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/tenants/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/users/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/users/roles/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/users/roles/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/users/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PATCH** `/api/v1/tenants/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PATCH** `/api/v1/users/roles/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PATCH** `/api/v1/users/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/{id}/activate/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/{id}/contracts/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/{id}/datasets/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/{id}/track-download/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/assets/{id}/track-view/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/auth/api-keys/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/compliance/compliance-runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/contracts/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/contracts/{id}/convert/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/contracts/{id}/lint/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/contracts/{id}/migrate/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/contracts/{id}/validate/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/datasets/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/dq/dq-runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/dq/runs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/files/init/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/files/{id}/chunks/init/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/files/{id}/complete/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/jobs/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/jobs/{id}/cancel/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/marketplace/listings/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/tenants/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/tenants/{id}/reactivate/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/tenants/{id}/suspend/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/invite/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/roles/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/roles/invite/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/roles/{id}/roles/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/users/{id}/roles/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/assets/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/contracts/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/marketplace/listings/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/tenants/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/users/roles/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PUT** `/api/v1/users/{id}/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

### Feature Features

#### Working

- **GET** `/api/v1/governance/analytics/anomalies/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/analytics/dashboard/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/analytics/expiring/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/analytics/patterns/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/analytics/security-events/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/analytics/summary/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/anomalies/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/dashboard/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/expiring/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/patterns/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/security-events/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/governance/certifications/summary/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/marketplace/listings/search/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/freshness/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/freshness/stale/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/incidents/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/metrics`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/schema-drift/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/slas/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/volume/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/search/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/search/analytics/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/search/suggestions/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/semantic/context.jsonld`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/semantic/ontology`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/semantic/sparql`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/webhooks/webhook-deliveries/{id}/deliveries/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/webhooks/{id}/deliveries/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **PATCH** `/api/v1/observability/incidents/update/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/governance/analytics/initiate-review/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/governance/analytics/{id}/review/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/governance/certifications/initiate-review/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/governance/certifications/{id}/review/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/observability/incidents/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/observability/metrics/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/observability/schema-drift/detect/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/observability/volume/aggregate/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/search/rebuild-index/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/search/track-click/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/webhooks/webhook-deliveries/{id}/retry/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/webhooks/webhook-deliveries/{id}/test/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/webhooks/{id}/retry/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **POST** `/api/v1/webhooks/{id}/test/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

#### Unknown

- **GET** `/api/v1/api-analytics/api/dashboard/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/api-analytics/api/performance/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/api-analytics/api/popular-endpoints/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/api-analytics/api/usage-trends/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/scheduled-ingestion/runs/costs/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/scheduled-ingestion/runs/dashboard/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/scheduled-ingestion/runs/dead-letter-queue/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **GET** `/api/v1/scheduled-ingestion/runs/{id}/runs/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

- **POST** `/api/v1/scheduled-ingestion/runs/{id}/trigger/`
  - **Completeness:** Incomplete
  - **Notes:** Missing OpenAPI schema definition, No tests found

### New Feature Features

#### Working

- **GET** `/api/v1/assets/recommendations/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

- **GET** `/api/v1/observability/pipelines/`
  - **Completeness:** Incomplete
  - ✅ Has Schema
  - ✅ Has Tests

## Complete Endpoint Categorization Table

| Method | Path | Feature Type | Status | Completeness | Schema | Tests | Deprecated |
|--------|------|--------------|--------|--------------|--------|-------|------------|
| DELETE | `/api/v1/assets/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/auth/api-keys/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/contracts/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/files/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/marketplace/listings/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/tenants/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/users/roles/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| DELETE | `/api/v1/users/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/api-analytics/api/dashboard/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/api-analytics/api/performance/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/api-analytics/api/popular-endpoints/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/api-analytics/api/usage-trends/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/assets/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/assets/recommendations/` | New Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/assets/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/assets/{id}/dependencies/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/assets/{id}/health-score/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/audit/audit-events/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/audit/audit-events/export/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/audit/audit-events/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/accept-invitation` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/api-keys/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/api-keys/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/login` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/logout` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/password-reset` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/password-reset/confirm` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/auth/refresh` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/compliance/compliance-runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/compliance/compliance-runs/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/compliance/runs/<uuid:id>` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/{id}/impact-analysis/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/{id}/lineage/contracts/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/{id}/lineage/full/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/contracts/{id}/lineage/visualization/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/datasets/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/datasets/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/datasets/{id}/versions/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/datasets/{id}/versions/compare/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/dq/dq-runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/dq/dq-runs/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/dq/runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/dq/runs/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/files/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/files/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/files/{id}/download/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/anomalies/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/dashboard/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/expiring/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/patterns/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/security-events/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/analytics/summary/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/anomalies/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/dashboard/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/expiring/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/patterns/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/security-events/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/governance/certifications/summary/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/jobs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/jobs/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/marketplace/listings/search/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/marketplace/listings/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/freshness/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/freshness/stale/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/incidents/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/metrics` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/pipelines/` | New Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/schema-drift/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/slas/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/observability/volume/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/scheduled-ingestion/runs/costs/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/scheduled-ingestion/runs/dashboard/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/scheduled-ingestion/runs/dead-letter-queue/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/scheduled-ingestion/runs/{id}/runs/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| GET | `/api/v1/search/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/search/analytics/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/search/suggestions/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/semantic/context.jsonld` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/semantic/ontology` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/semantic/sparql` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/tenants/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/tenants/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/users/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/users/roles/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/users/roles/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/users/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/deliveries/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| GET | `/api/v1/webhooks/{id}/deliveries/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| PATCH | `/api/v1/observability/incidents/update/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| PATCH | `/api/v1/tenants/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PATCH | `/api/v1/users/roles/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PATCH | `/api/v1/users/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/{id}/activate/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/{id}/contracts/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/{id}/datasets/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/{id}/track-download/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/assets/{id}/track-view/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/auth/api-keys/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/compliance/compliance-runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/contracts/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/contracts/{id}/convert/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/contracts/{id}/lint/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/contracts/{id}/migrate/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/contracts/{id}/validate/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/datasets/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/dq/dq-runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/dq/runs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/files/init/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/files/{id}/chunks/init/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/files/{id}/complete/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/governance/analytics/initiate-review/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/governance/analytics/{id}/review/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/governance/certifications/initiate-review/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/governance/certifications/{id}/review/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/jobs/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/jobs/{id}/cancel/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/marketplace/listings/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/observability/incidents/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/observability/metrics/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/observability/schema-drift/detect/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/observability/volume/aggregate/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/scheduled-ingestion/runs/{id}/trigger/` | Feature | Unknown | Incomplete | ❌ | ❌ | - |
| POST | `/api/v1/search/rebuild-index/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/search/track-click/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/tenants/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/tenants/{id}/reactivate/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/tenants/{id}/suspend/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/invite/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/roles/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/roles/invite/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/roles/{id}/roles/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/users/{id}/roles/` | Core | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/test/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/webhooks/{id}/retry/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| POST | `/api/v1/webhooks/{id}/test/` | Feature | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/assets/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/contracts/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/marketplace/listings/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/tenants/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/users/roles/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
| PUT | `/api/v1/users/{id}/` | Core | Working | Incomplete | ✅ | ✅ | - |
