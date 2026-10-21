# Meshant Platform API

The Platform API exposes administrative configuration endpoints for the
Meshant deployment. It provides health checks for monitoring, tenant-level
settings management, and feature flag controls that gate access to
experimental or gradually-rolled-out capabilities.

## Authentication

Health and readiness endpoints are **public**. All other endpoints require
a valid JWT bearer token or API key in the `Authorization` header.
See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/platform/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /platform/health/ | Liveness check (returns 200 if the service is up) |
| GET | /platform/ready/ | Readiness check (returns 200 when all dependencies are healthy) |
| GET | /platform/version/ | Return the current API version and build metadata |
| GET | /platform/settings/ | Get tenant-level platform settings |
| PUT | /platform/settings/ | Update tenant-level platform settings |
| GET | /platform/features/ | List feature flags and their states |
| GET | /platform/features/{key}/ | Get a single feature flag by key |
| PUT | /platform/features/{key}/ | Enable or disable a feature flag (admin only) |
| GET | /platform/regions/ | List available deployment regions |
| GET | /platform/maintenance/ | Check scheduled maintenance windows |

## Request / Response Examples

### GET /platform/health/

**Response 200:**

```json
{
  "status": "healthy",
  "timestamp": "2026-04-09T18:00:00Z"
}
```

### GET /platform/ready/

**Response 200:**

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "search_index": "ok",
    "object_storage": "ok"
  }
}
```

### GET /platform/features/

**Response 200:**

```json
{
  "features": [
    {"key": "semantic_search_v2", "enabled": true, "rollout_pct": 100},
    {"key": "marketplace_subscriptions", "enabled": false, "rollout_pct": 0},
    {"key": "advanced_lineage", "enabled": true, "rollout_pct": 25}
  ]
}
```

### PUT /platform/settings/

**Request body:**

```json
{
  "default_page_size": 25,
  "max_upload_size_mb": 512,
  "require_mfa": true,
  "allowed_ip_ranges": ["10.0.0.0/8", "203.0.113.0/24"]
}
```

## Common Parameters

- `page` (int) -- Page number for pagination (features list).
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `key` (string) -- Feature flag key identifier.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 403 | `PLATFORM_ADMIN_REQUIRED` | Only tenant admins can modify settings or flags |
| 404 | `PLATFORM_FEATURE_NOT_FOUND` | Feature flag key does not exist |
| 422 | `PLATFORM_SETTING_INVALID` | A setting value is outside the allowed range |
| 503 | `PLATFORM_NOT_READY` | One or more dependency checks failed |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub platform`](../cli-reference/platform.md)
- SDK: [`PlatformAPI`](../sdk-reference/python/platform.md)
