# Scheduled Export API Endpoints Reference

**Last Updated**: 2026-02-03
**Version**: 1.0.0

---

## Overview

The Scheduled Export API provides endpoints for managing scheduled data export workflows. The API includes:

- **Public API**: Endpoints for creating, managing, and monitoring scheduled exports (tenant-scoped)
- **Internal Worker API**: Endpoints used exclusively by Prefect workers for execution (worker-authenticated)

---

## Scheduled Export (Public API)

### List Scheduled Exports

**GET** `/api/v1/scheduled-exports/`

List all scheduled exports for the authenticated tenant.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`ACTIVE`, `PAUSED`, `ERROR`)

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped (users can only access their tenant's exports)

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
      "name": "Daily Sales Export",
      "destination_type": "S3",
      "destination_config": {
        "bucket": "export-bucket",
        "prefix": "exports/sales/"
      },
      "schedule_config": {
        "cron": "0 2 * * *"
      },
      "source_scope": {
        "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"]
      },
      "status": "ACTIVE",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### Create Scheduled Export

**POST** `/api/v1/scheduled-exports/`

Create a new scheduled export.

**Request Body:**
```json
{
  "name": "Daily Sales Export",
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"],
    "dataset_ids": [],
    "file_ids": [],
    "contract_id": null
  },
  "status": "ACTIVE"
}
```

**Authentication**: Required (JWT token or API key)

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "status": "ACTIVE",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### Get Scheduled Export

**GET** `/api/v1/scheduled-exports/{id}/`

Get details of a specific scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/"
  },
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"]
  },
  "status": "ACTIVE",
  "next_run_at": "2026-02-04T02:00:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Update Scheduled Export

**PUT** `/api/v1/scheduled-exports/{id}/`

Update a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Request Body:** Same as create, all fields optional

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):** Updated scheduled export object

### Delete Scheduled Export

**DELETE** `/api/v1/scheduled-exports/{id}/`

Delete a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (204 No Content)**

### Trigger Scheduled Export

**POST** `/api/v1/scheduled-exports/{id}/trigger/`

Manually trigger a scheduled export run.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Request Body (optional):**
```json
{
  "override_config": {
    "destination_config": {
      "bucket": "override-bucket"
    }
  }
}
```

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "status": "RUNNING",
  "triggered_at": "2026-02-03T10:00:00Z"
}
```

### List Export Runs

**GET** `/api/v1/scheduled-exports/{id}/runs/`

List all runs for a scheduled export.

**Path Parameters:**
- `id` (UUID): Scheduled export UUID

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `status` (string): Filter by status (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)
- `prefect_flow_run_id` (string): Filter by Prefect flow run ID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "count": 25,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "COMPLETED",
      "prefect_flow_run_id": "prefect-flow-run-123",
      "started_at": "2026-02-03T02:00:00Z",
      "completed_at": "2026-02-03T02:15:00Z",
      "items_exported": 150,
      "items_failed": 0,
      "error_message": null
    }
  ]
}
```

### Get Export Run

**GET** `/api/v1/scheduled-exports/runs/{run_id}/`

Get details of a specific export run.

**Path Parameters:**
- `run_id` (UUID): Export run UUID

**Authentication**: Required

**Authorization**: Tenant-scoped

**Rate Limiting**: Per tenant/user limits

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0,
  "error_message": null,
  "metadata": {
    "destination": "s3://export-bucket/exports/sales/2026-02-03/",
    "files_exported": ["dataset_123.parquet", "dataset_456.parquet"]
  }
}
```

---

## Scheduled Export Internal Worker API

**Status**: Internal (Worker-only)

The Internal Worker API endpoints are used exclusively by Prefect workers for scheduled export execution. These endpoints are **not** intended for public use and are tagged as "Internal (Worker)" in OpenAPI.

### Authentication

**Mechanism**: Worker API key authentication

- **Environment-based**: `HUB_WORKER_API_KEY` environment variable
  - Worker sends: `Authorization: ApiKey <HUB_WORKER_API_KEY>`
  - Worker must send: `X-Tenant-ID: <tenant-uuid>` header
- **Database API key**: API key with scope `scheduled_export:internal`
  - Worker sends: `Authorization: ApiKey <api-key>`
  - Tenant is resolved from API key

**Tenant Isolation**: Every request validates tenant; run and scheduled_export must belong to that tenant. Requests with missing/invalid token or wrong tenant are rejected (401/403).

**Rate Limiting**: **No rate limit** (internal worker endpoints are excluded from rate limiting)

### Create Run

**POST** `/api/v1/scheduled-exports/internal/runs/`

Create a new scheduled export run (status RUNNING). Idempotent by `idempotency_key` or `prefect_flow_run_id`.

**Request Body:**
```json
{
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "idempotency_key": "optional-idempotency-key"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Path Parameters:**
- `scheduled_export_id` (UUID, required): UUID of the scheduled export
- `prefect_flow_run_id` (string, optional): Prefect flow run ID for correlation
- `idempotency_key` (string, optional): If provided and a run already exists with this key, returns 200 with existing run (no duplicate)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z"
}
```

**Response (200 OK)** - If run already exists (idempotent):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z"
}
```

### Update Run

**PATCH** `/api/v1/scheduled-exports/internal/runs/{run_id}/`

Update a scheduled export run (status, completion, error message, counts).

**Path Parameters:**
- `run_id` (UUID): Export run UUID

**Request Body:**
```json
{
  "status": "COMPLETED",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0,
  "error_message": null
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "prefect_flow_run_id": "prefect-flow-run-123",
  "started_at": "2026-02-03T02:00:00Z",
  "completed_at": "2026-02-03T02:15:00Z",
  "items_exported": 150,
  "items_failed": 0
}
```

### Process Export

**POST** `/api/v1/scheduled-exports/internal/process-export/`

Process a single export item (dataset or file) for a scheduled export run. Validates run and tenant, applies business rules (scope, access), prepares payload or signed URL.

**Request Body:**
```json
{
  "run_id": "770e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "item_id": "880e8400-e29b-41d4-a716-446655440000"
}
```

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "item_id": "880e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "status": "ready",
  "upload_method": "direct",
  "upload_url": "s3://export-bucket/exports/sales/2026-02-03/dataset_123.parquet",
  "signed_url": null,
  "payload": null
}
```

**Response (200 OK)** - If signed URL required:
```json
{
  "item_id": "880e8400-e29b-41d4-a716-446655440000",
  "item_type": "dataset",
  "status": "ready",
  "upload_method": "signed_url",
  "upload_url": "s3://export-bucket/exports/sales/2026-02-03/dataset_123.parquet",
  "signed_url": "https://export-bucket.s3.amazonaws.com/exports/sales/2026-02-03/dataset_123.parquet?X-Amz-Algorithm=...",
  "payload": null
}
```

### Get Config

**GET** `/api/v1/scheduled-exports/internal/config/{scheduled_export_id}/`

Get scheduled export configuration for Prefect worker (without raw credentials).

**Path Parameters:**
- `scheduled_export_id` (UUID): Scheduled export UUID

**Request Headers:**
- `Authorization: ApiKey <worker-api-key>` (required)
- `X-Tenant-ID: <tenant-uuid>` (required if using environment-based key)

**Authentication**: Worker API key (required)

**Authorization**: Worker-only (requires `scheduled_export:internal` scope or `HUB_WORKER_API_KEY`)

**Rate Limiting**: **No rate limit**

**Response (200 OK):**
```json
{
  "scheduled_export_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Daily Sales Export",
  "destination_type": "S3",
  "destination_config": {
    "bucket": "export-bucket",
    "prefix": "exports/sales/",
    "access_key_id": "***masked***",
    "secret_access_key": "***masked***"
  },
  "schedule_config": {
    "cron": "0 2 * * *"
  },
  "source_scope": {
    "asset_ids": ["770e8400-e29b-41d4-a716-446655440000"],
    "dataset_ids": [],
    "file_ids": [],
    "contract_id": null
  },
  "status": "ACTIVE"
}
```

**Security**: Credentials in `destination_config` are **masked** (e.g., `***masked***`) or omitted. Worker must not log full config. See runbooks for credential handling.

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Tenant mismatch
- `404 Not Found`: Scheduled export not found

---

## Rate Limiting

### Public API Endpoints

Public scheduled export endpoints are rate-limited per tenant and per user:

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

Internal worker endpoints (`/api/v1/scheduled-exports/internal/*`) are not subject to rate limiting as they are:
- Used exclusively by Prefect workers (controlled infrastructure)
- Authenticated via worker API keys (not user-facing)
- Required for reliable workflow execution

---

## OpenAPI Schema

Internal worker API endpoints are tagged **"Internal (Worker)"** in the OpenAPI schema and can be:
- Excluded from public API documentation
- Documented separately (see this document)

Public API endpoints are tagged **"Scheduled Exports"** in the OpenAPI schema.

---

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-02-03T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "field_name",
          "message": "Field-specific error",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

**Common Error Codes:**
- `VALIDATION_ERROR`: Request validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Insufficient permissions
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `SERVICE_UNAVAILABLE`: Prefect service unavailable (503)

---

## Related Documentation

- [Scheduled Export Guide](SCHEDULED_EXPORT_GUIDE.md) - User and operator guide
- [Runbooks](../runbooks/RB-SCHEDULED-EXPORT-001.md) - Operational procedures
- [Services Architecture](SERVICES_ARCHITECTURE.md#scheduled-export-execution-model) - Execution model
- [OpenAPI Schema](../api-docs/openapi.json) - Complete API schema
