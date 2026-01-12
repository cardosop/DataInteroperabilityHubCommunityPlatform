# Marketplace Integration API Reference

Complete API reference for the Marketplace Integration Framework.

**Last Updated**: 2026-01-10
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URLs](#base-urls)
4. [Marketplace Connections API](#marketplace-connections-api)
5. [Marketplace Sync Jobs API](#marketplace-sync-jobs-api)
6. [Marketplace Mappings API](#marketplace-mappings-api)
7. [Request/Response Schemas](#requestresponse-schemas)
8. [Error Responses](#error-responses)
9. [Rate Limiting](#rate-limiting)
10. [OpenAPI/Swagger Examples](#openapiswagger-examples)

---

## Overview

The Marketplace Integration API provides endpoints for managing marketplace connections, synchronization jobs, and mappings between Hub assets and external marketplace listings.

### Key Features

- **Connection Management**: Create, update, test, and delete marketplace connections
- **Sync Job Management**: Create, monitor, and cancel synchronization jobs
- **Mapping Management**: View and delete marketplace mappings
- **Multi-Tenant Support**: All operations are tenant-scoped
- **RBAC/ABAC Authorization**: Role-based and attribute-based access control
- **Rate Limiting**: Built-in rate limiting for all endpoints
- **Comprehensive Filtering**: Filter, search, and paginate results

### API Version

All endpoints are under `/api/v1/integrations/marketplace/`.

---

## Authentication

All endpoints require authentication. Two authentication methods are supported:

### JWT Token Authentication

```bash
# Login to get token
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"password"}'

# Use token in requests
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/marketplace/connections/
```

### API Key Authentication

```bash
curl -H "X-API-Key: <api-key>" \
  http://localhost:8000/api/v1/integrations/marketplace/connections/
```

---

## Base URLs

- **Development**: `http://localhost:8000`
- **Staging**: `https://staging-api.datahub.example.com`
- **Production**: `https://api.datahub.example.com`

---

## Marketplace Connections API

### List Marketplace Connections

List all marketplace connections for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/`

**Authentication**: Required

**Authorization**:
- Read: Authenticated user (tenant-scoped)
- Write: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Query Parameters**:
- `marketplace_type` (string, optional): Filter by marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `search` (string, optional): Search in connection name
- `ordering` (string, optional): Order by field (e.g., `name`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 10,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/connections/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
      "name": "Snowflake Production",
      "is_active": true,
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:00:00Z"
    }
  ]
}
```

### Get Marketplace Connection

Get detailed information about a specific marketplace connection.

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

**Note**: The `config` field is not returned in responses for security reasons. Use the test endpoint to verify connection configuration.

### Create Marketplace Connection

Create a new marketplace connection.

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "test_token",
    "warehouse": "COMPUTE_WH",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

**Response**: `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors (invalid marketplace_type, missing required fields, etc.)
- `409 Conflict`: Connection name already exists for tenant
- `429 Too Many Requests`: Rate limit exceeded

### Update Marketplace Connection

Update an existing marketplace connection.

**Endpoint**: `PUT /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "name": "Snowflake Production Updated",
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "new_token",
    "warehouse": "COMPUTE_WH",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production Updated",
  "is_active": true,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z"
}
```

### Partially Update Marketplace Connection

Partially update an existing marketplace connection.

**Endpoint**: `PATCH /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "is_active": false
}
```

**Response**: `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "Snowflake Production",
  "is_active": false,
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z"
}
```

### Delete Marketplace Connection

Delete a marketplace connection.

**Endpoint**: `DELETE /api/v1/integrations/marketplace/connections/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Response**: `204 No Content`

**Error Responses**:
- `404 Not Found`: Connection not found
- `409 Conflict`: Connection has active sync jobs or mappings

### Test Marketplace Connection

Test a marketplace connection.

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{id}/test/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**: (optional)

```json
{
  "config": {
    "account": "test_account",
    "user": "test_user",
    "token": "test_token"
  }
}
```

**Response**: `200 OK`

```json
{
  "success": true,
  "message": "Connection test successful",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "tested_at": "2026-01-10T10:00:00Z"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid configuration
- `401 Unauthorized`: Authentication failed
- `404 Not Found`: Connection not found
- `500 Internal Server Error`: Connection test failed

---

## Marketplace Sync Jobs API

### List Marketplace Sync Jobs

List all marketplace sync jobs for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/sync/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Query Parameters**:
- `connection_id` (UUID, optional): Filter by connection ID
- `direction` (string, optional): Filter by sync direction (`PULL`, `PUSH`, `BIDIRECTIONAL`)
- `status` (string, optional): Filter by status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`)
- `ordering` (string, optional): Order by field (e.g., `created_at`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 25,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/sync/?page=2",
  "previous": null,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "direction": "PULL",
      "status": "COMPLETED",
      "items_synced": 100,
      "items_failed": 0,
      "errors": [],
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:05:00Z",
      "completed_at": "2026-01-10T10:05:00Z"
    }
  ]
}
```

### Get Marketplace Sync Job

Get detailed information about a specific marketplace sync job.

**Endpoint**: `GET /api/v1/integrations/marketplace/sync/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "COMPLETED",
  "items_synced": 100,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {},
    "options": {}
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:05:00Z",
  "completed_at": "2026-01-10T10:05:00Z"
}
```

### Create Marketplace Sync Job

Create a new marketplace sync job.

**Endpoint**: `POST /api/v1/integrations/marketplace/sync/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body** (PULL sync):

```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "listing_ids": null,
  "filters": {
    "category": "health"
  },
  "options": {
    "dry_run": false,
    "data_strategy": "METADATA_ONLY"
  }
}
```

**Request Body** (PUSH sync):

```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "asset_ids": [
    "770e8400-e29b-41d4-a716-446655440000",
    "880e8400-e29b-41d4-a716-446655440000"
  ],
  "options": {
    "dry_run": false
  }
}
```

**Response**: `201 Created`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "data_strategy": "METADATA_ONLY",
    "filters": {
      "category": "health"
    },
    "options": {
      "dry_run": false
    }
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z",
  "completed_at": null
}
```

**Error Responses**:
- `400 Bad Request`: Validation errors (invalid connection_id, missing required fields, etc.)
- `404 Not Found`: Connection not found
- `429 Too Many Requests`: Rate limit exceeded

**Note**: Sync jobs are executed asynchronously. Use the GET endpoint to monitor progress.

### Cancel Marketplace Sync Job

Cancel a running marketplace sync job.

**Endpoint**: `POST /api/v1/integrations/marketplace/sync/{id}/cancel/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Request Body**:

```json
{
  "reason": "User requested cancellation"
}
```

**Response**: `200 OK`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "direction": "PULL",
  "status": "CANCELLED",
  "items_synced": 50,
  "items_failed": 0,
  "errors": [],
  "metadata": {
    "cancellation_reason": "User requested cancellation"
  },
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:03:00Z",
  "completed_at": "2026-01-10T10:03:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Job cannot be cancelled (already completed/failed/cancelled)
- `404 Not Found`: Sync job not found
- `429 Too Many Requests`: Rate limit exceeded

---

## Marketplace Mappings API

### List Marketplace Mappings

List all marketplace mappings for the authenticated user's tenant.

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Query Parameters**:
- `connection_id` (UUID, optional): Filter by connection ID
- `hub_asset_id` (UUID, optional): Filter by hub asset ID
- `external_listing_id` (string, optional): Filter by external listing ID
- `ordering` (string, optional): Order by field (e.g., `created_at`, `-created_at`). Prefix with `-` for descending.
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Response**: `200 OK`

```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/integrations/marketplace/mappings/?page=2",
  "previous": null,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "connection": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Snowflake Production",
        "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
      },
      "hub_asset": {
        "id": "880e8400-e29b-41d4-a716-446655440000",
        "name": "Sample Dataset",
        "status": "ACTIVE"
      },
      "external_listing_id": "SNOWFLAKE_SAMPLE_DATA",
      "external_resource_ids": ["SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1"],
      "sync_metadata": {
        "last_sync_status": "SUCCESS",
        "last_sync_errors": []
      },
      "last_synced_at": "2026-01-10T10:00:00Z",
      "created_at": "2026-01-10T10:00:00Z",
      "updated_at": "2026-01-10T10:00:00Z"
    }
  ]
}
```

### Get Marketplace Mapping

Get detailed information about a specific marketplace mapping.

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/{id}/`

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response**: `200 OK`

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "connection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Snowflake Production",
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"
  },
  "hub_asset": {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "name": "Sample Dataset",
    "status": "ACTIVE"
  },
  "external_listing_id": "SNOWFLAKE_SAMPLE_DATA",
  "external_resource_ids": ["SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1"],
  "sync_metadata": {
    "last_sync_status": "SUCCESS",
    "last_sync_errors": []
  },
  "last_synced_at": "2026-01-10T10:00:00Z",
  "created_at": "2026-01-10T10:00:00Z",
  "updated_at": "2026-01-10T10:00:00Z"
}
```

### Delete Marketplace Mapping

Delete a marketplace mapping.

**Endpoint**: `DELETE /api/v1/integrations/marketplace/mappings/{id}/`

**Authentication**: Required

**Authorization**: DATA_PROVIDER or TENANT_ADMIN role + `integrations:write` scope

**Response**: `204 No Content`

**Error Responses**:
- `404 Not Found`: Mapping not found
- `429 Too Many Requests`: Rate limit exceeded

**Note**: Mappings are created automatically during sync operations. They cannot be created manually via API.

---

## Request/Response Schemas

### MarketplaceConnection Schema

```json
{
  "id": "UUID",
  "marketplace_type": "string (enum: SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE, ...)",
  "name": "string (max 255 chars, unique per tenant)",
  "is_active": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Note**: The `config` field is encrypted and not returned in API responses.

### MarketplaceSyncJob Schema

```json
{
  "id": "UUID",
  "connection": {
    "id": "UUID",
    "name": "string",
    "marketplace_type": "string"
  },
  "direction": "string (enum: PULL, PUSH, BIDIRECTIONAL)",
  "status": "string (enum: PENDING, RUNNING, COMPLETED, FAILED, PARTIAL, CANCELLED)",
  "items_synced": "integer",
  "items_failed": "integer",
  "errors": ["string"],
  "metadata": {
    "data_strategy": "string (enum: METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL)",
    "filters": {},
    "options": {},
    "cancellation_reason": "string (optional)"
  },
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "completed_at": "ISO 8601 datetime (nullable)"
}
```

### MarketplaceMapping Schema

```json
{
  "id": "UUID",
  "connection": {
    "id": "UUID",
    "name": "string",
    "marketplace_type": "string"
  },
  "hub_asset": {
    "id": "UUID",
    "name": "string",
    "status": "string"
  },
  "external_listing_id": "string",
  "external_resource_ids": ["string"],
  "sync_metadata": {
    "last_sync_status": "string",
    "last_sync_errors": ["string"]
  },
  "last_synced_at": "ISO 8601 datetime (nullable)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

### Create Connection Request Schema

```json
{
  "marketplace_type": "string (required, enum)",
  "name": "string (required, max 255 chars)",
  "config": {
    "account": "string (Snowflake)",
    "user": "string (Snowflake)",
    "token": "string (Snowflake)",
    "warehouse": "string (Snowflake, optional)",
    "role": "string (Snowflake, optional)",
    "base_url": "string (CKAN)",
    "api_key": "string (CKAN)",
    "aws_access_key_id": "string (AWS)",
    "aws_secret_access_key": "string (AWS)",
    "region_name": "string (AWS, optional)",
    "project_id": "string (GCP)",
    "credentials_json": "string (GCP, optional)",
    "host": "string (Databricks)",
    "token": "string (Databricks)",
    "cluster_id": "string (Databricks, optional)"
  },
  "is_active": "boolean (optional, default: true)"
}
```

### Create Sync Job Request Schema (PULL)

```json
{
  "connection_id": "UUID (required)",
  "direction": "PULL (required)",
  "listing_ids": ["string"] (optional),
  "filters": {
    "category": "string",
    "tags": ["string"],
    "provider": "string"
  } (optional),
  "options": {
    "dry_run": "boolean (optional, default: false)",
    "data_strategy": "string (optional, enum: METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL, default: METADATA_ONLY)",
    "limit": "integer (optional)"
  } (optional)
}
```

### Create Sync Job Request Schema (PUSH)

```json
{
  "connection_id": "UUID (required)",
  "direction": "PUSH (required)",
  "asset_ids": ["UUID"] (required),
  "options": {
    "dry_run": "boolean (optional, default: false)"
  } (optional)
}
```

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": "Error message",
  "details": {
    "field_name": ["Error message for field"]
  }
}
```

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `204 No Content`: Resource deleted successfully
- `400 Bad Request`: Validation errors, invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate name, active sync jobs)
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Common Error Responses

#### 400 Bad Request - Validation Error

```json
{
  "error": "Validation failed",
  "details": {
    "marketplace_type": ["Invalid marketplace type"],
    "name": ["This field is required"]
  }
}
```

#### 401 Unauthorized

```json
{
  "error": "Authentication credentials were not provided"
}
```

#### 403 Forbidden

```json
{
  "error": "You do not have permission to perform this action"
}
```

#### 404 Not Found

```json
{
  "error": "Marketplace connection not found"
}
```

#### 409 Conflict

```json
{
  "error": "Connection name already exists for this tenant"
}
```

#### 429 Too Many Requests

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

---

## Rate Limiting

All endpoints are rate-limited to prevent abuse and ensure fair usage.

### Rate Limit Headers

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1641900000
```

### Rate Limit Exceeded

When rate limit is exceeded, the API returns `429 Too Many Requests` with a `retry_after` value indicating when to retry.

---

## OpenAPI/Swagger Examples

### OpenAPI 3.0 Specification

The API follows OpenAPI 3.0 specification. The complete OpenAPI schema is available at:

- **Development**: `http://localhost:8000/api/schema/`
- **Staging**: `https://staging-api.datahub.example.com/api/schema/`
- **Production**: `https://api.datahub.example.com/api/schema/`

### Swagger UI

Interactive API documentation is available via Swagger UI:

- **Development**: `http://localhost:8000/api/docs/`
- **Staging**: `https://staging-api.datahub.example.com/api/docs/`
- **Production**: `https://api.datahub.example.com/api/docs/`

### Example: Create Connection (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/integrations/marketplace/connections/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "name": "Snowflake Production",
    "config": {
      "account": "test_account",
      "user": "test_user",
      "token": "test_token",
      "warehouse": "COMPUTE_WH",
      "role": "ACCOUNTADMIN"
    },
    "is_active": true
  }'
```

### Example: Create Connection (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/connections/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "name": "Snowflake Production",
    "config": {
        "account": "test_account",
        "user": "test_user",
        "token": "test_token",
        "warehouse": "COMPUTE_WH",
        "role": "ACCOUNTADMIN"
    },
    "is_active": True
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Example: Create Sync Job (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/integrations/marketplace/sync/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "direction": "PULL",
    "filters": {
      "category": "health"
    },
    "options": {
      "dry_run": false,
      "data_strategy": "METADATA_ONLY"
    }
  }'
```

### Example: Create Sync Job (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/sync/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "direction": "PULL",
    "filters": {
        "category": "health"
    },
    "options": {
        "dry_run": False,
        "data_strategy": "METADATA_ONLY"
    }
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Example: List Connections with Filtering (cURL)

```bash
curl -X GET "http://localhost:8000/api/v1/integrations/marketplace/connections/?marketplace_type=SNOWFLAKE_DATA_MARKETPLACE&is_active=true&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Example: List Connections with Filtering (Python)

```python
import requests

url = "http://localhost:8000/api/v1/integrations/marketplace/connections/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN"
}
params = {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "is_active": True,
    "page": 1,
    "page_size": 10
}

response = requests.get(url, headers=headers, params=params)
print(response.json())
```

---

## Additional Resources

- **Framework Architecture**: `docs/MARKETPLACE_INTEGRATION_FRAMEWORK.md` - Complete architecture documentation
- **Connector Development Guide**: `docs/MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md` - Connector implementation guide
- **API Standards**: `docs/API_STANDARDS.md` - API standards and conventions
- **API Error Codes**: `docs/API_ERROR_CODES.md` - Complete error code reference

---

**Last Updated**: 2026-01-10
**Version**: 1.0.0
