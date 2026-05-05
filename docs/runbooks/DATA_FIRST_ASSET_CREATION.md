# Data-First Asset Creation Runbook

This runbook describes the **data-first asset creation flow**: creating an asset, dataset, and contract from an uploaded file in a single API call. It covers troubleshooting, prerequisites, and operational procedures.

## Purpose and scope

- **Goal:** Enable users to create a complete data product (asset + dataset + contract) from an uploaded file via `POST /api/v1/assets/data-first/` or the Dataset Create page flow selector.
- **References:**
  - [API Reference — Data-First Asset Creation](../API_REFERENCE.md#data-first-asset-creation)
  - [Dataset Creation Flow tasks](../../openspec/changes/useronboardfix/tasks.md) — section 29.68 design and spec
  - [run_dataset_creation_flow_tests.sh](../../scripts/run_dataset_creation_flow_tests.sh) — backend and E2E test script

## Prerequisites

- Hub API running (e.g. `docker compose up -d` or `docker compose -f docker-compose.test.yml up -d`).
- MinIO (or S3) storage available for file uploads.
- Authenticated user with `DATA_PROVIDER` role and active tenant subscription.
- File uploaded via `POST /api/v1/files/` and in `COMPLETED` status.

## Flow overview

1. User uploads file → receives `file_id`.
2. User calls `POST /api/v1/assets/data-first/` with `file_id`, `key`, `name` (and optional `description`, `domain`, `visibility`).
3. Backend validates file (tenant-scoped, exists, active).
4. `AssetCreationWorkflow` executes: infer schema, generate ODCS, create asset, create dataset, create contract, run DQ checks (if DQ service available), run compliance checks, index for search.
5. Response: `201 Created` with `asset_id`, `dataset_id`, `contract_id`.

## API reference

### POST /api/v1/assets/data-first/

**Request body:**
```json
{
  "file_id": "uuid",
  "key": "my-asset-key",
  "name": "My Asset Name",
  "description": "Optional description",
  "domain": "sales",
  "visibility": "INTERNAL"
}
```

**Required:** `file_id`, `key`, `name`.

**Response (201):**
```json
{
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "contract_id": "uuid"
}
```

**Errors:**
- `400` — Missing/invalid `file_id`, `key`, or `name`; malformed UUID.
- `401` — Unauthenticated.
- `404` — File not found (invalid `file_id` or cross-tenant).
- `500` — Workflow failed (check logs).

## Troubleshooting

### File not found (404)

- **Cause:** `file_id` invalid, file belongs to another tenant, or file not in `COMPLETED` status.
- **Check:** `File.objects.filter(id=file_id, tenant_id=user.tenant_id, status=COMPLETED)`.
- **Fix:** Ensure file was uploaded by the same tenant; verify file status.

### Workflow failed (400/500)

- **Cause:** DQ service unreachable, datacontract service error, schema inference failure, or storage read failure.
- **Check:** Logs for `AssetCreationWorkflow`, `_run_dq_checks_task`, `_infer_schema_task`.
- **Fix:** DQ/compliance/datacontract services are optional for basic flow; workflow may skip DQ and set `dq_status=UNKNOWN` when DQ is unavailable. If schema inference fails, verify file format (CSV, JSON, Parquet) and content.

### Cross-tenant file_id (403/404)

- **Cause:** User from tenant A attempted to use `file_id` from tenant B.
- **Fix:** API returns 404 (no info leak). Ensure user uses only their tenant's files.

### Logs and debugging

- **API logs:** `docker compose logs api-service` (or `api-service-test` for test stack). Search for `AssetCreationWorkflow`, `data_first`, `_infer_schema_task`, `_run_dq_checks_task`.
- **DQ service:** When DQ is unavailable, workflow skips DQ checks and sets `dq_status=UNKNOWN`; no failure. Check `dq-service-test` logs if DQ integration is expected.
- **Test stack:** Use `docker compose -f docker-compose.test.yml`; full backend tests require DQ, datacontract, compliance, semantic services (started automatically by `run_dataset_creation_flow_tests.sh`). Use `--quick` for validation+IDOR only (no MinIO/DQ).

## Running tests

Run from repo root. Requires `docker compose -f docker-compose.test.yml` (or full stack) for E2E.

```bash
# Backend only (validation + IDOR, no MinIO/DQ)
./scripts/run_dataset_creation_flow_tests.sh --quick --skip-e2e

# Full backend (success + integration; needs DQ services)
./scripts/run_dataset_creation_flow_tests.sh --skip-e2e

# Full including E2E (dataset-creation-flow.spec.ts)
./scripts/run_dataset_creation_flow_tests.sh
```

**Asset Create entry point E2E** (tests "I have data to upload" redirect): from `frontend/`, run `npm run test:e2e -- e2e/journeys/dpo/asset-creation-flow.spec.ts --project=chromium`. Requires backend API on port 8001 (e.g. `docker compose -f docker-compose.test.yml up -d api-service-test`).

## Frontend flow

- **Asset Create page** (`/assets/create`): "I have data to upload" option at top redirects to `/datasets/create?linkMode=create_new`. Alternative entry point for data-first flow.
- **Dataset Create page** (`/datasets/create`): Flow selector with options `none`, `existing`, `create_new`. Supports `?linkMode=create_new` URL param to pre-select create_new.
- **create_new:** Upload file, enter asset key/name, submit → calls data-first API, redirects to dataset or asset detail.
- **existing:** Upload file, select asset via AssetPicker, submit → creates dataset and links to asset.
- **none:** Upload file, submit → creates dataset only (no asset linking).
