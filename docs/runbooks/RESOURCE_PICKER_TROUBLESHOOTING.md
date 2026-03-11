# Resource Picker Troubleshooting Runbook

**When to use:** Picker dropdowns empty or not loading; list API 403/404; integration tests failing; a11y violations; picker shows text input instead of search UI.

**Related docs:** [scripts/run_resource_picker_tests.sh](../../scripts/run_resource_picker_tests.sh) — full picker test suite; [openspec/changes/useronboardfix/tasks.md](../../openspec/changes/useronboardfix/tasks.md) — 29.69 Resource Pickers.

---

## Overview

Resource pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker and their Multi variants) provide searchable dropdowns for selecting assets, contracts, datasets, and files. They call backend list APIs (`/api/v1/assets/`, `/api/v1/contracts/`, `/api/v1/datasets/`, `/api/v1/files/`) with pagination and search. When `FEATURE_RESOURCE_PICKERS_ENABLED` is false, pickers fall back to plain text inputs (UUID entry).

**Architecture:**
- **Frontend:** `frontend/src/shared/components/pickers/` — AssetPicker, ContractPicker, DatasetPicker, FilePicker, AssetMultiPicker, DatasetMultiPicker, FileMultiPicker
- **Backend:** List APIs in `hub/apps/assets/`, `hub/apps/contracts/`, `hub/apps/datasets/`, `hub/apps/files/`
- **Feature flag:** `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` (default: true). When false, pickers render text inputs.
- **Test script:** `./scripts/run_resource_picker_tests.sh` — frontend unit, backend list API, integration, a11y; `--e2e` for optional E2E picker flows

---

## Root Causes and Fixes

### 1. Picker dropdown empty or "Loading..." never resolves

**Cause:** (a) Backend list API unreachable (CORS, wrong URL, auth); (b) User has no tenant or no membership; (c) Tenant isolation — user's tenant has no assets/contracts/datasets/files.

**Fix:**
- Ensure backend is running: `docker compose up -d api-service` (or `api-service-test` for tests).
- Check `VITE_API_BASE_URL` / `VITE_PROXY_TARGET` — must point to backend (e.g. `/api/v1` or `http://localhost:8001`).
- Verify user is authenticated and has `X-Tenant-ID` (or `tenant_id`). List APIs filter by tenant.
- Create test data: assets, contracts, datasets, files in the user's tenant.

**Verify:** `curl -H "Authorization: Bearer <token>" -H "X-Tenant-ID: <tenant_id>" http://localhost:8001/api/v1/assets/?page_size=5` returns 200 and `results` array.

---

### 2. List API returns 403 Forbidden

**Cause:** (a) Missing or invalid JWT; (b) User not in tenant; (c) Missing `X-Tenant-ID` header when user has multiple tenants.

**Fix:**
- Ensure frontend sends `Authorization: Bearer <access_token>` and `X-Tenant-ID` on list requests.
- Check `authService` / API client includes headers. Token refresh may have failed.
- Verify user has `UserTenantMembership` for the active tenant.

**Verify:** Inspect network tab — list API request must have `Authorization` and `X-Tenant-ID`. Backend logs: 403 usually logs "permission denied" or "tenant required".

---

### 3. Integration tests fail (picker-form-api.integration.test.ts)

**Cause:** (a) Backend not running on 8000 or 8001; (b) E2E user missing or wrong credentials; (c) `ensure_e2e_user_roles` / `ensure_e2e_subscription` not run.

**Fix:**
- Start backend: `docker compose -f docker-compose.test.yml up -d api-service-test` or dev stack.
- Ensure `VITE_API_BASE_URL` points to reachable backend (e.g. `http://localhost:8001/api/v1`).
- Run seed: `python manage.py ensure_e2e_user_roles` and `ensure_e2e_subscription` if required.
- Check `.env.test` or `.env` for `E2E_EMAIL`, `E2E_PASSWORD` if tests use custom credentials.

**Verify:** `cd frontend && npm run test:integration:api` — all tests pass when backend is up. Script skips integration when API unreachable.

---

### 4. Picker shows text input instead of search dropdown

**Cause:** `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` is false. Pickers fall back to plain text input for manual UUID entry.

**Fix:** Set `VITE_FEATURE_RESOURCE_PICKERS_ENABLED=true` in `frontend/.env` or Docker build args. Default is `true`. Rebuild: `npm run build` or `docker compose build frontend`.

**Verify:** `import.meta.env.VITE_FEATURE_RESOURCE_PICKERS_ENABLED` (or `"true"` in built output). Navigate to Dataset create, Scheduled Export create, Retention create — pickers should show search dropdown when enabled.

---

### 5. Backend list API tests fail (pytest)

**Cause:** (a) Test DB not migrated; (b) Wrong pytest filter; (c) Tenant isolation test expects empty results for cross-tenant filter.

**Fix:**
- Run migrations: `docker compose -f docker-compose.test.yml run --rm api-service-test python manage.py migrate`
- Use correct filter: `-k 'test_list_contracts or test_list_datasets or test_list_files or test_list_assets'`
- For tenant isolation: `test_list_datasets_asset_id_filter_tenant_isolation` — user from tenant B filtering by asset_id from tenant A must get empty results (IDOR prevention).

**Verify:** `./scripts/run_resource_picker_tests.sh` — backend section runs 51 list API tests. Or manually: `docker compose -f docker-compose.test.yml run --rm api-service-test pytest hub/apps/contracts/tests/ hub/apps/datasets/tests/ hub/apps/files/tests/ hub/apps/assets/tests/ -k 'test_list_...' -v`.

---

### 6. A11y tests fail (axe-core)

**Cause:** (a) Picker pages have contrast/label violations; (b) `picker-a11y.spec.ts` requires auth — login fails; (c) `resource-picker-a11y.spec.ts` runs unauthenticated — redirects to login (validates login page a11y).

**Fix:**
- Run `picker-a11y.spec.ts` with main E2E config (auth): `npm run test:e2e:ux` includes it.
- Run `resource-picker-a11y.spec.ts` with `playwright.a11y.config` — validates login page when `/datasets/create` redirects.
- Fix contrast: ensure picker options meet WCAG AA. Fix labels: ensure `aria-label` on search input and options.

**Verify:** `npm run test:a11y` — 3 tests. Or `./scripts/run_resource_picker_tests.sh` (includes a11y unless `--skip-a11y`).

---

### 7. E2E picker flows fail (Playwright)

**Cause:** (a) Backend not running; (b) Test data missing (no assets/datasets for picker to select); (c) Selector changed (e.g. `.asset-picker-option` vs `.resource-picker-option`); (d) Timing — picker loads slowly.

**Fix:**
- Ensure backend on 8001 (or `E2E_API_BASE_URL`). Create data via API before navigate: `createAssetViaApi`, `createDatasetViaApi`, etc.
- Use correct selectors: AssetPicker uses `.asset-picker-option`, `.asset-picker-empty`, `.asset-picker-loading`; ContractPicker uses `.contract-picker-option`; DatasetPicker `.dataset-picker-option`; FilePicker `.file-picker-option`.
- Add `waitFor` for picker options: `await page.waitForSelector('.asset-picker-option', { timeout: 5000 })`.

**Verify:** `npm run test:e2e:ux` — odps-asset-link, asset-attach-contract-dataset, dq-compliance-access-request, scheduled-export-retention-odps-link, dataset-edit, asset-dataset-flow, files-upload, picker-a11y.

---

### 8. Cascading pickers (DatasetPicker with assetId, FilePicker with assetId/datasetId) show wrong options

**Cause:** Parent value (assetId, datasetId) not passed or stale. DatasetPicker filters by `asset_id`; FilePicker filters by `asset_id` and `dataset_id`.

**Fix:**
- Ensure parent picker's `onChange` updates state; child picker receives `assetId` / `datasetId` props.
- When parent changes, child should reset selection (e.g. `datasetId` null when `assetId` changes).
- Check `useDatasets({ asset_id: assetId })` and `useFiles({ asset_id: assetId, dataset_id: datasetId })` — filters must be passed.

**Verify:** Retention create: select Asset → DatasetPicker filters to datasets in that asset; select Dataset → FilePicker filters to files in that dataset.

---

## Diagnostic Commands

```bash
# Run full resource picker test suite
./scripts/run_resource_picker_tests.sh

# Skip a11y (faster)
./scripts/run_resource_picker_tests.sh --skip-a11y

# Skip backend (frontend-only)
./scripts/run_resource_picker_tests.sh --skip-backend

# Include E2E picker flows (requires API on 8000 or 8001)
./scripts/run_resource_picker_tests.sh --e2e

# Frontend unit tests only
cd frontend && npm run test:run -- src/shared/components/pickers src/features/scheduledExport src/features/governance/components/RetentionPolicy src/features/odps src/features/datasets/components/DatasetDetailPage src/features/datasets/components/DatasetCreatePage

# Backend list API tests only
docker compose -f docker-compose.test.yml run --rm --no-deps api-service-test pytest hub/apps/contracts/tests/ hub/apps/datasets/tests/ hub/apps/files/tests/ hub/apps/assets/tests/ -k 'test_list_contracts or test_list_datasets or test_list_files or test_list_assets' -v --tb=short --reuse-db -p no:xdist

# Integration (requires backend on 8000 or 8001)
cd frontend && npm run test:integration:api

# A11y
cd frontend && npm run test:a11y

# E2E picker flows
export E2E_API_BASE_URL=http://localhost:8001/api/v1 E2E_WEB_PORT=5184
cd frontend && npx playwright test e2e/use-cases/ux/ --project=chromium
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` | `true` | When `false`, pickers render plain text inputs for manual UUID entry. |
| `VITE_API_BASE_URL` | `/api/v1` | API base path for frontend requests. |
| `VITE_PROXY_TARGET` | — | Dev server proxy target (e.g. `http://localhost:8001`). |
| `E2E_API_BASE_URL` | — | Backend URL for E2E/integration tests. |

---

## References

- [scripts/run_resource_picker_tests.sh](../../scripts/run_resource_picker_tests.sh) — test script
- [frontend/src/shared/components/pickers/](../../frontend/src/shared/components/pickers/) — picker components
- [frontend/src/integration/picker-form-api.integration.test.ts](../../frontend/src/integration/picker-form-api.integration.test.ts) — integration tests
- [frontend/e2e/use-cases/ux/](../../frontend/e2e/use-cases/ux/) — E2E picker flows
- [openspec/changes/useronboardfix/tasks.md](../../openspec/changes/useronboardfix/tasks.md) — 29.69 Resource Pickers spec
