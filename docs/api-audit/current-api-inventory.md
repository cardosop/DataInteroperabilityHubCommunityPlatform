# Current API Inventory from Codebase

**Document Version**: 2.0.0
**Last Updated**: 2026-02-08
**Source**: Static analysis of Django URL patterns and ViewSets
**Task**: 9.6.3.3.2 - Update API inventory files

---

## Overview

This document inventories all API endpoints extracted from the Django codebase by:
1. Parsing all `hub/apps/*/urls.py` files to extract URL patterns
2. Analyzing ViewSet classes to identify custom @action decorators
3. Extracting function-based views
4. Verifying endpoint patterns match standardized conventions

**Total Endpoints Found**: 431

---

## Endpoints by Application

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

### Baas (21 endpoints)

**Base Route**: `/api/v1/baas/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/baas/api-keys/` | `APIKeyViewSet.list` | list | Standard |
| POST | `/api/v1/baas/api-keys/` | `APIKeyViewSet.create` | create | Standard |
| DELETE | `/api/v1/baas/api-keys/{id}/` | `APIKeyViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/baas/api-keys/{id}/` | `APIKeyViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/baas/api-keys/{id}/` | `APIKeyViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/baas/api-keys/{id}/` | `APIKeyViewSet.update` | update | Standard |
| GET | `/api/v1/baas/docs/` | `DeveloperDocumentationViewSet.list` | list | Standard |
| POST | `/api/v1/baas/docs/` | `DeveloperDocumentationViewSet.create` | create | Standard |
| DELETE | `/api/v1/baas/docs/{id}/` | `DeveloperDocumentationViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/baas/docs/{id}/` | `DeveloperDocumentationViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/baas/docs/{id}/` | `DeveloperDocumentationViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/baas/docs/{id}/` | `DeveloperDocumentationViewSet.update` | update | Standard |
| GET | `/api/v1/baas/usage/` | `APIUsageViewSet.list` | list | Standard |
| POST | `/api/v1/baas/usage/` | `APIUsageViewSet.create` | create | Standard |
| GET | `/api/v1/baas/usage/by-endpoint/` | `APIUsageViewSet.by_endpoint` | by_endpoint | Custom |
| GET | `/api/v1/baas/usage/by-tenant/` | `APIUsageViewSet.by_tenant` | by_tenant | Custom |
| GET | `/api/v1/baas/usage/stats/` | `APIUsageViewSet.stats` | stats | Custom |
| DELETE | `/api/v1/baas/usage/{id}/` | `APIUsageViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/baas/usage/{id}/` | `APIUsageViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/baas/usage/{id}/` | `APIUsageViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/baas/usage/{id}/` | `APIUsageViewSet.update` | update | Standard |

### Billing (15 endpoints)

**Base Route**: `/api/v1/billing/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/billing/invoices/` | `InvoiceViewSet.list` | list | Standard |
| POST | `/api/v1/billing/invoices/` | `InvoiceViewSet.create` | create | Standard |
| DELETE | `/api/v1/billing/invoices/{id}/` | `InvoiceViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/billing/invoices/{id}/` | `InvoiceViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/billing/invoices/{id}/` | `InvoiceViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/billing/invoices/{id}/` | `InvoiceViewSet.update` | update | Standard |
| GET | `/api/v1/billing/subscription/` | `SubscriptionViewSet.list` | list | Standard |
| POST | `/api/v1/billing/subscription/` | `SubscriptionViewSet.create` | create | Standard |
| GET | `/api/v1/billing/subscription/current/` | `SubscriptionViewSet.current` | current | Custom |
| DELETE | `/api/v1/billing/subscription/{id}/` | `SubscriptionViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/billing/subscription/{id}/` | `SubscriptionViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/billing/subscription/{id}/` | `SubscriptionViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/billing/subscription/{id}/` | `SubscriptionViewSet.update` | update | Standard |
| GET | `/api/v1/billing/webhooks/stripe/` | `stripe_webhook` | stripe_webhook | Function-based |
| POST | `/api/v1/billing/webhooks/stripe/` | `stripe_webhook` | stripe_webhook | Function-based |

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

### Gdpr (14 endpoints)

**Base Route**: `/api/v1/gdpr/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/gdpr/erasure-requests/` | `ErasureRequestViewSet.list` | list | Standard |
| POST | `/api/v1/gdpr/erasure-requests/` | `ErasureRequestViewSet.create` | create | Standard |
| POST | `/api/v1/gdpr/erasure-requests/request-erasure/` | `ErasureRequestViewSet.request_erasure` | request_erasure | Custom |
| DELETE | `/api/v1/gdpr/erasure-requests/{id}/` | `ErasureRequestViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/gdpr/erasure-requests/{id}/` | `ErasureRequestViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/gdpr/erasure-requests/{id}/` | `ErasureRequestViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/gdpr/erasure-requests/{id}/` | `ErasureRequestViewSet.update` | update | Standard |
| GET | `/api/v1/gdpr/export-jobs/` | `DataExportJobViewSet.list` | list | Standard |
| POST | `/api/v1/gdpr/export-jobs/` | `DataExportJobViewSet.create` | create | Standard |
| POST | `/api/v1/gdpr/export-jobs/export-data/` | `DataExportJobViewSet.export_data` | export_data | Custom |
| DELETE | `/api/v1/gdpr/export-jobs/{id}/` | `DataExportJobViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/gdpr/export-jobs/{id}/` | `DataExportJobViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/gdpr/export-jobs/{id}/` | `DataExportJobViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/gdpr/export-jobs/{id}/` | `DataExportJobViewSet.update` | update | Standard |

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

### Health (4 endpoints)

**Base Route**: `/api/v1/health/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/health/circuit-breakers/` | `circuit_breaker_status` | circuit_breaker_status | Function-based |
| POST | `/api/v1/health/circuit-breakers/` | `circuit_breaker_status` | circuit_breaker_status | Function-based |
| GET | `/api/v1/health/live/` | `liveness` | liveness | Function-based |
| POST | `/api/v1/health/live/` | `liveness` | liveness | Function-based |

### Hub (2 endpoints)

**Base Route**: `/api/v1/hub/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/hub/admin/` | `urls` | urls | Function-based |
| POST | `/api/v1/hub/admin/` | `urls` | urls | Function-based |

### Integrations (24 endpoints)

**Base Route**: `/api/v1/integrations/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/integrations/marketplace/connections/` | `MarketplaceConnectionViewSet.list` | list | Standard |
| POST | `/api/v1/integrations/marketplace/connections/` | `MarketplaceConnectionViewSet.create` | create | Standard |
| DELETE | `/api/v1/integrations/marketplace/connections/{id}/` | `MarketplaceConnectionViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/integrations/marketplace/connections/{id}/` | `MarketplaceConnectionViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/integrations/marketplace/connections/{id}/` | `MarketplaceConnectionViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/integrations/marketplace/connections/{id}/` | `MarketplaceConnectionViewSet.update` | update | Standard |
| POST | `/api/v1/integrations/marketplace/connections/{id}/test/` | `MarketplaceConnectionViewSet.test` | test | Custom |
| GET | `/api/v1/integrations/marketplace/connectors/` | `list_connectors` | list_connectors | Function-based |
| POST | `/api/v1/integrations/marketplace/connectors/` | `list_connectors` | list_connectors | Function-based |
| GET | `/api/v1/integrations/marketplace/connectors/<str:connector_type>/` | `get_connector_info` | get_connector_info | Function-based |
| POST | `/api/v1/integrations/marketplace/connectors/<str:connector_type>/` | `get_connector_info` | get_connector_info | Function-based |
| GET | `/api/v1/integrations/marketplace/mappings/` | `MarketplaceMappingViewSet.list` | list | Standard |
| POST | `/api/v1/integrations/marketplace/mappings/` | `MarketplaceMappingViewSet.create` | create | Standard |
| DELETE | `/api/v1/integrations/marketplace/mappings/{id}/` | `MarketplaceMappingViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/integrations/marketplace/mappings/{id}/` | `MarketplaceMappingViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/integrations/marketplace/mappings/{id}/` | `MarketplaceMappingViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/integrations/marketplace/mappings/{id}/` | `MarketplaceMappingViewSet.update` | update | Standard |
| GET | `/api/v1/integrations/marketplace/sync/` | `MarketplaceSyncJobViewSet.list` | list | Standard |
| POST | `/api/v1/integrations/marketplace/sync/` | `MarketplaceSyncJobViewSet.create` | create | Standard |
| DELETE | `/api/v1/integrations/marketplace/sync/{id}/` | `MarketplaceSyncJobViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/integrations/marketplace/sync/{id}/` | `MarketplaceSyncJobViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/integrations/marketplace/sync/{id}/` | `MarketplaceSyncJobViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/integrations/marketplace/sync/{id}/` | `MarketplaceSyncJobViewSet.update` | update | Standard |
| POST | `/api/v1/integrations/marketplace/sync/{id}/cancel/` | `MarketplaceSyncJobViewSet.cancel` | cancel | Custom |

### Marketplace (33 endpoints)

**Base Route**: `/api/v1/marketplace/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/marketplace/config/trust-signals/` | `TrustSignalConfigViewSet.list` | list | Standard |
| POST | `/api/v1/marketplace/config/trust-signals/` | `TrustSignalConfigViewSet.create` | create | Standard |
| DELETE | `/api/v1/marketplace/config/trust-signals/{id}/` | `TrustSignalConfigViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/marketplace/config/trust-signals/{id}/` | `TrustSignalConfigViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/marketplace/config/trust-signals/{id}/` | `TrustSignalConfigViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/marketplace/config/trust-signals/{id}/` | `TrustSignalConfigViewSet.update` | update | Standard |
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

### Ml (25 endpoints)

**Base Route**: `/api/v1/ml/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/ml/deployments/` | `InferenceViewSet.list` | list | Standard |
| POST | `/api/v1/ml/deployments/` | `InferenceViewSet.create` | create | Standard |
| POST | `/api/v1/ml/deployments/predict/` | `InferenceViewSet.predict` | predict | Custom |
| DELETE | `/api/v1/ml/deployments/{id}/` | `InferenceViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/ml/deployments/{id}/` | `InferenceViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/ml/deployments/{id}/` | `InferenceViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/ml/deployments/{id}/` | `InferenceViewSet.update` | update | Standard |
| GET | `/api/v1/ml/deployments/{id}/metrics/` | `InferenceViewSet.metrics` | metrics | Custom |
| GET | `/api/v1/ml/jobs/` | `TrainingJobViewSet.list` | list | Standard |
| POST | `/api/v1/ml/jobs/` | `TrainingJobViewSet.create` | create | Standard |
| DELETE | `/api/v1/ml/jobs/{id}/` | `TrainingJobViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/ml/jobs/{id}/` | `TrainingJobViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/ml/jobs/{id}/` | `TrainingJobViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/ml/jobs/{id}/` | `TrainingJobViewSet.update` | update | Standard |
| POST | `/api/v1/ml/jobs/{id}/cancel/` | `TrainingJobViewSet.cancel` | cancel | Custom |
| GET | `/api/v1/ml/jobs/{id}/logs/` | `TrainingJobViewSet.logs` | logs | Custom |
| GET | `/api/v1/ml/models/` | `MLModelViewSet.list` | list | Standard |
| POST | `/api/v1/ml/models/` | `MLModelViewSet.create` | create | Standard |
| DELETE | `/api/v1/ml/models/{id}/` | `MLModelViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/ml/models/{id}/` | `MLModelViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/ml/models/{id}/` | `MLModelViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/ml/models/{id}/` | `MLModelViewSet.update` | update | Standard |
| GET | `/api/v1/ml/models/{id}/datasets/` | `MLModelViewSet.get_datasets` | get_datasets | Custom |
| POST | `/api/v1/ml/models/{id}/link-dataset/` | `MLModelViewSet.link_dataset` | link_dataset | Custom |
| POST | `/api/v1/ml/models/{id}/sync-from-odh/` | `MLModelViewSet.sync_from_odh` | sync_from_odh | Custom |

### Observability (19 endpoints)

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
| GET | `/api/v1/observability/observability/lineage/` | `ObservabilityViewSet.get_lineage` | get_lineage | Custom |
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

### Platform (17 endpoints)

**Base Route**: `/api/v1/platform/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/platform/tenants/` | `PlatformTenantViewSet.list` | list | Standard |
| POST | `/api/v1/platform/tenants/` | `PlatformTenantViewSet.create` | create | Standard |
| GET | `/api/v1/platform/tenants/usage/` | `PlatformTenantViewSet.usage` | usage | Custom |
| DELETE | `/api/v1/platform/tenants/{id}/` | `PlatformTenantViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/platform/tenants/{id}/` | `PlatformTenantViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/platform/tenants/{id}/` | `PlatformTenantViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/platform/tenants/{id}/` | `PlatformTenantViewSet.update` | update | Standard |
| POST | `/api/v1/platform/tenants/{id}/resume/` | `PlatformTenantViewSet.resume` | resume | Custom |
| POST | `/api/v1/platform/tenants/{id}/suspend/` | `PlatformTenantViewSet.suspend` | suspend | Custom |
| GET | `/api/v1/platform/users/` | `PlatformUserViewSet.list` | list | Standard |
| POST | `/api/v1/platform/users/` | `PlatformUserViewSet.create` | create | Standard |
| DELETE | `/api/v1/platform/users/{id}/` | `PlatformUserViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/platform/users/{id}/` | `PlatformUserViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/platform/users/{id}/` | `PlatformUserViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/platform/users/{id}/` | `PlatformUserViewSet.update` | update | Standard |
| GET | `/api/v1/platform/users/{id}/erasure-requests/` | `PlatformUserViewSet.erasure_requests` | erasure_requests | Custom |
| POST | `/api/v1/platform/users/{id}/request-erasure/` | `PlatformUserViewSet.request_erasure` | request_erasure | Custom |

### Scheduled_export (6 endpoints)

**Base Route**: `/api/v1/scheduled_export/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/scheduled_export/runs/` | `ScheduledExportRunViewSet.list` | list | Standard |
| POST | `/api/v1/scheduled_export/runs/` | `ScheduledExportRunViewSet.create` | create | Standard |
| DELETE | `/api/v1/scheduled_export/runs/{id}/` | `ScheduledExportRunViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/scheduled_export/runs/{id}/` | `ScheduledExportRunViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/scheduled_export/runs/{id}/` | `ScheduledExportRunViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/scheduled_export/runs/{id}/` | `ScheduledExportRunViewSet.update` | update | Standard |

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
| GET | `/api/v1/tenants/config/` | `TenantConfigViewSet.list` | list | Standard |
| POST | `/api/v1/tenants/config/` | `TenantConfigViewSet.create` | create | Standard |
| GET | `/api/v1/tenants/config/me/usage/` | `TenantConfigViewSet.usage` | usage | Custom |
| POST | `/api/v1/tenants/config/onboarding/` | `TenantConfigViewSet.onboarding` | onboarding | Custom |
| DELETE | `/api/v1/tenants/config/{id}/` | `TenantConfigViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/tenants/config/{id}/` | `TenantConfigViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/tenants/config/{id}/` | `TenantConfigViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/tenants/config/{id}/` | `TenantConfigViewSet.update` | update | Standard |

### Users (18 endpoints)

**Base Route**: `/api/v1/users/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/users/me/erasure-requests/` | `ErasureRequestViewSet.list` | list | Standard |
| POST | `/api/v1/users/me/erasure-requests/` | `ErasureRequestViewSet.create` | create | Standard |
| DELETE | `/api/v1/users/me/erasure-requests/{id}/` | `ErasureRequestViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/users/me/erasure-requests/{id}/` | `ErasureRequestViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/users/me/erasure-requests/{id}/` | `ErasureRequestViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/users/me/erasure-requests/{id}/` | `ErasureRequestViewSet.update` | update | Standard |
| GET | `/api/v1/users/me/export-jobs/` | `DataExportJobViewSet.list` | list | Standard |
| POST | `/api/v1/users/me/export-jobs/` | `DataExportJobViewSet.create` | create | Standard |
| DELETE | `/api/v1/users/me/export-jobs/{id}/` | `DataExportJobViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/users/me/export-jobs/{id}/` | `DataExportJobViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/users/me/export-jobs/{id}/` | `DataExportJobViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/users/me/export-jobs/{id}/` | `DataExportJobViewSet.update` | update | Standard |
| GET | `/api/v1/users/roles/` | `RoleViewSet.list` | list | Standard |
| POST | `/api/v1/users/roles/` | `RoleViewSet.create` | create | Standard |
| DELETE | `/api/v1/users/roles/{id}/` | `RoleViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/users/roles/{id}/` | `RoleViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/users/roles/{id}/` | `RoleViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/users/roles/{id}/` | `RoleViewSet.update` | update | Standard |

### Versioning (7 endpoints)

**Base Route**: `/api/v1/versioning/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/versioning/versions/` | `VersioningViewSet.list` | list | Standard |
| POST | `/api/v1/versioning/versions/` | `VersioningViewSet.create` | create | Standard |
| GET | `/api/v1/versioning/versions/compare/` | `VersioningViewSet.compare` | compare | Custom |
| DELETE | `/api/v1/versioning/versions/{id}/` | `VersioningViewSet.destroy` | destroy | Standard |
| GET | `/api/v1/versioning/versions/{id}/` | `VersioningViewSet.retrieve` | retrieve | Standard |
| PATCH | `/api/v1/versioning/versions/{id}/` | `VersioningViewSet.partial_update` | partial_update | Standard |
| PUT | `/api/v1/versioning/versions/{id}/` | `VersioningViewSet.update` | update | Standard |

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

- **Total Endpoints**: 431
- **Standard CRUD Actions**: 312
- **Custom Actions**: 75
- **Function-based Views**: 44

### Methods Breakdown

- **DELETE**: 53 endpoints
- **GET**: 173 endpoints
- **PATCH**: 53 endpoints
- **POST**: 100 endpoints
- **PUT**: 52 endpoints

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
**Total Endpoints Extracted**: 431
