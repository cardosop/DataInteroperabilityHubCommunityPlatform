# Frontend-to-Backend Feature Completeness Map

**Date:** 2026-05-21
**Method:** Frontend feature directory → Django URL router cross-reference
**Total frontend features:** 47

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Backend endpoints confirmed in Django URL router or microservice routes |
| ⚠ | Partial coverage — some endpoints exist, some missing |
| ❌ | Orphan — no matching backend endpoints found |
| — | Platform/infra feature (no direct API needed) |

## Feature Map

| # | Frontend Feature | Backend App/Service | Status | Notes |
|---|---|---|---|---|
| 1 | admin | `hub/apps/tenants/`, admin viewsets | ✅ | Admin API for tenant/plan/flag management |
| 2 | ai | `hub/apps/ai/` | ✅ | Sunset: 2026-09-01. Read-only, deprecated |
| 3 | assets | `hub/apps/assets/views.py` → `AssetViewSet` | ✅ | CRUD + versioning + activation |
| 4 | audit | `hub/apps/audit/views.py` | ✅ | Audit event list/search/export |
| 5 | auth | `hub/apps/auth/views.py` | ✅ | Login, MFA, SSO (sso_views.py), sessions |
| 6 | baas | `hub/apps/baas/views.py` | ✅ | BaaS customer billing reports |
| 7 | billing | `hub/apps/billing/views.py` | ✅ | Plans, subscriptions, invoices, Stripe |
| 8 | breach | `hub/apps/breach/views.py` | ✅ | Breach notification CRUD + SLA clock |
| 9 | capabilities | `hub/apps/core/capabilities/` | ✅ | Feature capability detection |
| 10 | compliance | `hub/apps/compliance/views.py` | ✅ | Compliance runs, results, frameworks |
| 11 | contracts | `hub/apps/contracts/views.py` | ✅ | Contract CRUD, validation, versioning |
| 12 | cost | `hub/apps/billing/views.py` → `CostOverviewView` | ✅ | Cost overview dashboard |
| 13 | datasets | `hub/apps/datasets/views.py` → `DatasetViewSet` | ✅ | Dataset CRUD + refresh + versioning |
| 14 | developer | `hub/apps/developer/views.py` | ✅ | Plugins, SDK docs, API keys, usage |
| 15 | dpia | `hub/apps/dpia/views.py` | ✅ | DPIA CRUD + review workflow |
| 16 | dq | `hub/apps/dq/views.py` → `DqRunViewSet`, `DqQualityViewSet` | ✅ | DQ runs, anomalies, trends, scorecards |
| 17 | dsar | `hub/apps/dsar/views.py` | ✅ | DSAR handler queue + public submission |
| 18 | federated-import | `hub/apps/integrations/federated_import_views.py` | ✅ | Federated marketplace import |
| 19 | files | `hub/apps/files/views.py` | ✅ | File upload, scan status, presigned URLs |
| 20 | gdpr | `hub/apps/gdpr/views.py` | ✅ | GDPR rights management |
| 21 | governance | `hub/apps/governance/views.py` | ✅ | Access requests, approvals, policies |
| 22 | home | `frontend/src/features/home/` | — | Static landing/dashboard page |
| 23 | integrations | `hub/apps/integrations/views.py` | ✅ | Connector configuration |
| 24 | jobs | `hub/apps/jobs/views.py` | ✅ | Job queue monitoring, retry |
| 25 | lineage | `hub/apps/lineage/views.py` | ✅ | Data lineage graph + edge management |
| 26 | marketplace | `hub/apps/marketplace/views.py` → `ListingViewSet` | ✅ | Listings, orders, saved searches |
| 27 | mesh | `hub/apps/mesh/views.py` → `DomainViewSet` | ✅ | Data mesh domains, topology, governance |
| 28 | ml | `hub/apps/ml/views.py` → `MLModelViewSet` | ✅ | ML models, training, inference, AB tests |
| 29 | notifications | `hub/apps/notifications/views.py` | ✅ | User notification list + read state |
| 30 | observability | `hub/apps/observability/` | — | Health probes, metrics, dashboards |
| 31 | onboarding | `frontend/src/features/onboarding/` | — | Product tour / onboarding wizard (UI-only) |
| 32 | pricing | `frontend/src/features/pricing/` | ⚠ | Reads plans via billing API; no dedicated pricing endpoint |
| 33 | processorAgreements | `hub/apps/processor_agreements/views.py` | ✅ | Processor agreement CRUD |
| 34 | public | `hub/apps/public/views.py` | ✅ | Public DSAR, legal pages, pricing |
| 35 | ropa | `hub/apps/ropa/views.py` | ✅ | RoPA generation + export |
| 36 | scheduledExport | `hub/apps/scheduled_export/views.py` | ✅ | Scheduled export CRUD + runs |
| 37 | scheduledIngestion | `hub/apps/scheduled_ingestion/views.py` | ✅ | Scheduled ingestion CRUD + runs |
| 38 | search | `hub/apps/search/views.py` → `UnifiedSearchView` | ✅ | Full-text + SPARQL search |
| 39 | semantic | `hub/apps/semantic/views.py` | ✅ | SPARQL endpoint, GraphQL-LD, ontology |
| 40 | settings | `hub/apps/tenants/views.py` → tenant config | ✅ | Tenant settings/config |
| 41 | shell | `frontend/src/features/shell/` | — | App shell / layout (UI-only) |
| 42 | social | `hub/apps/social/views.py` | ✅ | Ratings, reviews, comments, communities |
| 43 | tenants | `hub/apps/tenants/views.py` | ✅ | Tenant CRUD (admin) |
| 44 | transformation | `hub/apps/transformation/views.py` | ✅ | Transformation pipelines, dbt executor |
| 45 | users | `hub/apps/users/views.py` | ✅ | User management |
| 46 | virtualization | `hub/apps/virtualization/views.py` | ✅ | Virtual dataset query |
| 47 | webhooks | `hub/apps/webhooks/views.py` | ✅ | Webhook subscription + delivery |

## Summary

| Status | Count | % |
|---|---|---|
| ✅ Connected | 42 | 89.4% |
| ⚠ Partial | 1 | 2.1% |
| — Platform/UI-only | 4 | 8.5% |
| ❌ Orphan | 0 | 0% |

### Platform/UI-only features

These 4 features have no dedicated backend endpoint — they are pure frontend
or use shared infrastructure:

- **home:** Landing page rendering static content
- **onboarding:** Product tour component, reads feature flags via capabilities API
- **observability:** Health probes are backend endpoints consumed by infra; frontend shows dashboard links
- **shell:** App layout shell (navigation, sidebar, header) — no backend logic

### Partial coverage

- **pricing:** Reads plan data from the billing API (`GET /api/v1/billing/plans/`) but has no dedicated `/api/v1/pricing/` endpoint. The billing API provides all necessary data. Consider adding a dedicated public pricing endpoint if the pricing page needs different caching or public access patterns.

## Orphans & Fixes

No orphan frontend features found. All 42 API-backed features have corresponding
Django URL routes or microservice endpoints.

### Verification Command

```bash
# Verify each frontend feature has a backend app match
for dir in frontend/src/features/*/; do
  name=$(basename "$dir")
  case $name in
    home|onboarding|observability|shell|pricing) continue ;;  # UI-only or shared
    *) 
      found=$(grep -rl "$name" hub/apps/ --include="urls.py" --include="views.py" | head -1)
      [ -n "$found" ] && echo "✓ $name → $found" || echo "✗ $name ORPHAN"
      ;;
  esac
done
```

## Maintenance

- **Owner:** Platform Engineering
- **Last reviewed:** 2026-05-21
- **Next review:** When adding or removing frontend feature directories
