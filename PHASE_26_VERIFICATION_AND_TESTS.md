# Phase 26 — Verification and Test Documentation

## CLI Commands Verification

### Assets CLI ✅
**File**: `cli/datahub_cli/commands/assets.py`

**Backend API**: `/api/v1/assets/assets/` (ModelViewSet)

**Commands Verified**:
- ✅ `list` - Matches backend: supports `status`, `domain`, pagination (`limit`, `offset`)
- ✅ `get <asset_id>` - Matches backend: supports `include` parameter for related resources
- ✅ `create` - Matches backend: requires `name`, `key`; supports `description`, `domain`, `visibility`
- ✅ `update <asset_id>` - Matches backend: partial update via PATCH
- ✅ `delete <asset_id>` - Matches backend: DELETE endpoint
- ✅ `activate <asset_id>` - Matches backend: POST to `/activate/` action

**Status**: ✅ All commands match backend API structure

### Datasets CLI ✅
**File**: `cli/datahub_cli/commands/virtualization.py` (datasets command group)

**Backend API**:
- Virtual datasets: `/api/v1/virtualization/datasets/` ✅
- Regular datasets: `/api/v1/datasets/` ⚠️ (CLI only covers virtualization datasets)

**Virtual Datasets Commands Verified**:
- ✅ `list` - Matches backend: supports `status`, `query_type`, `owner`, `search`, `ordering`, pagination
- ✅ `get <dataset_id>` - Matches backend: GET endpoint
- ✅ `create` - Matches backend: POST with JSON file
- ✅ `update <dataset_id>` - Matches backend: PATCH with JSON file
- ✅ `delete <dataset_id>` - Matches backend: DELETE endpoint

**Regular Datasets**: CLI does not have commands for `/api/v1/datasets/` (file-based datasets). This is acceptable as virtualization datasets are the primary interface.

**Status**: ✅ Virtual datasets commands match backend API

### Search CLI ✅
**File**: `cli/datahub_cli/commands/search.py` (NEW)

**Backend API**: `/api/v1/search/search/` (ViewSet with `search` action)

**Commands Implemented**:
- ✅ `search` - Matches backend: supports all query parameters (`q`, `type`, `classification`, `owner`, `tags`, `domain`, `quality_status`, `compliance_status`, `limit`, `offset`, `sort_by`, `sort_order`)
- ✅ `suggestions` - Matches backend: GET `/search/suggestions/`
- ✅ `analytics` - Matches backend: GET `/search/analytics/`

**Status**: ✅ All commands match backend API structure

## SDK Coverage Verification

### Assets SDK ⚠️
**Status**: No dedicated SDK module found. Assets are accessed through other APIs (contracts, virtualization).

**Recommendation**: Assets are typically managed through contracts and virtualization APIs. If direct asset management is needed, consider creating `assets.py` SDK module.

### Datasets SDK ⚠️
**Status**: No dedicated SDK module for regular datasets (`/api/v1/datasets/`). Virtualization SDK exists (`virtualization.py`) which covers virtual datasets.

**Recommendation**: If regular dataset management is needed, consider creating `datasets.py` SDK module.

### DQ (Data Quality) SDK ⚠️
**Status**: No dedicated SDK module found. DQ operations may be accessed through other APIs.

**Recommendation**: Check if DQ operations are exposed through other SDK modules or create `dq.py` if needed.

### Compliance SDK ⚠️
**Status**: No dedicated SDK module found. Compliance operations may be accessed through other APIs.

**Recommendation**: Check if compliance operations are exposed through other SDK modules or create `compliance.py` if needed.

### Files SDK ⚠️
**Status**: No dedicated SDK module found.

**Backend API**: `/api/v1/files/files/` exists (ModelViewSet)

**Recommendation**: Create `files.py` SDK module with methods:
- `list_files()`
- `get_file(file_id)`
- `upload_file(file_path)`
- `download_file(file_id)`
- `delete_file(file_id)`

### Jobs SDK ⚠️
**Status**: No dedicated SDK module found.

**Backend API**: `/api/v1/jobs/jobs/` exists (ModelViewSet)

**Recommendation**: Create `jobs.py` SDK module with methods:
- `list_jobs()`
- `get_job(job_id)`
- `cancel_job(job_id)`
- `watch_job(job_id)` (if supported)

## Integration Tests

### Test Structure

Tests should be placed in:
- CLI: `cli/tests/integration/test_phase26_*.py`
- SDK: `sdk/python/tests/test_phase26_*.py`

### Test Requirements

1. **No Mocks/Stubs**: All tests use real backend API
2. **Real Backend**: Tests require `HUB_BASE_URL` environment variable
3. **Authentication**: Tests require valid API key or JWT token
4. **Tenant Context**: Tests must run in tenant context
5. **Cleanup**: Tests should clean up created resources

### Test Execution

#### CLI Tests

```bash
# Set environment variables
export HUB_BASE_URL=http://localhost:8000/api/v1
export DATAHUB_API_KEY=your-api-key

# Run CLI tests
cd cli
pytest tests/integration/test_phase26_*.py -v
```

#### SDK Tests

```bash
# Set environment variables
export HUB_BASE_URL=http://localhost:8000/api/v1
export DATAHUB_API_KEY=your-api-key

# Run SDK tests
cd sdk/python
pytest tests/test_phase26_*.py -v
```

### Test Coverage

#### CLI Tests Required

1. **Scheduled Ingestion**:
   - `test_scheduled_ingestion_list`
   - `test_scheduled_ingestion_create`
   - `test_scheduled_ingestion_get`
   - `test_scheduled_ingestion_update`
   - `test_scheduled_ingestion_trigger`
   - `test_scheduled_ingestion_runs`
   - `test_scheduled_ingestion_run_detail`

2. **Scheduled Export**:
   - `test_scheduled_export_list`
   - `test_scheduled_export_create`
   - `test_scheduled_export_get`
   - `test_scheduled_export_update`
   - `test_scheduled_export_trigger`
   - `test_scheduled_export_runs`
   - `test_scheduled_export_run_detail`

3. **Webhooks**:
   - `test_webhooks_list`
   - `test_webhooks_create`
   - `test_webhooks_get`
   - `test_webhooks_update`
   - `test_webhooks_delete`
   - `test_webhooks_event_types`

4. **Audit**:
   - `test_audit_query`
   - `test_audit_get`
   - `test_audit_export`

5. **Health**:
   - `test_health_check`

6. **Billing**:
   - `test_billing_subscription`
   - `test_billing_invoices`
   - `test_billing_invoice`

7. **Tenants**:
   - `test_tenants_usage`

8. **GDPR**:
   - `test_gdpr_export_data`
   - `test_gdpr_export_jobs`
   - `test_gdpr_request_erasure`
   - `test_gdpr_erasure_requests`

9. **Search**:
   - `test_search_search`
   - `test_search_suggestions`
   - `test_search_analytics`

#### SDK Tests Required

1. **Scheduled Export**:
   - `test_scheduled_export_create`
   - `test_scheduled_export_list`
   - `test_scheduled_export_get`
   - `test_scheduled_export_update`
   - `test_scheduled_export_delete`
   - `test_scheduled_export_trigger`
   - `test_scheduled_export_get_run_history`
   - `test_scheduled_export_get_run`

2. **Billing**:
   - `test_billing_get_subscription`
   - `test_billing_list_invoices`
   - `test_billing_get_invoice`

3. **Tenants**:
   - `test_tenants_get_usage`

4. **GDPR**:
   - `test_gdpr_request_export`
   - `test_gdpr_list_export_jobs`
   - `test_gdpr_get_export_job`
   - `test_gdpr_request_erasure`
   - `test_gdpr_list_erasure_requests`
   - `test_gdpr_get_erasure_request`

## Documentation

### CLI Documentation

Update `cli/docs/` with:
- `SCHEDULED_INGESTION_USAGE.md` - Scheduled ingestion commands
- `SCHEDULED_EXPORT_USAGE.md` - Scheduled export commands
- `WEBHOOKS_USAGE.md` - Webhooks commands
- `AUDIT_USAGE.md` - Audit commands
- `HEALTH_USAGE.md` - Health check commands
- `BILLING_USAGE.md` - Billing commands (Phase 25)
- `TENANTS_USAGE.md` - Tenants commands (Phase 25)
- `GDPR_USAGE.md` - GDPR commands (Phase 25)
- `SEARCH_USAGE.md` - Search commands

### SDK Documentation

Update `sdk/python/docs/` with:
- `SCHEDULED_EXPORT_USAGE.md` - Scheduled export SDK methods
- `BILLING_USAGE.md` - Billing SDK methods (Phase 25)
- `TENANTS_USAGE.md` - Tenants SDK methods (Phase 25)
- `GDPR_USAGE.md` - GDPR SDK methods (Phase 25)

### Test Execution Documentation

Create `cli/tests/README_PHASE26.md` and `sdk/python/tests/README_PHASE26.md` with:
- Environment setup instructions
- How to run tests
- Required environment variables
- Test data setup
- Troubleshooting

## Next Steps

1. ✅ Create search CLI commands
2. ⚠️ Verify SDK coverage for assets, datasets, DQ, compliance, files, jobs
3. ⚠️ Create missing SDK modules if needed (files, jobs)
4. ⚠️ Create integration tests for all new CLI/SDK functionality
5. ⚠️ Create documentation for new commands and methods
6. ⚠️ Document test execution process
