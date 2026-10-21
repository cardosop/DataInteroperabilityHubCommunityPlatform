# Meshant Jobs API

The Jobs API provides visibility into asynchronous background tasks
running on the Meshant platform. Schema inference, data quality checks,
compliance scans, and exports all create trackable jobs whose status
and results can be polled through this API.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/jobs/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /jobs/ | List jobs in the current tenant |
| GET | /jobs/{id}/ | Get job details and current status |
| POST | /jobs/{id}/cancel/ | Cancel a running or queued job |
| GET | /jobs/{id}/logs/ | Stream or fetch log output for a job |
| GET | /jobs/{id}/result/ | Retrieve the result payload of a completed job |
| DELETE | /jobs/{id}/ | Delete a completed job and its artifacts |

## Job States

| State | Description |
|-------|-------------|
| `queued` | Job is waiting to be picked up by a worker |
| `running` | Job is actively executing |
| `completed` | Job finished successfully |
| `failed` | Job terminated with an error |
| `cancelled` | Job was cancelled by a user |

## Request / Response Examples

### GET /jobs/{id}/

**Response 200:**

```json
{
  "id": "job_xyz789",
  "type": "schema_inference",
  "state": "completed",
  "resource_type": "dataset",
  "resource_id": "ds_abc123",
  "progress_pct": 100,
  "started_at": "2026-04-09T10:31:00Z",
  "completed_at": "2026-04-09T10:31:45Z",
  "error": null
}
```

### POST /jobs/{id}/cancel/

**Response 200:**

```json
{
  "id": "job_xyz789",
  "state": "cancelled"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `state` (string) -- Filter by job state.
- `type` (string) -- Filter by job type (e.g., `schema_inference`, `dq_check`).
- `resource_id` (string) -- Filter by the related resource ID.
- `since` (datetime) -- Only jobs created after this timestamp (ISO 8601).

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 404 | `JOB_NOT_FOUND` | Job ID does not exist |
| 409 | `JOB_NOT_CANCELLABLE` | Job has already completed or failed |
| 409 | `JOB_RESULT_NOT_READY` | Result requested for a job that has not completed |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub jobs`](../cli-reference/jobs.md)
- SDK: [`JobsAPI`](../sdk-reference/python/jobs.md)
