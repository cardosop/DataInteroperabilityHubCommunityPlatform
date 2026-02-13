# Scheduled Ingestion Worker API (Internal)

This document describes the **internal** hub API used only by the Prefect worker for scheduled ingestion execution. These endpoints are not intended for public use and are tagged "Internal (Worker)" in OpenAPI.

## URL namespace

- Base path: `/api/v1/scheduled-ingestions/internal/`
- Endpoints are **not** exposed in public API docs except as internal/worker-only.
- All endpoints require worker authentication (see [Authentication](#authentication)).

## Authentication

- **Mechanism:** API key with scope `scheduled_ingestion:internal`, or environment-based worker key.
- **Required env for worker:** `HUB_WORKER_API_KEY` (or equivalent). When set, the worker can authenticate with `Authorization: ApiKey <HUB_WORKER_API_KEY>` and must send `X-Tenant-ID` on every request. Alternatively, use a tenant API key (from the hub) with scope `scheduled_ingestion:internal`.
- **Tenant isolation:** Every request validates tenant; run and scheduled_ingestion must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

## Rate Limiting

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

Internal worker API endpoints (`/api/v1/scheduled-ingestions/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

This ensures that Prefect workers can execute scheduled ingestion workflows without being throttled by rate limits.

## 1. Run lifecycle

### 1.1 Create run — `POST .../internal/runs/`

**Request body:**

```json
{
  "scheduled_ingestion_id": "uuid",
  "prefect_flow_run_id": "optional-string",
  "idempotency_key": "optional-string"
}
```

- `scheduled_ingestion_id` (required): UUID of the scheduled ingestion.
- `prefect_flow_run_id` (optional): Prefect flow run ID for correlation.
- `idempotency_key` (optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate).

**Response:**

- **201 Created:** `{"id": "run-uuid", "scheduled_ingestion_id": "...", "status": "RUNNING", ...}`
- **200 OK:** When idempotent replay (same idempotency_key or prefect_flow_run_id); body includes existing run id and status.

**Side effects:** Creates `ScheduledIngestionRun` with status RUNNING; emits audit event and domain events (e.g. IngestionEventPublisher); emits Prometheus metrics (run started).

### 1.2 Update run — `PATCH .../internal/runs/{run_id}/`

**Request body (all optional):**

```json
{
  "status": "COMPLETED|FAILED|CANCELLED|RUNNING",
  "files_found": 0,
  "files_processed": 0,
  "files_failed": 0,
  "result_json": {},
  "completed_at": "ISO8601",
  "prefect_flow_run_id": "string",
  "error_message": "string"
}
```

**Response:** 200 OK with updated run representation.

**Side effects when status is COMPLETED or FAILED:**

1. **ScheduledIngestion:** Recalculate and set `next_run_at`; if COMPLETED and ingestion was in ERROR, clear status to ACTIVE and clear `error_message`.
2. **If COMPLETED:** Call `CostTrackingManager.calculate_run_costs(run.id)`.
3. Call `DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)`.
4. Send completion or failure notification if configured (`source_config.send_notifications`, `notification_recipients`).
5. Emit domain events and audit.

**Metrics:** Run completed/failed/cancelled.

## 2. Process file — `POST .../internal/process-file/`

**Request:** Multipart or JSON with file content or upload URL.

- `run_id` (required): UUID of the run.
- `file_path` (required): Logical path/key of the file.
- `file`: File upload (multipart), or provide `file_content` (base64) / `file_url` per implementation.
- `asset_id` (optional): Override asset.
- `contract_id` (optional): Override contract.
- `dq_options` (optional): e.g. `{"profile_key": "...", "strict_mode": true, "min_quality_score": 0.8}`.

**Response:**

- **201 Created:** `{"file_id": "uuid", "dataset_id": "uuid", ...}` — file and dataset created, indexed, incremental state updated.
- **4xx/5xx:** Structured error; on permanent failure a DLQ record is created and audit/domain events emitted.

**Processing order (same as hub ScheduledIngestionWorkflow):**

1. Load run and scheduled ingestion (tenant check).
2. Validate file using **ScheduledIngestionBusinessRules** (validation_type="source" for format/size).
3. Optional DQ (existing DQ service).
4. Create File + Dataset (existing Files/Datasets services).
5. Index (Search).
6. Update incremental state.
7. On permanent failure: DLQ, audit, domain events, Prometheus metrics.

No business logic in the view; all in service method (e.g. `ScheduledIngestionService.process_file_for_run`).

## 3. Config — `GET .../internal/config/{scheduled_ingestion_id}/`

**Response:** JSON with fields needed by the Prefect flow:

- `source_type`, `source_config` (credentials **masked** or omitted), `file_pattern`, `asset_id`, `contract_id`, `schedule_config`, `ingestion_state` (incremental state), DQ-related options, etc.

**Security:** Config response and hub logs MUST NOT contain raw secrets. Credentials in `source_config` are masked or omitted. Worker must not log full config. See runbooks.

## 4. Error responses

Structured body: `{"error": "message", "code": "CODE", "details": {}}`. Same shape as platform error consistency (e.g. ValidationError → 400, NotFoundError → 404).

## 5. OpenAPI

Internal endpoints are tagged **"Internal (Worker)"** and can be excluded from public schema or documented separately per project convention.

## 6. Running Phase 1 tests

Phase 1 tests (run lifecycle, process-file, config, auth) live in `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py`. No mocks; they use real DB and real services.

**Recommended:** Run with api-service and postgres already up so the database is stable during test DB creation and migrations:

```bash
docker compose up -d postgres redis-cache redis-queue redis-events redis-channels minio jaeger mock-server
# Wait for postgres healthy, then:
docker compose up -d api-service
# Then:
docker compose exec api-service bash -c "cd /app && TESTING=1 python -m pytest hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py -v --tb=short --reuse-db"
```

Or use the script (prefers exec when api-service is running):

```bash
./scripts/run_internal_worker_api_tests.sh
```

If postgres is restarting or you see "database system is shutting down", wait for the stack to be healthy and re-run with `--reuse-db`.

## 7. Phase 2 — Prefect full flow and worker credentials

The Prefect worker runs `scheduled_ingestion_full_flow` (HTTP-only; no Django in worker). Config is fetched from the hub (GET config); credentials in `source_config` are **masked** in the response.

**Worker credentials for connectors:** If a connector needs real credentials (e.g. S3 `access_key_id`/`secret_access_key`), use one of:

- **Prefect Blocks (optional):** Store credentials in a Prefect Block keyed by `scheduled_ingestion/{id}/source_config` and merge into the masked config in the flow before discovery/download. Document block schema in runbooks.
- **Environment / config from hub:** For public or env-based auth (e.g. IAM role for S3, or HTTP with no auth), the masked config may be sufficient; or pass credentials via environment variables in the worker and merge in the flow.

Discovery and filter logic match current scheduled ingestion semantics (incremental, file pattern); state is read from hub config (`ingestion_state`).
