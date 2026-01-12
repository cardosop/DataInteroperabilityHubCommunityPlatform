# API Endpoint Test Report

**Generated**: 2025-12-28T23:20:09.795899+00:00
**Base URL**: http://localhost:8000
**Tested By**: Anonymous

---

## Summary

- **Total Endpoints**: 238
- **Tested**: 238
- **Working**: 0 ✅
- **Broken**: 10 ❌
- **Deprecated**: 0 ⚠️
- **Skipped**: 228 ⏭️

## Broken Endpoints

| Endpoint | Method | Status Code | Error |
|----------|--------|-------------|-------|
| `/api/v1/auth/login/` | GET | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/login/` | POST | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/password-reset/` | GET | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/password-reset/` | POST | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/password-reset/confirm/` | GET | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/password-reset/confirm/` | POST | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/register/` | GET | 404 | Not found - endpoint may not exist |
| `/api/v1/auth/register/` | POST | 404 | Not found - endpoint may not exist |
| `/api/v1/health/circuit-breakers/` | GET | 404 | Not found - endpoint may not exist |
| `/api/v1/health/circuit-breakers/` | POST | 404 | Not found - endpoint may not exist |

## Skipped Endpoints

| Endpoint | Method | Reason |
|----------|--------|--------|
| `/api/v1/ai/ai/` | POST | Requires authentication but no token available |
| `/api/v1/ai/ai/natural-language-search/` | POST | Requires authentication but no token available |
| `/api/v1/ai/ai/schema-matching/` | POST | Requires authentication but no token available |
| `/api/v1/ai/ai/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/ai/ai/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/ai/ai/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/analytics/api/` | POST | Requires authentication but no token available |
| `/api/v1/analytics/api/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/analytics/api/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/analytics/api/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/assets/assets/` | POST | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/activate/` | POST | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/contracts/` | POST | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/datasets/` | POST | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/track-download/` | POST | Requires authentication but no token available |
| `/api/v1/assets/assets/{id}/track-view/` | POST | Requires authentication but no token available |
| `/api/v1/audit/audit-events/` | POST | Requires authentication but no token available |
| `/api/v1/audit/audit-events/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/audit/audit-events/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/audit/audit-events/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/auth/accept-invitation/` | GET | Requires authentication but no token available |
| `/api/v1/auth/accept-invitation/` | POST | Requires authentication but no token available |
| `/api/v1/auth/api-keys/` | POST | Requires authentication but no token available |
| `/api/v1/auth/api-keys/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/auth/api-keys/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/auth/api-keys/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/auth/logout/` | GET | Requires authentication but no token available |
| `/api/v1/auth/logout/` | POST | Requires authentication but no token available |
| `/api/v1/auth/me/` | GET | Requires authentication but no token available |
| `/api/v1/auth/me/` | POST | Requires authentication but no token available |
| `/api/v1/auth/refresh/` | GET | Requires authentication but no token available |
| `/api/v1/auth/refresh/` | POST | Requires authentication but no token available |
| `/api/v1/auth/sessions/` | GET | Requires authentication but no token available |
| `/api/v1/auth/sessions/` | POST | Requires authentication but no token available |
| `/api/v1/auth/sessions/<uuid:session_id>/revoke/` | GET | Requires authentication but no token available |
| `/api/v1/auth/sessions/<uuid:session_id>/revoke/` | POST | Requires authentication but no token available |
| `/api/v1/auth/sso/` | POST | Requires authentication but no token available |
| `/api/v1/auth/sso/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/auth/sso/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/auth/sso/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/compliance/runs/` | POST | Requires authentication but no token available |
| `/api/v1/compliance/runs/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/compliance/runs/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/compliance/runs/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/datasets/datasets/` | POST | Requires authentication but no token available |
| `/api/v1/datasets/datasets/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/datasets/datasets/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/datasets/datasets/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/datasets/datasets/{id}/versions/` | POST | Requires authentication but no token available |
| `/api/v1/developer/plugins/` | POST | Requires authentication but no token available |
| `/api/v1/developer/plugins/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/developer/plugins/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/developer/plugins/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/developer/sdk/` | POST | Requires authentication but no token available |
| `/api/v1/developer/sdk/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/developer/sdk/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/developer/sdk/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/dq/runs/` | POST | Requires authentication but no token available |
| `/api/v1/dq/runs/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/dq/runs/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/dq/runs/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/files/files/` | POST | Requires authentication but no token available |
| `/api/v1/files/files/init/` | POST | Requires authentication but no token available |
| `/api/v1/files/files/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/files/files/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/files/files/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/files/files/{id}/chunks/init/` | POST | Requires authentication but no token available |
| `/api/v1/files/files/{id}/complete/` | POST | Requires authentication but no token available |
| `/api/v1/governance/access-requests/` | POST | Requires authentication but no token available |
| `/api/v1/governance/access-requests/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/governance/access-requests/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/governance/access-requests/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/governance/analytics/` | POST | Requires authentication but no token available |
| `/api/v1/governance/analytics/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/governance/analytics/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/governance/analytics/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/governance/certifications/` | POST | Requires authentication but no token available |
| `/api/v1/governance/certifications/initiate-review/` | POST | Requires authentication but no token available |
| `/api/v1/governance/certifications/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/governance/certifications/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/governance/certifications/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/governance/certifications/{id}/review/` | POST | Requires authentication but no token available |
| `/api/v1/governance/retention-policies/` | POST | Requires authentication but no token available |
| `/api/v1/governance/retention-policies/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/governance/retention-policies/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/governance/retention-policies/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/hub/admin/` | GET | Requires authentication but no token available |
| `/api/v1/hub/admin/` | POST | Requires authentication but no token available |
| `/api/v1/jobs/jobs/` | POST | Requires authentication but no token available |
| `/api/v1/jobs/jobs/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/jobs/jobs/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/jobs/jobs/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/jobs/jobs/{id}/cancel/` | POST | Requires authentication but no token available |
| `/api/v1/marketplace/entitlements/` | POST | Requires authentication but no token available |
| `/api/v1/marketplace/entitlements/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/marketplace/entitlements/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/marketplace/entitlements/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/marketplace/listings/` | POST | Requires authentication but no token available |
| `/api/v1/marketplace/listings/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/marketplace/listings/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/marketplace/listings/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/marketplace/orders/` | POST | Requires authentication but no token available |
| `/api/v1/marketplace/orders/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/marketplace/orders/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/marketplace/orders/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/mesh/domains/` | POST | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/compliance/check/` | POST | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/policies/(?P<policy_id>[^/.]+)/` | DELETE | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/policies/apply/` | POST | Requires authentication but no token available |
| `/api/v1/mesh/domains/{id}/transfer-ownership/` | POST | Requires authentication but no token available |
| `/api/v1/mesh/topology/` | POST | Requires authentication but no token available |
| `/api/v1/mesh/topology/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/mesh/topology/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/mesh/topology/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/observability/metrics/` | GET | Requires authentication but no token available |
| `/api/v1/observability/metrics/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/incidents/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/incidents/update/` | PATCH | Requires authentication but no token available |
| `/api/v1/observability/observability/metrics/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/schema-drift/detect/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/volume/aggregate/` | POST | Requires authentication but no token available |
| `/api/v1/observability/observability/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/observability/observability/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/observability/observability/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/scheduled_ingestion/runs/` | POST | Requires authentication but no token available |
| `/api/v1/scheduled_ingestion/runs/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/scheduled_ingestion/runs/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/scheduled_ingestion/runs/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/semantic/context.jsonld/` | GET | Requires authentication but no token available |
| `/api/v1/semantic/context.jsonld/` | POST | Requires authentication but no token available |
| `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>/` | GET | Requires authentication but no token available |
| `/api/v1/semantic/id/<str:resource_type>/<str:resource_id>/` | POST | Requires authentication but no token available |
| `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/` | GET | Requires authentication but no token available |
| `/api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/` | POST | Requires authentication but no token available |
| `/api/v1/semantic/ontology/` | GET | Requires authentication but no token available |
| `/api/v1/semantic/ontology/` | POST | Requires authentication but no token available |
| `/api/v1/semantic/semantic-resources/` | POST | Requires authentication but no token available |
| `/api/v1/semantic/semantic-resources/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/semantic/semantic-resources/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/semantic/semantic-resources/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/semantic/sparql/` | GET | Requires authentication but no token available |
| `/api/v1/semantic/sparql/` | POST | Requires authentication but no token available |
| `/api/v1/social/comments/` | POST | Requires authentication but no token available |
| `/api/v1/social/comments/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/social/comments/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/social/comments/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/social/communities/` | POST | Requires authentication but no token available |
| `/api/v1/social/communities/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/social/communities/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/social/communities/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/social/ratings/` | POST | Requires authentication but no token available |
| `/api/v1/social/ratings/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/social/ratings/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/social/ratings/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/social/reviews/` | POST | Requires authentication but no token available |
| `/api/v1/social/reviews/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/social/reviews/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/social/reviews/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/tenants/tenants/` | POST | Requires authentication but no token available |
| `/api/v1/tenants/tenants/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/tenants/tenants/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/tenants/tenants/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/tenants/tenants/{id}/reactivate/` | POST | Requires authentication but no token available |
| `/api/v1/tenants/tenants/{id}/suspend/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/executions/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/executions/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/transformation/executions/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/transformation/executions/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/transformation/executions/{id}/cancel/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/execute/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/preview/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/pipelines/{id}/validate/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/previews/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/previews/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/transformation/previews/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/transformation/previews/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/{id}/redo/` | POST | Requires authentication but no token available |
| `/api/v1/transformation/wrangling/{id}/undo/` | POST | Requires authentication but no token available |
| `/api/v1/users/roles/` | POST | Requires authentication but no token available |
| `/api/v1/users/roles/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/users/roles/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/users/roles/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/users/users/` | POST | Requires authentication but no token available |
| `/api/v1/users/users/invite/` | POST | Requires authentication but no token available |
| `/api/v1/users/users/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/users/users/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/users/users/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/users/users/{id}/roles/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/{id}/queries/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/datasets/{id}/validate/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/queries/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/queries/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/virtualization/queries/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/virtualization/queries/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/virtualization/queries/{id}/cancel/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/topology/` | POST | Requires authentication but no token available |
| `/api/v1/virtualization/topology/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/virtualization/topology/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/virtualization/topology/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/webhooks/webhook-deliveries/` | POST | Requires authentication but no token available |
| `/api/v1/webhooks/webhook-deliveries/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/webhooks/webhook-deliveries/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/webhooks/webhook-deliveries/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | POST | Requires authentication but no token available |
| `/api/v1/webhooks/webhooks/` | POST | Requires authentication but no token available |
| `/api/v1/webhooks/webhooks/{id}/` | DELETE | Requires authentication but no token available |
| `/api/v1/webhooks/webhooks/{id}/` | PATCH | Requires authentication but no token available |
| `/api/v1/webhooks/webhooks/{id}/` | PUT | Requires authentication but no token available |
| `/api/v1/webhooks/webhooks/{id}/test/` | POST | Requires authentication but no token available |

## Detailed Results

### POST /api/v1/ai/ai/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/ai/ai/natural-language-search/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/ai/ai/schema-matching/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/ai/ai/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/ai/ai/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/ai/ai/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/analytics/api/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/analytics/api/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/analytics/api/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/analytics/api/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/assets/assets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/assets/assets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/assets/assets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/{id}/activate/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/{id}/contracts/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/{id}/datasets/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/{id}/track-download/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/assets/assets/{id}/track-view/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/audit/audit-events/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/audit/audit-events/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/audit/audit-events/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/audit/audit-events/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/accept-invitation/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/accept-invitation/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/api-keys/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/auth/api-keys/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/auth/api-keys/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/auth/api-keys/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/login/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 4.2ms
- **Error**: Not found - endpoint may not exist

### POST /api/v1/auth/login/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 42.71ms
- **Error**: Not found - endpoint may not exist

### GET /api/v1/auth/logout/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/logout/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/me/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/me/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/password-reset/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 44.93ms
- **Error**: Not found - endpoint may not exist

### POST /api/v1/auth/password-reset/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 43.9ms
- **Error**: Not found - endpoint may not exist

### GET /api/v1/auth/password-reset/confirm/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 43.98ms
- **Error**: Not found - endpoint may not exist

### POST /api/v1/auth/password-reset/confirm/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 43.97ms
- **Error**: Not found - endpoint may not exist

### GET /api/v1/auth/refresh/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/refresh/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/register/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 44.95ms
- **Error**: Not found - endpoint may not exist

### POST /api/v1/auth/register/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 43.93ms
- **Error**: Not found - endpoint may not exist

### GET /api/v1/auth/sessions/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/sessions/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/auth/sessions/<uuid:session_id>/revoke/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/sessions/<uuid:session_id>/revoke/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/auth/sso/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/auth/sso/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/auth/sso/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/auth/sso/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/compliance/runs/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/compliance/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/compliance/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/compliance/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/datasets/datasets/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/datasets/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/datasets/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/datasets/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/datasets/datasets/{id}/versions/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/developer/plugins/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/developer/plugins/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/developer/plugins/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/developer/plugins/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/developer/sdk/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/developer/sdk/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/developer/sdk/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/developer/sdk/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/dq/runs/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/dq/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/dq/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/dq/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/files/files/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/files/files/init/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/files/files/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/files/files/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/files/files/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/files/files/{id}/chunks/init/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/files/files/{id}/complete/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/access-requests/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/governance/access-requests/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/governance/access-requests/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/governance/access-requests/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/analytics/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/governance/analytics/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/governance/analytics/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/governance/analytics/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/certifications/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/certifications/initiate-review/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/governance/certifications/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/governance/certifications/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/governance/certifications/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/certifications/{id}/review/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/governance/retention-policies/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/governance/retention-policies/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/governance/retention-policies/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/governance/retention-policies/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/health/circuit-breakers/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 44.59ms
- **Error**: Not found - endpoint may not exist

### POST /api/v1/health/circuit-breakers/

- **Status**: broken
- **Status Code**: 404
- **Response Time**: 44.98ms
- **Error**: Not found - endpoint may not exist

### GET /api/v1/hub/admin/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/hub/admin/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/jobs/jobs/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/jobs/jobs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/jobs/jobs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/jobs/jobs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/jobs/jobs/{id}/cancel/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/marketplace/entitlements/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/marketplace/entitlements/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/marketplace/entitlements/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/marketplace/entitlements/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/marketplace/listings/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/marketplace/listings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/marketplace/listings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/marketplace/listings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/marketplace/orders/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/marketplace/orders/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/marketplace/orders/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/marketplace/orders/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/mesh/domains/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/mesh/domains/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/mesh/domains/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/mesh/domains/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/mesh/domains/{id}/compliance/check/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/mesh/domains/{id}/policies/(?P<policy_id>[^/.]+)/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/mesh/domains/{id}/policies/apply/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/mesh/domains/{id}/transfer-ownership/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/mesh/topology/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/mesh/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/mesh/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/mesh/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/observability/metrics/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/metrics/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/observability/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/observability/incidents/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/observability/observability/incidents/update/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/observability/metrics/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/observability/schema-drift/detect/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/observability/observability/volume/aggregate/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/observability/observability/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/observability/observability/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/observability/observability/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/scheduled_ingestion/runs/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/scheduled_ingestion/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/scheduled_ingestion/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/scheduled_ingestion/runs/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/semantic/context.jsonld/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/context.jsonld/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/semantic/id/<str:resource_type>/<str:resource_id>/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/id/<str:resource_type>/<str:resource_id>/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/id/field/<str:asset_uuid>/<str:field_name>/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/semantic/ontology/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/ontology/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/semantic-resources/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/semantic/semantic-resources/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/semantic/semantic-resources/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/semantic/semantic-resources/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### GET /api/v1/semantic/sparql/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/semantic/sparql/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/social/comments/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/social/comments/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/social/comments/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/social/comments/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/social/communities/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/social/communities/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/social/communities/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/social/communities/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/social/ratings/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/social/ratings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/social/ratings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/social/ratings/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/social/reviews/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/social/reviews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/social/reviews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/social/reviews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/tenants/tenants/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/tenants/tenants/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/tenants/tenants/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/tenants/tenants/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/tenants/tenants/{id}/reactivate/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/tenants/tenants/{id}/suspend/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/executions/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/transformation/executions/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/transformation/executions/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/transformation/executions/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/executions/{id}/cancel/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/pipelines/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/transformation/pipelines/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/transformation/pipelines/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/transformation/pipelines/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/pipelines/{id}/execute/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/pipelines/{id}/preview/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/pipelines/{id}/validate/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/previews/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/transformation/previews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/transformation/previews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/transformation/previews/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/wrangling/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/transformation/wrangling/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/transformation/wrangling/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/transformation/wrangling/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/wrangling/{id}/redo/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/transformation/wrangling/{id}/undo/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/users/roles/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/users/roles/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/users/roles/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/users/roles/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/users/users/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/users/users/invite/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/users/users/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/users/users/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/users/users/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/users/users/{id}/roles/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/datasets/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/virtualization/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/virtualization/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/virtualization/datasets/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/datasets/{id}/queries/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/datasets/{id}/validate/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/queries/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/virtualization/queries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/virtualization/queries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/virtualization/queries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/queries/{id}/cancel/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/virtualization/topology/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/virtualization/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/virtualization/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/virtualization/topology/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/webhooks/webhook-deliveries/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/webhooks/webhook-deliveries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/webhooks/webhook-deliveries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/webhooks/webhook-deliveries/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/webhooks/webhook-deliveries/{id}/retry/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/webhooks/webhooks/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### DELETE /api/v1/webhooks/webhooks/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PATCH /api/v1/webhooks/webhooks/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### PUT /api/v1/webhooks/webhooks/{id}/

- **Status**: skipped
- **Notes**: Requires authentication but no token available

### POST /api/v1/webhooks/webhooks/{id}/test/

- **Status**: skipped
- **Notes**: Requires authentication but no token available
