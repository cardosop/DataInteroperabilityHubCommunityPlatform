# Meshant Audit API

The Audit API provides read access to the immutable audit log maintained
by the Meshant platform. Every state-changing action -- user logins, data
uploads, contract changes, permission grants -- is recorded and queryable
through this API.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/audit/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /audit/ | List audit events with filtering and pagination |
| GET | /audit/{id}/ | Get a single audit event by ID |
| GET | /audit/summary/ | Aggregated event counts grouped by action or actor |
| POST | /audit/export/ | Start an async export of audit events to CSV or JSON |
| GET | /audit/export/{job_id}/ | Check the status of an audit export job |
| GET | /audit/export/{job_id}/download/ | Download the completed export file |

## Request / Response Examples

### GET /audit/?actor=usr_abc123&action=login&since=2026-04-01

**Response 200:**

```json
{
  "count": 12,
  "next": null,
  "results": [
    {
      "id": "evt_001",
      "actor": "usr_abc123",
      "action": "login",
      "resource_type": "session",
      "resource_id": "sess_xyz",
      "ip_address": "203.0.113.42",
      "timestamp": "2026-04-08T09:15:00Z",
      "metadata": {}
    }
  ]
}
```

### POST /audit/export/

**Request body:**

```json
{
  "format": "csv",
  "since": "2026-01-01T00:00:00Z",
  "until": "2026-04-01T00:00:00Z",
  "actions": ["login", "dataset.create", "contract.update"]
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `actor` (string) -- Filter by user ID.
- `action` (string) -- Filter by action type (e.g., `login`, `dataset.create`).
- `resource_type` (string) -- Filter by resource type.
- `since` (datetime) -- Only events after this timestamp (ISO 8601).
- `until` (datetime) -- Only events before this timestamp (ISO 8601).

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 403 | `AUDIT_FORBIDDEN` | Caller lacks audit read permission |
| 404 | `AUDIT_EVENT_NOT_FOUND` | Event ID does not exist |
| 404 | `AUDIT_EXPORT_NOT_FOUND` | Export job ID does not exist |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub audit`](../cli-reference/audit.md)
- SDK: [`AuditAPI`](../sdk-reference/python/audit.md)
