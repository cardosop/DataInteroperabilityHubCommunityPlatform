# Current API Inventory from Codebase

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Source**: `hub/apps/*/urls.py` files  
**Task**: 0.2.2 - Review codebase for API endpoints

---

## Overview

This document inventories all API endpoints extracted from the Django codebase by:
1. Reviewing all `hub/apps/*/urls.py` files
2. Extracting URL patterns and view classes
3. Identifying ViewSet actions (standard CRUD + custom @action decorators)
4. Documenting custom function-based views
5. Checking for deprecated endpoints
6. Comparing with OpenAPI schema (next step: 0.2.1)

**Total Endpoints Found**: 148

---

## Extraction Methodology

### Process

1. **URL Pattern Extraction**: Parsed all `urls.py` files to extract:
   - Router registrations (`router.register()`)
   - Custom path() routes
   - ViewSet class names and basenames

2. **ViewSet Action Extraction**: For each ViewSet, extracted:
   - Standard CRUD actions (list, create, retrieve, update, partial_update, destroy)
   - Custom @action decorators with their HTTP methods and URL paths

3. **Path Generation**: Generated full API paths by:
   - Combining base route from `api/urls.py` with resource path
   - Removing duplicate resource segments (e.g., `/assets/assets/` → `/assets/`)
   - Handling detail vs list actions correctly

4. **Deprecated Endpoint Detection**: Checked `APIVersionManager.DEPRECATED_ENDPOINTS` registry

---

## Endpoints by Application

### Analytics (4 endpoints)

**Base Route**: `/api/v1/analytics/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/analytics/api/dashboard/` | `APIAnalyticsViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/analytics/api/performance/` | `APIAnalyticsViewSet.performance` | performance | Custom |
| GET | `/api/v1/analytics/api/popular-endpoints/` | `APIAnalyticsViewSet.popular_endpoints` | popular_endpoints | Custom |
| GET | `/api/v1/analytics/api/usage-trends/` | `APIAnalyticsViewSet.usage_trends` | usage_trends | Custom |

### Assets (13 endpoints)

**Base Route**: `/api/v1/assets/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/assets/` | `AssetViewSet.list` | list | Standard |
| POST | `/api/v1/assets/` | `AssetViewSet.create` | create | Standard |
| GET | `/api/v1/assets/{id}/` | `AssetViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/assets/{id}/` | `AssetViewSet.update` | update | Standard |
| DELETE | `/api/v1/assets/{id}/` | `AssetViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/assets/recommendations/` | `AssetViewSet.recommendations` | recommendations | Custom |
| POST | `/api/v1/assets/{id}/activate/` | `AssetViewSet.activate` | activate | Custom |
| POST | `/api/v1/assets/{id}/contracts/` | `AssetViewSet.attach_contract` | attach_contract | Custom |
| POST | `/api/v1/assets/{id}/datasets/` | `AssetViewSet.attach_dataset` | attach_dataset | Custom |
| GET | `/api/v1/assets/{id}/dependencies/` | `AssetViewSet.dependencies` | dependencies | Custom |
| GET | `/api/v1/assets/{id}/health-score/` | `AssetViewSet.health_score` | health_score | Custom |
| POST | `/api/v1/assets/{id}/track-download/` | `AssetViewSet.track_download` | track_download | Custom |
| POST | `/api/v1/assets/{id}/track-view/` | `AssetViewSet.track_view` | track_view | Custom |

### Audit (3 endpoints)

**Base Route**: `/api/v1/audit/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/audit/audit-events/` | `AuditEventViewSet.list` | list | Standard |
| GET | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/audit/audit-events/export/` | `AuditEventViewSet.export` | export | Custom |

### Auth (10 endpoints)

**Base Route**: `/api/v1/auth/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| POST | `/api/v1/auth/login/` | `login` | - | Function-based |
| POST | `/api/v1/auth/refresh/` | `refresh_token` | - | Function-based |
| POST | `/api/v1/auth/logout/` | `logout` | - | Function-based |
| POST | `/api/v1/auth/password-reset/` | `password_reset_request` | - | Function-based |
| POST | `/api/v1/auth/password-reset/confirm/` | `password_reset_confirm` | - | Function-based |
| GET | `/api/v1/auth/accept-invitation/` | `accept_invitation` | - | Function-based |
| GET | `/api/v1/auth/api-keys/` | `APIKeyViewSet.list` | list | Standard |
| POST | `/api/v1/auth/api-keys/` | `APIKeyViewSet.create` | create | Standard |
| GET | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.retrieve` | retrieve | Standard |
| DELETE | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.destroy` | destroy | Standard |

**Note**: SSO endpoints are registered via `SSOViewSet` but not detailed here.

### Compliance (4 endpoints)

**Base Route**: `/api/v1/compliance/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/compliance/compliance-runs/` | `ComplianceRunViewSet.list` | list | Standard |
| POST | `/api/v1/compliance/compliance-runs/` | `ComplianceRunViewSet.create` | create | Standard |
| GET | `/api/v1/compliance/compliance-runs/{id}/` | `ComplianceRunViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/compliance/runs/` | `ComplianceRunViewSet.list` | list | Standard (backward compat) |
| GET | `/api/v1/compliance/runs/{id}/` | `ComplianceRunViewSet.retrieve` | retrieve | Standard (backward compat) |

**Note**: Backward compatibility routes (`/runs/`) are maintained for existing tests.

### Contracts (13 endpoints)

**Base Route**: `/api/v1/contracts/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/contracts/` | `ContractViewSet.list` | list | Standard |
| POST | `/api/v1/contracts/` | `ContractViewSet.create` | create | Standard |
| GET | `/api/v1/contracts/{id}/` | `ContractViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/contracts/{id}/` | `ContractViewSet.update` | update | Standard |
| DELETE | `/api/v1/contracts/{id}/` | `ContractViewSet.destroy` | destroy | Standard |
| POST | `/api/v1/contracts/{id}/validate/` | `ContractViewSet.validate_contract` | validate_contract | Custom |
| POST | `/api/v1/contracts/{id}/lint/` | `ContractViewSet.lint_contract` | lint_contract | Custom |
| POST | `/api/v1/contracts/{id}/convert/` | `ContractViewSet.convert_contract` | convert_contract | Custom |
| POST | `/api/v1/contracts/{id}/migrate/` | `ContractViewSet.migrate_contract` | migrate_contract | Custom |
| GET | `/api/v1/contracts/{id}/impact-analysis/` | `ContractViewSet.get_impact_analysis` | get_impact_analysis | Custom |
| GET | `/api/v1/contracts/{id}/lineage/contracts/` | `ContractViewSet.get_contract_lineage` | get_contract_lineage | Custom |
| GET | `/api/v1/contracts/{id}/lineage/full/` | `ContractViewSet.get_hierarchical_lineage` | get_hierarchical_lineage | Custom |
| GET | `/api/v1/contracts/{id}/lineage/visualization/` | `ContractViewSet.get_lineage_visualization` | get_lineage_visualization | Custom |

**Note**: Additional lineage endpoints exist for fields and models (not shown in detail here).

### Datasets (5 endpoints)

**Base Route**: `/api/v1/datasets/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/datasets/` | `DatasetViewSet.list` | list | Standard |
| POST | `/api/v1/datasets/` | `DatasetViewSet.create` | create | Standard |
| GET | `/api/v1/datasets/{id}/` | `DatasetViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/datasets/{id}/versions/` | `DatasetViewSet.versions` | versions | Custom |
| GET | `/api/v1/datasets/{id}/versions/compare/` | `DatasetViewSet.compare_versions` | compare_versions | Custom |

### Data Quality (6 endpoints)

**Base Route**: `/api/v1/dq/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/dq/dq-runs/` | `DQRunViewSet.list` | list | Standard |
| POST | `/api/v1/dq/dq-runs/` | `DQRunViewSet.create` | create | Standard |
| GET | `/api/v1/dq/dq-runs/{id}/` | `DQRunViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/dq/runs/` | `DQRunViewSet.list` | list | Standard (backward compat) |
| POST | `/api/v1/dq/runs/` | `DQRunViewSet.create` | create | Standard (backward compat) |
| GET | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.retrieve` | retrieve | Standard (backward compat) |

**Note**: Backward compatibility routes (`/runs/`) are maintained.

### Files (7 endpoints)

**Base Route**: `/api/v1/files/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/files/` | `FileViewSet.list` | list | Standard |
| GET | `/api/v1/files/{id}/` | `FileViewSet.retrieve` | retrieve | Standard |
| DELETE | `/api/v1/files/{id}/` | `FileViewSet.destroy` | destroy | Standard |
| POST | `/api/v1/files/init/` | `FileViewSet.init_upload` | init_upload | Custom |
| POST | `/api/v1/files/{id}/chunks/init/` | `FileViewSet.init_chunk_upload` | init_chunk_upload | Custom |
| POST | `/api/v1/files/{id}/complete/` | `FileViewSet.complete_upload` | complete_upload | Custom |
| GET | `/api/v1/files/{id}/download/` | `FileViewSet.download` | download | Custom |

### Governance (16 endpoints)

**Base Route**: `/api/v1/governance/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/governance/analytics/dashboard/` | `AccessAnalyticsViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/governance/analytics/summary/` | `AccessAnalyticsViewSet.summary` | summary | Custom |
| GET | `/api/v1/governance/analytics/patterns/` | `AccessAnalyticsViewSet.patterns` | patterns | Custom |
| GET | `/api/v1/governance/analytics/anomalies/` | `AccessAnalyticsViewSet.anomalies` | anomalies | Custom |
| GET | `/api/v1/governance/analytics/expiring/` | `AccessAnalyticsViewSet.expiring` | expiring | Custom |
| GET | `/api/v1/governance/analytics/security-events/` | `AccessAnalyticsViewSet.security_events` | security_events | Custom |
| POST | `/api/v1/governance/analytics/initiate-review/` | `AccessAnalyticsViewSet.initiate_review` | initiate_review | Custom |
| POST | `/api/v1/governance/analytics/{id}/review/` | `AccessAnalyticsViewSet.review` | review | Custom |
| GET | `/api/v1/governance/certifications/dashboard/` | `AccessCertificationViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/governance/certifications/summary/` | `AccessCertificationViewSet.summary` | summary | Custom |
| GET | `/api/v1/governance/certifications/patterns/` | `AccessCertificationViewSet.patterns` | patterns | Custom |
| GET | `/api/v1/governance/certifications/anomalies/` | `AccessCertificationViewSet.anomalies` | anomalies | Custom |
| GET | `/api/v1/governance/certifications/expiring/` | `AccessCertificationViewSet.expiring` | expiring | Custom |
| GET | `/api/v1/governance/certifications/security-events/` | `AccessCertificationViewSet.security_events` | security_events | Custom |
| POST | `/api/v1/governance/certifications/initiate-review/` | `AccessCertificationViewSet.initiate_review` | initiate_review | Custom |
| POST | `/api/v1/governance/certifications/{id}/review/` | `AccessCertificationViewSet.review` | review | Custom |

**Note**: Additional ViewSets exist for `AccessRequestViewSet` and `RetentionPolicyViewSet` (not detailed here).

### Jobs (4 endpoints)

**Base Route**: `/api/v1/jobs/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/jobs/` | `JobViewSet.list` | list | Standard |
| POST | `/api/v1/jobs/` | `JobViewSet.create` | create | Standard |
| GET | `/api/v1/jobs/{id}/` | `JobViewSet.retrieve` | retrieve | Standard |
| POST | `/api/v1/jobs/{id}/cancel/` | `JobViewSet.cancel` | cancel | Custom |

### Marketplace (5 endpoints)

**Base Route**: `/api/v1/marketplace/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/marketplace/listings/` | `ListingViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/listings/` | `ListingViewSet.create` | create | Standard |
| GET | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.update` | update | Standard |
| DELETE | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/listings/search/` | `ListingViewSet.search` | search | Custom |

**Note**: Additional ViewSets exist for `OrderViewSet` and `EntitlementViewSet` (not detailed here).

### Observability (13 endpoints)

**Base Route**: `/api/v1/observability/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/observability/metrics/` | `metrics_view` | - | Function-based |
| GET | `/api/v1/observability/observability/freshness/` | `ObservabilityViewSet.get_freshness_dashboard` | get_freshness_dashboard | Custom |
| GET | `/api/v1/observability/observability/freshness/stale/` | `ObservabilityViewSet.get_stale_data` | get_stale_data | Custom |
| GET | `/api/v1/observability/observability/incidents/` | `ObservabilityViewSet.get_incidents_dashboard` | get_incidents_dashboard | Custom |
| POST | `/api/v1/observability/observability/incidents/` | `ObservabilityViewSet.create_incident` | create_incident | Custom |
| PATCH | `/api/v1/observability/observability/incidents/update/` | `ObservabilityViewSet.update_incident` | update_incident | Custom |
| GET | `/api/v1/observability/observability/pipelines/` | `ObservabilityViewSet.get_pipeline_dashboard` | get_pipeline_dashboard | Custom |
| GET | `/api/v1/observability/observability/schema-drift/` | `ObservabilityViewSet.get_schema_drift_dashboard` | get_schema_drift_dashboard | Custom |
| POST | `/api/v1/observability/observability/schema-drift/detect/` | `ObservabilityViewSet.detect_schema_drift` | detect_schema_drift | Custom |
| GET | `/api/v1/observability/observability/slas/` | `ObservabilityViewSet.get_slas_dashboard` | get_slas_dashboard | Custom |
| GET | `/api/v1/observability/observability/volume/` | `ObservabilityViewSet.get_volume_dashboard` | get_volume_dashboard | Custom |
| POST | `/api/v1/observability/observability/volume/aggregate/` | `ObservabilityViewSet.aggregate_volume_trends` | aggregate_volume_trends | Custom |
| POST | `/api/v1/observability/observability/metrics/` | `ObservabilityViewSet.record_metric` | record_metric | Custom |

### Scheduled Ingestion (5 endpoints)

**Base Route**: `/api/v1/scheduled-ingestions/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/scheduled-ingestions/` | `ScheduledIngestionViewSet.list` | list | Standard |
| POST | `/api/v1/scheduled-ingestions/` | `ScheduledIngestionViewSet.create` | create | Standard |
| GET | `/api/v1/scheduled-ingestions/{id}/` | `ScheduledIngestionViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/scheduled-ingestions/runs/dashboard/` | `ScheduledIngestionRunViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/scheduled-ingestions/runs/costs/` | `ScheduledIngestionRunViewSet.costs` | costs | Custom |
| GET | `/api/v1/scheduled-ingestions/runs/dead-letter-queue/` | `ScheduledIngestionRunViewSet.dead_letter_queue` | dead_letter_queue | Custom |
| POST | `/api/v1/scheduled-ingestions/runs/{id}/trigger/` | `ScheduledIngestionRunViewSet.trigger` | trigger | Custom |

### Search (5 endpoints)

**Base Route**: `/api/v1/search/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/search/search/` | `SearchViewSet.search` | search | Custom |
| GET | `/api/v1/search/search/suggestions/` | `SearchViewSet.suggestions` | suggestions | Custom |
| GET | `/api/v1/search/search/analytics/` | `SearchViewSet.analytics` | analytics | Custom |
| POST | `/api/v1/search/search/rebuild-index/` | `SearchViewSet.rebuild_index` | rebuild_index | Custom |
| POST | `/api/v1/search/search/track-click/` | `SearchViewSet.track_click` | track_click | Custom |

### Semantic (5 endpoints)

**Base Route**: `/api/v1/semantic/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/semantic/semantic-resources/` | `SemanticResourceViewSet.list` | list | Standard |
| POST | `/api/v1/semantic/semantic-resources/` | `SemanticResourceViewSet.create` | create | Standard |
| GET | `/api/v1/semantic/semantic-resources/{id}/` | `SemanticResourceViewSet.retrieve` | retrieve | Standard |
| GET | `/api/v1/semantic/sparql` | `sparql_query` | - | Function-based |
| GET | `/api/v1/semantic/id/{resource_type}/{resource_id}` | `resolve_uri` | - | Function-based |
| GET | `/api/v1/semantic/id/field/{asset_uuid}/{field_name}` | `resolve_field_uri` | - | Function-based |
| GET | `/api/v1/semantic/ontology` | `get_ontology` | - | Function-based |
| GET | `/api/v1/semantic/context.jsonld` | `get_jsonld_context` | - | Function-based |

### Tenants (8 endpoints)

**Base Route**: `/api/v1/tenants/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/tenants/` | `TenantViewSet.list` | list | Standard |
| POST | `/api/v1/tenants/` | `TenantViewSet.create` | create | Standard |
| GET | `/api/v1/tenants/{id}/` | `TenantViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/tenants/{id}/` | `TenantViewSet.update` | update | Standard |
| PATCH | `/api/v1/tenants/{id}/` | `TenantViewSet.partial_update` | partial_update | Standard |
| DELETE | `/api/v1/tenants/{id}/` | `TenantViewSet.destroy` | destroy | Standard |
| POST | `/api/v1/tenants/{id}/suspend/` | `TenantViewSet.suspend` | suspend | Custom |
| POST | `/api/v1/tenants/{id}/reactivate/` | `TenantViewSet.reactivate` | reactivate | Custom |
| GET | `/api/v1/tenants/{tenant_id}/config/` | `TenantConfigViewSet.retrieve` | retrieve | Custom |
| PATCH | `/api/v1/tenants/{tenant_id}/config/` | `TenantConfigViewSet.partial_update` | partial_update | Custom |

### Users (16 endpoints)

**Base Route**: `/api/v1/users/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/users/users/` | `UserViewSet.list` | list | Standard |
| POST | `/api/v1/users/users/` | `UserViewSet.create` | create | Standard |
| GET | `/api/v1/users/users/{id}/` | `UserViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/users/users/{id}/` | `UserViewSet.update` | update | Standard |
| PATCH | `/api/v1/users/users/{id}/` | `UserViewSet.partial_update` | partial_update | Standard |
| DELETE | `/api/v1/users/users/{id}/` | `UserViewSet.destroy` | destroy | Standard |
| POST | `/api/v1/users/users/invite/` | `UserViewSet.invite` | invite | Custom |
| POST | `/api/v1/users/users/{id}/roles/` | `UserViewSet.manage_roles` | manage_roles | Custom |
| GET | `/api/v1/users/roles/` | `RoleViewSet.list` | list | Standard |
| POST | `/api/v1/users/roles/` | `RoleViewSet.create` | create | Standard |
| GET | `/api/v1/users/roles/{id}/` | `RoleViewSet.retrieve` | retrieve | Standard |
| PUT | `/api/v1/users/roles/{id}/` | `RoleViewSet.update` | update | Standard |
| PATCH | `/api/v1/users/roles/{id}/` | `RoleViewSet.partial_update` | partial_update | Standard |
| DELETE | `/api/v1/users/roles/{id}/` | `RoleViewSet.destroy` | destroy | Standard |
| POST | `/api/v1/users/roles/invite/` | `RoleViewSet.invite` | invite | Custom |
| POST | `/api/v1/users/roles/{id}/roles/` | `RoleViewSet.manage_roles` | manage_roles | Custom |

### Webhooks (6 endpoints)

**Base Route**: `/api/v1/webhooks/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/webhooks/webhooks/` | `WebhookViewSet.list` | list | Standard |
| POST | `/api/v1/webhooks/webhooks/` | `WebhookViewSet.create` | create | Standard |
| GET | `/api/v1/webhooks/webhooks/{id}/` | `WebhookViewSet.retrieve` | retrieve | Standard |
| POST | `/api/v1/webhooks/webhooks/{id}/retry/` | `WebhookViewSet.retry_delivery` | retry_delivery | Custom |
| POST | `/api/v1/webhooks/webhooks/{id}/test/` | `WebhookViewSet.test_webhook` | test_webhook | Custom |
| GET | `/api/v1/webhooks/webhooks/{id}/deliveries/` | `WebhookViewSet.deliveries` | deliveries | Custom |
| GET | `/api/v1/webhooks/webhook-deliveries/` | `WebhookDeliveryViewSet.list` | list | Standard |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/` | `WebhookDeliveryViewSet.retrieve` | retrieve | Standard |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | `WebhookDeliveryViewSet.retry_delivery` | retry_delivery | Custom |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/test/` | `WebhookDeliveryViewSet.test_webhook` | test_webhook | Custom |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/deliveries/` | `WebhookDeliveryViewSet.deliveries` | deliveries | Custom |

---


## Categorization

- **Total Endpoints:** 148
- **With Schema:** 139 (93%)
- **With Tests:** 139 (93%)
- **Deprecated:** 0


## Summary Statistics

- **Total Endpoints**: 148
- **Standard CRUD Actions**: 56
- **Custom Actions**: 92
- **Function-based Views**: 10

### Methods Breakdown

- **GET**: 84 endpoints
- **POST**: 46 endpoints
- **DELETE**: 8 endpoints
- **PUT**: 6 endpoints
- **PATCH**: 4 endpoints

### Endpoint Types

- **ViewSet Standard Actions**: 56 (list, create, retrieve, update, partial_update, destroy)
- **ViewSet Custom Actions**: 82 (via @action decorators)
- **Function-based Views**: 10 (custom path() routes)

---

## Deprecated Endpoints

**Status**: No deprecated endpoints found in `APIVersionManager.DEPRECATED_ENDPOINTS` registry.

**Note**: The deprecation system exists (`hub/apps/api/versioning.py`) but no endpoints are currently registered as deprecated. To mark an endpoint as deprecated, use:

```python
from hub.apps.api.versioning import APIVersionManager, DeprecatedEndpoint

endpoint = DeprecatedEndpoint(
    path="/api/v1/old-endpoint/",
    method="GET",
    deprecated_since="2024-01-01",
    sunset_date="2025-01-01",  # Optional
    replacement_path="/api/v1/new-endpoint/"  # Optional
)
APIVersionManager.register_deprecated_endpoint(endpoint)
```

---

## Endpoints Not in OpenAPI Schema

**Status**: Comparison with OpenAPI schema will be performed in Task 0.2.1 (Extract current APIs from OpenAPI schema).

**Next Steps**:
1. Fetch OpenAPI schema from `/api/v1/openapi.json`
2. Compare codebase endpoints with OpenAPI schema
3. Document missing endpoints
4. Document endpoints with incomplete schemas

---

## Notes

### Backward Compatibility Routes

Some apps maintain backward compatibility routes:
- **Compliance**: `/api/v1/compliance/runs/` (in addition to `/api/v1/compliance/compliance-runs/`)
- **DQ**: `/api/v1/dq/runs/` (in addition to `/api/v1/dq/dq-runs/`)

### GraphQL Endpoints

GraphQL endpoints are not included in this inventory:
- `/api/v1/graphql/` (GraphQL endpoint)
- `/api/v1/graphql-graphene/` (Graphene GraphQL endpoint)

### Health Check

- `/api/v1/health/` - Health check endpoint (not detailed here)

### OpenAPI Schema Endpoints

- `/api/v1/openapi.json` - OpenAPI JSON schema
- `/api/v1/openapi.yaml` - OpenAPI YAML schema

---

## Extraction Script

The extraction was performed using: `docs/api-audit/extract-endpoints-from-codebase.py`

**Script Features**:
- Parses all `hub/apps/*/urls.py` files
- Extracts router registrations and custom path() routes
- Identifies ViewSet actions (standard + custom @action decorators)
- Generates full API paths with proper formatting
- Removes duplicate resource segments

---

**Document Status**: ✅ Complete  
**Total Endpoints Extracted**: 148  
**Next Task**: 0.2.1 - Extract current APIs from OpenAPI schema (for comparison)

---

**Last Updated**: 2025-12-13
