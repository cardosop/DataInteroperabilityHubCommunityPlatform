# Current API Inventory from Codebase

**Document Version**: 1.0.0
**Last Updated**: 2025-12-13
**Source**: `hub/apps/*/urls.py` files
**Task**: 0.2.2 - Review codebase for API endpoints

---

## Overview

This document inventories all API endpoints extracted from the codebase.
**Total Endpoints Found**: 148

## Endpoints by Application

### Analytics (4 endpoints)

#### Api-Analytics

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/api-analytics/api/dashboard/` | `APIAnalyticsViewSet.dashboard` | dashboard | Custom action: dashboard (custom) |
| GET | `/api/v1/api-analytics/api/performance/` | `APIAnalyticsViewSet.performance` | performance | Custom action: performance (custom) |
| GET | `/api/v1/api-analytics/api/popular-endpoints/` | `APIAnalyticsViewSet.popular_endpoints` | popular_endpoints | Custom action: popular_endpoints (custom) |
| GET | `/api/v1/api-analytics/api/usage-trends/` | `APIAnalyticsViewSet.usage_trends` | usage_trends | Custom action: usage_trends (custom) |

### Assets (13 endpoints)

#### Assets

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/assets/{id}/` | `AssetViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/assets/` | `AssetViewSet.list` | list | Standard list action |
| GET | `/api/v1/assets/recommendations/` | `AssetViewSet.recommendations` | recommendations | Custom action: recommendations (custom) |
| GET | `/api/v1/assets/{id}/` | `AssetViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/assets/{id}/dependencies/` | `AssetViewSet.dependencies` | dependencies | Custom action: dependencies (custom) |
| GET | `/api/v1/assets/{id}/health-score/` | `AssetViewSet.health_score` | health_score | Custom action: health_score (custom) |
| POST | `/api/v1/assets/` | `AssetViewSet.create` | create | Standard create action |
| POST | `/api/v1/assets/{id}/activate/` | `AssetViewSet.activate` | activate | Custom action: activate (custom) |
| POST | `/api/v1/assets/{id}/contracts/` | `AssetViewSet.attach_contract` | attach_contract | Custom action: attach_contract (custom) |
| POST | `/api/v1/assets/{id}/datasets/` | `AssetViewSet.attach_dataset` | attach_dataset | Custom action: attach_dataset (custom) |
| POST | `/api/v1/assets/{id}/track-download/` | `AssetViewSet.track_download` | track_download | Custom action: track_download (custom) |
| POST | `/api/v1/assets/{id}/track-view/` | `AssetViewSet.track_view` | track_view | Custom action: track_view (custom) |
| PUT | `/api/v1/assets/{id}/` | `AssetViewSet.update` | update | Standard update action |

### Audit (3 endpoints)

#### Audit

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/audit/audit-events/` | `AuditEventViewSet.list` | list | Standard list action |
| GET | `/api/v1/audit/audit-events/export/` | `AuditEventViewSet.export` | export | Custom action: export (custom) |
| GET | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.retrieve` | retrieve | Standard retrieve action |

### Auth (10 endpoints)

#### Auth

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/auth/accept-invitation` | `accept_invitation` | N/A | Custom endpoint: accept-invitation (custom) |
| GET | `/api/v1/auth/api-keys/` | `APIKeyViewSet.list` | list | Standard list action |
| GET | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/auth/login` | `login` | N/A | Custom endpoint: login (custom) |
| GET | `/api/v1/auth/logout` | `logout` | N/A | Custom endpoint: logout (custom) |
| GET | `/api/v1/auth/password-reset` | `password_reset_request` | N/A | Custom endpoint: password-reset-request (custom) |
| GET | `/api/v1/auth/password-reset/confirm` | `password_reset_confirm` | N/A | Custom endpoint: password-reset-confirm (custom) |
| GET | `/api/v1/auth/refresh` | `refresh_token` | N/A | Custom endpoint: refresh-token (custom) |
| POST | `/api/v1/auth/api-keys/` | `APIKeyViewSet.create` | create | Standard create action |

### Compliance (4 endpoints)

#### Compliance

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/compliance/compliance-runs/` | `ComplianceRunViewSet.list` | list | Standard list action |
| GET | `/api/v1/compliance/compliance-runs/{id}/` | `ComplianceRunViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/compliance/runs/<uuid:id>` | `ComplianceRunViewSet.as_view({"get": "retrieve"})` | N/A | Custom endpoint: compliance-run-detail (custom) |
| POST | `/api/v1/compliance/compliance-runs/` | `ComplianceRunViewSet.create` | create | Standard create action |

### Contracts (13 endpoints)

#### Contracts

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/contracts/{id}/` | `ContractViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/contracts/` | `ContractViewSet.list` | list | Standard list action |
| GET | `/api/v1/contracts/{id}/` | `ContractViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/contracts/{id}/impact-analysis/` | `ContractViewSet.get_impact_analysis` | get_impact_analysis | Custom action: get_impact_analysis (custom) |
| GET | `/api/v1/contracts/{id}/lineage/contracts/` | `ContractViewSet.get_contract_lineage` | get_contract_lineage | Custom action: get_contract_lineage (custom) |
| GET | `/api/v1/contracts/{id}/lineage/full/` | `ContractViewSet.get_hierarchical_lineage` | get_hierarchical_lineage | Custom action: get_hierarchical_lineage (custom) |
| GET | `/api/v1/contracts/{id}/lineage/visualization/` | `ContractViewSet.get_lineage_visualization` | get_lineage_visualization | Custom action: get_lineage_visualization (custom) |
| POST | `/api/v1/contracts/` | `ContractViewSet.create` | create | Standard create action |
| POST | `/api/v1/contracts/{id}/convert/` | `ContractViewSet.convert_contract` | convert_contract | Custom action: convert_contract (custom) |
| POST | `/api/v1/contracts/{id}/lint/` | `ContractViewSet.lint_contract` | lint_contract | Custom action: lint_contract (custom) |
| POST | `/api/v1/contracts/{id}/migrate/` | `ContractViewSet.migrate_contract` | migrate_contract | Custom action: migrate_contract (custom) |
| POST | `/api/v1/contracts/{id}/validate/` | `ContractViewSet.validate_contract` | validate_contract | Custom action: validate_contract (custom) |
| PUT | `/api/v1/contracts/{id}/` | `ContractViewSet.update` | update | Standard update action |

### Datasets (5 endpoints)

#### Datasets

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/datasets/` | `DatasetViewSet.list` | list | Standard list action |
| GET | `/api/v1/datasets/{id}/` | `DatasetViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/datasets/{id}/versions/` | `DatasetViewSet.versions` | versions | Custom action: versions (custom) |
| GET | `/api/v1/datasets/{id}/versions/compare/` | `DatasetViewSet.compare_versions` | compare_versions | Custom action: compare_versions (custom) |
| POST | `/api/v1/datasets/` | `DatasetViewSet.create` | create | Standard create action |

### Dq (6 endpoints)

#### Dq

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/dq/dq-runs/` | `DQRunViewSet.list` | list | Standard list action |
| GET | `/api/v1/dq/dq-runs/{id}/` | `DQRunViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/dq/runs/` | `DQRunViewSet.list` | list | Standard list action |
| GET | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.retrieve` | retrieve | Standard retrieve action |
| POST | `/api/v1/dq/dq-runs/` | `DQRunViewSet.create` | create | Standard create action |
| POST | `/api/v1/dq/runs/` | `DQRunViewSet.create` | create | Standard create action |

### Files (7 endpoints)

#### Files

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/files/{id}/` | `FileViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/files/` | `FileViewSet.list` | list | Standard list action |
| GET | `/api/v1/files/{id}/` | `FileViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/files/{id}/download/` | `FileViewSet.download` | download | Custom action: download (custom) |
| POST | `/api/v1/files/init/` | `FileViewSet.init_upload` | init_upload | Custom action: init_upload (custom) |
| POST | `/api/v1/files/{id}/chunks/init/` | `FileViewSet.init_chunk_upload` | init_chunk_upload | Custom action: init_chunk_upload (custom) |
| POST | `/api/v1/files/{id}/complete/` | `FileViewSet.complete_upload` | complete_upload | Custom action: complete_upload (custom) |

### Governance (16 endpoints)

#### Governance

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/governance/analytics/anomalies/` | `AccessAnalyticsViewSet.anomalies` | anomalies | Custom action: anomalies (custom) |
| GET | `/api/v1/governance/analytics/dashboard/` | `AccessAnalyticsViewSet.dashboard` | dashboard | Custom action: dashboard (custom) |
| GET | `/api/v1/governance/analytics/expiring/` | `AccessAnalyticsViewSet.expiring` | expiring | Custom action: expiring (custom) |
| GET | `/api/v1/governance/analytics/patterns/` | `AccessAnalyticsViewSet.patterns` | patterns | Custom action: patterns (custom) |
| GET | `/api/v1/governance/analytics/security-events/` | `AccessAnalyticsViewSet.security_events` | security_events | Custom action: security_events (custom) |
| GET | `/api/v1/governance/analytics/summary/` | `AccessAnalyticsViewSet.summary` | summary | Custom action: summary (custom) |
| GET | `/api/v1/governance/certifications/anomalies/` | `AccessCertificationViewSet.anomalies` | anomalies | Custom action: anomalies (custom) |
| GET | `/api/v1/governance/certifications/dashboard/` | `AccessCertificationViewSet.dashboard` | dashboard | Custom action: dashboard (custom) |
| GET | `/api/v1/governance/certifications/expiring/` | `AccessCertificationViewSet.expiring` | expiring | Custom action: expiring (custom) |
| GET | `/api/v1/governance/certifications/patterns/` | `AccessCertificationViewSet.patterns` | patterns | Custom action: patterns (custom) |
| GET | `/api/v1/governance/certifications/security-events/` | `AccessCertificationViewSet.security_events` | security_events | Custom action: security_events (custom) |
| GET | `/api/v1/governance/certifications/summary/` | `AccessCertificationViewSet.summary` | summary | Custom action: summary (custom) |
| POST | `/api/v1/governance/analytics/initiate-review/` | `AccessAnalyticsViewSet.initiate_review` | initiate_review | Custom action: initiate_review (custom) |
| POST | `/api/v1/governance/analytics/{id}/review/` | `AccessAnalyticsViewSet.review` | review | Custom action: review (custom) |
| POST | `/api/v1/governance/certifications/initiate-review/` | `AccessCertificationViewSet.initiate_review` | initiate_review | Custom action: initiate_review (custom) |
| POST | `/api/v1/governance/certifications/{id}/review/` | `AccessCertificationViewSet.review` | review | Custom action: review (custom) |

### Jobs (4 endpoints)

#### Jobs

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/jobs/` | `JobViewSet.list` | list | Standard list action |
| GET | `/api/v1/jobs/{id}/` | `JobViewSet.retrieve` | retrieve | Standard retrieve action |
| POST | `/api/v1/jobs/` | `JobViewSet.create` | create | Standard create action |
| POST | `/api/v1/jobs/{id}/cancel/` | `JobViewSet.cancel` | cancel | Custom action: cancel (custom) |

### Marketplace (5 endpoints)

#### Marketplace

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/marketplace/listings/search/` | `ListingViewSet.search` | search | Custom action: search (custom) |
| GET | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.retrieve` | retrieve | Standard retrieve action |
| POST | `/api/v1/marketplace/listings/` | `ListingViewSet.create` | create | Standard create action |
| PUT | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.update` | update | Standard update action |

### Observability (13 endpoints)

#### Observability

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/observability/freshness/` | `ObservabilityViewSet.get_freshness_dashboard` | get_freshness_dashboard | Custom action: get_freshness_dashboard (custom) |
| GET | `/api/v1/observability/freshness/stale/` | `ObservabilityViewSet.get_stale_data` | get_stale_data | Custom action: get_stale_data (custom) |
| GET | `/api/v1/observability/incidents/` | `ObservabilityViewSet.get_incidents_dashboard` | get_incidents_dashboard | Custom action: get_incidents_dashboard (custom) |
| GET | `/api/v1/observability/metrics` | `metrics_view` | N/A | Custom endpoint: prometheus-metrics (custom) |
| GET | `/api/v1/observability/pipelines/` | `ObservabilityViewSet.get_pipeline_dashboard` | get_pipeline_dashboard | Custom action: get_pipeline_dashboard (custom) |
| GET | `/api/v1/observability/schema-drift/` | `ObservabilityViewSet.get_schema_drift_dashboard` | get_schema_drift_dashboard | Custom action: get_schema_drift_dashboard (custom) |
| GET | `/api/v1/observability/slas/` | `ObservabilityViewSet.get_slas_dashboard` | get_slas_dashboard | Custom action: get_slas_dashboard (custom) |
| GET | `/api/v1/observability/volume/` | `ObservabilityViewSet.get_volume_dashboard` | get_volume_dashboard | Custom action: get_volume_dashboard (custom) |
| PATCH | `/api/v1/observability/incidents/update/` | `ObservabilityViewSet.update_incident` | update_incident | Custom action: update_incident (custom) |
| POST | `/api/v1/observability/incidents/` | `ObservabilityViewSet.create_incident` | create_incident | Custom action: create_incident (custom) |
| POST | `/api/v1/observability/metrics/` | `ObservabilityViewSet.record_metric` | record_metric | Custom action: record_metric (custom) |
| POST | `/api/v1/observability/schema-drift/detect/` | `ObservabilityViewSet.detect_schema_drift` | detect_schema_drift | Custom action: detect_schema_drift (custom) |
| POST | `/api/v1/observability/volume/aggregate/` | `ObservabilityViewSet.aggregate_volume_trends` | aggregate_volume_trends | Custom action: aggregate_volume_trends (custom) |

### Scheduled Ingestion (5 endpoints)

#### Scheduled-Ingestion

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/scheduled-ingestion/runs/costs/` | `ScheduledIngestionRunViewSet.costs` | costs | Custom action: costs (custom) |
| GET | `/api/v1/scheduled-ingestion/runs/dashboard/` | `ScheduledIngestionRunViewSet.dashboard` | dashboard | Custom action: dashboard (custom) |
| GET | `/api/v1/scheduled-ingestion/runs/dead-letter-queue/` | `ScheduledIngestionRunViewSet.dead_letter_queue` | dead_letter_queue | Custom action: dead_letter_queue (custom) |
| GET | `/api/v1/scheduled-ingestion/runs/{id}/runs/` | `ScheduledIngestionRunViewSet.runs` | runs | Custom action: runs (custom) |
| POST | `/api/v1/scheduled-ingestion/runs/{id}/trigger/` | `ScheduledIngestionRunViewSet.trigger` | trigger | Custom action: trigger (custom) |

### Search (5 endpoints)

#### Search

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/search/` | `SearchViewSet.search` | search | Custom action: search (custom) |
| GET | `/api/v1/search/analytics/` | `SearchViewSet.analytics` | analytics | Custom action: analytics (custom) |
| GET | `/api/v1/search/suggestions/` | `SearchViewSet.suggestions` | suggestions | Custom action: suggestions (custom) |
| POST | `/api/v1/search/rebuild-index/` | `SearchViewSet.rebuild_index` | rebuild_index | Custom action: rebuild_index (custom) |
| POST | `/api/v1/search/track-click/` | `SearchViewSet.track_click` | track_click | Custom action: track_click (custom) |

### Semantic (5 endpoints)

#### Semantic

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/semantic/context.jsonld` | `get_jsonld_context` | N/A | Custom endpoint: get-jsonld-context (custom) |
| GET | `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>` | `resolve_uri` | N/A | Custom endpoint: resolve-uri (custom) |
| GET | `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>` | `resolve_field_uri` | N/A | Custom endpoint: resolve-field-uri (custom) |
| GET | `/api/v1/semantic/ontology` | `get_ontology` | N/A | Custom endpoint: get-ontology (custom) |
| GET | `/api/v1/semantic/sparql` | `sparql_query` | N/A | Custom endpoint: sparql-query (custom) |

### Tenants (8 endpoints)

#### Tenants

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/tenants/{id}/` | `TenantViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/tenants/` | `TenantViewSet.list` | list | Standard list action |
| GET | `/api/v1/tenants/{id}/` | `TenantViewSet.retrieve` | retrieve | Standard retrieve action |
| PATCH | `/api/v1/tenants/{id}/` | `TenantViewSet.partial_update` | partial_update | Standard partial_update action |
| POST | `/api/v1/tenants/` | `TenantViewSet.create` | create | Standard create action |
| POST | `/api/v1/tenants/{id}/reactivate/` | `TenantViewSet.reactivate` | reactivate | Custom action: reactivate (custom) |
| POST | `/api/v1/tenants/{id}/suspend/` | `TenantViewSet.suspend` | suspend | Custom action: suspend (custom) |
| PUT | `/api/v1/tenants/{id}/` | `TenantViewSet.update` | update | Standard update action |

### Users (16 endpoints)

#### Users

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| DELETE | `/api/v1/users/roles/{id}/` | `RoleViewSet.destroy` | destroy | Standard destroy action |
| DELETE | `/api/v1/users/{id}/` | `UserViewSet.destroy` | destroy | Standard destroy action |
| GET | `/api/v1/users/` | `UserViewSet.list` | list | Standard list action |
| GET | `/api/v1/users/roles/` | `RoleViewSet.list` | list | Standard list action |
| GET | `/api/v1/users/roles/{id}/` | `RoleViewSet.retrieve` | retrieve | Standard retrieve action |
| GET | `/api/v1/users/{id}/` | `UserViewSet.retrieve` | retrieve | Standard retrieve action |
| PATCH | `/api/v1/users/roles/{id}/` | `RoleViewSet.partial_update` | partial_update | Standard partial_update action |
| PATCH | `/api/v1/users/{id}/` | `UserViewSet.partial_update` | partial_update | Standard partial_update action |
| POST | `/api/v1/users/` | `UserViewSet.create` | create | Standard create action |
| POST | `/api/v1/users/invite/` | `UserViewSet.invite` | invite | Custom action: invite (custom) |
| POST | `/api/v1/users/roles/` | `RoleViewSet.create` | create | Standard create action |
| POST | `/api/v1/users/roles/invite/` | `RoleViewSet.invite` | invite | Custom action: invite (custom) |
| POST | `/api/v1/users/roles/{id}/roles/` | `RoleViewSet.manage_roles` | manage_roles | Custom action: manage_roles (custom) |
| POST | `/api/v1/users/{id}/roles/` | `UserViewSet.manage_roles` | manage_roles | Custom action: manage_roles (custom) |
| PUT | `/api/v1/users/roles/{id}/` | `RoleViewSet.update` | update | Standard update action |
| PUT | `/api/v1/users/{id}/` | `UserViewSet.update` | update | Standard update action |

### Webhooks (6 endpoints)

#### Webhooks

| Method | Path | View | Action | Description |
|--------|------|------|--------|-------------|
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/deliveries/` | `WebhookDeliveryViewSet.deliveries` | deliveries | Custom action: deliveries (custom) |
| GET | `/api/v1/webhooks/{id}/deliveries/` | `WebhookViewSet.deliveries` | deliveries | Custom action: deliveries (custom) |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | `WebhookDeliveryViewSet.retry_delivery` | retry_delivery | Custom action: retry_delivery (custom) |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/test/` | `WebhookDeliveryViewSet.test_webhook` | test_webhook | Custom action: test_webhook (custom) |
| POST | `/api/v1/webhooks/{id}/retry/` | `WebhookViewSet.retry_delivery` | retry_delivery | Custom action: retry_delivery (custom) |
| POST | `/api/v1/webhooks/{id}/test/` | `WebhookViewSet.test_webhook` | test_webhook | Custom action: test_webhook (custom) |

## Summary Statistics

- **Total Endpoints**: 148
- **Custom Actions**: 92
- **Standard CRUD**: 56

**Methods Breakdown**:
- DELETE: 8
- GET: 84
- PATCH: 4
- POST: 46
- PUT: 6

---

**Document Status**: ✅ Complete
**Total Endpoints Extracted**: 148

**Next Steps**:
1. Compare with OpenAPI schema to identify missing endpoints
2. Identify deprecated endpoints (if any markers exist)
3. Document endpoints not in OpenAPI schema
