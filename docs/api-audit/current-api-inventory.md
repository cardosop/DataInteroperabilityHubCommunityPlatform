# Current API Inventory from Codebase

**Document Version**: 2.0.0
**Last Updated**: 2026-01-05
**Source**: Static analysis of Django URL patterns and ViewSets
**Task**: 9.6.3.3.2 - Update API inventory files

---

## Overview

This document inventories all API endpoints extracted from the Django codebase by:
1. Parsing all `hub/apps/*/urls.py` files to extract URL patterns
2. Analyzing ViewSet classes to identify custom @action decorators
3. Extracting function-based views
4. Verifying endpoint patterns match standardized conventions

**Total Endpoints Found**: 370

---

## Endpoints by Application

### Ai (8 endpoints)

**Base Route**: `/api/v1/ai/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/ai/ai/` | `AIViewSet.list` | list | Standard |
| POST | `/api/v1/ai/ai/` | `AIViewSet.create` | create | Standard |
| POST | `/api/v1/ai/ai/natural-language-search/` | `AIViewSet.natural_language_search` | natural_language_search | Custom |
| POST | `/api/v1/ai/ai/schema-matching/` | `AIViewSet.schema_matching` | schema_matching | Custom |
| DELETE | `/api/v1/ai/ai/{id}/` | `AIViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/ai/ai/{id}/` | `AIViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/ai/ai/{id}/` | `AIViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/ai/ai/{id}/` | `AIViewSet.update` | update | Standard |

### Analytics (10 endpoints)

**Base Route**: `/api/v1/analytics/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/analytics/api/` | `APIAnalyticsViewSet.list` | list | Standard |
| POST | `/api/v1/analytics/api/` | `APIAnalyticsViewSet.create` | create | Standard |
| GET | `/api/v1/analytics/api/dashboard/` | `APIAnalyticsViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/analytics/api/performance/` | `APIAnalyticsViewSet.performance` | performance | Custom |
| GET | `/api/v1/analytics/api/popular-endpoints/` | `APIAnalyticsViewSet.popular_endpoints` | popular_endpoints | Custom |
| GET | `/api/v1/analytics/api/usage-trends/` | `APIAnalyticsViewSet.usage_trends` | usage_trends | Custom |
| DELETE | `/api/v1/analytics/api/{id}/` | `APIAnalyticsViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/analytics/api/{id}/` | `APIAnalyticsViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/analytics/api/{id}/` | `APIAnalyticsViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/analytics/api/{id}/` | `APIAnalyticsViewSet.update` | update | Standard |

### Assets (14 endpoints)

**Base Route**: `/api/v1/assets/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/assets/assets/` | `AssetViewSet.list` | list | Standard |
| POST | `/api/v1/assets/assets/` | `AssetViewSet.create` | create | Standard |
| GET | `/api/v1/assets/assets/recommendations/` | `AssetViewSet.recommendations` | recommendations | Custom |
| DELETE | `/api/v1/assets/assets/{id}/` | `AssetViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/assets/assets/{id}/` | `AssetViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/assets/assets/{id}/` | `AssetViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/assets/assets/{id}/` | `AssetViewSet.update` | update | Standard |
| POST | `/api/v1/assets/assets/{id}/activate/` | `AssetViewSet.activate` | activate | Custom |
| POST | `/api/v1/assets/assets/{id}/contracts/` | `AssetViewSet.attach_contract` | attach_contract | Custom |
| POST | `/api/v1/assets/assets/{id}/datasets/` | `AssetViewSet.attach_dataset` | attach_dataset | Custom |
| GET | `/api/v1/assets/assets/{id}/dependencies/` | `AssetViewSet.dependencies` | dependencies | Custom |
| GET | `/api/v1/assets/assets/{id}/health-score/` | `AssetViewSet.health_score` | health_score | Custom |
| POST | `/api/v1/assets/assets/{id}/track-download/` | `AssetViewSet.track_download` | track_download | Custom |
| POST | `/api/v1/assets/assets/{id}/track-view/` | `AssetViewSet.track_view` | track_view | Custom |

### Audit (7 endpoints)

**Base Route**: `/api/v1/audit/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/audit/audit-events/` | `AuditEventViewSet.list` | list | Standard |
| POST | `/api/v1/audit/audit-events/` | `AuditEventViewSet.create` | create | Standard |
| GET | `/api/v1/audit/audit-events/export/` | `AuditEventViewSet.export` | export | Custom |
| DELETE | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/audit/audit-events/{id}/` | `AuditEventViewSet.update` | update | Standard |

### Auth (32 endpoints)

**Base Route**: `/api/v1/auth/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/auth/accept-invitation/` | `accept_invitation` | accept_invitation | Function-based |
| POST | `/api/v1/auth/accept-invitation/` | `accept_invitation` | accept_invitation | Function-based |
| GET | `/api/v1/auth/api-keys/` | `APIKeyViewSet.list` | list | Standard |
| POST | `/api/v1/auth/api-keys/` | `APIKeyViewSet.create` | create | Standard |
| DELETE | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/auth/api-keys/{id}/` | `APIKeyViewSet.update` | update | Standard |
| GET | `/api/v1/auth/login/` | `login` | login | Function-based |
| POST | `/api/v1/auth/login/` | `login` | login | Function-based |
| GET | `/api/v1/auth/logout/` | `logout` | logout | Function-based |
| POST | `/api/v1/auth/logout/` | `logout` | logout | Function-based |
| GET | `/api/v1/auth/me/` | `me` | me | Function-based |
| POST | `/api/v1/auth/me/` | `me` | me | Function-based |
| GET | `/api/v1/auth/password-reset/` | `password_reset_request` | password_reset_request | Function-based |
| POST | `/api/v1/auth/password-reset/` | `password_reset_request` | password_reset_request | Function-based |
| GET | `/api/v1/auth/password-reset/confirm/` | `password_reset_confirm` | password_reset_confirm | Function-based |
| POST | `/api/v1/auth/password-reset/confirm/` | `password_reset_confirm` | password_reset_confirm | Function-based |
| GET | `/api/v1/auth/refresh/` | `refresh_token` | refresh_token | Function-based |
| POST | `/api/v1/auth/refresh/` | `refresh_token` | refresh_token | Function-based |
| GET | `/api/v1/auth/register/` | `register` | register | Function-based |
| POST | `/api/v1/auth/register/` | `register` | register | Function-based |
| GET | `/api/v1/auth/sessions/` | `list_active_sessions` | list_active_sessions | Function-based |
| POST | `/api/v1/auth/sessions/` | `list_active_sessions` | list_active_sessions | Function-based |
| GET | `/api/v1/auth/sessions/<uuid:session_id>/revoke/` | `revoke_session` | revoke_session | Function-based |
| POST | `/api/v1/auth/sessions/<uuid:session_id>/revoke/` | `revoke_session` | revoke_session | Function-based |
| GET | `/api/v1/auth/sso/` | `SSOViewSet.list` | list | Standard |
| POST | `/api/v1/auth/sso/` | `SSOViewSet.create` | create | Standard |
| DELETE | `/api/v1/auth/sso/{id}/` | `SSOViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/auth/sso/{id}/` | `SSOViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/auth/sso/{id}/` | `SSOViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/auth/sso/{id}/` | `SSOViewSet.update` | update | Standard |

### Compliance (7 endpoints)

**Base Route**: `/api/v1/compliance/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/compliance/runs/` | `ComplianceRunViewSet.list` | list | Standard |
| POST | `/api/v1/compliance/runs/` | `ComplianceRunViewSet.create` | create | Standard |
| DELETE | `/api/v1/compliance/runs/{id}/` | `ComplianceRunViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/compliance/runs/{id}/` | `ComplianceRunViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/compliance/runs/{id}/` | `ComplianceRunViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/compliance/runs/{id}/` | `ComplianceRunViewSet.update` | update | Standard |
| GET | `/api/v1/compliance/runs/{id}/results/` | `ComplianceRunViewSet.results` | results | Custom |

### Datasets (9 endpoints)

**Base Route**: `/api/v1/datasets/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/datasets/datasets/` | `DatasetViewSet.list` | list | Standard |
| POST | `/api/v1/datasets/datasets/` | `DatasetViewSet.create` | create | Standard |
| DELETE | `/api/v1/datasets/datasets/{id}/` | `DatasetViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/datasets/datasets/{id}/` | `DatasetViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/datasets/datasets/{id}/` | `DatasetViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/datasets/datasets/{id}/` | `DatasetViewSet.update` | update | Standard |
| GET | `/api/v1/datasets/datasets/{id}/versions/` | `DatasetViewSet.versions` | versions | Custom |
| POST | `/api/v1/datasets/datasets/{id}/versions/` | `DatasetViewSet.versions` | versions | Custom |
| GET | `/api/v1/datasets/datasets/{id}/versions/compare/` | `DatasetViewSet.compare_versions` | compare_versions | Custom |

### Developer (12 endpoints)

**Base Route**: `/api/v1/developer/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/developer/plugins/` | `PluginViewSet.list` | list | Standard |
| POST | `/api/v1/developer/plugins/` | `PluginViewSet.create` | create | Standard |
| DELETE | `/api/v1/developer/plugins/{id}/` | `PluginViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/developer/plugins/{id}/` | `PluginViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/developer/plugins/{id}/` | `PluginViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/developer/plugins/{id}/` | `PluginViewSet.update` | update | Standard |
| GET | `/api/v1/developer/sdk/` | `SDKDocumentationViewSet.list` | list | Standard |
| POST | `/api/v1/developer/sdk/` | `SDKDocumentationViewSet.create` | create | Standard |
| DELETE | `/api/v1/developer/sdk/{id}/` | `SDKDocumentationViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/developer/sdk/{id}/` | `SDKDocumentationViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/developer/sdk/{id}/` | `SDKDocumentationViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/developer/sdk/{id}/` | `SDKDocumentationViewSet.update` | update | Standard |

### Dq (7 endpoints)

**Base Route**: `/api/v1/dq/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/dq/runs/` | `DQRunViewSet.list` | list | Standard |
| POST | `/api/v1/dq/runs/` | `DQRunViewSet.create` | create | Standard |
| DELETE | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/dq/runs/{id}/` | `DQRunViewSet.update` | update | Standard |
| GET | `/api/v1/dq/runs/{id}/results/` | `DQRunViewSet.results` | results | Custom |

### Events (2 endpoints)

**Base Route**: `/api/v1/events/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/events/replay/` | `replay_events` | replay_events | Function-based |
| POST | `/api/v1/events/replay/` | `replay_events` | replay_events | Function-based |

### Files (10 endpoints)

**Base Route**: `/api/v1/files/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/files/files/` | `FileViewSet.list` | list | Standard |
| POST | `/api/v1/files/files/` | `FileViewSet.create` | create | Standard |
| POST | `/api/v1/files/files/init/` | `FileViewSet.init_upload` | init_upload | Custom |
| DELETE | `/api/v1/files/files/{id}/` | `FileViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/files/files/{id}/` | `FileViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/files/files/{id}/` | `FileViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/files/files/{id}/` | `FileViewSet.update` | update | Standard |
| POST | `/api/v1/files/files/{id}/chunks/init/` | `FileViewSet.init_chunk_upload` | init_chunk_upload | Custom |
| POST | `/api/v1/files/files/{id}/complete/` | `FileViewSet.complete_upload` | complete_upload | Custom |
| GET | `/api/v1/files/files/{id}/download/` | `FileViewSet.download` | download | Custom |

### Governance (32 endpoints)

**Base Route**: `/api/v1/governance/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/governance/access-requests/` | `AccessRequestViewSet.list` | list | Standard |
| POST | `/api/v1/governance/access-requests/` | `AccessRequestViewSet.create` | create | Standard |
| DELETE | `/api/v1/governance/access-requests/{id}/` | `AccessRequestViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/governance/access-requests/{id}/` | `AccessRequestViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/governance/access-requests/{id}/` | `AccessRequestViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/governance/access-requests/{id}/` | `AccessRequestViewSet.update` | update | Standard |
| GET | `/api/v1/governance/analytics/` | `AccessAnalyticsViewSet.list` | list | Standard |
| POST | `/api/v1/governance/analytics/` | `AccessAnalyticsViewSet.create` | create | Standard |
| GET | `/api/v1/governance/analytics/anomalies/` | `AccessAnalyticsViewSet.anomalies` | anomalies | Custom |
| GET | `/api/v1/governance/analytics/dashboard/` | `AccessAnalyticsViewSet.dashboard` | dashboard | Custom |
| GET | `/api/v1/governance/analytics/patterns/` | `AccessAnalyticsViewSet.patterns` | patterns | Custom |
| GET | `/api/v1/governance/analytics/security-events/` | `AccessAnalyticsViewSet.security_events` | security_events | Custom |
| DELETE | `/api/v1/governance/analytics/{id}/` | `AccessAnalyticsViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/governance/analytics/{id}/` | `AccessAnalyticsViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/governance/analytics/{id}/` | `AccessAnalyticsViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/governance/analytics/{id}/` | `AccessAnalyticsViewSet.update` | update | Standard |
| GET | `/api/v1/governance/certifications/` | `AccessCertificationViewSet.list` | list | Standard |
| POST | `/api/v1/governance/certifications/` | `AccessCertificationViewSet.create` | create | Standard |
| GET | `/api/v1/governance/certifications/expiring/` | `AccessCertificationViewSet.expiring` | expiring | Custom |
| POST | `/api/v1/governance/certifications/initiate-review/` | `AccessCertificationViewSet.initiate_review` | initiate_review | Custom |
| GET | `/api/v1/governance/certifications/summary/` | `AccessCertificationViewSet.summary` | summary | Custom |
| DELETE | `/api/v1/governance/certifications/{id}/` | `AccessCertificationViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/governance/certifications/{id}/` | `AccessCertificationViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/governance/certifications/{id}/` | `AccessCertificationViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/governance/certifications/{id}/` | `AccessCertificationViewSet.update` | update | Standard |
| POST | `/api/v1/governance/certifications/{id}/review/` | `AccessCertificationViewSet.review` | review | Custom |
| GET | `/api/v1/governance/retention-policies/` | `RetentionPolicyViewSet.list` | list | Standard |
| POST | `/api/v1/governance/retention-policies/` | `RetentionPolicyViewSet.create` | create | Standard |
| DELETE | `/api/v1/governance/retention-policies/{id}/` | `RetentionPolicyViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/governance/retention-policies/{id}/` | `RetentionPolicyViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/governance/retention-policies/{id}/` | `RetentionPolicyViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/governance/retention-policies/{id}/` | `RetentionPolicyViewSet.update` | update | Standard |

### Health (2 endpoints)

**Base Route**: `/api/v1/health/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/health/circuit-breakers/` | `circuit_breaker_status` | circuit_breaker_status | Function-based |
| POST | `/api/v1/health/circuit-breakers/` | `circuit_breaker_status` | circuit_breaker_status | Function-based |

### Hub (2 endpoints)

**Base Route**: `/api/v1/hub/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/hub/admin/` | `urls` | urls | Function-based |
| POST | `/api/v1/hub/admin/` | `urls` | urls | Function-based |

### Jobs (7 endpoints)

**Base Route**: `/api/v1/jobs/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/jobs/jobs/` | `JobViewSet.list` | list | Standard |
| POST | `/api/v1/jobs/jobs/` | `JobViewSet.create` | create | Standard |
| DELETE | `/api/v1/jobs/jobs/{id}/` | `JobViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/jobs/jobs/{id}/` | `JobViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/jobs/jobs/{id}/` | `JobViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/jobs/jobs/{id}/` | `JobViewSet.update` | update | Standard |
| POST | `/api/v1/jobs/jobs/{id}/cancel/` | `JobViewSet.cancel` | cancel | Custom |

### Marketplace (27 endpoints)

**Base Route**: `/api/v1/marketplace/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/marketplace/entitlements/` | `EntitlementViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/entitlements/` | `EntitlementViewSet.create` | create | Standard |
| DELETE | `/api/v1/marketplace/entitlements/{id}/` | `EntitlementViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/entitlements/{id}/` | `EntitlementViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/marketplace/entitlements/{id}/` | `EntitlementViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/marketplace/entitlements/{id}/` | `EntitlementViewSet.update` | update | Standard |
| GET | `/api/v1/marketplace/listings/` | `ListingViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/listings/` | `ListingViewSet.create` | create | Standard |
| GET | `/api/v1/marketplace/listings/search/` | `ListingViewSet.search` | search | Custom |
| DELETE | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/marketplace/listings/{id}/` | `ListingViewSet.update` | update | Standard |
| GET | `/api/v1/marketplace/listings/{id}/download/` | `ListingViewSet.download` | download | Custom |
| GET | `/api/v1/marketplace/listings/{id}/preview/` | `ListingViewSet.preview` | preview | Custom |
| GET | `/api/v1/marketplace/orders/` | `OrderViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/orders/` | `OrderViewSet.create` | create | Standard |
| DELETE | `/api/v1/marketplace/orders/{id}/` | `OrderViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/orders/{id}/` | `OrderViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/marketplace/orders/{id}/` | `OrderViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/marketplace/orders/{id}/` | `OrderViewSet.update` | update | Standard |
| GET | `/api/v1/marketplace/payment-gateways/` | `PaymentGatewayViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/payment-gateways/` | `PaymentGatewayViewSet.create` | create | Standard |
| DELETE | `/api/v1/marketplace/payment-gateways/{id}/` | `PaymentGatewayViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/payment-gateways/{id}/` | `PaymentGatewayViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/marketplace/payment-gateways/{id}/` | `PaymentGatewayViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/marketplace/payment-gateways/{id}/` | `PaymentGatewayViewSet.update` | update | Standard |

### Mesh (22 endpoints)

**Base Route**: `/api/v1/mesh/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/mesh/domains/` | `DomainViewSet.list` | list | Standard |
| POST | `/api/v1/mesh/domains/` | `DomainViewSet.create` | create | Standard |
| DELETE | `/api/v1/mesh/domains/{id}/` | `DomainViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/mesh/domains/{id}/` | `DomainViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/mesh/domains/{id}/` | `DomainViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/mesh/domains/{id}/` | `DomainViewSet.update` | update | Standard |
| GET | `/api/v1/mesh/domains/{id}/analytics/` | `DomainViewSet.analytics` | analytics | Custom |
| POST | `/api/v1/mesh/domains/{id}/compliance/check/` | `DomainViewSet.check_compliance` | check_compliance | Custom |
| GET | `/api/v1/mesh/domains/{id}/compliance/reports/` | `DomainViewSet.list_compliance_reports` | list_compliance_reports | Custom |
| GET | `/api/v1/mesh/domains/{id}/compliance/reports/(?P<report_id>[^/.]+)/` | `DomainViewSet.get_compliance_report` | get_compliance_report | Custom |
| GET | `/api/v1/mesh/domains/{id}/policies/` | `DomainViewSet.list_policies` | list_policies | Custom |
| DELETE | `/api/v1/mesh/domains/{id}/policies/(?P<policy_id>[^/.]+)/` | `DomainViewSet.remove_policy` | remove_policy | Custom |
| POST | `/api/v1/mesh/domains/{id}/policies/apply/` | `DomainViewSet.apply_policy` | apply_policy | Custom |
| POST | `/api/v1/mesh/domains/{id}/transfer-ownership/` | `DomainViewSet.transfer_ownership` | transfer_ownership | Custom |
| GET | `/api/v1/mesh/topology/` | `TopologyViewSet.list` | list | Standard |
| POST | `/api/v1/mesh/topology/` | `TopologyViewSet.create` | create | Standard |
| GET | `/api/v1/mesh/topology/health/` | `TopologyViewSet.health` | health | Custom |
| GET | `/api/v1/mesh/topology/relationships/` | `TopologyViewSet.relationships` | relationships | Custom |
| DELETE | `/api/v1/mesh/topology/{id}/` | `TopologyViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/mesh/topology/{id}/` | `TopologyViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/mesh/topology/{id}/` | `TopologyViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/mesh/topology/{id}/` | `TopologyViewSet.update` | update | Standard |

### Observability (18 endpoints)

**Base Route**: `/api/v1/observability/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/observability/observability/` | `ObservabilityViewSet.list` | list | Standard |
| POST | `/api/v1/observability/observability/` | `ObservabilityViewSet.create` | create | Standard |
| GET | `/api/v1/observability/observability/freshness/` | `ObservabilityViewSet.get_freshness_dashboard` | get_freshness_dashboard | Custom |
| GET | `/api/v1/observability/observability/freshness/stale/` | `ObservabilityViewSet.get_stale_data` | get_stale_data | Custom |
| GET | `/api/v1/observability/observability/incidents/` | `ObservabilityViewSet.get_incidents_dashboard` | get_incidents_dashboard | Custom |
| POST | `/api/v1/observability/observability/incidents/` | `ObservabilityViewSet.create_incident` | create_incident | Custom |
| PATCH | `/api/v1/observability/observability/incidents/update/` | `ObservabilityViewSet.update_incident` | update_incident | Custom |
| POST | `/api/v1/observability/observability/metrics/` | `ObservabilityViewSet.record_metric` | record_metric | Custom |
| GET | `/api/v1/observability/observability/pipelines/` | `ObservabilityViewSet.get_pipeline_dashboard` | get_pipeline_dashboard | Custom |
| GET | `/api/v1/observability/observability/schema-drift/` | `ObservabilityViewSet.get_schema_drift_dashboard` | get_schema_drift_dashboard | Custom |
| POST | `/api/v1/observability/observability/schema-drift/detect/` | `ObservabilityViewSet.detect_schema_drift` | detect_schema_drift | Custom |
| GET | `/api/v1/observability/observability/slas/` | `ObservabilityViewSet.get_slas_dashboard` | get_slas_dashboard | Custom |
| GET | `/api/v1/observability/observability/volume/` | `ObservabilityViewSet.get_volume_dashboard` | get_volume_dashboard | Custom |
| POST | `/api/v1/observability/observability/volume/aggregate/` | `ObservabilityViewSet.aggregate_volume_trends` | aggregate_volume_trends | Custom |
| DELETE | `/api/v1/observability/observability/{id}/` | `ObservabilityViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/observability/observability/{id}/` | `ObservabilityViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/observability/observability/{id}/` | `ObservabilityViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/observability/observability/{id}/` | `ObservabilityViewSet.update` | update | Standard |

### Scheduled_ingestion (6 endpoints)

**Base Route**: `/api/v1/scheduled_ingestion/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/scheduled_ingestion/runs/` | `ScheduledIngestionRunViewSet.list` | list | Standard |
| POST | `/api/v1/scheduled_ingestion/runs/` | `ScheduledIngestionRunViewSet.create` | create | Standard |
| DELETE | `/api/v1/scheduled_ingestion/runs/{id}/` | `ScheduledIngestionRunViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/scheduled_ingestion/runs/{id}/` | `ScheduledIngestionRunViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/scheduled_ingestion/runs/{id}/` | `ScheduledIngestionRunViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/scheduled_ingestion/runs/{id}/` | `ScheduledIngestionRunViewSet.update` | update | Standard |

### Semantic (16 endpoints)

**Base Route**: `/api/v1/semantic/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/semantic/context.jsonld/` | `get_jsonld_context` | get_jsonld_context | Function-based |
| POST | `/api/v1/semantic/context.jsonld/` | `get_jsonld_context` | get_jsonld_context | Function-based |
| GET | `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>/` | `resolve_uri` | resolve_uri | Function-based |
| POST | `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>/` | `resolve_uri` | resolve_uri | Function-based |
| GET | `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/` | `resolve_field_uri` | resolve_field_uri | Function-based |
| POST | `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/` | `resolve_field_uri` | resolve_field_uri | Function-based |
| GET | `/api/v1/semantic/ontology/` | `get_ontology` | get_ontology | Function-based |
| POST | `/api/v1/semantic/ontology/` | `get_ontology` | get_ontology | Function-based |
| GET | `/api/v1/semantic/semantic-resources/` | `SemanticResourceViewSet.list` | list | Standard |
| POST | `/api/v1/semantic/semantic-resources/` | `SemanticResourceViewSet.create` | create | Standard |
| DELETE | `/api/v1/semantic/semantic-resources/{id}/` | `SemanticResourceViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/semantic/semantic-resources/{id}/` | `SemanticResourceViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/semantic/semantic-resources/{id}/` | `SemanticResourceViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/semantic/semantic-resources/{id}/` | `SemanticResourceViewSet.update` | update | Standard |
| GET | `/api/v1/semantic/sparql/` | `sparql_query` | sparql_query | Function-based |
| POST | `/api/v1/semantic/sparql/` | `sparql_query` | sparql_query | Function-based |

### Social (24 endpoints)

**Base Route**: `/api/v1/social/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/social/comments/` | `CommentViewSet.list` | list | Standard |
| POST | `/api/v1/social/comments/` | `CommentViewSet.create` | create | Standard |
| DELETE | `/api/v1/social/comments/{id}/` | `CommentViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/social/comments/{id}/` | `CommentViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/social/comments/{id}/` | `CommentViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/social/comments/{id}/` | `CommentViewSet.update` | update | Standard |
| GET | `/api/v1/social/communities/` | `CommunityViewSet.list` | list | Standard |
| POST | `/api/v1/social/communities/` | `CommunityViewSet.create` | create | Standard |
| DELETE | `/api/v1/social/communities/{id}/` | `CommunityViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/social/communities/{id}/` | `CommunityViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/social/communities/{id}/` | `CommunityViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/social/communities/{id}/` | `CommunityViewSet.update` | update | Standard |
| GET | `/api/v1/social/ratings/` | `RatingViewSet.list` | list | Standard |
| POST | `/api/v1/social/ratings/` | `RatingViewSet.create` | create | Standard |
| DELETE | `/api/v1/social/ratings/{id}/` | `RatingViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/social/ratings/{id}/` | `RatingViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/social/ratings/{id}/` | `RatingViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/social/ratings/{id}/` | `RatingViewSet.update` | update | Standard |
| GET | `/api/v1/social/reviews/` | `ReviewViewSet.list` | list | Standard |
| POST | `/api/v1/social/reviews/` | `ReviewViewSet.create` | create | Standard |
| DELETE | `/api/v1/social/reviews/{id}/` | `ReviewViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/social/reviews/{id}/` | `ReviewViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/social/reviews/{id}/` | `ReviewViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/social/reviews/{id}/` | `ReviewViewSet.update` | update | Standard |

### Tenants (8 endpoints)

**Base Route**: `/api/v1/tenants/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/tenants/tenants/` | `TenantViewSet.list` | list | Standard |
| POST | `/api/v1/tenants/tenants/` | `TenantViewSet.create` | create | Standard |
| DELETE | `/api/v1/tenants/tenants/{id}/` | `TenantViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/tenants/tenants/{id}/` | `TenantViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/tenants/tenants/{id}/` | `TenantViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/tenants/tenants/{id}/` | `TenantViewSet.update` | update | Standard |
| POST | `/api/v1/tenants/tenants/{id}/reactivate/` | `TenantViewSet.reactivate` | reactivate | Custom |
| POST | `/api/v1/tenants/tenants/{id}/suspend/` | `TenantViewSet.suspend` | suspend | Custom |

### Transformation (33 endpoints)

**Base Route**: `/api/v1/transformation/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/transformation/executions/` | `PipelineExecutionViewSet.list` | list | Standard |
| POST | `/api/v1/transformation/executions/` | `PipelineExecutionViewSet.create` | create | Standard |
| DELETE | `/api/v1/transformation/executions/{id}/` | `PipelineExecutionViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/transformation/executions/{id}/` | `PipelineExecutionViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/transformation/executions/{id}/` | `PipelineExecutionViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/transformation/executions/{id}/` | `PipelineExecutionViewSet.update` | update | Standard |
| POST | `/api/v1/transformation/executions/{id}/cancel/` | `PipelineExecutionViewSet.cancel_execution` | cancel_execution | Custom |
| GET | `/api/v1/transformation/executions/{id}/progress/` | `PipelineExecutionViewSet.get_progress` | get_progress | Custom |
| GET | `/api/v1/transformation/executions/{id}/result/` | `PipelineExecutionViewSet.get_result` | get_result | Custom |
| GET | `/api/v1/transformation/pipelines/` | `TransformationPipelineViewSet.list` | list | Standard |
| POST | `/api/v1/transformation/pipelines/` | `TransformationPipelineViewSet.create` | create | Standard |
| DELETE | `/api/v1/transformation/pipelines/{id}/` | `TransformationPipelineViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/transformation/pipelines/{id}/` | `TransformationPipelineViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/transformation/pipelines/{id}/` | `TransformationPipelineViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/transformation/pipelines/{id}/` | `TransformationPipelineViewSet.update` | update | Standard |
| POST | `/api/v1/transformation/pipelines/{id}/execute/` | `TransformationPipelineViewSet.execute_pipeline` | execute_pipeline | Custom |
| GET | `/api/v1/transformation/pipelines/{id}/executions/` | `TransformationPipelineViewSet.list_executions` | list_executions | Custom |
| POST | `/api/v1/transformation/pipelines/{id}/preview/` | `TransformationPipelineViewSet.preview_pipeline` | preview_pipeline | Custom |
| POST | `/api/v1/transformation/pipelines/{id}/validate/` | `TransformationPipelineViewSet.validate_pipeline` | validate_pipeline | Custom |
| GET | `/api/v1/transformation/previews/` | `PreviewResultViewSet.list` | list | Standard |
| POST | `/api/v1/transformation/previews/` | `PreviewResultViewSet.create` | create | Standard |
| DELETE | `/api/v1/transformation/previews/{id}/` | `PreviewResultViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/transformation/previews/{id}/` | `PreviewResultViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/transformation/previews/{id}/` | `PreviewResultViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/transformation/previews/{id}/` | `PreviewResultViewSet.update` | update | Standard |
| GET | `/api/v1/transformation/wrangling/` | `WranglingSessionViewSet.list` | list | Standard |
| POST | `/api/v1/transformation/wrangling/` | `WranglingSessionViewSet.create` | create | Standard |
| DELETE | `/api/v1/transformation/wrangling/{id}/` | `WranglingSessionViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/transformation/wrangling/{id}/` | `WranglingSessionViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/transformation/wrangling/{id}/` | `WranglingSessionViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/transformation/wrangling/{id}/` | `WranglingSessionViewSet.update` | update | Standard |
| POST | `/api/v1/transformation/wrangling/{id}/redo/` | `WranglingSessionViewSet.redo_operation` | redo_operation | Custom |
| POST | `/api/v1/transformation/wrangling/{id}/undo/` | `WranglingSessionViewSet.undo_operation` | undo_operation | Custom |

### Users (14 endpoints)

**Base Route**: `/api/v1/users/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/users/roles/` | `RoleViewSet.list` | list | Standard |
| POST | `/api/v1/users/roles/` | `RoleViewSet.create` | create | Standard |
| DELETE | `/api/v1/users/roles/{id}/` | `RoleViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/users/roles/{id}/` | `RoleViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/users/roles/{id}/` | `RoleViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/users/roles/{id}/` | `RoleViewSet.update` | update | Standard |
| GET | `/api/v1/users/users/` | `UserViewSet.list` | list | Standard |
| POST | `/api/v1/users/users/` | `UserViewSet.create` | create | Standard |
| POST | `/api/v1/users/users/invite/` | `UserViewSet.invite` | invite | Custom |
| DELETE | `/api/v1/users/users/{id}/` | `UserViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/users/users/{id}/` | `UserViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/users/users/{id}/` | `UserViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/users/users/{id}/` | `UserViewSet.update` | update | Standard |
| POST | `/api/v1/users/users/{id}/roles/` | `UserViewSet.manage_roles` | manage_roles | Custom |

### Virtualization (25 endpoints)

**Base Route**: `/api/v1/virtualization/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/virtualization/datasets/` | `VirtualDatasetViewSet.list` | list | Standard |
| POST | `/api/v1/virtualization/datasets/` | `VirtualDatasetViewSet.create` | create | Standard |
| DELETE | `/api/v1/virtualization/datasets/{id}/` | `VirtualDatasetViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/virtualization/datasets/{id}/` | `VirtualDatasetViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/virtualization/datasets/{id}/` | `VirtualDatasetViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/virtualization/datasets/{id}/` | `VirtualDatasetViewSet.update` | update | Standard |
| POST | `/api/v1/virtualization/datasets/{id}/queries/` | `VirtualDatasetViewSet.execute_query` | execute_query | Custom |
| POST | `/api/v1/virtualization/datasets/{id}/validate/` | `VirtualDatasetViewSet.validate_dataset` | validate_dataset | Custom |
| GET | `/api/v1/virtualization/datasets/{id}/versions/` | `VirtualDatasetViewSet.versions` | versions | Custom |
| GET | `/api/v1/virtualization/queries/` | `QueryExecutionViewSet.list` | list | Standard |
| POST | `/api/v1/virtualization/queries/` | `QueryExecutionViewSet.create` | create | Standard |
| DELETE | `/api/v1/virtualization/queries/{id}/` | `QueryExecutionViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/virtualization/queries/{id}/` | `QueryExecutionViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/virtualization/queries/{id}/` | `QueryExecutionViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/virtualization/queries/{id}/` | `QueryExecutionViewSet.update` | update | Standard |
| POST | `/api/v1/virtualization/queries/{id}/cancel/` | `QueryExecutionViewSet.cancel_execution` | cancel_execution | Custom |
| GET | `/api/v1/virtualization/queries/{id}/progress/` | `QueryExecutionViewSet.get_progress` | get_progress | Custom |
| GET | `/api/v1/virtualization/queries/{id}/result/` | `QueryExecutionViewSet.get_result` | get_result | Custom |
| GET | `/api/v1/virtualization/queries/{id}/stream/` | `QueryExecutionViewSet.stream_result` | stream_result | Custom |
| GET | `/api/v1/virtualization/topology/` | `VirtualizationTopologyViewSet.list` | list | Standard |
| POST | `/api/v1/virtualization/topology/` | `VirtualizationTopologyViewSet.create` | create | Standard |
| DELETE | `/api/v1/virtualization/topology/{id}/` | `VirtualizationTopologyViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/virtualization/topology/{id}/` | `VirtualizationTopologyViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/virtualization/topology/{id}/` | `VirtualizationTopologyViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/virtualization/topology/{id}/` | `VirtualizationTopologyViewSet.update` | update | Standard |

### Webhooks (16 endpoints)

**Base Route**: `/api/v1/webhooks/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/webhooks/webhook-deliveries/` | `WebhookDeliveryViewSet.list` | list | Standard |
| POST | `/api/v1/webhooks/webhook-deliveries/` | `WebhookDeliveryViewSet.create` | create | Standard |
| DELETE | `/api/v1/webhooks/webhook-deliveries/{id}/` | `WebhookDeliveryViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/` | `WebhookDeliveryViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/webhooks/webhook-deliveries/{id}/` | `WebhookDeliveryViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/webhooks/webhook-deliveries/{id}/` | `WebhookDeliveryViewSet.update` | update | Standard |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | `WebhookDeliveryViewSet.retry_delivery` | retry_delivery | Custom |
| GET | `/api/v1/webhooks/webhooks/` | `WebhookViewSet.list` | list | Standard |
| POST | `/api/v1/webhooks/webhooks/` | `WebhookViewSet.create` | create | Standard |
| GET | `/api/v1/webhooks/webhooks/event-types/` | `WebhookViewSet.event_types` | event_types | Custom |
| DELETE | `/api/v1/webhooks/webhooks/{id}/` | `WebhookViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/webhooks/webhooks/{id}/` | `WebhookViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/webhooks/webhooks/{id}/` | `WebhookViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/webhooks/webhooks/{id}/` | `WebhookViewSet.update` | update | Standard |
| GET | `/api/v1/webhooks/webhooks/{id}/deliveries/` | `WebhookViewSet.deliveries` | deliveries | Custom |
| POST | `/api/v1/webhooks/webhooks/{id}/test/` | `WebhookViewSet.test_webhook` | test_webhook | Custom |

## Summary Statistics

- **Total Endpoints**: 370
- **Standard CRUD Actions**: 252
- **Custom Actions**: 82
- **Function-based Views**: 36

### Methods Breakdown

- **DELETE**: 43 endpoints
- **GET**: 146 endpoints
- **PATCH**: 43 endpoints
- **POST**: 96 endpoints
- **PUT**: 42 endpoints

## Notes

### Standardized Endpoint Patterns

All endpoints follow standardized patterns:
- Compliance runs: `/api/v1/compliance/runs/` (not `/compliance-runs/`)
- Data quality runs: `/api/v1/dq/runs/` (not `/dq-runs/`)

### Extraction Methodology

1. **Static Code Analysis**: Parses Python AST to extract URL patterns and ViewSet actions
2. **Router Registration Mapping**: Maps ViewSets to URL prefixes via router.register() calls
3. **ViewSet Action Detection**: Identifies custom @action decorators in ViewSet classes
4. **Pattern Verification**: Verifies endpoints match standardized URL patterns

---

**Document Status**: ✅ Complete
**Total Endpoints Extracted**: 370
