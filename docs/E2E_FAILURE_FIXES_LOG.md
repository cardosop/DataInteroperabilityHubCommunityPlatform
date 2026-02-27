# E2E Failure Fixes Log

Summary of root-cause fixes applied to E2E tests (no mocks/stubs).  
Full run reference: 67 failed, 1346 passed, 69 skipped (2026-02-27 run).

## Fixes Applied (2026-02-25)

### 1. `test_django6_upgrade_critical_workflows.py`

- **test_jsonfield_api_filtering (401)**  
  **Cause:** `/api/v1/contracts/` is DRF with `IsAuthenticated`; default auth is JWT/APIKey only. The test used Django `Client` + `force_login()` (session), which DRF does not use.  
  **Fix:** Use `rest_framework.test.APIClient` and `force_authenticate(user=self.user)` so the contracts API receives a recognized authenticated user. Response parsing uses `getattr(response, "data", None) or response.json()` for compatibility.

- **test_contract_create_api (400)**  
  **Cause:** Payload `original_raw: '{"info": {"title": "Test"}}'` can fail normalization (ODCS normalizer may require e.g. `schema.fields`).  
  **Fix:** Use minimal valid ODCS in create payload: `id`, `info`, and `schema.fields` so normalization succeeds and the test asserts 200/201.

### 2. `test_dq_alerting_scorecards_root_cause_e2e.py`

- **test_complete_root_cause_analysis_workflow (IntegrityError: unique_dataset_version_per_asset)**  
  **Cause:** Loop created 10 `Dataset` rows with same `(tenant, asset, version=1)`, violating `unique_dataset_version_per_asset`.  
  **Fix:** Use `version=2 + i` for historical datasets so each has a distinct version for the same asset.

## Fixes Applied (2026-02-27)

### 3. Marketplace/Entitlements/KYC 403s (~24 tests)

- **Root cause:** `SubscriptionStatusMiddleware` and `TenantSuspensionMiddleware` block POST/PUT/PATCH/DELETE when tenant has no active subscription. Tests created `consumer_tenant`, `provider_tenant`, or `unverified_tenant` without subscriptions.
- **Fix:** Call `ensure_e2e_tenant_ready()` or `ensure_tenant_has_active_subscription()` for every tenant that performs API write operations. Applied in:
  - `test_entitlements.py`, `test_marketplace_orders.py`, `test_marketplace_comprehensive.py`, `test_marketplace_purchase_flow.py`, `test_marketplace_use_cases.py`, `test_persona_workflows_odps_enhanced.py`
  - `test_tenant_management.py` (unverified_tenant + DATA_PROVIDER role for asset creation)
  - `test_graphql_api.py` (other_tenant for cross-tenant isolation test)
  - `test_phase25_gdpr_erasure_e2e.py` (tenant for request-erasure)

### 4. User Management audit log (1 test)

- **test_invite_user:** Expected `USER_INVITED` audit action but `UserService.create_user` always logged `USER_CREATED`.
- **Fix:** In `hub/apps/users/services.py`, use `USER_INVITED` when `status == UserStatus.INVITED`, otherwise `USER_CREATED`.

### 5. Contract schema in marketplace orders

- **Fix:** Use valid ODCS `schema.fields` in `test_marketplace_orders.py` (`[{"name": "id", "type": "string"}]` instead of `[]`).

---

## Remaining Failure Groups (~40 tests)

To be addressed in follow-up batches (root-cause only, no mocks):

| Category | Count (approx) | Root cause / direction |
|----------|----------------|------------------------|
| **ODPS/GraphQL** | ~15 | Contract normalization failed; Relay UUID vs plain UUID in mutations; exportODPS mutation returning None; product.dataSchema required in workflow. |
| **Semantic** | 6 | 503 Semantic service unavailable (circuit breaker); ensure semantic service healthy in test env or tests handle unavailability. |
| **Scheduled ingestion** | 2 | 400 Connection test failed (S3/source config); MinIO/S3 config or connection test in test env. |
| **Auditor persona** | 2 | Permission denied for compliance/DQ run creation; may need role/permission adjustment. |

Re-run only failed/error/skipped from a log:

```bash
docker compose -f docker-compose.test.yml run --rm api-service-test \
  python scripts/run_failed_error_skipped_from_log.py test_reports_e2e/2026-02-27/e2e.log -v --tb=short
```

Use `--skip` to exclude SKIPPED and run only FAILED/ERROR.
