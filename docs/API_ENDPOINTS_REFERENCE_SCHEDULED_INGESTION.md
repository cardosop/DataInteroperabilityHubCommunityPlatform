# Scheduled Ingestion API Endpoints Reference

**Last Updated**: 2026-02-03
**Version**: 1.0.0

---

## Overview

The Scheduled Ingestion API provides endpoints for managing scheduled data ingestion workflows. The API includes:

- **Public API**: Endpoints for creating, managing, and monitoring scheduled ingestions (tenant-scoped)
- **Internal Worker API**: Endpoints used exclusively by Prefect workers for execution (worker-authenticated)

---

## Scheduled Ingestion (Public API)

### List Scheduled Ingestions

**GET** `/api/v1/scheduled-ingestions/`

List all scheduled ingestions for the authenticated tenant.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`ACTIVE`, `PAUSED`, `ERROR`)
- `source_type` (string): Filter by source type (`S3`, `GCS`, `AZURE_BLOB`, `HTTP`, `FTP`, `SFTP`)

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped (users can only access their tenant's ingestions)

**Rate Limiting**: Per tenant/user limits (see [Rate Limiting](#rate-limiting))

**Response (200 OK):**
```json
{
  "count": 10,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Daily Sales Data",
      "source_type": "S3",
      "source_config": {
        "bucket": "data-bucket",
        "path": "sales/daily/"
      },
      "schedule_type": "DAILY",
      "schedule_config": {
        "time": "02:00"
      },
      "file_pattern": ".*\\.csv",
      "status": "ACTIVE",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### Create Scheduled Ingestion

**POST** `/api/v1/scheduled-ingestions/`

Create a new scheduled ingestion.

**Request Body:**
```json
{
  "name": "Daily Sales Data",
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  },
  "schedule_type": "DAILY",
  "schedule_config": {
    "time": "02:00"
  },
  "file_pattern": ".*\\.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Data",
  "source_type": "S3",
  "status": "ACTIVE",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### Get Scheduled Ingestion

**GET** `/api/v1/scheduled-ingestions/{id}/`

Get details of a specific scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Data",
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/"
  },
  "schedule_type": "DAILY",
  "schedule_config": {
    "time": "02:00"
  },
  "file_pattern": ".*\\.csv",
  "status": "ACTIVE",
  "next_run_at": "2026-02-04T02:00:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Update Scheduled Ingestion

**PUT** `/api/v1/scheduled-ingestions/{id}/`

Update a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Request Body:** Same as create, all fields optional

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):** Updated scheduled ingestion object

### Delete Scheduled Ingestion

**DELETE** `/api/v1/scheduled-ingestions/{id}/`

Delete a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (204 No Content)**

### Trigger Scheduled Ingestion

**POST** `/api/v1/scheduled-ingestions/{id}/trigger/`

Manually trigger a scheduled ingestion run (creates Prefect flow run).

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (202 Accepted):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "status": "RUNNING"
}
```

### List Scheduled Ingestion Runs

**GET** `/api/v1/scheduled-ingestions/{id}/runs/`

List runs for a scheduled ingestion.

**Path Parameters:**
- `id` (UUID): Scheduled ingestion UUID

**Query Parameters:**
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `status` (string): Filter by status (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "count": 50,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "COMPLETED",
      "files_found": 10,
      "files_processed": 10,
      "files_failed": 0,
      "started_at": "2026-02-03T02:00:00Z",
      "completed_at": "2026-02-03T02:15:00Z",
      "prefect_flow_run_id": "prefect-flow-run-123"
    }
  ]
}
```

---

## Scheduled Ingestion Internal Worker API

**Base Path**: `/api/v1/scheduled-ingestions/internal/`

**Status**: Internal (Worker-only)

The Internal Worker API endpoints are used exclusively by Prefect workers for scheduled ingestion execution. These endpoints are **not** intended for public use and are tagged as "Internal (Worker)" in OpenAPI.

### Authentication

**Mechanism**: Worker API key authentication

- **Environment-based**: `HUB_WORKER_API_KEY` environment variable
  - Worker sends: `Authorization: ApiKey <HUB_WORKER_API_KEY>`
  - Worker must send: `X-Tenant-ID: <tenant-uuid>` header
- **Database API key**: API key with scope `scheduled_ingestion:internal`
  - Worker sends: `Authorization: ApiKey <api-key>`
  - Tenant is resolved from API key

**Tenant Isolation**: Every request validates tenant; run and scheduled_ingestion must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

### Create Run

**POST** `/api/v1/scheduled-ingestions/internal/runs/`

Create a new scheduled ingestion run (status RUNNING). Idempotent by `idempotency_key` or `prefect_flow_run_id`.

**Request Body:**
```json
{
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "idempotency_key": "optional-idempotency-key"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Path Parameters:**
- `scheduled_ingestion_id` (UUID, required): UUID of the scheduled ingestion
- `prefect_flow_run_id` (string, optional): Prefect flow run ID for correlation
- `idempotency_key` (string, optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_ingestion:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "started_at": "2026-02-03T02:00:00Z",
  "prefect_flow_run_id": "prefect-flow-run-123"
}
```

**Response (200 OK - Idempotent Replay):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123"
}
```

**Side Effects:**
- Creates `ScheduledIngestionRun` with status RUNNING
- Emits audit event (`SCHEDULED_INGESTION_RUN.CREATED`)
- Publishes domain event (`ingestion.started`)
- Emits Prometheus metrics (`scheduled_ingestion_runs_total`, `scheduled_ingestion_runs_running`)

**Error Responses:**
- `400 Bad Request`: Validation error or tenant required
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled ingestion not found

### Update Run

**PATCH** `/api/v1/scheduled-ingestions/internal/runs/{run_id}/`

Update a scheduled ingestion run (status, file counts, result_json, completed_at, etc.).

**Path Parameters:**
- `run_id` (UUID): Run UUID

**Request Body (all fields optional):**
```json
{
  "status": "COMPLETED",
  "files_found": 10,
  "files_processed": 10,
  "files_failed": 0,
  "result_json": {
    "summary": "Processing complete"
  },
  "completed_at": "2026-02-03T02:15:00Z",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "error_message": null
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "files_found": 10,
  "files_processed": 10,
  "files_failed": 0,
  "completed_at": "2026-02-03T02:15:00Z"
}
```

**Side Effects (when status changes to COMPLETED or FAILED):**
1. **ScheduledIngestion**: Recalculate and set `next_run_at`; if COMPLETED and ingestion was in ERROR, clear status to ACTIVE and clear `error_message`
2. **If COMPLETED**: Call `CostTrackingManager.calculate_run_costs(run.id)`
3. Call `DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)`
4. Send completion or failure notification if configured (`source_config.send_notifications`, `notification_recipients`)
5. Emit domain events (`ingestion.completed` or `ingestion.failed`) and audit events
6. Emit Prometheus metrics (`scheduled_ingestion_runs_total`, `scheduled_ingestion_duration_seconds`, `scheduled_ingestion_runs_running`)

**Error Responses:**
- `400 Bad Request`: Validation error or tenant required
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Run not found

### Process File

**POST** `/api/v1/scheduled-ingestions/internal/process-file/`

Process a single file for a scheduled ingestion run (validate, DQ, create file/dataset, index, incremental state).

**Request Body (multipart or JSON):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "file_path": "sales/daily/2026-02-03.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001",
  "dq_options": {
    "profile_key": "sales-profile",
    "strict_mode": true,
    "min_quality_score": 0.8
  },
  "file_content": "<base64-encoded-file-content>"
}
```

**Multipart Form Data:**
- `run_id` (UUID, required): Run UUID
- `file_path` (string, required): Logical path/key of the file
- `file` (file, optional): File upload (multipart)
- `file_content` (string, optional): Base64-encoded file content (JSON)
- `asset_id` (UUID, optional): Override asset
- `contract_id` (UUID, optional): Override contract
- `dq_options` (JSON, optional): DQ options

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)
- `Content-Type: multipart/form-data` (for file upload) or `application/json` (for base64 content)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "file_id": "880e8400-e29b-41d4-a716-446655440000",
  "dataset_id": "990e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSED",
  "dq_result": {
    "quality_score": 0.95,
    "passed": true
  }
}
```

**Processing Order:**
1. Load run and scheduled ingestion (tenant check)
2. Validate file using **ScheduledIngestionBusinessRules** (validation_type="source" for format/size)
3. Optional DQ (existing DQ service)
4. Create File + Dataset (existing Files/Datasets services)
5. Index (Search service)
6. Update incremental state
7. On permanent failure: DLQ, audit, domain events, Prometheus metrics

**Error Responses:**
- `400 Bad Request`: Validation error (run_id and file_path required)
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Run not found
- `422 Unprocessable Entity`: File validation failed or DQ failed
- `500 Internal Server Error`: Processing error (DLQ record created)

### Get Configuration

**GET** `/api/v1/scheduled-ingestions/internal/config/{scheduled_ingestion_id}/`

Get configuration for a scheduled ingestion (source_type, source_config with masked credentials, file_pattern, schedule_config, ingestion_state, etc.).

**Path Parameters:**
- `scheduled_ingestion_id` (UUID): Scheduled ingestion UUID

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "source_type": "S3",
  "source_config": {
    "bucket": "data-bucket",
    "path": "sales/daily/",
    "access_key_id": "***masked***",
    "secret_access_key": "***masked***"
  },
  "file_pattern": ".*\\.csv",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": "660e8400-e29b-41d4-a716-446655440001",
  "schedule_config": {
    "time": "02:00"
  },
  "ingestion_state": {
    "processed_files": ["sales/daily/2026-02-02.csv", "sales/daily/2026-02-03.csv"],
    "last_processed_at": "2026-02-03T02:15:00Z"
  },
  "auto_create_asset": true,
  "auto_activate": false
}
```

**Security**: Credentials in `source_config` are **masked** (e.g., `***masked***`) or omitted. Worker must not log full config. See runbooks for credential handling.

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled ingestion not found

---

## Rate Limiting

### Public API Endpoints

Public scheduled ingestion endpoints are rate-limited per tenant and per user:

- **Tenant-level**: Per tenant, per endpoint category
- **User-level**: Per user, per endpoint category (50% of tenant limit)
- **API Key-level**: Per API key, per endpoint category (same as user limit)

**Endpoint Category**: `GENERAL` (default)

**Default Limits**:
- **BURST** (10 seconds): 100 requests
- **SUSTAINED** (60 seconds): 600 requests
- **DAILY** (24 hours): 100,000 requests

### Internal Worker API Endpoints

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

Internal worker endpoints (`/api/v1/scheduled-ingestions/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

---

## OpenAPI Schema

Internal worker API endpoints are tagged **"Internal (Worker)"** in the OpenAPI schema and can be:
- Excluded from public API documentation
- Documented separately (see [SCHEDULED_INGESTION_WORKER_API.md](SCHEDULED_INGESTION_WORKER_API.md))
- Included in internal/developer documentation only

To view the OpenAPI schema:
- **Public API**: `/api/schema/` (excludes internal endpoints)
- **Full Schema**: `/api/schema/?include_internal=true` (includes internal endpoints)

---

## Error Responses

All endpoints return structured error responses:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

**Common Error Codes:**
- `TENANT_REQUIRED`: Tenant ID missing or invalid
- `NOT_FOUND`: Resource not found
- `FORBIDDEN`: Tenant mismatch or insufficient permissions
- `VALIDATION_ERROR`: Request validation failed
- `AUTHENTICATION_REQUIRED`: Authentication required

---

## Related Documentation

- [Scheduled Ingestion Worker API](SCHEDULED_INGESTION_WORKER_API.md) - Detailed internal API documentation
- [Deployment Order](DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md) - Deployment procedures
- [Release Notes](RELEASE_NOTES_SCHEDULED_INGESTION_PREFECT.md) - Release information
- [Runbooks](runbooks/RB-SCHEDULED-INGESTION-001.md) - Operational procedures
