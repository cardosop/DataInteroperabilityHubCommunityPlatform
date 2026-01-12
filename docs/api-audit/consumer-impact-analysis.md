# Consumer Impact Analysis Report

**Generated**: 2025-12-28 11:03:47
**Task**: 9.6.1.2.6 - Generate consumer impact report

---

## Overview

This report analyzes all API consumer references across the codebase to identify
which endpoints are consumed by which consumers and assess the impact of
potential API changes.

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Endpoints Analyzed** | **1418** |
| **Total Consumer References** | **10684** |
| **CRITICAL Priority Endpoints** | **51** |
| **HIGH Priority Endpoints** | **80** |
| **MEDIUM Priority Endpoints** | **359** |
| **LOW Priority Endpoints** | **928** |

## Consumer Type Breakdown

| Consumer Type | Count | Description |
|---------------|-------|-------------|
| **SDK** | **92** | SDK method calls |
| **Webhook** | **76** | Webhook endpoint references |
| **API Client** | **2923** | Direct API client calls |
| **Reverse Lookup** | **130** | Django reverse() calls |
| **Hardcoded** | **7463** | Hardcoded endpoint strings |

## CRITICAL Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/assets/assets` | 631.0 | 631 | hardcoded:444, api_client:187 |
| `/api/v1/contracts/contracts` | 508.0 | 508 | api_client:159, hardcoded:349 |
| `/api/v1/assets` | 379.0 | 379 | hardcoded:344, api_client:35 |
| `/api/v1/auth/login` | 312.0 | 312 | hardcoded:237, api_client:75 |
| `/api/v1/marketplace/listings` | 297.0 | 297 | hardcoded:238, api_client:59 |
| `/api/v1/tenants/tenants/{self.tenant.id}/config` | 278.0 | 278 | hardcoded:180, api_client:98 |
| `/api/v1/contracts` | 272.0 | 270 | api_client:51, hardcoded:217, sdk:2 |
| `/api/v1/search/search` | 207.0 | 208 | api_client:49, hardcoded:154, sdk:1, reverse_lookup:4 |
| `/api/v1/auth/register` | 201.0 | 201 | hardcoded:159, api_client:42 |
| `/api/v1/dq/runs` | 199.0 | 199 | hardcoded:158, api_client:41 |
| `/api/v1/auth/me` | 178.0 | 178 | hardcoded:149, api_client:29 |
| `/api/v1/assets/{id}/activate` | 168.0 | 168 | hardcoded:168 |
| `/api/v1/compliance/runs` | 159.0 | 159 | hardcoded:113, api_client:46 |
| `/api/v1/assets/assets/` | 150.0 | 150 | api_client:56, hardcoded:94 |
| `/api/v1/datasets` | 134.0 | 134 | hardcoded:129, api_client:5 |
| `/api/v1/assets/assets/{asset_id}` | 129.0 | 129 | api_client:43, hardcoded:86 |
| `/api/v1/auth/api-keys` | 129.0 | 129 | hardcoded:112, api_client:17 |
| `/api/v1/marketplace/orders` | 127.0 | 127 | hardcoded:90, api_client:37 |
| `/api/v1/auth/refresh` | 120.0 | 120 | hardcoded:94, api_client:26 |
| `/api/v1/assets/assets/{self.asset.id}` | 119.0 | 119 | hardcoded:80, api_client:39 |

### Breakdown by Consumer Type

#### API_CLIENT (1 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/tenants/tenants/{self.tenant1.id}/config` | 103.0 | 103 |

#### HARDCODED (50 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/assets/assets` | 631.0 | 631 |
| `/api/v1/contracts/contracts` | 508.0 | 508 |
| `/api/v1/assets` | 379.0 | 379 |
| `/api/v1/auth/login` | 312.0 | 312 |
| `/api/v1/marketplace/listings` | 297.0 | 297 |
| `/api/v1/tenants/tenants/{self.tenant.id}/config` | 278.0 | 278 |
| `/api/v1/contracts` | 272.0 | 270 |
| `/api/v1/search/search` | 207.0 | 208 |
| `/api/v1/auth/register` | 201.0 | 201 |
| `/api/v1/dq/runs` | 199.0 | 199 |

## HIGH Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/tenants/tenants` | 49.0 | 49 | api_client:17, hardcoded:32 |
| `/api/v1/tenants` | 48.0 | 48 | hardcoded:46, api_client:2 |
| `/api/v1/assets/assets/{asset_id}/activate` | 47.0 | 47 | api_client:21, hardcoded:26 |
| `/api/v1/transformation/pipelines/{pipeline_id}` | 47.0 | 44 | api_client:19, hardcoded:22, sdk:3 |
| `/api/v1/social/communities` | 47.0 | 47 | hardcoded:47 |
| `/api/v1/assets/assets/{asset.id}` | 46.0 | 46 | api_client:18, hardcoded:28 |
| `/api/v1/developer/plugins` | 46.0 | 46 | hardcoded:45, api_client:1 |
| `/api/v1/developer/sdk` | 46.0 | 46 | api_client:2, hardcoded:44 |
| `/api/v1/datasets/datasets/{self.dataset.id}` | 45.0 | 45 | api_client:15, hardcoded:30 |
| `/api/v1/audit/audit-events/` | 43.0 | 43 | hardcoded:26, api_client:17 |
| `/api/v1/tenants/{id}` | 43.0 | 43 | hardcoded:43 |
| `/api/v1/search` | 42.0 | 42 | hardcoded:42 |
| `/api/v1/virtualization/datasets` | 42.0 | 40 | hardcoded:14, api_client:24, sdk:2 |
| `/api/v1/jobs/jobs/{job.id}/cancel` | 41.0 | 41 | hardcoded:22, api_client:19 |
| `/api/v1/openapi.json` | 41.0 | 41 | hardcoded:36, api_client:5 |
| `/api/v1/social/comments` | 41.0 | 41 | hardcoded:41 |
| `/api/v1/contracts/contracts/{self.contract.id}/validate` | 40.0 | 40 | api_client:18, hardcoded:22 |
| `/api/v1/auth/password-reset` | 40.0 | 40 | hardcoded:35, api_client:5 |
| `/api/v1/users/roles/{id}` | 40.0 | 40 | hardcoded:40 |
| `/api/v1/contracts/` | 39.0 | 39 | hardcoded:35, api_client:4 |

### Breakdown by Consumer Type

#### API_CLIENT (5 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/virtualization/datasets` | 42.0 | 40 |
| `/api/v1/marketplace/listings/{self.listing.id}/download` | 26.0 | 26 |
| `/api/v1/contracts/contracts/{self.contract.id}/export` | 23.0 | 23 |
| `/api/v1/contracts/contracts/{self.contract_without_original.id}/download` | 20.0 | 20 |
| `/api/v1/contracts/contracts/{self.contract_without_original.id}/export` | 20.0 | 20 |

#### HARDCODED (75 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/tenants/tenants` | 49.0 | 49 |
| `/api/v1/tenants` | 48.0 | 48 |
| `/api/v1/assets/assets/{asset_id}/activate` | 47.0 | 47 |
| `/api/v1/transformation/pipelines/{pipeline_id}` | 47.0 | 44 |
| `/api/v1/social/communities` | 47.0 | 47 |
| `/api/v1/assets/assets/{asset.id}` | 46.0 | 46 |
| `/api/v1/developer/plugins` | 46.0 | 46 |
| `/api/v1/developer/sdk` | 46.0 | 46 |
| `/api/v1/datasets/datasets/{self.dataset.id}` | 45.0 | 45 |
| `/api/v1/audit/audit-events/` | 43.0 | 43 |

## MEDIUM Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/observability/incidents` | 19.0 | 19 | hardcoded:15, api_client:4 |
| `/api/v1/dq/runs/{id}` | 19.0 | 19 | hardcoded:19 |
| `/api/v1/contracts/{id}/lint` | 19.0 | 19 | hardcoded:19 |
| `/api/v1/resources/` | 19.0 | 19 | hardcoded:19 |
| `/api/v1/files/init-upload` | 18.0 | 18 | hardcoded:12, api_client:6 |
| `/api/v1/compliance/runs/{self.compliance_run.id}` | 18.0 | 18 | api_client:6, hardcoded:12 |
| `/api/v1/files/files/{self.file_obj.id}/complete` | 18.0 | 18 | hardcoded:12, api_client:6 |
| `/api/v1/marketplace/listings/{listing_id}/publish` | 18.0 | 18 | hardcoded:12, api_client:6 |
| `/api/v1/users/users/invite` | 18.0 | 18 | hardcoded:13, api_client:5 |
| `/api/v1/files/files/{file.id}` | 18.0 | 18 | hardcoded:12, api_client:6 |
| `/api/v1/mesh/domains` | 18.0 | 16 | hardcoded:14, sdk:2 |
| `/api/v1/contracts/{id}/export/` | 18.0 | 18 | hardcoded:18 |
| `/api/v1/auth` | 18.0 | 18 | hardcoded:18 |
| `/api/v1/compliance/runs/<uuid:id>` | 18.0 | 18 | hardcoded:18 |
| `/api/v1/semantic` | 18.0 | 18 | hardcoded:18 |
| `/api/v1/health` | 17.0 | 17 | hardcoded:16, api_client:1 |
| `/api/v1/virtualization/queries` | 17.0 | 16 | api_client:5, hardcoded:10, sdk:1 |
| `/api/v1/users/users/{id}` | 17.0 | 17 | hardcoded:17 |
| `/api/v1/hub.apps.webhooks.service.requests.post` | 16.5 | 11 | webhook:11 |
| `/api/v1/nonexistent` | 16.0 | 16 | api_client:6, hardcoded:10 |

### Breakdown by Consumer Type

#### API_CLIENT (11 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/api-docs/openapi.json` | 15.0 | 15 |
| `/api/v1/virtualization/datasets/{dataset.id}` | 15.0 | 15 |
| `/api/v1/virtualization/datasets/` | 14.0 | 14 |
| `/api/v1/contracts/contracts/{self.contract.id}/download` | 14.0 | 14 |
| `/api/v1/marketplace/listings/{listing.id}` | 13.0 | 13 |
| `/api/v1/users/users/{user_id}` | 13.0 | 13 |
| `/api/v1/localhost:8000/api/v1` | 13.0 | 13 |
| `/api/v1/tenants/tenants/{tenant.id}` | 12.0 | 12 |
| `/api/v1/resource/123` | 11.0 | 11 |
| `/api/v1/contracts/contracts/{contract.id}/validate` | 10.0 | 10 |

#### HARDCODED (343 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/observability/incidents` | 19.0 | 19 |
| `/api/v1/dq/runs/{id}` | 19.0 | 19 |
| `/api/v1/contracts/{id}/lint` | 19.0 | 19 |
| `/api/v1/resources/` | 19.0 | 19 |
| `/api/v1/files/init-upload` | 18.0 | 18 |
| `/api/v1/compliance/runs/{self.compliance_run.id}` | 18.0 | 18 |
| `/api/v1/files/files/{self.file_obj.id}/complete` | 18.0 | 18 |
| `/api/v1/marketplace/listings/{listing_id}/publish` | 18.0 | 18 |
| `/api/v1/users/users/invite` | 18.0 | 18 |
| `/api/v1/files/files/{file.id}` | 18.0 | 18 |

#### REVERSE_LOOKUP (4 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/contract/link/odps` | 12.0 | 24 |
| `/api/v1/domain` | 12.0 | 24 |
| `/api/v1/virtualization/topology` | 12.0 | 15 |
| `/api/v1/contract/create/product` | 10.0 | 20 |

#### WEBHOOK (1 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/hub.apps.webhooks.service.requests.post` | 16.5 | 11 |

## LOW Priority Endpoints

### Top 20 Endpoints by Impact Score

| Endpoint | Impact Score | Consumers | Consumer Types |
|----------|--------------|-----------|----------------|
| `/api/v1/domain/{id}` | 9.0 | 18 | reverse_lookup:18 |
| `/api/v1/assets/assets/invalid-uuid` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/files/files/{fake_id}` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/compliance/compliance-runs/{self.compliance_run_id}` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/marketplace/orders/{order_id}` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/marketplace/orders/` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/auth/api-keys/{api_key.id}` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/compliance/compliance-runs/{compliance_run_id}` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/access/access-requests` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/users/users/{user.id}/roles` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/users/users/` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/dq/dq-runs/{dq_run_id}` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/assets/assets/{self.asset.id}/health-score` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization` | 9.0 | 9 | hardcoded:6, api_client:3 |
| `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/semantic/semantic-resources/{semantic_resource.id}` | 9.0 | 9 | api_client:3, hardcoded:6 |
| `/api/v1/observability/pipelines` | 9.0 | 9 | hardcoded:7, api_client:2 |
| `/api/v1/mesh/topology` | 9.0 | 8 | hardcoded:7, sdk:1 |
| `/api/v1/users/invite` | 9.0 | 9 | hardcoded:9 |

### Breakdown by Consumer Type

#### API_CLIENT (143 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/scheduled-ingestions/{ingestion.id}` | 9.0 | 9 |
| `/api/v1/tenants/tenants/{fake_tenant_id}/config` | 9.0 | 9 |
| `/api/v1/contracts/contracts/{self.odcs_contract.id}/generate-odps` | 9.0 | 9 |
| `/api/v1/transformation/pipelines/{pipeline.id}` | 7.0 | 7 |
| `/api/v1/contracts/{self.contract.id}/export` | 7.0 | 7 |
| `/api/v1/contracts/contracts/{self.odps_contract.id}/product-details` | 7.0 | 7 |
| `/api/v1/virtualization/queries/{self.query_execution.id}` | 6.0 | 6 |
| `/api/v1/transformation/pipelines/{other_pipeline.id}` | 6.0 | 6 |
| `/api/v1/contracts/contracts/{odcs_contract.id}/link-odps` | 6.0 | 6 |
| `/api/v1/scheduled-ingestions/{ingestion.id}/trigger` | 5.0 | 5 |

#### HARDCODED (682 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/assets/assets/invalid-uuid` | 9.0 | 9 |
| `/api/v1/files/files/{fake_id}` | 9.0 | 9 |
| `/api/v1/compliance/compliance-runs/{self.compliance_run_id}` | 9.0 | 9 |
| `/api/v1/marketplace/orders/{order_id}` | 9.0 | 9 |
| `/api/v1/marketplace/orders/` | 9.0 | 9 |
| `/api/v1/auth/api-keys/{api_key.id}` | 9.0 | 9 |
| `/api/v1/compliance/compliance-runs/{compliance_run_id}` | 9.0 | 9 |
| `/api/v1/access/access-requests` | 9.0 | 9 |
| `/api/v1/users/users/{user.id}/roles` | 9.0 | 9 |
| `/api/v1/users/users/` | 9.0 | 9 |

#### REVERSE_LOOKUP (30 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/domain/{id}` | 9.0 | 18 |
| `/api/v1/contract/impact/analysis` | 6.0 | 12 |
| `/api/v1/topology` | 5.0 | 10 |
| `/api/v1/virtual/dataset` | 5.0 | 10 |
| `/api/v1/virtual/dataset/{id}` | 5.0 | 10 |
| `/api/v1/domain/transfer/ownership` | 4.0 | 8 |
| `/api/v1/domain/apply/policy` | 4.0 | 8 |
| `/api/v1/domain/remove/policy` | 4.0 | 8 |
| `/api/v1/domain/check/compliance` | 4.0 | 8 |
| `/api/v1/query/execution` | 4.0 | 8 |

#### SDK (34 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/virtualization/datasets/{dataset_id}` | 7.0 | 4 |
| `/api/v1/mesh/domains/{domain_id}` | 6.0 | 3 |
| `/api/v1/transformation/wrangling/{session_id}/undo` | 4.0 | 3 |
| `/api/v1/governance/retention-policies/{policy_id}` | 4.0 | 2 |
| `/api/v1/transformation/previews/{preview_id}` | 3.0 | 2 |
| `/api/v1/transformation/wrangling/{session_id}/redo` | 3.0 | 2 |
| `/api/v1/mesh/topology/{domain_id}` | 3.0 | 2 |
| `/api/v1/mesh/domains/{domain_id}/policies` | 3.0 | 2 |
| `/api/v1/mesh/domains/{domain_id}/policies/{policy_id}` | 3.0 | 2 |
| `/api/v1/mesh/domains/{domain_id}/compliance/check` | 3.0 | 2 |

#### WEBHOOK (39 endpoints)

| Endpoint | Impact Score | Consumers |
|----------|--------------|-----------|
| `/api/v1/{webhook.url}` | 3.0 | 2 |
| `/api/v1/example.com/webhook` | 3.0 | 2 |
| `/api/v1/Test trigger_odps_webhook raises error for non-ODPS event type` | 3.0 | 2 |
| `/api/v1/Test _deliver_webhook raises error for inactive webhook` | 3.0 | 2 |
| `/api/v1/Test _deliver_webhook raises error when webhook doesn` | 3.0 | 2 |
| `/api/v1/WebhookDeliveryService|trigger_webhook|deliver_webhook` | 1.5 | 1 |
| `/api/v1/webhook` | 1.5 | 1 |
| `/api/v1/Test that webhook service references were found` | 1.5 | 1 |
| `/api/v1/No webhook service references found` | 1.5 | 1 |
| `/api/v1/mesh_webhook_triggered_from_event` | 1.5 | 1 |

## Detailed Consumer References

### By Endpoint

#### `/api/v1/assets/assets`

- **Impact Score**: 631.0
- **Priority**: CRITICAL
- **Total Consumers**: 631
- **Consumer Types**: hardcoded:444, api_client:187

**Consumers:**

- **HARDCODED** (444 references):
  - `tests/regression/test_middleware.py:59`
  - `tests/regression/test_middleware.py:59`
  - `tests/e2e/test_api_usability_comprehensive.py:793`
  - `tests/e2e/test_api_usability_comprehensive.py:793`
  - `tests/e2e/test_auth_authorization_comprehensive.py:414`
  - ... and 439 more
- **API_CLIENT** (187 references):
  - `tests/e2e/test_auth_authorization_comprehensive.py:407`
  - `tests/regression/test_middleware.py:205`
  - `tests/e2e/test_auth_authorization_comprehensive.py:942`
  - `tests/integration/test_asset_apis_comprehensive.py:1803`
  - `tests/regression/test_tenant_isolation.py:324`
  - ... and 182 more

#### `/api/v1/contracts/contracts`

- **Impact Score**: 508.0
- **Priority**: CRITICAL
- **Total Consumers**: 508
- **Consumer Types**: api_client:159, hardcoded:349

**Consumers:**

- **API_CLIENT** (159 references):
  - `tests/integration/test_contract_apis_comprehensive.py:548`
  - `tests/integration/test_contract_apis_comprehensive.py:516`
  - `tests/integration/test_api_edge_cases.py:576`
  - `tests/e2e/test_contract_first_flow.py:121`
  - `tests/e2e/test_persona_data_engineer_comprehensive.py:880`
  - ... and 154 more
- **HARDCODED** (349 references):
  - `tests/e2e/test_persona_data_consumer.py:143`
  - `tests/e2e/test_persona_data_consumer.py:143`
  - `tests/integration/test_contract_apis_comprehensive.py:346`
  - `tests/integration/test_contract_apis_comprehensive.py:346`
  - `tests/integration/test_contract_apis_comprehensive.py:532`
  - ... and 344 more

#### `/api/v1/assets`

- **Impact Score**: 379.0
- **Priority**: CRITICAL
- **Total Consumers**: 379
- **Consumer Types**: hardcoded:344, api_client:35

**Consumers:**

- **HARDCODED** (344 references):
  - `docs/api-audit/endpoint-inventory-current.json:1957`
  - `docs/api-audit/endpoint-inventory-current.json:1957`
  - `docs/api-audit/GAP_ANALYSIS_SUMMARY.md:112`
  - `docs/api-audit/GAP_ANALYSIS_SUMMARY.md:112`
  - `docs/api-audit/api-testing-plan.md:815`
  - ... and 339 more
- **API_CLIENT** (35 references):
  - `tests/uat/test_user_acceptance_django6.py:118`
  - `tests/integration/test_services_django6.py:97`
  - `hub/apps/rate_limiting/tests/test_integration.py:55`
  - `tests/performance/locust_job_queue_throughput.py:208`
  - `tests/uat/test_no_user_facing_changes_django6.py:66`
  - ... and 30 more

#### `/api/v1/auth/login`

- **Impact Score**: 312.0
- **Priority**: CRITICAL
- **Total Consumers**: 312
- **Consumer Types**: hardcoded:237, api_client:75

**Consumers:**

- **HARDCODED** (237 references):
  - `docs/api-audit/generate-api-timeline.py:285`
  - `tests/regression/test_auth_authorization.py:81`
  - `tests/regression/test_auth_authorization.py:81`
  - `tests/integration/test_auth_apis_comprehensive.py:882`
  - `tests/integration/test_auth_apis_comprehensive.py:882`
  - ... and 232 more
- **API_CLIENT** (75 references):
  - `tests/e2e/test_auth_authorization_comprehensive.py:922`
  - `tests/e2e/test_auth_authorization_comprehensive.py:675`
  - `tests/integration/test_auth_apis_comprehensive.py:1242`
  - `tests/integration/test_auth_apis_comprehensive.py:1030`
  - `tests/integration/test_auth_apis_comprehensive.py:998`
  - ... and 70 more

#### `/api/v1/marketplace/listings`

- **Impact Score**: 297.0
- **Priority**: CRITICAL
- **Total Consumers**: 297
- **Consumer Types**: hardcoded:238, api_client:59

**Consumers:**

- **HARDCODED** (238 references):
  - `docs/deprecated-doc/feature-docs/USER_JOURNEYS.md:154`
  - `docs/deprecated-doc/feature-docs/USER_JOURNEYS.md:154`
  - `docs/deprecated-doc/feature-docs/USER_JOURNEYS.md:154`
  - `docs/deprecated-doc/feature-docs/USER_JOURNEYS.md:154`
  - `tests/e2e/test_marketplace_use_cases.py:192`
  - ... and 233 more
- **API_CLIENT** (59 references):
  - `tests/e2e/test_entitlements.py:67`
  - `hub/apps/marketplace/tests/test_performance.py:131`
  - `tests/integration/test_marketplace_apis_comprehensive.py:212`
  - `tests/integration/test_marketplace_apis_comprehensive.py:578`
  - `tests/integration/test_marketplace_apis_comprehensive.py:105`
  - ... and 54 more

#### `/api/v1/tenants/tenants/{self.tenant.id}/config`

- **Impact Score**: 278.0
- **Priority**: CRITICAL
- **Total Consumers**: 278
- **Consumer Types**: hardcoded:180, api_client:98

**Consumers:**

- **HARDCODED** (180 references):
  - `tests/e2e/test_persona_auditor.py:60`
  - `tests/e2e/test_persona_auditor.py:60`
  - `tests/e2e/test_persona_ta_comprehensive.py:550`
  - `tests/e2e/test_persona_ta_comprehensive.py:550`
  - `tests/e2e/test_persona_tenant_admin.py:70`
  - ... and 175 more
- **API_CLIENT** (98 references):
  - `tests/e2e/test_tenant_config_e2e.py:273`
  - `tests/e2e/test_persona_tenant_admin.py:233`
  - `tests/e2e/test_persona_ta_comprehensive.py:501`
  - `tests/e2e/test_persona_tenant_admin.py:280`
  - `tests/e2e/test_persona_data_consumer.py:52`
  - ... and 93 more

#### `/api/v1/contracts`

- **Impact Score**: 272.0
- **Priority**: CRITICAL
- **Total Consumers**: 270
- **Consumer Types**: api_client:51, hardcoded:217, sdk:2

**Consumers:**

- **API_CLIENT** (51 references):
  - `hub/apps/contracts/tests/test_views_filtering_sorting.py:285`
  - `hub/apps/contracts/tests/test_performance.py:520`
  - `hub/apps/contracts/tests/test_api_filtering_phase15.py:188`
  - `tests/performance/test_performance_baseline.py:220`
  - `hub/apps/contracts/tests/test_api_filtering_phase15.py:230`
  - ... and 46 more
- **HARDCODED** (217 references):
  - `docs/TESTING_GUIDE.md:135`
  - `docs/TESTING_GUIDE.md:135`
  - `docs/API_REFERENCE.md:54`
  - `docs/api-audit/codebase-endpoints-inventory.md:93`
  - `docs/api-audit/codebase-endpoints-inventory.md:93`
  - ... and 212 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/contracts.py:448`
  - `sdk/python/datahub_interoperability/contracts.py:486`

#### `/api/v1/search/search`

- **Impact Score**: 207.0
- **Priority**: CRITICAL
- **Total Consumers**: 208
- **Consumer Types**: api_client:49, hardcoded:154, sdk:1, reverse_lookup:4

**Consumers:**

- **API_CLIENT** (49 references):
  - `tests/integration/test_search_apis_comprehensive.py:394`
  - `tests/integration/test_search_apis_comprehensive.py:755`
  - `tests/integration/test_search_apis_comprehensive.py:286`
  - `tests/integration/test_search_apis_comprehensive.py:740`
  - `tests/integration/test_search_apis_comprehensive.py:450`
  - ... and 44 more
- **HARDCODED** (154 references):
  - `tests/integration/test_search_apis_comprehensive.py:5`
  - `tests/integration/test_search_apis_comprehensive.py:813`
  - `tests/integration/test_search_apis_comprehensive.py:813`
  - `tests/integration/test_search_apis_comprehensive.py:394`
  - `tests/integration/test_search_apis_comprehensive.py:394`
  - ... and 149 more
- **SDK** (1 references):
  - `sdk/python/datahub_interoperability/search.py:85`
- **REVERSE_LOOKUP** (4 references):
  - `apps/search/tests/test_views.py:87`
  - `apps/search/tests/test_views.py:87`
  - `apps/search/tests/test_views.py:97`
  - `apps/search/tests/test_views.py:97`

#### `/api/v1/auth/register`

- **Impact Score**: 201.0
- **Priority**: CRITICAL
- **Total Consumers**: 201
- **Consumer Types**: hardcoded:159, api_client:42

**Consumers:**

- **HARDCODED** (159 references):
  - `docs/api-audit/api-testing-plan.md:354`
  - `docs/api-audit/GAP_DETAILS_SUMMARY.md:210`
  - `docs/api-audit/GAP_DETAILS_SUMMARY.md:210`
  - `docs/api-audit/integration-test-requirements.md:32`
  - `docs/api-audit/endpoint-inventory-current.json:67`
  - ... and 154 more
- **API_CLIENT** (42 references):
  - `hub/apps/auth/tests/test_register_me.py:240`
  - `tests/integration/test_auth_apis_comprehensive.py:307`
  - `tests/integration/test_auth_apis_comprehensive.py:120`
  - `tests/integration/test_auth_apis_comprehensive.py:344`
  - `tests/integration/test_auth_apis_comprehensive.py:507`
  - ... and 37 more

#### `/api/v1/dq/runs`

- **Impact Score**: 199.0
- **Priority**: CRITICAL
- **Total Consumers**: 199
- **Consumer Types**: hardcoded:158, api_client:41

**Consumers:**

- **HARDCODED** (158 references):
  - `tests/integration/test_dq_apis_comprehensive.py:1177`
  - `tests/integration/test_dq_apis_comprehensive.py:1177`
  - `docs/api-audit/api-performance-requirements.md:133`
  - `docs/api-audit/api-performance-requirements.md:133`
  - `tests/integration/test_dq_apis_comprehensive.py:797`
  - ... and 153 more
- **API_CLIENT** (41 references):
  - `tests/integration/test_dq_apis_comprehensive.py:164`
  - `tests/integration/test_dq_apis_comprehensive.py:834`
  - `hub/apps/tenants/tests/test_tenant_config_dq_integration.py:171`
  - `tests/e2e/test_persona_auditor.py:154`
  - `tests/e2e/test_persona_auditor.py:139`
  - ... and 36 more

#### `/api/v1/auth/me`

- **Impact Score**: 178.0
- **Priority**: CRITICAL
- **Total Consumers**: 178
- **Consumer Types**: hardcoded:149, api_client:29

**Consumers:**

- **HARDCODED** (149 references):
  - `docs/api-audit/api-dependencies.md:245`
  - `docs/api-audit/api-requirements-matrix.md:78`
  - `docs/api-audit/api-requirements-matrix.md:78`
  - `docs/api-audit/generate-api-timeline.py:286`
  - `docs/api-audit/gap-details.md:130`
  - ... and 144 more
- **API_CLIENT** (29 references):
  - `hub/apps/auth/tests/test_register_me.py:647`
  - `tests/integration/test_auth_apis_comprehensive.py:835`
  - `hub/apps/auth/tests/test_register_me.py:439`
  - `tests/integration/test_auth_apis_comprehensive.py:715`
  - `hub/apps/auth/tests/test_register_me.py:371`
  - ... and 24 more

#### `/api/v1/assets/{id}/activate`

- **Impact Score**: 168.0
- **Priority**: CRITICAL
- **Total Consumers**: 168
- **Consumer Types**: hardcoded:168

**Consumers:**

- **HARDCODED** (168 references):
  - `docs/api-audit/api-requirements-matrix.md:143`
  - `docs/api-audit/api-requirements-matrix.md:143`
  - `docs/api-audit/current-api-inventory-categorized.md:323`
  - `docs/api-audit/current-api-inventory-categorized.md:323`
  - `tests/e2e/COVERAGE_ANALYSIS.md:39`
  - ... and 163 more

#### `/api/v1/compliance/runs`

- **Impact Score**: 159.0
- **Priority**: CRITICAL
- **Total Consumers**: 159
- **Consumer Types**: hardcoded:113, api_client:46

**Consumers:**

- **HARDCODED** (113 references):
  - `tests/integration/test_compliance_apis_comprehensive.py:1318`
  - `tests/integration/test_compliance_apis_comprehensive.py:1318`
  - `docs/api-audit/endpoint-inventory-current.md:258`
  - `tests/integration/test_compliance_apis_comprehensive.py:329`
  - `tests/integration/test_compliance_apis_comprehensive.py:329`
  - ... and 108 more
- **API_CLIENT** (46 references):
  - `tests/integration/test_compliance_apis_comprehensive.py:109`
  - `hub/apps/tenants/tests/test_tenant_config_compliance_integration.py:67`
  - `tests/integration/test_compliance_apis_comprehensive.py:1318`
  - `hub/apps/tenants/tests/test_tenant_config_compliance_integration.py:203`
  - `tests/integration/test_compliance_apis_comprehensive.py:1567`
  - ... and 41 more

#### `/api/v1/assets/assets/`

- **Impact Score**: 150.0
- **Priority**: CRITICAL
- **Total Consumers**: 150
- **Consumer Types**: api_client:56, hardcoded:94

**Consumers:**

- **API_CLIENT** (56 references):
  - `tests/integration/test_asset_apis_comprehensive.py:1589`
  - `tests/integration/test_asset_apis_comprehensive.py:158`
  - `hub/apps/assets/tests/test_asset_crud.py:318`
  - `hub/apps/assets/tests/test_asset_crud.py:328`
  - `tests/e2e/test_api_usability_comprehensive.py:341`
  - ... and 51 more
- **HARDCODED** (94 references):
  - `tests/e2e/test_asset_operations.py:92`
  - `tests/e2e/test_asset_operations.py:92`
  - `tests/integration/test_asset_apis_comprehensive.py:315`
  - `tests/integration/test_asset_apis_comprehensive.py:315`
  - `tests/e2e/test_api_usability_comprehensive.py:324`
  - ... and 89 more

#### `/api/v1/datasets`

- **Impact Score**: 134.0
- **Priority**: CRITICAL
- **Total Consumers**: 134
- **Consumer Types**: hardcoded:129, api_client:5

**Consumers:**

- **HARDCODED** (129 references):
  - `docs/api-audit/analyze-api-dependencies.py:486`
  - `docs/api-audit/current-api-inventory-categorized.md:825`
  - `docs/api-audit/current-api-inventory-categorized.md:825`
  - `docs/api-audit/analyze-api-dependencies.py:382`
  - `docs/api-audit/api-development-backlog.md:1460`
  - ... and 124 more
- **API_CLIENT** (5 references):
  - `hub/apps/datasets/tests/test_version_integration.py:72`
  - `tests/integration/test_dataset_apis_comprehensive.py:348`
  - `tests/integration/test_dataset_apis_comprehensive.py:340`
  - `tests/integration/test_dataset_apis_comprehensive.py:660`
  - `tests/integration/test_dataset_apis_comprehensive.py:370`

#### `/api/v1/assets/assets/{asset_id}`

- **Impact Score**: 129.0
- **Priority**: CRITICAL
- **Total Consumers**: 129
- **Consumer Types**: api_client:43, hardcoded:86

**Consumers:**

- **API_CLIENT** (43 references):
  - `tests/e2e/test_persona_cpo_comprehensive.py:154`
  - `tests/regression/test_workflows.py:353`
  - `tests/e2e/test_auth_authorization_comprehensive.py:972`
  - `tests/e2e/test_asset_operations.py:120`
  - `tests/e2e/test_persona_dpo_comprehensive.py:800`
  - ... and 38 more
- **HARDCODED** (86 references):
  - `tests/regression/test_workflows.py:297`
  - `tests/regression/test_workflows.py:297`
  - `tests/e2e/test_security_comprehensive.py:284`
  - `tests/e2e/test_security_comprehensive.py:284`
  - `tests/e2e/test_api_usability_comprehensive.py:385`
  - ... and 81 more

#### `/api/v1/auth/api-keys`

- **Impact Score**: 129.0
- **Priority**: CRITICAL
- **Total Consumers**: 129
- **Consumer Types**: hardcoded:112, api_client:17

**Consumers:**

- **HARDCODED** (112 references):
  - `docs/api-audit/api-requirements-matrix.md:80`
  - `docs/api-audit/api-requirements-matrix.md:80`
  - `tests/e2e/test_authentication.py:394`
  - `tests/e2e/test_authentication.py:394`
  - `docs/api-audit/api-requirements-matrix-consolidated.md:121`
  - ... and 107 more
- **API_CLIENT** (17 references):
  - `tests/e2e/test_persona_dev_comprehensive.py:67`
  - `tests/e2e/test_auth_authorization_comprehensive.py:693`
  - `hub/apps/auth/tests/test_api_key_auth.py:155`
  - `tests/e2e/test_auth_authorization_comprehensive.py:168`
  - `tests/regression/test_auth_authorization.py:136`
  - ... and 12 more

#### `/api/v1/marketplace/orders`

- **Impact Score**: 127.0
- **Priority**: CRITICAL
- **Total Consumers**: 127
- **Consumer Types**: hardcoded:90, api_client:37

**Consumers:**

- **HARDCODED** (90 references):
  - `tests/e2e/test_marketplace_orders.py:402`
  - `tests/e2e/test_marketplace_orders.py:402`
  - `tests/e2e/test_persona_dc_comprehensive.py:259`
  - `tests/e2e/test_persona_dc_comprehensive.py:259`
  - `tests/e2e/test_marketplace_use_cases.py:434`
  - ... and 85 more
- **API_CLIENT** (37 references):
  - `tests/e2e/test_marketplace_orders.py:186`
  - `hub/apps/marketplace/tests/test_auto_approval.py:104`
  - `tests/e2e/test_marketplace_orders.py:401`
  - `hub/apps/marketplace/tests/test_auto_approval.py:130`
  - `tests/e2e/test_marketplace_orders.py:370`
  - ... and 32 more

#### `/api/v1/auth/refresh`

- **Impact Score**: 120.0
- **Priority**: CRITICAL
- **Total Consumers**: 120
- **Consumer Types**: hardcoded:94, api_client:26

**Consumers:**

- **HARDCODED** (94 references):
  - `tests/e2e/test_auth_authorization_comprehensive.py:440`
  - `tests/e2e/test_auth_authorization_comprehensive.py:440`
  - `tests/regression/test_auth_authorization.py:89`
  - `tests/regression/test_auth_authorization.py:89`
  - `docs/api-audit/integration-test-requirements.md:34`
  - ... and 89 more
- **API_CLIENT** (26 references):
  - `tests/integration/test_auth_apis_comprehensive.py:1488`
  - `tests/regression/test_api_endpoints.py:86`
  - `tests/e2e/test_auth_authorization_comprehensive.py:439`
  - `hub/apps/auth/tests/test_authentication_flows.py:112`
  - `tests/e2e/test_authentication.py:174`
  - ... and 21 more

#### `/api/v1/assets/assets/{self.asset.id}`

- **Impact Score**: 119.0
- **Priority**: CRITICAL
- **Total Consumers**: 119
- **Consumer Types**: hardcoded:80, api_client:39

**Consumers:**

- **HARDCODED** (80 references):
  - `tests/integration/test_asset_apis_comprehensive.py:1899`
  - `tests/integration/test_asset_apis_comprehensive.py:1899`
  - `tests/integration/test_asset_apis_comprehensive.py:874`
  - `tests/integration/test_asset_apis_comprehensive.py:874`
  - `tests/integration/test_asset_apis_comprehensive.py:2038`
  - ... and 75 more
- **API_CLIENT** (39 references):
  - `tests/regression/test_api_endpoints.py:287`
  - `tests/integration/test_asset_apis_comprehensive.py:2061`
  - `tests/integration/test_asset_apis_comprehensive.py:657`
  - `tests/integration/test_asset_apis_comprehensive.py:673`
  - `tests/integration/test_asset_apis_comprehensive.py:778`
  - ... and 34 more

#### `/api/v1/datasets/datasets`

- **Impact Score**: 113.0
- **Priority**: CRITICAL
- **Total Consumers**: 113
- **Consumer Types**: hardcoded:76, api_client:37

**Consumers:**

- **HARDCODED** (76 references):
  - `tests/integration/test_dataset_apis_comprehensive.py:516`
  - `tests/integration/test_dataset_apis_comprehensive.py:516`
  - `tests/e2e/test_dataset_operations.py:91`
  - `tests/e2e/test_dataset_operations.py:91`
  - `tests/integration/test_dataset_apis_comprehensive.py:446`
  - ... and 71 more
- **API_CLIENT** (37 references):
  - `tests/integration/test_dataset_apis_comprehensive.py:533`
  - `tests/e2e/test_data_first_flow.py:181`
  - `tests/e2e/test_data_first_comprehensive.py:304`
  - `tests/e2e/test_persona_data_engineer_comprehensive.py:300`
  - `tests/integration/test_dataset_apis_comprehensive.py:561`
  - ... and 32 more

#### `/api/v1/dq/dq-runs`

- **Impact Score**: 112.0
- **Priority**: CRITICAL
- **Total Consumers**: 112
- **Consumer Types**: hardcoded:87, api_client:25

**Consumers:**

- **HARDCODED** (87 references):
  - `docs/api-audit/codebase-endpoints-inventory.md:124`
  - `docs/api-audit/codebase-endpoints-inventory.md:124`
  - `tests/e2e/test_persona_dpo_comprehensive.py:632`
  - `tests/e2e/test_persona_dpo_comprehensive.py:632`
  - `tests/e2e/test_complete_user_journeys.py:172`
  - ... and 82 more
- **API_CLIENT** (25 references):
  - `tests/integration/test_cross_service_integration_comprehensive.py:67`
  - `tests/integration/test_dpo_api_endpoints.py:387`
  - `tests/regression/test_integrations.py:154`
  - `tests/regression/test_integrations.py:74`
  - `tests/e2e/test_complete_user_journeys.py:171`
  - ... and 20 more

#### `/api/v1/files/files/init`

- **Impact Score**: 111.0
- **Priority**: CRITICAL
- **Total Consumers**: 111
- **Consumer Types**: hardcoded:66, api_client:45

**Consumers:**

- **HARDCODED** (66 references):
  - `tests/integration/test_file_apis_comprehensive.py:311`
  - `tests/integration/test_file_apis_comprehensive.py:311`
  - `tests/e2e/test_data_first_flow.py:129`
  - `tests/e2e/test_data_first_flow.py:129`
  - `tests/regression/test_file_storage.py:53`
  - ... and 61 more
- **API_CLIENT** (45 references):
  - `tests/e2e/test_contract_first_flow.py:159`
  - `hub/apps/files/tests/test_file_upload_download.py:143`
  - `hub/apps/tenants/tests/test_tenant_config_file_upload_integration.py:68`
  - `tests/integration/test_file_apis_comprehensive.py:71`
  - `tests/regression/test_file_storage.py:52`
  - ... and 40 more

#### `/api/v1/scheduled-ingestions`

- **Impact Score**: 107.0
- **Priority**: CRITICAL
- **Total Consumers**: 105
- **Consumer Types**: api_client:23, hardcoded:80, sdk:2

**Consumers:**

- **API_CLIENT** (23 references):
  - `tests/e2e/test_scheduled_ingestion_use_cases.py:77`
  - `tests/e2e/test_persona_data_engineer_comprehensive.py:564`
  - `tests/integration/test_data_engineer_api_endpoints.py:282`
  - `tests/e2e/test_persona_data_engineer_comprehensive.py:618`
  - `tests/e2e/test_scheduled_ingestion.py:264`
  - ... and 18 more
- **HARDCODED** (80 references):
  - `tests/e2e/test_scheduled_ingestion_use_cases.py:210`
  - `tests/e2e/test_scheduled_ingestion_use_cases.py:210`
  - `docs/api-audit/endpoint-inventory-current.json:23731`
  - `docs/api-audit/endpoint-inventory-current.json:23731`
  - `docs/deprecated-doc/feature-docs/API_DOCUMENTATION.md:806`
  - ... and 75 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/scheduled_ingestion.py:93`
  - `sdk/python/datahub_interoperability/scheduled_ingestion.py:63`

#### `/api/v1/tenants/tenants/{self.tenant1.id}/config`

- **Impact Score**: 103.0
- **Priority**: CRITICAL
- **Total Consumers**: 103
- **Consumer Types**: api_client:59, hardcoded:44

**Consumers:**

- **API_CLIENT** (59 references):
  - `hub/apps/tenants/tests/test_tenant_config_views.py:520`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:718`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:539`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:390`
  - `hub/apps/tenants/tests/test_tenant_config_views.py:226`
  - ... and 54 more
- **HARDCODED** (44 references):
  - `tests/integration/test_tenant_config_api.py:307`
  - `tests/integration/test_tenant_config_api.py:307`
  - `tests/integration/test_tenant_config_api.py:84`
  - `tests/integration/test_tenant_config_api.py:84`
  - `tests/integration/test_tenant_config_api.py:323`
  - ... and 39 more

#### `/api/v1/compliance/compliance-runs`

- **Impact Score**: 102.0
- **Priority**: CRITICAL
- **Total Consumers**: 102
- **Consumer Types**: api_client:28, hardcoded:74

**Consumers:**

- **API_CLIENT** (28 references):
  - `tests/e2e/test_data_first_flow.py:197`
  - `tests/uat/test_user_acceptance_django6.py:217`
  - `tests/e2e/conftest.py:972`
  - `hub/apps/contracts/tests/test_integration_onboarding.py:188`
  - `tests/e2e/test_audit_compliance_journeys.py:165`
  - ... and 23 more
- **HARDCODED** (74 references):
  - `tests/uat/test_user_acceptance_django6.py:218`
  - `tests/uat/test_user_acceptance_django6.py:218`
  - `cli/datahub_cli/commands/compliance.py:54`
  - `docs/api-audit/api-performance-requirements.md:100`
  - `docs/api-audit/api-performance-requirements.md:100`
  - ... and 69 more

#### `/api/v1/contracts/contracts/{self.contract.id}`

- **Impact Score**: 96.0
- **Priority**: CRITICAL
- **Total Consumers**: 96
- **Consumer Types**: api_client:32, hardcoded:64

**Consumers:**

- **API_CLIENT** (32 references):
  - `tests/integration/test_contract_apis_comprehensive.py:1676`
  - `tests/integration/test_contract_apis_comprehensive.py:1932`
  - `tests/integration/test_contract_apis_comprehensive.py:1439`
  - `tests/integration/test_contract_apis_comprehensive.py:1339`
  - `tests/integration/test_contract_apis_comprehensive.py:1348`
  - ... and 27 more
- **HARDCODED** (64 references):
  - `tests/integration/test_contract_apis_comprehensive.py:1921`
  - `tests/integration/test_contract_apis_comprehensive.py:1921`
  - `tests/integration/test_contract_apis_comprehensive.py:1780`
  - `tests/integration/test_contract_apis_comprehensive.py:1780`
  - `tests/regression/test_api_endpoints.py:371`
  - ... and 59 more

#### `/api/v1/ai/schema-matching`

- **Impact Score**: 91.0
- **Priority**: CRITICAL
- **Total Consumers**: 91
- **Consumer Types**: hardcoded:91

**Consumers:**

- **HARDCODED** (91 references):
  - `docs/api-audit/analyze-api-dependencies.py:774`
  - `docs/api-audit/integration-requirements-documentation.md:427`
  - `docs/api-audit/error-responses-summary.md:91`
  - `docs/api-audit/error-responses-summary.md:91`
  - `docs/api-audit/error-responses-documentation.md:485`
  - ... and 86 more

#### `/api/v1/jobs`

- **Impact Score**: 88.0
- **Priority**: CRITICAL
- **Total Consumers**: 88
- **Consumer Types**: hardcoded:83, api_client:5

**Consumers:**

- **HARDCODED** (83 references):
  - `docs/api-audit/current-api-inventory-categorized.md:848`
  - `docs/api-audit/current-api-inventory-categorized.md:848`
  - `docs/api-audit/codebase-endpoints-inventory.md:174`
  - `docs/api-audit/codebase-endpoints-inventory.md:174`
  - `tests/performance/locust_database_query_performance.py:144`
  - ... and 78 more
- **API_CLIENT** (5 references):
  - `tests/integration/test_api_endpoints_comprehensive.py:114`
  - `tests/integration/test_api_endpoints_comprehensive.py:126`
  - `tests/performance/locust_database_query_performance.py:140`
  - `tests/performance/locust_job_queue_throughput.py:128`
  - `tests/performance/locust_database_query_performance.py:109`

#### `/api/v1/contracts/{id}/validate`

- **Impact Score**: 86.0
- **Priority**: CRITICAL
- **Total Consumers**: 86
- **Consumer Types**: hardcoded:86

**Consumers:**

- **HARDCODED** (86 references):
  - `docs/api-audit/api-effort-estimates-summary.md:590`
  - `docs/api-audit/api-effort-estimates-summary.md:590`
  - `docs/api-audit/codebase-endpoints-inventory.md:103`
  - `docs/api-audit/codebase-endpoints-inventory.md:103`
  - `docs/api-audit/api-requirements-matrix.md:221`
  - ... and 81 more

#### `/api/v1/transformation/pipelines`

- **Impact Score**: 82.0
- **Priority**: CRITICAL
- **Total Consumers**: 80
- **Consumer Types**: api_client:37, hardcoded:41, sdk:2

**Consumers:**

- **API_CLIENT** (37 references):
  - `hub/apps/transformation/tests/test_views.py:510`
  - `hub/apps/transformation/tests/test_views.py:139`
  - `hub/apps/transformation/tests/test_views.py:426`
  - `hub/apps/transformation/tests/test_views.py:483`
  - `hub/apps/transformation/tests/test_views_integration.py:216`
  - ... and 32 more
- **HARDCODED** (41 references):
  - `docs/api-audit/api-performance-requirements.md:324`
  - `docs/api-audit/api-performance-requirements.md:324`
  - `docs/api-audit/journey-api-extraction-script.py:262`
  - `docs/api-audit/journey-api-extraction-script.py:262`
  - `docs/api-audit/api-requirements-from-journeys.md:1101`
  - ... and 36 more
- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/transformation.py:182`
  - `sdk/python/datahub_interoperability/transformation.py:258`

#### `/api/v1/assets/{id}`

- **Impact Score**: 81.0
- **Priority**: CRITICAL
- **Total Consumers**: 81
- **Consumer Types**: hardcoded:81

**Consumers:**

- **HARDCODED** (81 references):
  - `tests/integration/test_asset_apis_comprehensive.py:10`
  - `docs/api-audit/api-requirements-matrix-consolidated.md:535`
  - `docs/api-audit/api-requirements-matrix-consolidated.md:535`
  - `docs/api-audit/codebase-endpoints-inventory.md:46`
  - `docs/api-audit/codebase-endpoints-inventory.md:46`
  - ... and 76 more

#### `/api/v1/assets/assets/{asset.id}/activate`

- **Impact Score**: 80.0
- **Priority**: CRITICAL
- **Total Consumers**: 80
- **Consumer Types**: api_client:34, hardcoded:46

**Consumers:**

- **API_CLIENT** (34 references):
  - `tests/integration/test_asset_apis_comprehensive.py:1072`
  - `tests/integration/test_asset_apis_comprehensive.py:2096`
  - `tests/integration/test_asset_apis_comprehensive.py:978`
  - `hub/apps/assets/tests/test_asset_activation.py:306`
  - `tests/integration/test_asset_apis_comprehensive.py:1214`
  - ... and 29 more
- **HARDCODED** (46 references):
  - `tests/integration/test_asset_apis_comprehensive.py:1031`
  - `tests/integration/test_asset_apis_comprehensive.py:1031`
  - `tests/integration/test_asset_apis_comprehensive.py:1197`
  - `tests/integration/test_asset_apis_comprehensive.py:1197`
  - `tests/integration/test_asset_apis_comprehensive.py:1055`
  - ... and 41 more

#### `/api/v1/audit/audit-events`

- **Impact Score**: 80.0
- **Priority**: CRITICAL
- **Total Consumers**: 80
- **Consumer Types**: api_client:24, hardcoded:56

**Consumers:**

- **API_CLIENT** (24 references):
  - `tests/e2e/test_audit_compliance_journeys.py:282`
  - `hub/apps/audit/tests/test_audit_event_querying.py:108`
  - `tests/e2e/test_persona_cpo_comprehensive.py:883`
  - `tests/e2e/test_audit_compliance_journeys.py:94`
  - `tests/e2e/test_persona_cpo_comprehensive.py:994`
  - ... and 19 more
- **HARDCODED** (56 references):
  - `docs/api-audit/codebase-endpoints-inventory.md:54`
  - `docs/api-audit/codebase-endpoints-inventory.md:54`
  - `tests/e2e/test_audit_logging.py:194`
  - `tests/e2e/test_audit_logging.py:194`
  - `tests/e2e/test_audit_compliance_journeys.py:95`
  - ... and 51 more

#### `/api/v1/contracts/{id}`

- **Impact Score**: 80.0
- **Priority**: CRITICAL
- **Total Consumers**: 80
- **Consumer Types**: hardcoded:80

**Consumers:**

- **HARDCODED** (80 references):
  - `docs/api-audit/current-api-inventory-categorized.md:931`
  - `docs/api-audit/current-api-inventory-categorized.md:931`
  - `docs/api-audit/api-performance-requirements.md:122`
  - `docs/api-audit/api-performance-requirements.md:122`
  - `docs/api-audit/current-api-inventory-categorized.md:820`
  - ... and 75 more

#### `/api/v1/social/ratings`

- **Impact Score**: 77.0
- **Priority**: CRITICAL
- **Total Consumers**: 77
- **Consumer Types**: hardcoded:77

**Consumers:**

- **HARDCODED** (77 references):
  - `docs/api-audit/api-dependencies.md:263`
  - `docs/api-audit/integration-requirements-documentation.md:456`
  - `docs/api-audit/analyze-api-dependencies.py:439`
  - `docs/api-audit/api-requirements-from-journeys.md:1113`
  - `docs/api-audit/api-requirements-from-journeys.md:1113`
  - ... and 72 more

#### `/api/v1/social/reviews`

- **Impact Score**: 75.0
- **Priority**: CRITICAL
- **Total Consumers**: 75
- **Consumer Types**: hardcoded:75

**Consumers:**

- **HARDCODED** (75 references):
  - `docs/api-contracts/missing/README.md:226`
  - `docs/api-contracts/missing/README.md:226`
  - `docs/api-audit/api-dependencies.md:351`
  - `docs/api-audit/gap-details.md:884`
  - `docs/api-audit/gap-details.md:884`
  - ... and 70 more

#### `/api/v1/ai/natural-language-search`

- **Impact Score**: 73.0
- **Priority**: CRITICAL
- **Total Consumers**: 73
- **Consumer Types**: hardcoded:73

**Consumers:**

- **HARDCODED** (73 references):
  - `docs/api-audit/error-responses-documentation.md:484`
  - `docs/api-audit/error-responses-documentation.md:484`
  - `docs/api-audit/integration-requirements-documentation.md:143`
  - `docs/api-audit/integration-requirements-documentation.md:258`
  - `docs/api-audit/integration-requirements-documentation.md:706`
  - ... and 68 more

#### `/api/v1/assets/assets/{fake_id}`

- **Impact Score**: 70.0
- **Priority**: CRITICAL
- **Total Consumers**: 70
- **Consumer Types**: hardcoded:48, api_client:22

**Consumers:**

- **HARDCODED** (48 references):
  - `tests/e2e/test_error_handling_comprehensive.py:100`
  - `tests/e2e/test_error_handling_comprehensive.py:100`
  - `tests/integration/test_asset_apis_comprehensive.py:2333`
  - `tests/integration/test_asset_apis_comprehensive.py:2333`
  - `tests/e2e/test_error_handling_comprehensive.py:46`
  - ... and 43 more
- **API_CLIENT** (22 references):
  - `tests/e2e/test_error_handling_comprehensive.py:87`
  - `tests/e2e/test_error_handling_comprehensive.py:550`
  - `tests/e2e/test_error_handling_comprehensive.py:162`
  - `tests/e2e/test_error_handling_comprehensive.py:623`
  - `tests/e2e/test_error_handling_comprehensive.py:569`
  - ... and 17 more

#### `/api/v1/contracts/contracts/{contract.id}`

- **Impact Score**: 69.0
- **Priority**: CRITICAL
- **Total Consumers**: 69
- **Consumer Types**: hardcoded:44, api_client:25

**Consumers:**

- **HARDCODED** (44 references):
  - `tests/integration/test_api_edge_cases.py:540`
  - `tests/integration/test_api_edge_cases.py:540`
  - `tests/integration/test_api_edge_cases.py:131`
  - `tests/integration/test_api_edge_cases.py:131`
  - `tests/integration/test_api_edge_cases.py:618`
  - ... and 39 more
- **API_CLIENT** (25 references):
  - `tests/integration/test_api_edge_cases.py:587`
  - `hub/apps/contracts/tests/test_contract_crud.py:116`
  - `tests/integration/test_api_edge_cases.py:439`
  - `tests/integration/test_dpo_api_endpoints.py:222`
  - `tests/integration/test_api_edge_cases.py:130`
  - ... and 20 more

#### `/api/v1/marketplace/listings/{id}/preview`

- **Impact Score**: 67.0
- **Priority**: CRITICAL
- **Total Consumers**: 67
- **Consumer Types**: hardcoded:67

**Consumers:**

- **HARDCODED** (67 references):
  - `docs/api-audit/api-dependencies.md:270`
  - `docs/api-contracts/missing/README.md:436`
  - `docs/api-contracts/missing/README.md:436`
  - `docs/api-audit/error-responses-documentation.md:504`
  - `docs/api-audit/error-responses-documentation.md:504`
  - ... and 62 more

#### `/api/v1/jobs/jobs`

- **Impact Score**: 66.0
- **Priority**: CRITICAL
- **Total Consumers**: 66
- **Consumer Types**: hardcoded:39, api_client:27

**Consumers:**

- **HARDCODED** (39 references):
  - `tests/integration/test_job_apis_comprehensive.py:437`
  - `tests/integration/test_job_apis_comprehensive.py:437`
  - `tests/e2e/test_job_orchestration.py:296`
  - `tests/e2e/test_job_orchestration.py:296`
  - `tests/integration/test_job_apis_comprehensive.py:259`
  - ... and 34 more
- **API_CLIENT** (27 references):
  - `tests/regression/test_api_endpoints.py:495`
  - `tests/integration/test_job_apis_comprehensive.py:259`
  - `tests/e2e/test_job_orchestration.py:425`
  - `hub/apps/tenants/tests/test_tenant_config_job_integration.py:131`
  - `tests/integration/test_job_apis_comprehensive.py:359`
  - ... and 22 more

#### `/api/v1/users/users`

- **Impact Score**: 64.0
- **Priority**: CRITICAL
- **Total Consumers**: 64
- **Consumer Types**: api_client:23, hardcoded:41

**Consumers:**

- **API_CLIENT** (23 references):
  - `hub/apps/users/tests/test_views.py:85`
  - `tests/regression/test_api_endpoints.py:725`
  - `hub/apps/users/tests/test_views.py:192`
  - `tests/e2e/test_persona_ta_comprehensive.py:757`
  - `tests/e2e/test_persona_ta_comprehensive.py:132`
  - ... and 18 more
- **HARDCODED** (41 references):
  - `tests/regression/test_tenant_isolation.py:242`
  - `tests/regression/test_tenant_isolation.py:242`
  - `tests/regression/test_api_endpoints.py:724`
  - `tests/e2e/test_persona_ta_comprehensive.py:869`
  - `tests/e2e/test_persona_ta_comprehensive.py:869`
  - ... and 36 more

#### `/api/v1/scheduled-ingestions/{id}/credentials`

- **Impact Score**: 63.0
- **Priority**: CRITICAL
- **Total Consumers**: 63
- **Consumer Types**: hardcoded:63

**Consumers:**

- **HARDCODED** (63 references):
  - `docs/api-audit/api-development-timeline.md:84`
  - `docs/api-audit/api-development-timeline.md:84`
  - `docs/api-audit/api-effort-estimates-summary.md:281`
  - `docs/api-audit/api-effort-estimates-summary.md:281`
  - `docs/api-audit/integration-test-requirements.md:285`
  - ... and 58 more

#### `/api/v1/scheduled-ingestions/{id}/credentials/test`

- **Impact Score**: 63.0
- **Priority**: CRITICAL
- **Total Consumers**: 63
- **Consumer Types**: hardcoded:63

**Consumers:**

- **HARDCODED** (63 references):
  - `docs/api-audit/gap-categorization-by-priority.md:756`
  - `docs/api-audit/gap-categorization-by-priority.md:756`
  - `docs/api-audit/integration-test-requirements.md:590`
  - `docs/api-audit/GAP_DETAILS_SUMMARY.md:145`
  - `docs/api-audit/GAP_DETAILS_SUMMARY.md:145`
  - ... and 58 more

#### `/api/v1/files`

- **Impact Score**: 62.0
- **Priority**: CRITICAL
- **Total Consumers**: 62
- **Consumer Types**: hardcoded:60, api_client:2

**Consumers:**

- **HARDCODED** (60 references):
  - `docs/api-audit/current-api-inventory-categorized.md:243`
  - `docs/api-audit/current-api-inventory-categorized.md:243`
  - `docs/api-audit/codebase-endpoints-inventory.md:138`
  - `docs/api-audit/codebase-endpoints-inventory.md:138`
  - `docs/api-audit/gap-categorization-by-priority.md:257`
  - ... and 55 more
- **API_CLIENT** (2 references):
  - `tests/integration/test_api_endpoints_comprehensive.py:99`
  - `hub/apps/rate_limiting/tests/test_integration.py:205`

#### `/api/v1/marketplace/listings/{listing_id}`

- **Impact Score**: 62.0
- **Priority**: CRITICAL
- **Total Consumers**: 62
- **Consumer Types**: hardcoded:48, api_client:14

**Consumers:**

- **HARDCODED** (48 references):
  - `tests/e2e/test_marketplace_use_cases.py:207`
  - `tests/e2e/test_marketplace_use_cases.py:207`
  - `tests/e2e/test_marketplace_use_cases.py:241`
  - `tests/e2e/test_marketplace_use_cases.py:241`
  - `tests/e2e/test_complete_user_journeys.py:327`
  - ... and 43 more
- **API_CLIENT** (14 references):
  - `tests/e2e/test_persona_dc_comprehensive.py:331`
  - `tests/e2e/test_persona_dpo_comprehensive.py:394`
  - `tests/e2e/test_complete_journeys_enhanced.py:401`
  - `tests/e2e/test_complete_user_journeys.py:275`
  - `tests/e2e/test_persona_dc_comprehensive.py:131`
  - ... and 9 more

#### `/api/v1/webhooks/webhooks`

- **Impact Score**: 61.5
- **Priority**: CRITICAL
- **Total Consumers**: 54
- **Consumer Types**: sdk:2, hardcoded:30, api_client:11, webhook:11

**Consumers:**

- **SDK** (2 references):
  - `sdk/python/datahub_interoperability/webhooks.py:84`
  - `sdk/python/datahub_interoperability/webhooks.py:58`
- **HARDCODED** (30 references):
  - `docs/api-audit/api-performance-requirements.md:294`
  - `docs/api-audit/api-performance-requirements.md:294`
  - `tests/e2e/test_persona_dev_comprehensive.py:798`
  - `tests/e2e/test_persona_dev_comprehensive.py:798`
  - `tests/e2e/test_persona_dev_comprehensive.py:863`
  - ... and 25 more
- **API_CLIENT** (11 references):
  - `tests/e2e/test_persona_dev_comprehensive.py:717`
  - `tests/e2e/test_persona_dev_comprehensive.py:757`
  - `tests/e2e/test_persona_dev_comprehensive.py:862`
  - `tests/e2e/test_persona_dev_comprehensive.py:986`
  - `tests/e2e/test_persona_dev_comprehensive.py:416`
  - ... and 6 more
- **WEBHOOK** (11 references):
  - `tests/e2e/test_persona_dev_comprehensive.py:798`
  - `tests/e2e/test_persona_dev_comprehensive.py:758`
  - `tests/e2e/test_persona_dev_comprehensive.py:987`
  - `tests/e2e/test_persona_dev_comprehensive.py:863`
  - `tests/e2e/test_persona_dev_comprehensive.py:369`
  - ... and 6 more

#### `/api/v1/auth/logout`

- **Impact Score**: 58.0
- **Priority**: CRITICAL
- **Total Consumers**: 58
- **Consumer Types**: api_client:9, hardcoded:49

**Consumers:**

- **API_CLIENT** (9 references):
  - `tests/regression/test_api_endpoints.py:96`
  - `tests/integration/test_auth_apis_comprehensive.py:1274`
  - `hub/apps/auth/tests/test_authentication_flows.py:155`
  - `tests/regression/test_auth_authorization.py:108`
  - `tests/e2e/test_auth_authorization_comprehensive.py:358`
  - ... and 4 more
- **HARDCODED** (49 references):
  - `docs/API_REFERENCE.md:119`
  - `docs/api-audit/api-performance-requirements.md:90`
  - `docs/api-audit/api-performance-requirements.md:90`
  - `tests/e2e/test_authentication.py:253`
  - `tests/e2e/test_authentication.py:253`
  - ... and 44 more

#### `/api/v1/contracts/contracts/{contract_id}`

- **Impact Score**: 54.0
- **Priority**: CRITICAL
- **Total Consumers**: 54
- **Consumer Types**: api_client:18, hardcoded:36

**Consumers:**

- **API_CLIENT** (18 references):
  - `tests/regression/test_workflows.py:357`
  - `tests/performance/locust_endurance_test.py:95`
  - `tests/e2e/test_contract_migration.py:43`
  - `tests/e2e/test_security_comprehensive.py:301`
  - `tests/performance/locust_stress_test.py:131`
  - ... and 13 more
- **HARDCODED** (36 references):
  - `tests/e2e/test_contract_operations.py:474`
  - `tests/e2e/test_contract_operations.py:474`
  - `tests/regression/test_workflows.py:102`
  - `tests/regression/test_workflows.py:102`
  - `tests/e2e/test_performance_comprehensive.py:161`
  - ... and 31 more

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
