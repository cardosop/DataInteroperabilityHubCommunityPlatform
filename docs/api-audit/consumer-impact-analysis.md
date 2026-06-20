# Consumer Impact Analysis Report

**Generated**: 2026-06-10 19:15:46
**Task**: 9.6.1.2.6 - Generate consumer impact report

---

## Overview

This report analyzes all API consumer references across the codebase to identify
which endpoints are consumed by which consumers and assess the impact of
potential API changes.

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Endpoints Analyzed** | **1287** |
| **Total Consumer References** | **7268** |
| **CRITICAL Priority Endpoints** | **24** |
| **HIGH Priority Endpoints** | **40** |
| **MEDIUM Priority Endpoints** | **77** |
| **LOW Priority Endpoints** | **1146** |

## Consumer Type Breakdown

| Consumer Type | Count | Description |
|---------------|-------|-------------|
| **SDK** | **355** | SDK method calls |
| **Webhook** | **169** | Webhook endpoint references |
| **API Client** | **6614** | Direct API client calls |
| **Reverse Lookup** | **130** | Django reverse() calls |
| **Hardcoded** | **0** | Hardcoded endpoint strings |

## CRITICAL Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/contracts` | 427.0 | 425 | api_client:423, sdk:2 |
| `/api/v1/assets` | 408.0 | 406 | api_client:404, sdk:2 |
| `/api/v1/auth/login` | 202.0 | 201 | api_client:200, sdk:1 |
| `/api/v1/compliance/runs` | 118.0 | 116 | api_client:114, sdk:2 |
| `/api/v1/marketplace/listings` | 115.0 | 113 | api_client:111, sdk:2 |
| `/api/v1/contracts/products` | 114.0 | 113 | api_client:112, sdk:1 |
| `/api/v1/tenants/{self.tenant.id}/config` | 104.0 | 104 | api_client:104 |
| `/api/v1/dq/runs` | 96.0 | 94 | api_client:92, sdk:2 |
| `/api/v1/files/init` | 95.0 | 95 | api_client:95 |
| `/api/v1/auth/register` | 93.0 | 92 | api_client:91, sdk:1 |
| `/api/v1/datasets` | 90.0 | 88 | api_client:86, sdk:2 |
| `/api/v1/auth/me` | 75.0 | 73 | api_client:71, sdk:2 |
| `/api/v1/contracts/{self.contract.id}` | 73.0 | 73 | api_client:73 |
| `/api/v1/webhooks/webhooks` | 71.0 | 55 | api_client:25, webhook:28, sdk:2 |
| `/api/v1/contracts/{contract.id}` | 70.0 | 70 | api_client:70 |
| `/api/v1/search/search` | 62.0 | 63 | api_client:58, reverse_lookup:4, sdk:1 |
| `/api/v1/jobs` | 60.0 | 59 | api_client:58, sdk:1 |
| `/api/v1/tenants/{self.tenant1.id}/config` | 59.0 | 59 | api_client:59 |
| `/api/v1/assets/{asset_id}` | 57.0 | 54 | api_client:51, sdk:3 |
| `/api/v1/auth/refresh` | 56.0 | 56 | api_client:56 |

### Breakdown by Consumer Type

#### API_CLIENT (23 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/contracts` | 427.0 | 425 |
| `/api/v1/assets` | 408.0 | 406 |
| `/api/v1/auth/login` | 202.0 | 201 |
| `/api/v1/compliance/runs` | 118.0 | 116 |
| `/api/v1/marketplace/listings` | 115.0 | 113 |
| `/api/v1/contracts/products` | 114.0 | 113 |
| `/api/v1/tenants/{self.tenant.id}/config` | 104.0 | 104 |
| `/api/v1/dq/runs` | 96.0 | 94 |
| `/api/v1/files/init` | 95.0 | 95 |
| `/api/v1/auth/register` | 93.0 | 92 |

#### WEBHOOK (1 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/webhooks/webhooks` | 71.0 | 55 |

## HIGH Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/assets/{self.asset.id}` | 49.0 | 49 | api_client:49 |
| `/api/v1/assets/{asset.id}/activate` | 46.0 | 46 | api_client:46 |
| `/api/v1/contracts/{contract_id}` | 45.0 | 42 | api_client:39, sdk:3 |
| `/api/v1/audit/audit-events/export/` | 41.0 | 41 | api_client:41 |
| `/api/v1/assets/{asset.id}` | 39.0 | 39 | api_client:39 |
| `/api/v1/virtualization/datasets` | 39.0 | 37 | api_client:35, sdk:2 |
| `/api/v1/audit/audit-events/` | 39.0 | 39 | api_client:39 |
| `/api/v1/integrations/marketplace/connections` | 38.0 | 36 | api_client:34, sdk:2 |
| `/api/v1/assets/{asset_id}/activate` | 37.0 | 36 | api_client:35, sdk:1 |
| `/api/v1/marketplace/listings/{listing_id}` | 36.0 | 34 | api_client:32, sdk:2 |
| `/api/v1/openapi.json` | 35.0 | 35 | api_client:35 |
| `/api/v1/auth/api-keys` | 35.0 | 35 | api_client:35 |
| `/api/v1/integrations/marketplace/sync` | 32.0 | 28 | api_client:24, sdk:4 |
| `/api/v1/jobs/{job.id}/cancel` | 31.0 | 31 | api_client:31 |
| `/api/v1/users` | 30.0 | 30 | api_client:30 |
| `/api/v1/contracts/{self.contract.id}/export` | 30.0 | 30 | api_client:30 |
| `/api/v1/tenants` | 29.0 | 29 | api_client:29 |
| `/api/v1/contracts/` | 28.0 | 28 | api_client:28 |
| `/api/v1/datasets/{self.dataset.id}` | 28.0 | 28 | api_client:28 |
| `/api/v1/auth/logout` | 27.0 | 26 | api_client:25, sdk:1 |

### Breakdown by Consumer Type

#### API_CLIENT (39 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/assets/{self.asset.id}` | 49.0 | 49 |
| `/api/v1/assets/{asset.id}/activate` | 46.0 | 46 |
| `/api/v1/contracts/{contract_id}` | 45.0 | 42 |
| `/api/v1/audit/audit-events/export/` | 41.0 | 41 |
| `/api/v1/assets/{asset.id}` | 39.0 | 39 |
| `/api/v1/virtualization/datasets` | 39.0 | 37 |
| `/api/v1/audit/audit-events/` | 39.0 | 39 |
| `/api/v1/integrations/marketplace/connections` | 38.0 | 36 |
| `/api/v1/assets/{asset_id}/activate` | 37.0 | 36 |
| `/api/v1/marketplace/listings/{listing_id}` | 36.0 | 34 |

#### WEBHOOK (1 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/webhooks` | 25.0 | 19 |

## MEDIUM Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/hub.apps.webhooks.service_client.WebhookDeliveryClient` | 19.5 | 13 | webhook:13 |
| `/api/v1/billing/subscription/current` | 19.0 | 17 | api_client:15, sdk:2 |
| `/api/v1/files` | 19.0 | 17 | api_client:15, sdk:2 |
| `/api/v1/assets/data-first` | 19.0 | 19 | api_client:19 |
| `/api/v1/scheduled-exports` | 19.0 | 17 | api_client:15, sdk:2 |
| `/api/v1/governance/retention-policies` | 19.0 | 17 | api_client:15, sdk:2 |
| `/api/v1/social/communities` | 19.0 | 18 | api_client:17, sdk:1 |
| `/api/v1/scheduled-ingestions/internal/runs` | 19.0 | 19 | api_client:19 |
| `/api/v1/capabilities` | 19.0 | 18 | api_client:17, sdk:1 |
| `/api/v1/tenants/me/config` | 19.0 | 19 | api_client:19 |
| `/api/v1/transformation/pipelines` | 19.0 | 17 | api_client:15, sdk:2 |
| `/api/v1/semantic/graphql` | 19.0 | 18 | api_client:17, sdk:1 |
| `/api/v1/api-docs/openapi.json` | 18.0 | 18 | api_client:18 |
| `/api/v1/users/me/erasure-requests/request-erasure` | 18.0 | 17 | api_client:16, sdk:1 |
| `/api/v1/ai/schema-matching` | 18.0 | 17 | api_client:16, sdk:1 |
| `/api/v1/integrations/marketplace/mappings` | 18.0 | 16 | api_client:14, sdk:2 |
| `/api/v1/webhooks/webhooks/{webhook.id}` | 17.5 | 14 | api_client:7, webhook:7 |
| `/api/v1/files/{file_id}` | 17.0 | 15 | api_client:13, sdk:2 |
| `/api/v1/marketplace/listings/search` | 17.0 | 17 | api_client:17 |
| `/api/v1/social/reviews` | 17.0 | 15 | api_client:13, sdk:2 |

### Breakdown by Consumer Type

#### API_CLIENT (71 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/billing/subscription/current` | 19.0 | 17 |
| `/api/v1/files` | 19.0 | 17 |
| `/api/v1/assets/data-first` | 19.0 | 19 |
| `/api/v1/scheduled-exports` | 19.0 | 17 |
| `/api/v1/governance/retention-policies` | 19.0 | 17 |
| `/api/v1/social/communities` | 19.0 | 18 |
| `/api/v1/scheduled-ingestions/internal/runs` | 19.0 | 19 |
| `/api/v1/capabilities` | 19.0 | 18 |
| `/api/v1/tenants/me/config` | 19.0 | 19 |
| `/api/v1/transformation/pipelines` | 19.0 | 17 |

#### REVERSE_LOOKUP (3 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/contract/link/odps` | 12.0 | 24 |
| `/api/v1/domain` | 12.0 | 24 |
| `/api/v1/contract/create/product` | 10.0 | 20 |

#### SDK (1 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/ml/inference/deployments` | 11.0 | 7 |

#### WEBHOOK (2 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/hub.apps.webhooks.service_client.WebhookDeliveryClient` | 19.5 | 13 |
| `/api/v1/.deliver_webhook_with_response` | 16.5 | 11 |

## LOW Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/domain/{id}` | 9.0 | 18 | reverse_lookup:18 |
| `/api/v1/tenants/{self.tenant.id}` | 9.0 | 9 | api_client:9 |
| `/api/v1/10.255.255.1/api/v1/health` | 9.0 | 9 | api_client:9 |
| `/api/v1/{html_error_server}/api/v1/assets` | 9.0 | 9 | api_client:9 |
| `/api/v1/{slow_server}/api/v1/health` | 9.0 | 9 | api_client:9 |
| `/api/v1/{malformed_server}/api/v1/assets` | 9.0 | 9 | api_client:9 |
| `/api/v1/127.0.0.1:{port}/api/v1/assets` | 9.0 | 9 | api_client:9 |
| `/api/v1/files/{file_id}/download` | 9.0 | 8 | api_client:7, sdk:1 |
| `/api/v1/scheduled-ingestions/{ingestion.id}` | 9.0 | 9 | api_client:9 |
| `/api/v1/dq/runs/{dq_run_id}` | 9.0 | 9 | api_client:9 |
| `/api/v1/tenants/onboarding` | 9.0 | 9 | api_client:9 |
| `/api/v1/marketplace/entitlements` | 9.0 | 8 | api_client:7, sdk:1 |
| `/api/v1/localhost:8000/api/v1/ml/models` | 9.0 | 9 | api_client:9 |
| `/api/v1/contracts/{contract_id}/migrate` | 9.0 | 9 | api_client:9 |
| `/api/v1/semantic/context.jsonld` | 9.0 | 9 | api_client:9 |
| `/api/v1/users/{self.regular_user.id}` | 9.0 | 9 | api_client:9 |
| `/api/v1/versioning/versions` | 9.0 | 9 | api_client:9 |
| `/api/v1/consent/consent-purposes/{self.purpose.id}` | 9.0 | 9 | api_client:9 |
| `/api/v1/governance/access-requests/{self.ar.id}/approve` | 9.0 | 9 | api_client:9 |
| `/api/v1/resource/123` | 9.0 | 9 | api_client:9 |

### Breakdown by Consumer Type

#### API_CLIENT (861 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/tenants/{self.tenant.id}` | 9.0 | 9 |
| `/api/v1/10.255.255.1/api/v1/health` | 9.0 | 9 |
| `/api/v1/{html_error_server}/api/v1/assets` | 9.0 | 9 |
| `/api/v1/{slow_server}/api/v1/health` | 9.0 | 9 |
| `/api/v1/{malformed_server}/api/v1/assets` | 9.0 | 9 |
| `/api/v1/127.0.0.1:{port}/api/v1/assets` | 9.0 | 9 |
| `/api/v1/files/{file_id}/download` | 9.0 | 8 |
| `/api/v1/scheduled-ingestions/{ingestion.id}` | 9.0 | 9 |
| `/api/v1/dq/runs/{dq_run_id}` | 9.0 | 9 |
| `/api/v1/tenants/onboarding` | 9.0 | 9 |

#### REVERSE_LOOKUP (31 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/domain/{id}` | 9.0 | 18 |
| `/api/v1/contract/impact/analysis` | 6.0 | 12 |
| `/api/v1/search/suggestions` | 5.0 | 6 |
| `/api/v1/topology` | 5.0 | 10 |
| `/api/v1/virtual/dataset` | 5.0 | 10 |
| `/api/v1/virtual/dataset/{id}` | 5.0 | 10 |
| `/api/v1/domain/transfer/ownership` | 4.0 | 8 |
| `/api/v1/domain/apply/policy` | 4.0 | 8 |
| `/api/v1/domain/remove/policy` | 4.0 | 8 |
| `/api/v1/domain/check/compliance` | 4.0 | 8 |

#### SDK (166 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/scheduled-exports/{export_id}` | 8.0 | 5 |
| `/api/v1/virtualization/datasets/{dataset_id}` | 7.0 | 4 |
| `/api/v1/transformation/pipelines/{pipeline_id}` | 7.0 | 4 |
| `/api/v1/integrations/marketplace/connections/{connection_id}` | 7.0 | 4 |
| `/api/v1/ml/models/{model_id}` | 7.0 | 4 |
| `/api/v1/ml/inference/ab-tests` | 6.0 | 4 |
| `/api/v1/integrations/connections/{conn_id}` | 6.0 | 3 |
| `/api/v1/lineage-subscriptions/{sub_id}` | 6.0 | 3 |
| `/api/v1/billing/subscription/ml/current` | 6.0 | 3 |
| `/api/v1/{DPIA_PREFIX}/{dpia_id}` | 6.0 | 3 |

#### WEBHOOK (88 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/webhook` | 7.5 | 5 |
| `/api/v1/hub.apps.webhooks.ssrf_guard.socket.getaddrinfo` | 7.5 | 5 |
| `/api/v1/trigger_webhook` | 6.0 | 4 |
| `/api/v1/hub.apps.webhooks.service` | 6.0 | 4 |
| `/api/v1/hub.apps.webhooks.odps_event_subscriber.WebhookDeliveryService.trigger_odps_webhook` | 6.0 | 4 |
| `/api/v1/webhooks/webhook-deliveries` | 5.0 | 4 |
| `/api/v1/example.com/webhook` | 4.5 | 3 |
| `/api/v1/webhooks/{self.webhook_a.id}` | 4.5 | 3 |
| `/api/v1/.deliver_webhook` | 4.5 | 3 |
| `/api/v1/webhook.test` | 4.5 | 3 |

## Detailed Consumer References

### By Endpoint

#### `/api/v1/contracts`

- **Impact Score**: 427.0
- **Priority**: CRITICAL
- **Total Consumers**: 425
- **Consumer Types**: api_client:423, sdk:2

**Consumers:**

- **API_CLIENT** (423 references):
  - `tests/performance/locust_stress_test.py:238`
  - `hub/apps/contracts/tests/test_views_filtering_sorting.py:131`
  - `tests/integration/test_contract_apis_comprehensive.py:1170`
  - `hub/apps/contracts/tests/test_odps_api_schema_validation.py:1089`
  - `hub/apps/contracts/tests/test_api_filtering_sorting_consistency.py:395`
  - ... and 418 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/contracts.py:530`
  - `sdk/python/datahub_interoperability/contracts.py:452`

#### `/api/v1/assets`

- **Impact Score**: 408.0
- **Priority**: CRITICAL
- **Total Consumers**: 406
- **Consumer Types**: api_client:404, sdk:2

**Consumers:**

- **API_CLIENT** (404 references):
  - `hub/apps/integrations/tests/security/test_idor.py:295`
  - `tests/e2e/test_phase25_tenant_onboarding_e2e.py:133`
  - `hub/apps/integrations/tests/security/test_idor.py:316`
  - `hub/apps/assets/tests/test_idempotency.py:137`
  - `tests/e2e/test_security_comprehensive.py:627`
  - ... and 399 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/assets.py:31`
  - `sdk/python/datahub_interoperability/assets.py:60`

#### `/api/v1/auth/login`

- **Impact Score**: 202.0
- **Priority**: CRITICAL
- **Total Consumers**: 201
- **Consumer Types**: api_client:200, sdk:1

**Consumers:**

- **API_CLIENT** (200 references):
  - `hub/apps/auth/tests/test_authentication_flows.py:93`
  - `hub/apps/auth/tests/test_authentication.py:302`
  - `hub/apps/auth/tests/test_authentication.py:169`
  - `frontend/e2e/lifecycle/payment-failure.spec.ts:15`
  - `tests/e2e/test_auth_authorization_comprehensive.py:645`
  - ... and 195 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/auth.py:14`

#### `/api/v1/compliance/runs`

- **Impact Score**: 118.0
- **Priority**: CRITICAL
- **Total Consumers**: 116
- **Consumer Types**: api_client:114, sdk:2

**Consumers:**

- **API_CLIENT** (114 references):
  - `hub/apps/contracts/tests/test_integration_onboarding.py:598`
  - `tests/regression/test_api_endpoints.py:655`
  - `hub/apps/compliance/tests/test_views.py:206`
  - `hub/apps/tenants/tests/test_tenant_config_compliance_integration.py:135`
  - `tests/integration/test_compliance_apis_comprehensive.py:263`
  - ... and 109 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/compliance.py:54`
  - `sdk/python/datahub_interoperability/compliance.py:40`

#### `/api/v1/marketplace/listings`

- **Impact Score**: 115.0
- **Priority**: CRITICAL
- **Total Consumers**: 113
- **Consumer Types**: api_client:111, sdk:2

**Consumers:**

- **API_CLIENT** (111 references):
  - `hub/apps/marketplace/tests/test_views.py:248`
  - `tests/e2e/test_marketplace_listings.py:458`
  - `tests/e2e/test_enhanced_use_cases_with_odps.py:1522`
  - `frontend/e2e/lifecycle/full-value-chain.spec.ts:103`
  - `tests/e2e/test_marketplace_listings.py:140`
  - ... and 106 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/marketplace_listings.py:25`
  - `sdk/python/datahub_interoperability/marketplace_listings.py:42`

#### `/api/v1/contracts/products`

- **Impact Score**: 114.0
- **Priority**: CRITICAL
- **Total Consumers**: 113
- **Consumer Types**: api_client:112, sdk:1

**Consumers:**

- **API_CLIENT** (112 references):
  - `hub/apps/contracts/tests/test_error_handling_e2e_comprehensive.py:366`
  - `tests/e2e/test_odps_journeys_comprehensive.py:1658`
  - `hub/apps/contracts/tests/test_creation_flows_e2e_comprehensive.py:1294`
  - `hub/apps/contracts/tests/test_error_handling_e2e_comprehensive.py:461`
  - `hub/apps/contracts/tests/test_odps_api_schema_validation.py:666`
  - ... and 107 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/contracts.py:630`

#### `/api/v1/tenants/{self.tenant.id}/config`

- **Impact Score**: 104.0
- **Priority**: CRITICAL
- **Total Consumers**: 104
- **Consumer Types**: api_client:104

**Consumers:**

- **API_CLIENT** (104 references):
  - `tests/e2e/test_tenant_config_e2e.py:506`
  - `tests/e2e/test_persona_tenant_admin.py:140`
  - `tests/e2e/test_persona_tenant_admin.py:440`
  - `tests/e2e/test_persona_ta_comprehensive.py:1282`
  - `tests/e2e/test_persona_data_provider.py:337`
  - ... and 99 more

#### `/api/v1/dq/runs`

- **Impact Score**: 96.0
- **Priority**: CRITICAL
- **Total Consumers**: 94
- **Consumer Types**: api_client:92, sdk:2

**Consumers:**

- **API_CLIENT** (92 references):
  - `tests/integration/test_rest_business_rules_alignment.py:1167`
  - `hub/apps/dq/tests/test_views.py:387`
  - `tests/e2e/test_persona_auditor.py:134`
  - `tests/uat/test_user_acceptance_django6.py:178`
  - `tests/integration/test_dq_apis_comprehensive.py:186`
  - ... and 87 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/dq.py:48`
  - `sdk/python/datahub_interoperability/dq.py:65`

#### `/api/v1/files/init`

- **Impact Score**: 95.0
- **Priority**: CRITICAL
- **Total Consumers**: 95
- **Consumer Types**: api_client:95

**Consumers:**

- **API_CLIENT** (95 references):
  - `tests/regression/test_workflows.py:402`
  - `tests/regression/test_api_endpoints.py:492`
  - `tests/integration/test_file_apis_comprehensive.py:101`
  - `tests/e2e/test_file_operations.py:304`
  - `tests/e2e/test_complete_user_journeys.py:129`
  - ... and 90 more

#### `/api/v1/auth/register`

- **Impact Score**: 93.0
- **Priority**: CRITICAL
- **Total Consumers**: 92
- **Consumer Types**: api_client:91, sdk:1

**Consumers:**

- **API_CLIENT** (91 references):
  - `hub/apps/auth/tests/test_register_me.py:443`
  - `tests/integration/test_auth_apis_comprehensive.py:400`
  - `hub/apps/auth/tests/test_register_me.py:530`
  - `tests/e2e/test_authentication.py:176`
  - `tests/integration/test_auth_apis_comprehensive.py:220`
  - ... and 86 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/auth.py:25`

#### `/api/v1/datasets`

- **Impact Score**: 90.0
- **Priority**: CRITICAL
- **Total Consumers**: 88
- **Consumer Types**: api_client:86, sdk:2

**Consumers:**

- **API_CLIENT** (86 references):
  - `hub/apps/datasets/tests/test_version_integration.py:42`
  - `tests/e2e/test_data_first_comprehensive.py:370`
  - `tests/integration/test_dataset_apis_comprehensive.py:549`
  - `frontend/e2e/features/file-virus-scan.spec.ts:120`
  - `tests/e2e/test_dq_service.py:275`
  - ... and 81 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/datasets.py:38`
  - `sdk/python/datahub_interoperability/datasets.py:25`

#### `/api/v1/auth/me`

- **Impact Score**: 75.0
- **Priority**: CRITICAL
- **Total Consumers**: 73
- **Consumer Types**: api_client:71, sdk:2

**Consumers:**

- **API_CLIENT** (71 references):
  - `tests/integration/test_auth_apis_comprehensive.py:746`
  - `tests/integration/test_auth_apis_comprehensive.py:898`
  - `hub/apps/auth/tests/test_me_profile.py:146`
  - `hub/apps/auth/tests/test_me_profile.py:179`
  - `tests/integration/test_auth_apis_comprehensive.py:578`
  - ... and 66 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/auth.py:37`
  - `sdk/python/datahub_interoperability/auth.py:40`

#### `/api/v1/contracts/{self.contract.id}`

- **Impact Score**: 73.0
- **Priority**: CRITICAL
- **Total Consumers**: 73
- **Consumer Types**: api_client:73

**Consumers:**

- **API_CLIENT** (73 references):
  - `tests/integration/test_contract_apis_comprehensive.py:1819`
  - `hub/apps/contracts/tests/test_views.py:270`
  - `hub/apps/contracts/tests/test_views.py:393`
  - `hub/apps/contracts/tests/test_views.py:681`
  - `hub/apps/contracts/tests/test_api_caching_headers.py:367`
  - ... and 68 more

#### `/api/v1/webhooks/webhooks`

- **Impact Score**: 71.0
- **Priority**: CRITICAL
- **Total Consumers**: 55
- **Consumer Types**: api_client:25, webhook:28, sdk:2

**Consumers:**

- **API_CLIENT** (25 references):
  - `hub/apps/webhooks/tests/test_webhook_api_integration.py:247`
  - `tests/e2e/test_persona_dev_comprehensive.py:836`
  - `hub/apps/webhooks/tests/test_webhook_api_integration.py:217`
  - `tests/e2e/test_persona_dev_comprehensive.py:914`
  - `tests/e2e/test_persona_dev_comprehensive.py:745`
  - ... and 20 more
- **WEBHOOK** (28 references):
  - `hub/apps/webhooks/tests/test_webhook_api_integration.py:58`
  - `tests/e2e/test_persona_dev_comprehensive.py:746`
  - `tests/e2e/test_persona_dev_comprehensive.py:797`
  - `tests/e2e/test_persona_dev_comprehensive.py:716`
  - `tests/integration/test_advanced_observability_new_use_cases_comprehensive.py:321`
  - ... and 23 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/webhooks.py:58`
  - `sdk/python/datahub_interoperability/webhooks.py:84`

#### `/api/v1/contracts/{contract.id}`

- **Impact Score**: 70.0
- **Priority**: CRITICAL
- **Total Consumers**: 70
- **Consumer Types**: api_client:70

**Consumers:**

- **API_CLIENT** (70 references):
  - `hub/apps/contracts/tests/test_frontend_integration_points.py:313`
  - `hub/apps/contracts/tests/test_payload_size_limit.py:184`
  - `hub/apps/contracts/tests/test_etag_concurrent_edit.py:101`
  - `tests/integration/test_api_edge_cases.py:698`
  - `hub/apps/contracts/tests/test_etag_concurrent_edit.py:170`
  - ... and 65 more

#### `/api/v1/search/search`

- **Impact Score**: 62.0
- **Priority**: CRITICAL
- **Total Consumers**: 63
- **Consumer Types**: api_client:58, reverse_lookup:4, sdk:1

**Consumers:**

- **API_CLIENT** (58 references):
  - `tests/integration/test_search_apis_comprehensive.py:186`
  - `tests/security/test_search_security.py:81`
  - `tests/integration/test_search_apis_comprehensive.py:207`
  - `tests/integration/test_search_apis_comprehensive.py:821`
  - `tests/integration/test_search_apis_comprehensive.py:264`
  - ... and 53 more
- **REVERSE_LOOKUP** (4 references):
  - `apps/search/tests/test_views.py:97`
  - `apps/search/tests/test_views.py:97`
  - `apps/search/tests/test_views.py:87`
  - `apps/search/tests/test_views.py:87`
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/search.py:85`

#### `/api/v1/jobs`

- **Impact Score**: 60.0
- **Priority**: CRITICAL
- **Total Consumers**: 59
- **Consumer Types**: api_client:58, sdk:1

**Consumers:**

- **API_CLIENT** (58 references):
  - `hub/apps/jobs/tests/test_views.py:127`
  - `hub/apps/jobs/tests/test_views.py:255`
  - `hub/apps/jobs/tests/test_integration_processing.py:205`
  - `tests/integration/test_tenant_isolation.py:285`
  - `tests/performance/locust_job_queue_throughput.py:128`
  - ... and 53 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/jobs.py:41`

#### `/api/v1/tenants/{self.tenant1.id}/config`

- **Impact Score**: 59.0
- **Priority**: CRITICAL
- **Total Consumers**: 59
- **Consumer Types**: api_client:59

**Consumers:**

- **API_CLIENT** (59 references):
  - `tests/regression/test_tenant_isolation.py:227`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:318`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:274`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:184`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:777`
  - ... and 54 more

#### `/api/v1/assets/{asset_id}`

- **Impact Score**: 57.0
- **Priority**: CRITICAL
- **Total Consumers**: 54
- **Consumer Types**: api_client:51, sdk:3

**Consumers:**

- **API_CLIENT** (51 references):
  - `tests/e2e/test_asset_operations.py:133`
  - `tests/integration/test_asset_management_original_use_cases_comprehensive.py:667`
  - `tests/regression/test_existing_functionality_verification.py:262`
  - `tests/e2e/test_persona_cpo_comprehensive.py:166`
  - `tests/e2e/test_auth_authorization_comprehensive.py:724`
  - ... and 46 more
- **SDK** (3 references):
  - `sdk/python/datahub_interoperability/assets.py:41`
  - `sdk/python/datahub_interoperability/assets.py:63`
  - `sdk/python/datahub_interoperability/assets.py:66`

#### `/api/v1/auth/refresh`

- **Impact Score**: 56.0
- **Priority**: CRITICAL
- **Total Consumers**: 56
- **Consumer Types**: api_client:56

**Consumers:**

- **API_CLIENT** (56 references):
  - `hub/apps/auth/tests/test_security_hardening.py:191`
  - `hub/apps/auth/tests/test_security_hardening.py:331`
  - `hub/apps/auth/tests/test_authentication_flows.py:449`
  - `tests/integration/test_auth_apis_comprehensive.py:1555`
  - `hub/tests/test_auth_security.py:209`
  - ... and 51 more

#### `/api/v1/scheduled-ingestions`

- **Impact Score**: 52.0
- **Priority**: CRITICAL
- **Total Consumers**: 50
- **Consumer Types**: api_client:48, sdk:2

**Consumers:**

- **API_CLIENT** (48 references):
  - `tests/e2e/test_persona_data_engineer_comprehensive.py:719`
  - `tests/integration/test_rest_business_rules_alignment.py:1310`
  - `tests/e2e/test_scheduled_ingestion.py:348`
  - `hub/apps/scheduled_ingestion/tests/test_scheduled_ingestion_comprehensive_validation.py:430`
  - `hub/tests/regression/test_service_layer_regression.py:363`
  - ... and 43 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/scheduled_ingestion.py:63`
  - `sdk/python/datahub_interoperability/scheduled_ingestion.py:93`

#### `/api/v1/localhost:8000/api/v1`

- **Impact Score**: 52.0
- **Priority**: CRITICAL
- **Total Consumers**: 52
- **Consumer Types**: api_client:52

**Consumers:**

- **API_CLIENT** (52 references):
  - `cli/tests/integration/test_odh_cli_comprehensive_validation.py:470`
  - `cli/tests/integration/test_ml_serving_cli_comprehensive.py:134`
  - `cli/tests/integration/test_baas_cli_comprehensive.py:44`
  - `cli/tests/integration/test_ml_training_commands_real_api.py:352`
  - `cli/tests/integration/test_odh_cli_comprehensive_validation.py:647`
  - ... and 47 more

#### `/api/v1/marketplace/orders`

- **Impact Score**: 51.0
- **Priority**: CRITICAL
- **Total Consumers**: 49
- **Consumer Types**: api_client:47, sdk:2

**Consumers:**

- **API_CLIENT** (47 references):
  - `tests/e2e/test_persona_workflows_odps_enhanced.py:1546`
  - `hub/apps/marketplace/tests/test_auto_approval.py:169`
  - `hub/apps/marketplace/tests/test_auto_approval.py:232`
  - `tests/integration/test_marketplace_apis_comprehensive.py:1044`
  - `tests/regression/test_api_endpoints.py:766`
  - ... and 42 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/marketplace_listings.py:62`
  - `sdk/python/datahub_interoperability/marketplace_listings.py:59`

#### `/api/v1/audit/audit-events`

- **Impact Score**: 51.0
- **Priority**: CRITICAL
- **Total Consumers**: 51
- **Consumer Types**: api_client:51

**Consumers:**

- **API_CLIENT** (51 references):
  - `hub/apps/audit/tests/test_audit_event_querying.py:106`
  - `tests/e2e/test_persona_failure_paths_comprehensive.py:241`
  - `hub/apps/audit/tests/test_views.py:125`
  - `tests/integration/test_audit_apis_comprehensive.py:49`
  - `tests/e2e/test_audit_compliance_journeys.py:334`
  - ... and 46 more

#### `/api/v1/assets/{self.asset.id}`

- **Impact Score**: 49.0
- **Priority**: HIGH
- **Total Consumers**: 49
- **Consumer Types**: api_client:49

**Consumers:**

- **API_CLIENT** (49 references):
  - `tests/integration/test_asset_apis_comprehensive.py:897`
  - `tests/integration/test_asset_apis_comprehensive.py:2043`
  - `hub/apps/assets/tests/test_asset_if_match_locking.py:55`
  - `hub/apps/assets/tests/test_asset_if_match_locking.py:86`
  - `tests/integration/test_asset_apis_comprehensive.py:2029`
  - ... and 44 more

#### `/api/v1/assets/{asset.id}/activate`

- **Impact Score**: 46.0
- **Priority**: HIGH
- **Total Consumers**: 46
- **Consumer Types**: api_client:46

**Consumers:**

- **API_CLIENT** (46 references):
  - `hub/apps/assets/tests/test_asset_activation.py:108`
  - `hub/apps/compliance/tests/test_circuit_breaker.py:120`
  - `tests/integration/test_asset_apis_comprehensive.py:1294`
  - `hub/apps/assets/tests/test_activation_blockers_api.py:133`
  - `hub/apps/assets/tests/test_asset_activation.py:199`
  - ... and 41 more

#### `/api/v1/contracts/{contract_id}`

- **Impact Score**: 45.0
- **Priority**: HIGH
- **Total Consumers**: 42
- **Consumer Types**: api_client:39, sdk:3

**Consumers:**

- **API_CLIENT** (39 references):
  - `scripts/verify_existing_functionality.py:738`
  - `tests/e2e/test_contract_operations.py:539`
  - `tests/e2e/test_persona_dpo_comprehensive.py:633`
  - `tests/concurrency/test_race_conditions.py:163`
  - `tests/regression/test_workflows.py:376`
  - ... and 34 more
- **SDK** (3 references):
  - `sdk/python/datahub_interoperability/contracts.py:677`
  - `sdk/python/datahub_interoperability/contracts.py:464`
  - `sdk/python/datahub_interoperability/contracts.py:668`

#### `/api/v1/audit/audit-events/export/`

- **Impact Score**: 41.0
- **Priority**: HIGH
- **Total Consumers**: 41
- **Consumer Types**: api_client:41

**Consumers:**

- **API_CLIENT** (41 references):
  - `hub/apps/audit/tests/test_views.py:569`
  - `hub/apps/audit/tests/test_views.py:462`
  - `hub/apps/audit/tests/test_views.py:454`
  - `hub/apps/audit/tests/test_views.py:478`
  - `tests/e2e/test_audit_logging.py:148`
  - ... and 36 more

#### `/api/v1/assets/{asset.id}`

- **Impact Score**: 39.0
- **Priority**: HIGH
- **Total Consumers**: 39
- **Consumer Types**: api_client:39

**Consumers:**

- **API_CLIENT** (39 references):
  - `tests/integration/test_asset_apis_comprehensive.py:2460`
  - `hub/apps/assets/tests/test_asset_relationships.py:743`
  - `tests/regression/test_api_endpoints.py:347`
  - `tests/integration/test_asset_apis_comprehensive.py:2424`
  - `tests/integration/test_dpo_api_endpoints.py:107`
  - ... and 34 more

#### `/api/v1/virtualization/datasets`

- **Impact Score**: 39.0
- **Priority**: HIGH
- **Total Consumers**: 37
- **Consumer Types**: api_client:35, sdk:2

**Consumers:**

- **API_CLIENT** (35 references):
  - `hub/apps/virtualization/tests/test_views.py:183`
  - `hub/apps/virtualization/tests/test_views_integration.py:392`
  - `hub/apps/virtualization/tests/test_views.py:199`
  - `tests/e2e/test_new_user_journeys_comprehensive.py:4779`
  - `hub/apps/virtualization/tests/test_views.py:938`
  - ... and 30 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/virtualization.py:157`
  - `sdk/python/datahub_interoperability/virtualization.py:227`

#### `/api/v1/audit/audit-events/`

- **Impact Score**: 39.0
- **Priority**: HIGH
- **Total Consumers**: 39
- **Consumer Types**: api_client:39

**Consumers:**

- **API_CLIENT** (39 references):
  - `hub/apps/audit/tests/test_views.py:204`
  - `tests/e2e/test_persona_aud_comprehensive.py:220`
  - `hub/apps/audit/tests/test_views.py:213`
  - `tests/e2e/test_audit_logging.py:200`
  - `hub/apps/audit/tests/test_views.py:282`
  - ... and 34 more

#### `/api/v1/integrations/marketplace/connections`

- **Impact Score**: 38.0
- **Priority**: HIGH
- **Total Consumers**: 36
- **Consumer Types**: api_client:34, sdk:2

**Consumers:**

- **API_CLIENT** (34 references):
  - `hub/apps/integrations/tests/test_views.py:626`
  - `hub/apps/integrations/tests/test_views.py:590`
  - `hub/apps/integrations/tests/test_urls.py:568`
  - `hub/apps/integrations/tests/test_views.py:611`
  - `tests/security/test_marketplace_security.py:1090`
  - ... and 29 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/marketplace.py:356`
  - `sdk/python/datahub_interoperability/marketplace.py:301`

#### `/api/v1/assets/{asset_id}/activate`

- **Impact Score**: 37.0
- **Priority**: HIGH
- **Total Consumers**: 36
- **Consumer Types**: api_client:35, sdk:1

**Consumers:**

- **API_CLIENT** (35 references):
  - `hub/apps/assets/tests/test_activation_integration.py:550`
  - `hub/apps/contracts/tests/test_integration_onboarding.py:677`
  - `hub/apps/assets/tests/test_activation_integration.py:115`
  - `tests/e2e/test_asset_operations.py:251`
  - `hub/apps/assets/tests/test_activation_integration.py:514`
  - ... and 30 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/assets.py:69`

#### `/api/v1/marketplace/listings/{listing_id}`

- **Impact Score**: 36.0
- **Priority**: HIGH
- **Total Consumers**: 34
- **Consumer Types**: api_client:32, sdk:2

**Consumers:**

- **API_CLIENT** (32 references):
  - `tests/e2e/test_enhanced_journeys_with_odps.py:1398`
  - `tests/e2e/test_enhanced_journeys_with_odps.py:1205`
  - `tests/e2e/test_persona_workflows_odps_enhanced.py:1536`
  - `tests/e2e/test_enhanced_journeys_with_odps.py:1327`
  - `tests/e2e/test_marketplace_listings.py:124`
  - ... and 27 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/marketplace_listings.py:45`
  - `sdk/python/datahub_interoperability/marketplace_listings.py:28`

#### `/api/v1/openapi.json`

- **Impact Score**: 35.0
- **Priority**: HIGH
- **Total Consumers**: 35
- **Consumer Types**: api_client:35

**Consumers:**

- **API_CLIENT** (35 references):
  - `hub/apps/contracts/tests/test_api_contract_documentation.py:95`
  - `tests/e2e/test_openapi_spec_comprehensive.py:384`
  - `tests/integration/test_api_endpoint_discovery.py:230`
  - `tests/e2e/test_api_usability_comprehensive.py:168`
  - `tests/e2e/test_health_endpoints.py:86`
  - ... and 30 more

#### `/api/v1/auth/api-keys`

- **Impact Score**: 35.0
- **Priority**: HIGH
- **Total Consumers**: 35
- **Consumer Types**: api_client:35

**Consumers:**

- **API_CLIENT** (35 references):
  - `hub/apps/auth/tests/test_api_key_auth.py:103`
  - `hub/apps/auth/tests/test_api_key_auth.py:286`
  - `tests/regression/test_auth_authorization.py:154`
  - `hub/apps/auth/tests/test_api_key_auth.py:139`
  - `hub/apps/auth/tests/test_api_key_auth.py:438`
  - ... and 30 more

#### `/api/v1/integrations/marketplace/sync`

- **Impact Score**: 32.0
- **Priority**: HIGH
- **Total Consumers**: 28
- **Consumer Types**: api_client:24, sdk:4

**Consumers:**

- **API_CLIENT** (24 references):
  - `tests/e2e/test_new_user_journeys_comprehensive.py:4884`
  - `hub/apps/integrations/tests/test_sync_job_views.py:496`
  - `hub/apps/integrations/tests/test_sync_job_views.py:154`
  - `hub/apps/integrations/tests/test_urls.py:431`
  - `hub/apps/integrations/tests/test_sync_job_views.py:166`
  - ... and 19 more
- **SDK** (4 references):
  - `sdk/python/datahub_interoperability/marketplace.py:581`
  - `sdk/python/datahub_interoperability/marketplace.py:537`
  - `sdk/python/datahub_interoperability/marketplace.py:637`
  - `sdk/python/datahub_interoperability/marketplace.py:738`

#### `/api/v1/jobs/{job.id}/cancel`

- **Impact Score**: 31.0
- **Priority**: HIGH
- **Total Consumers**: 31
- **Consumer Types**: api_client:31

**Consumers:**

- **API_CLIENT** (31 references):
  - `tests/integration/test_job_apis_comprehensive.py:804`
  - `hub/apps/jobs/tests/test_views.py:648`
  - `tests/integration/test_job_apis_comprehensive.py:738`
  - `hub/apps/jobs/tests/test_integration_processing.py:224`
  - `hub/apps/jobs/tests/test_job_cancellation.py:84`
  - ... and 26 more

#### `/api/v1/users`

- **Impact Score**: 30.0
- **Priority**: HIGH
- **Total Consumers**: 30
- **Consumer Types**: api_client:30

**Consumers:**

- **API_CLIENT** (30 references):
  - `tests/e2e/test_persona_ta_comprehensive.py:139`
  - `scripts/verify_existing_functionality.py:466`
  - `tests/e2e/test_persona_failure_paths_comprehensive.py:174`
  - `hub/apps/auth/tests/test_api_key_auth.py:70`
  - `hub/tests/regression/test_service_layer_regression.py:403`
  - ... and 25 more

#### `/api/v1/contracts/{self.contract.id}/export`

- **Impact Score**: 30.0
- **Priority**: HIGH
- **Total Consumers**: 30
- **Consumer Types**: api_client:30

**Consumers:**

- **API_CLIENT** (30 references):
  - `hub/apps/contracts/tests/test_export_endpoint.py:99`
  - `hub/apps/contracts/tests/test_export_endpoints_integration.py:527`
  - `hub/apps/contracts/tests/test_export_endpoints_integration.py:447`
  - `hub/apps/contracts/tests/test_export_endpoints_integration.py:473`
  - `hub/apps/contracts/tests/test_export_endpoint.py:215`
  - ... and 25 more

#### `/api/v1/tenants`

- **Impact Score**: 29.0
- **Priority**: HIGH
- **Total Consumers**: 29
- **Consumer Types**: api_client:29

**Consumers:**

- **API_CLIENT** (29 references):
  - `tests/e2e/test_persona_pa_comprehensive.py:268`
  - `tests/e2e/test_persona_pa_comprehensive.py:175`
  - `scripts/verify_existing_functionality.py:450`
  - `tests/e2e/test_auth_authorization_comprehensive.py:675`
  - `tests/e2e/test_auth_authorization_comprehensive.py:682`
  - ... and 24 more

#### `/api/v1/contracts/`

- **Impact Score**: 28.0
- **Priority**: HIGH
- **Total Consumers**: 28
- **Consumer Types**: api_client:28

**Consumers:**

- **API_CLIENT** (28 references):
  - `hub/apps/contracts/tests/test_views.py:745`
  - `hub/apps/contracts/tests/test_views.py:654`
  - `hub/apps/contracts/tests/test_post_migration_validation_e2e_comprehensive.py:418`
  - `tests/integration/test_odps_cross_integration.py:560`
  - `hub/apps/contracts/tests/test_views.py:183`
  - ... and 23 more

#### `/api/v1/datasets/{self.dataset.id}`

- **Impact Score**: 28.0
- **Priority**: HIGH
- **Total Consumers**: 28
- **Consumer Types**: api_client:28

**Consumers:**

- **API_CLIENT** (28 references):
  - `hub/apps/datasets/tests/test_views.py:349`
  - `hub/apps/datasets/tests/test_views.py:315`
  - `tests/integration/test_dataset_apis_comprehensive.py:861`
  - `tests/integration/test_dataset_apis_comprehensive.py:766`
  - `hub/apps/datasets/tests/test_views.py:535`
  - ... and 23 more

#### `/api/v1/auth/logout`

- **Impact Score**: 27.0
- **Priority**: HIGH
- **Total Consumers**: 26
- **Consumer Types**: api_client:25, sdk:1

**Consumers:**

- **API_CLIENT** (25 references):
  - `hub/apps/auth/tests/test_httponly_cookie_auth.py:178`
  - `tests/integration/test_auth_apis_comprehensive.py:1211`
  - `hub/apps/auth/tests/test_authentication.py:468`
  - `tests/integration/test_auth_apis_comprehensive.py:1256`
  - `hub/apps/auth/tests/test_authentication_flows.py:461`
  - ... and 20 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/auth.py:31`

#### `/api/v1/governance/access-requests`

- **Impact Score**: 26.0
- **Priority**: HIGH
- **Total Consumers**: 24
- **Consumer Types**: api_client:22, sdk:2

**Consumers:**

- **API_CLIENT** (22 references):
  - `hub/apps/governance/tests/test_access_request_views.py:418`
  - `tests/e2e/test_new_user_journeys_comprehensive.py:4527`
  - `hub/apps/governance/tests/test_access_request_views.py:509`
  - `hub/apps/governance/tests/test_access_request_views.py:336`
  - `hub/apps/governance/tests/test_access_request_views.py:198`
  - ... and 17 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/governance.py:196`
  - `sdk/python/datahub_interoperability/governance.py:170`

#### `/api/v1/assets/{fake_id}`

- **Impact Score**: 26.0
- **Priority**: HIGH
- **Total Consumers**: 26
- **Consumer Types**: api_client:26

**Consumers:**

- **API_CLIENT** (26 references):
  - `tests/e2e/test_error_handling_comprehensive.py:702`
  - `tests/e2e/test_error_handling_comprehensive.py:754`
  - `tests/e2e/test_security_comprehensive.py:585`
  - `tests/e2e/test_error_handling_comprehensive.py:166`
  - `hub/apps/assets/tests/test_asset_crud.py:734`
  - ... and 21 more

#### `/api/v1/marketplace/listings/{self.listing.id}/download`

- **Impact Score**: 26.0
- **Priority**: HIGH
- **Total Consumers**: 26
- **Consumer Types**: api_client:26

**Consumers:**

- **API_CLIENT** (26 references):
  - `hub/apps/marketplace/tests/test_marketplace_export_integration.py:550`
  - `hub/apps/marketplace/tests/test_marketplace_export_integration.py:333`
  - `hub/apps/marketplace/tests/test_marketplace_export_integration.py:195`
  - `hub/apps/contracts/tests/test_export_endpoints_integration.py:570`
  - `hub/apps/marketplace/tests/test_marketplace_export_integration.py:486`
  - ... and 21 more

#### `/api/v1/assets/`

- **Impact Score**: 25.0
- **Priority**: HIGH
- **Total Consumers**: 25
- **Consumer Types**: api_client:25

**Consumers:**

- **API_CLIENT** (25 references):
  - `tests/e2e/test_multi_tenant_isolation.py:248`
  - `hub/apps/assets/tests/test_asset_crud.py:483`
  - `hub/apps/assets/tests/test_asset_crud.py:603`
  - `tests/schema/test_pagination_consistency.py:97`
  - `hub/apps/assets/tests/test_asset_crud.py:465`
  - ... and 20 more

#### `/api/v1/contracts/{self.contract.id}/validate`

- **Impact Score**: 25.0
- **Priority**: HIGH
- **Total Consumers**: 25
- **Consumer Types**: api_client:25

**Consumers:**

- **API_CLIENT** (25 references):
  - `hub/apps/contracts/tests/test_views_validation.py:567`
  - `hub/apps/contracts/tests/test_views_validation.py:556`
  - `tests/integration/test_contract_apis_comprehensive.py:2125`
  - `tests/integration/test_contract_apis_comprehensive.py:2376`
  - `hub/apps/contracts/tests/test_views_validation.py:415`
  - ... and 20 more

#### `/api/v1/webhooks`

- **Impact Score**: 25.0
- **Priority**: HIGH
- **Total Consumers**: 19
- **Consumer Types**: webhook:12, api_client:7

**Consumers:**

- **WEBHOOK** (12 references):
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:50`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:45`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:133`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:85`
  - `hub/tests/test_security_121f.py:425`
  - ... and 7 more
- **API_CLIENT** (7 references):
  - `frontend/e2e/journeys/features/webhooks-management.spec.ts:30`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:85`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:50`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:45`
  - `hub/apps/webhooks/tests/test_views_comprehensive.py:145`
  - ... and 2 more

## Methodology

### Impact Score Calculation

The impact score is calculated based on:

1. **Number of consumers**: Each consumer adds to the base score
2. **Consumer type weights**:
   - SDK: 2.0x (external API consumers)
   - Webhook: 1.5x (event-driven integrations)
   - API Client: 1.0x (internal service calls)
   - Reverse Lookup: 0.5x (internal URL references)
   - Hardcoded: 1.0x (direct endpoint strings)

### Priority Classification

- **CRITICAL**: Impact score >= 50
- **HIGH**: Impact score >= 20
- **MEDIUM**: Impact score >= 10
- **LOW**: Impact score < 10

## Data Sources

This report is compiled from the following analysis tasks:

1. **Task 9.6.1.2.2**: URL reverse lookups (`reverse_lookup_analysis.json`)
2. **Task 9.6.1.2.3**: API client usage (`api-client-usage-report.json`)
3. **Task 9.6.1.2.5**: Webhook payloads and events (`webhook-payloads-and-events-report.json`)
4. **Task 9.6.1.2.1**: Hardcoded endpoints (`hardcoded-endpoints-impact-matrix.json`)
