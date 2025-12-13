# API Endpoints Reference

Complete reference for all API endpoints in the Data Interoperability Hub API v1.

## Table of Contents

1. [Contracts](#contracts)
2. [Lineage](#lineage)
3. [Assets](#assets)
4. [Datasets](#datasets)
5. [Search](#search)
6. [Observability](#observability)
7. [Authentication](#authentication)

---

## Contracts

### List Contracts

**GET** `/api/v1/contracts/`

List all contracts with filtering, sorting, and pagination.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields (comma-separated, prefix with `-` for descending)
- `owner_email` (string): Filter by owner email (case-insensitive)
- `owner_name` (string): Filter by owner name (case-insensitive partial match)
- `tag` (string): Filter by tag (can specify multiple)
- `quality_profile` (string): Filter by quality profile key
- `compliance_regime` (string): Filter by compliance jurisdiction
- `contact_email` (string): Filter by contact email (case-insensitive)
- `contact_name` (string): Filter by contact name (case-insensitive partial match)
- `server_type` (string): Filter by server type
- `server_url` (string): Filter by server URL (case-insensitive partial match)
- `min_availability` (float): Filter by minimum availability SLA
- `max_latency_ms` (float): Filter by maximum latency SLA
- `model_name` (string): Filter by model name

**Response (200 OK):**
```json
{
  "count": 100,
  "page": 1,
  "page_size": 50,
  "total_pages": 2,
  "has_next": true,
  "has_previous": false,
  "next_page": 2,
  "previous_page": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "hub_contract_json": {
        "hub_contract_version": "1.0.0",
        "id": "contract-1",
        "info": {"name": "Contract 1"}
      },
      "status": "ACTIVE",
      "normalization_status": "NORMALIZED_OK",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Get Contract

**GET** `/api/v1/contracts/{id}/`

Retrieve a specific contract by ID.

**Path Parameters:**
- `id` (UUID): Contract UUID

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {
    "hub_contract_version": "1.0.0",
    "id": "contract-1",
    "info": {"name": "Contract 1"},
    "contact": [{"email": "support@example.com"}],
    "servers": [{"type": "s3", "url": "s3://bucket"}],
    "models": [{"name": "model1", "fields": []}]
  },
  "status": "ACTIVE",
  "normalization_status": "NORMALIZED_OK",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Create Contract

**POST** `/api/v1/contracts/`

Create a new contract from ODCS format.

**Request Body:**
```json
{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"contract-1\",\"name\":\"Contract 1\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}",
  "original_format": "JSON",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {...},
  "status": "ACTIVE",
  "normalization_status": "NORMALIZED_OK"
}
```

### Update Contract

**PATCH** `/api/v1/contracts/{id}/`

Update a contract (partial update supported).

**Request Body:**
```json
{
  "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"contract-1\",\"name\":\"Updated Contract 1\",\"schema\":{\"fields\":[{\"name\":\"id\",\"type\":\"string\"}]}}"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_contract_json": {...},
  "status": "ACTIVE"
}
```

### Delete Contract

**DELETE** `/api/v1/contracts/{id}/`

Delete a contract (soft delete: sets status to RETIRED).

**Response (204 No Content)**

---

## Lineage

### Get Contract-Level Lineage

**GET** `/api/v1/contracts/{id}/lineage/contracts/`

Get contract-level lineage including contract references.

**Response (200 OK):**
```json
{
  "contracts": [
    {
      "namespace": "ns1",
      "name": "source-contract",
      "version": "1.0.0"
    }
  ],
  "entries": [
    {
      "input_fields": [...],
      "transformations": [...]
    }
  ]
}
```

### Get Model-Level Lineage

**GET** `/api/v1/contracts/{id}/models/{model_name}/lineage/`

Get lineage for a specific model.

**Path Parameters:**
- `id` (UUID): Contract UUID
- `model_name` (string): Model name

**Response (200 OK):**
```json
{
  "model_name": "customer",
  "lineage": {
    "models": [...],
    "entries": [...]
  }
}
```

### Get Field-Level Lineage

**GET** `/api/v1/contracts/{id}/fields/{field_name}/lineage/`

Get lineage for a specific field.

**Path Parameters:**
- `id` (UUID): Contract UUID
- `field_name` (string): Field name

**Response (200 OK):**
```json
{
  "field_name": "email",
  "model_name": "customer",
  "lineage": {
    "input_fields": [
      {
        "namespace": "ns1",
        "name": "source-contract",
        "model_name": "source-model",
        "field": "email_address"
      }
    ],
    "transformations": [
      {
        "logic": "LOWER(email_address)"
      }
    ]
  }
}
```

### Get Full Hierarchical Lineage

**GET** `/api/v1/contracts/{id}/lineage/full/`

Get complete hierarchical lineage (contract, model, and field levels).

**Query Parameters:**
- `max_contract_depth` (integer): Maximum contract depth (default: 10)
- `max_model_depth` (integer): Maximum model depth (default: 10)
- `max_field_depth` (integer): Maximum field depth (default: 10)

**Response (200 OK):**
```json
{
  "upstream": {...},
  "downstream": {...}
}
```

### Get Lineage Visualization

**GET** `/api/v1/contracts/{id}/lineage/visualization/`

Get lineage graph in various visualization formats.

**Query Parameters:**
- `format` (string): Visualization format - `json`, `dot`, or `mermaid` (default: `json`)

**Response (200 OK):**
- JSON format: JSON object for D3.js
- DOT format: Text string for Graphviz
- Mermaid format: Text string for Mermaid

---

## Assets

### List Assets

**GET** `/api/v1/assets/`

List all assets with filtering and pagination.

**Query Parameters:**
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `status` (string): Filter by status
- `type` (string): Filter by asset type

**Response (200 OK):**
```json
{
  "count": 50,
  "results": [...]
}
```

### Get Asset

**GET** `/api/v1/assets/{id}/`

Retrieve a specific asset by ID.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Asset 1",
  "type": "DATASET",
  "status": "ACTIVE"
}
```

---

## Datasets

### List Datasets

**GET** `/api/v1/datasets/`

List all datasets with filtering and pagination.

**Response (200 OK):**
```json
{
  "count": 50,
  "results": [...]
}
```

### Get Dataset

**GET** `/api/v1/datasets/{id}/`

Retrieve a specific dataset by ID.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Dataset 1",
  "status": "ACTIVE"
}
```

---

## Search

### Search

**GET** `/api/v1/search/`

Full-text search across contracts and assets.

**Query Parameters:**
- `q` (string): Search query string
- `type` (string): Filter by type (contract, asset, dataset)
- `classification` (string): Filter by data classification
- `owner` (string): Filter by owner
- `tags` (string): Filter by tags
- `domain` (string): Filter by domain
- `quality_status` (string): Filter by quality status
- `compliance_status` (string): Filter by compliance status
- `limit` (integer): Maximum results (default: 50)
- `offset` (integer): Result offset (default: 0)
- `sort_by` (string): Sort field (default: relevance)
- `sort_order` (string): Sort order - `asc` or `desc` (default: desc)

**Response (200 OK):**
```json
{
  "count": 10,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "contract",
      "name": "Contract 1",
      "relevance_score": 0.95
    }
  ]
}
```

### Search Suggestions

**GET** `/api/v1/search/suggestions/`

Get search suggestions/autocomplete.

**Query Parameters:**
- `q` (string): Search query string
- `limit` (integer): Maximum suggestions (default: 10)

**Response (200 OK):**
```json
{
  "suggestions": [
    "customer data",
    "customer analytics",
    "customer profile"
  ]
}
```

---

## Observability

### Get Freshness Metrics

**GET** `/api/v1/observability/freshness/`

Get data freshness monitoring metrics.

**Query Parameters:**
- `dataset_id` (UUID): Filter by dataset ID
- `start_date` (datetime): Start date for metrics
- `end_date` (datetime): End date for metrics

**Response (200 OK):**
```json
{
  "metrics": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "last_update": "2025-01-15T10:30:00Z",
      "freshness_age_hours": 2.5,
      "is_stale": false
    }
  ]
}
```

### Get Volume Metrics

**GET** `/api/v1/observability/volume/`

Get data volume monitoring metrics.

**Response (200 OK):**
```json
{
  "metrics": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "row_count": 1000000,
      "size_bytes": 1073741824,
      "timestamp": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Get Schema Drift

**GET** `/api/v1/observability/schema-drift/`

Get schema drift detection results.

**Response (200 OK):**
```json
{
  "drifts": [
    {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "detected_at": "2025-01-15T10:30:00Z",
      "changes": [
        {
          "type": "field_added",
          "field": "new_field",
          "field_type": "string"
        }
      ]
    }
  ]
}
```

---

## Authentication

### Login

**POST** `/api/v1/auth/login/`

Authenticate user and get access token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Refresh Token

**POST** `/api/v1/auth/refresh/`

Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

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
    "timestamp": "2025-01-15T10:30:00Z",
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

See [API Error Codes](./API_ERROR_CODES.md) for complete error code reference.

---

## Additional Resources

- [API Best Practices](./API_BEST_PRACTICES.md)
- [API Error Codes](./API_ERROR_CODES.md)
- [Interactive Documentation](../api-docs/)
- [OpenAPI Schema](../api-docs/openapi.json)

