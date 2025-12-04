# API Documentation

Complete API documentation for the Interoperable Data Hub REST API v1.

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [API Endpoints](#api-endpoints)
5. [Request/Response Format](#requestresponse-format)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [OpenAPI Schema](#openapi-schema)
9. [Interactive Documentation](#interactive-documentation)

---

## Overview

The Interoperable Data Hub provides a RESTful API (v1) for managing data assets, contracts, datasets, compliance, data quality, and marketplace operations.

**API Version**: v1  
**Content Type**: `application/json`  
**Character Encoding**: UTF-8

---

## Base URL

### Environments

- **Production**: `https://api.hub.example.com/api/v1`
- **Staging**: `https://api-staging.hub.example.com/api/v1`
- **Local Development**: `http://localhost:8000/api/v1`

### Versioning

The API uses URL-based versioning. The current version is `/api/v1`. Future versions will be `/api/v2`, `/api/v3`, etc.

---

## Authentication

The API uses JWT (JSON Web Tokens) for authentication.

### Getting an Access Token

```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Using the Access Token

Include the token in the `Authorization` header:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Refreshing the Token

```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### API Keys (Alternative)

For service-to-service authentication, API keys are supported:

```bash
Authorization: ApiKey your-api-key-here
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login/` | User login |
| POST | `/auth/refresh/` | Refresh access token |
| POST | `/auth/logout/` | User logout |
| POST | `/auth/register/` | User registration |

### Tenants

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tenants/` | List tenants |
| POST | `/tenants/` | Create tenant |
| GET | `/tenants/{id}/` | Get tenant details |
| PATCH | `/tenants/{id}/` | Update tenant |
| POST | `/tenants/{id}/suspend/` | Suspend tenant |
| POST | `/tenants/{id}/activate/` | Activate tenant |

### Tenant Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tenants/{id}/config/` | Get tenant configuration |
| PATCH | `/tenants/{id}/config/` | Update tenant configuration (partial) |

**Authorization**: Requires `TENANT_ADMIN` role (for own tenant) or Platform Admin (for any tenant).

**GET /tenants/{id}/config/**  
Returns tenant configuration with platform defaults for any unset values. Response format matches API spec §13.1.

**Example Request:**
```bash
GET /api/v1/tenants/{tenant_id}/config/
Authorization: Bearer <token>
```

**Example Response (200 OK):**
```json
{
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "default_dq_profile": "intake_basic_gx",
  "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"],
  "default_compliance_regimes": ["GDPR", "LGPD"],
  "data_retention_days": 2555,
  "rate_limits": {
    "dq_runs": {
      "burst_per_10s": 20,
      "sustained_per_min": 60,
      "daily_cap": 10000
    },
    "file_uploads": {
      "burst_per_10s": 10,
      "sustained_per_min": 30
    }
  },
  "max_file_size_bytes": 10737418240,
  "max_job_concurrency": 5,
  "max_queued_jobs": 50,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**PATCH /tenants/{id}/config/**  
Updates tenant configuration (partial update). Only provided fields are updated. Response format matches API spec §13.2.

**Example Request:**
```bash
PATCH /api/v1/tenants/{tenant_id}/config/
Authorization: Bearer <token>
Content-Type: application/json

{
  "default_dq_profile": "intake_basic_soda",
  "data_retention_days": 1825,
  "rate_limits": {
    "dq_runs": {
      "daily_cap": 20000
    }
  }
}
```

**Example Response (200 OK):**  
Returns updated configuration in same format as GET response.

**Error Responses:**

| Status | Error Code | Description |
|--------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Invalid configuration values (e.g., invalid profile key, invalid regime, retention days out of range, rate limits exceed platform maximums) |
| 401 | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token |
| 403 | `AUTH_FORBIDDEN` | User is not `TENANT_ADMIN` for this tenant or platform admin |
| 404 | `TENANT_NOT_FOUND` | Tenant with given ID does not exist |

**Rate Limits Merge Behavior:**  
When updating `rate_limits`, the entire dictionary is replaced (not merged). To update a single category, include all desired categories in the request. Empty dict `{}` clears all rate limits and uses platform defaults.

**Null vs Empty Value Behavior:**
- `null` for list fields (e.g., `allowed_compliance_regimes: null`) uses platform default
- Empty list `[]` for list fields uses platform default (treated as falsy)
- `null` for dict fields (e.g., `rate_limits: null`) uses platform default
- Empty dict `{}` for `rate_limits` clears all rate limits and uses platform defaults

**Platform Defaults:**  
When a tenant has no specific configuration or a field is `null`/empty, platform defaults are used:
- `default_dq_profile`: `"intake_basic_gx"`
- `allowed_compliance_regimes`: `["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"]`
- `default_compliance_regimes`: `["GDPR", "LGPD"]`
- `data_retention_days`: `2555` (7 years)
- `max_file_size_bytes`: `10737418240` (10 GB)
- `max_job_concurrency`: `5`
- `max_queued_jobs`: `50`
- `rate_limits`: Platform defaults per category (see API spec §13.1)

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/` | List users |
| POST | `/users/` | Create user |
| GET | `/users/{id}/` | Get user details |
| PATCH | `/users/{id}/` | Update user |
| DELETE | `/users/{id}/` | Delete user |
| POST | `/users/invite/` | Invite user |

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/files/` | List files |
| POST | `/files/` | Upload file |
| GET | `/files/{id}/` | Get file details |
| DELETE | `/files/{id}/` | Delete file |
| POST | `/files/{id}/download/` | Get download URL |

### Datasets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/datasets/` | List datasets |
| POST | `/datasets/` | Create dataset |
| GET | `/datasets/{id}/` | Get dataset details |
| PATCH | `/datasets/{id}/` | Update dataset |
| DELETE | `/datasets/{id}/` | Delete dataset |

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/assets/` | List assets |
| POST | `/assets/` | Create asset |
| GET | `/assets/{id}/` | Get asset details |
| PATCH | `/assets/{id}/` | Update asset |
| DELETE | `/assets/{id}/` | Delete asset |
| POST | `/assets/{id}/activate/` | Activate asset |
| POST | `/assets/{id}/contracts/` | Attach contract to asset |

### Contracts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contracts/` | List contracts (with filtering and sorting) |
| POST | `/contracts/` | Create contract |
| GET | `/contracts/{id}/` | Get contract details |
| PATCH | `/contracts/{id}/` | Update contract |
| DELETE | `/contracts/{id}/` | Delete contract (soft delete) |
| POST | `/contracts/{id}/validate/` | Validate contract |
| POST | `/contracts/{id}/lint/` | Lint contract |
| POST | `/contracts/{id}/convert/` | Convert contract format |
| POST | `/contracts/{id}/migrate/` | Migrate contract version |

#### Contract Model

Contracts represent data contracts with normalized HubContract format. Each contract includes:

**Core Fields:**
- `id`: Contract UUID
- `tenant`: Tenant ID
- `asset`: Asset ID (optional, for contract-only assets)
- `version`: Contract version number
- `status`: Contract lifecycle status (`DRAFT`, `ACTIVE`, `RETIRED`)
- `original_spec_type`: Original spec type (`ODCS`, `DATACONTRACT_COM`)
- `original_spec_version`: Original spec version
- `original_format`: Original format (`JSON`, `YAML`)
- `original_raw`: Original contract content
- `hub_contract_version`: HubContract version (e.g., `1.0.0`)
- `hub_contract_json`: Normalized HubContract JSON with all sections

**Normalization Status:**
- `NORMALIZED_OK`: Contract normalized successfully
- `NORMALIZED_WITH_WARNINGS`: Normalized with warnings
- `NORMALIZATION_FAILED`: Normalization failed
- `NOT_NORMALIZED`: Not yet normalized

**Validation Status:**
- `VALID`: Contract is valid
- `INVALID`: Contract has errors
- `WARNING_ONLY`: Contract has warnings but no errors
- `ERROR`: Validation error occurred

**Computed Fields (extracted from `hub_contract_json`):**

1. **Owners** (`owners`): Array of contract owners
   ```json
   [
     {
       "name": "Data Platform Team",
       "email": "dataplatform@example.com"
     }
   ]
   ```

2. **Tags** (`tags`): Array of tags for organization
   ```json
   ["analytics", "sales", "orders"]
   ```

3. **Quality Rules** (`quality_rules`): Array of data quality rules
   ```json
   [
     {
       "rule_id": "not_null_order_id",
       "dimension": "completeness",
       "expression": "order_id IS NOT NULL",
       "severity": "ERROR",
       "field": "order_id"
     }
   ]
   ```

4. **Compliance Policy** (`compliance_policy`): Privacy and compliance requirements
   ```json
   {
     "contains_personal_data": true,
     "personal_data_categories": ["EMAIL", "PHONE"],
     "jurisdictions": ["GDPR", "LGPD"],
     "legal_bases": ["CONSENT", "CONTRACT"],
     "retention_policy": {
       "period": "P5Y",
       "notes": "5 years retention after contract end"
     }
   }
   ```

5. **Lifecycle Policy** (`lifecycle_policy`): Data refresh and SLA information
   ```json
   {
     "data_source": "OLTP.orders",
     "refresh_cadence": "DAILY",
     "slas": {
       "availability": "99.0",
       "latency_ms_p95": 5000
     }
   }
   ```

6. **Marketplace Policy** (`marketplace_policy`): Marketplace sharing and usage rules
   ```json
   {
     "license_summary": "MIT License",
     "intended_use": ["analytics", "machine_learning"],
     "restricted_use": ["resale"]
   }
   ```

7. **Schema Fields** (`schema_fields`): Array of schema fields with all properties
   ```json
   [
     {
       "name": "order_id",
       "data_type": "string",
       "nullable": false,
       "description": "Unique identifier for the order",
       "semantic_type": "ORDER_ID",
       "format": null,
       "pattern": "^ORD-[0-9]{8}$",
       "enum": null,
       "default": null,
       "min_length": 10,
       "max_length": 20,
       "minimum": null,
       "maximum": null,
       "metadata": {
         "source_system": "OLTP",
         "business_key": true
       },
       "is_primary_key": true,
       "is_unique": true,
       "is_indexed": true
     }
   ]
   ```

#### List Contracts

**GET /contracts/**

List contracts with enhanced filtering and sorting.

**Query Parameters:**
- `owner_email`: Filter by owner email (case-insensitive)
- `owner_name`: Filter by owner name (case-insensitive partial match)
- `tag`: Filter by tag (can specify multiple times)
- `quality_profile`: Filter by quality profile key (e.g., `intake_basic`)
- `compliance_regime`: Filter by compliance jurisdiction (e.g., `GDPR`, `LGPD`, `CCPA`)
- `ordering`: Comma-separated list of fields to sort by (e.g., `-created_at,quality_score`)
  - Supported fields: `created_at`, `updated_at`, `quality_score`, `compliance_risk`
  - Prefix with `-` for descending order
  - Default: `-created_at` (newest first)

**Example Request:**
```bash
GET /api/v1/contracts/?tag=analytics&tag=sales&ordering=-created_at
Authorization: Bearer <token>
```

**Example Response (200 OK):**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "tenant": "123e4567-e89b-12d3-a456-426614174001",
      "asset": "123e4567-e89b-12d3-a456-426614174002",
      "version": 1,
      "status": "DRAFT",
      "normalization_status": "NORMALIZED_OK",
      "validation_status": "VALID",
      "owners": [
        {"name": "Data Platform Team", "email": "dataplatform@example.com"}
      ],
      "tags": ["analytics", "sales"],
      "quality_rules": [...],
      "compliance_policy": {...},
      "lifecycle_policy": {...},
      "marketplace_policy": {...},
      "schema_fields": [...],
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

#### Create Contract

**POST /contracts/**

Create a new contract from original contract content. The contract will be automatically normalized to HubContract format.

**Request Body:**
```json
{
  "asset_id": "123e4567-e89b-12d3-a456-426614174002",
  "original_raw": "{\"id\": \"orders\", \"info\": {...}, \"schema\": {...}}",
  "original_format": "JSON",
  "original_spec_type": "ODCS"
}
```

**Supported Formats:**
- `JSON`: JSON format
- `YAML`: YAML format

**Supported Spec Types:**
- `ODCS`: Open Data Contract Specification
- `DATACONTRACT_COM`: DataContract.com format

If `original_spec_type` is not provided, it will be auto-detected.

**Example Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "tenant": "123e4567-e89b-12d3-a456-426614174001",
  "asset": "123e4567-e89b-12d3-a456-426614174002",
  "version": 1,
  "status": "DRAFT",
  "normalization_status": "NORMALIZED_OK",
  "hub_contract_version": "1.0.0",
  "hub_contract_json": {
    "hub_contract_version": 1,
    "id": "orders",
    "info": {
      "name": "Customer Orders",
      "owners": [{"name": "Data Platform Team", "email": "dataplatform@example.com"}],
      "tags": ["analytics", "sales"]
    },
    "schema": {...},
    "quality": {...},
    "privacy_compliance": {...},
    "lifecycle": {...},
    "marketplace": {...}
  },
  "owners": [...],
  "tags": [...],
  "quality_rules": [...],
  "compliance_policy": {...},
  "lifecycle_policy": {...},
  "marketplace_policy": {...},
  "schema_fields": [...],
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### Get Contract

**GET /contracts/{id}/**

Retrieve a contract by ID. Returns complete contract with all sections and computed fields.

**Example Response (200 OK):**
Same format as Create Contract response, with all computed fields populated.

#### Update Contract

**PATCH /contracts/{id}/**

Update a contract (partial update supported). If `original_raw` is updated, the contract will be re-normalized.

**Request Body:**
```json
{
  "original_raw": "{\"id\": \"orders\", \"info\": {...}}",
  "original_format": "JSON",
  "status": "ACTIVE"
}
```

#### Validate Contract

**POST /contracts/{id}/validate/**

Validate a contract using DataContract CLI.

**Request Body:**
```json
{
  "async": false
}
```

**Response (200 OK, synchronous):**
```json
{
  "validation_status": "VALID",
  "errors": [],
  "warnings": [],
  "grouped_errors": {},
  "cli_version": "0.9.0",
  "validated_at": "2025-01-15T10:00:00Z"
}
```

**Response (202 Accepted, asynchronous):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174003",
  "status": "pending",
  "message": "Validation job created. Poll /jobs/{job_id} for status."
}
```

#### Lint Contract

**POST /contracts/{id}/lint/**

Lint a contract using DataContract CLI. Returns linting issues and recommendations.

**Response (200 OK):**
```json
{
  "issues": [
    {
      "severity": "warning",
      "message": "Missing description for field 'order_id'",
      "path": "schema.fields[0]"
    }
  ],
  "cli_version": "0.9.0"
}
```

#### Convert Contract Format

**POST /contracts/{id}/convert/**

Convert a contract between JSON and YAML formats.

**Request Body:**
```json
{
  "target_format": "YAML"
}
```

**Response (200 OK):**
```json
{
  "converted_contract": "id: orders\ninfo:\n  name: Customer Orders\n...",
  "target_format": "YAML",
  "format": "YAML",
  "cli_version": "0.9.0"
}
```

#### Migrate Contract

**POST /contracts/{id}/migrate/**

Migrate contract to a new HubContract version.

**Request Body:**
```json
{
  "target_hub_contract_version": "2.0.0",
  "migration_strategy": "ON_WRITE"
}
```

**Migration Strategies:**
- `ON_WRITE`: Migrate immediately and persist to database
- `ON_READ`: Migrate in-memory only (lazy migration, not persisted)
- `BACKGROUND`: Queue background job for migration

**Response (200 OK, ON_WRITE/ON_READ):**
```json
{
  "contract": {...},
  "migration_applied": true,
  "migration_details": {
    "source_version": "1.0.0",
    "target_version": "2.0.0",
    "migration_strategy": "ON_WRITE",
    "warnings": []
  }
}
```

**Response (202 Accepted, BACKGROUND):**
```json
{
  "job": {
    "id": "123e4567-e89b-12d3-a456-426614174003",
    "type": "CONTRACT_MIGRATION",
    "status": "pending"
  },
  "migration_details": {
    "source_version": "1.0.0",
    "target_version": "2.0.0",
    "migration_strategy": "BACKGROUND"
  }
}
```

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs/` | List jobs |
| GET | `/jobs/{id}/` | Get job details |
| POST | `/jobs/{id}/cancel/` | Cancel job |

### Data Quality

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/dq/runs/` | Create DQ run |
| GET | `/dq/runs/{id}/` | Get DQ run details |
| GET | `/dq/runs/{id}/results/` | Get DQ run results |

### Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/compliance/scans/` | Create compliance scan |
| GET | `/compliance/scans/{id}/` | Get scan details |
| GET | `/compliance/scans/{id}/results/` | Get scan results |

### Semantic

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/semantic/context/` | Get JSON-LD context |
| GET | `/semantic/ontology/` | Get ontology |
| GET | `/semantic/uri/{resource_type}/{resource_id}/` | Resolve URI to JSON-LD |

### Marketplace

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/marketplace/listings/` | List marketplace listings |
| POST | `/marketplace/listings/` | Create listing |
| GET | `/marketplace/listings/{id}/` | Get listing details |
| POST | `/marketplace/orders/` | Create order |
| GET | `/marketplace/orders/{id}/` | Get order details |
| POST | `/marketplace/orders/{id}/approve/` | Approve order |

### Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audit/events/` | List audit events |
| GET | `/audit/events/{id}/` | Get audit event details |
| GET | `/audit/events/export/` | Export audit events (CSV) |

---

## Request/Response Format

### Request Headers

All requests should include:

```
Content-Type: application/json
Authorization: Bearer <token>
Accept: application/json
```

### Request Body

Request bodies should be JSON:

```json
{
  "name": "My Asset",
  "description": "Asset description",
  "domain": "marketing"
}
```

### Response Format

Successful responses (2xx):

```json
{
  "id": "uuid",
  "name": "My Asset",
  "status": "ACTIVE",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

List responses include pagination:

```json
{
  "count": 100,
  "next": "https://api.hub.example.com/api/v1/assets/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field_name": ["Error detail for this field"]
    },
    "request_id": "unique-request-id"
  }
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 204 | No Content | Request succeeded, no content |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Common Error Codes

- `VALIDATION_ERROR` - Request validation failed
- `NOT_FOUND` - Resource not found
- `UNAUTHORIZED` - Authentication required
- `FORBIDDEN` - Insufficient permissions
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `INTERNAL_ERROR` - Internal server error

---

## Rate Limiting

The API enforces rate limits to ensure fair usage:

- **Authenticated users**: 1000 requests per hour
- **Unauthenticated users**: 100 requests per hour

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

When rate limit is exceeded, a `429 Too Many Requests` response is returned.

---

## OpenAPI Schema

The complete OpenAPI 3.0 schema is available at:

- **JSON**: `/api-docs/openapi.json`
- **Swagger UI**: `/api-docs/`
- **ReDoc**: `/api-docs/redoc/`

### Download Schema

```bash
curl https://api.hub.example.com/api-docs/openapi.json > openapi.json
```

### Schema Features

- Complete endpoint documentation
- Request/response schemas
- Authentication requirements
- Error responses
- Examples

---

## Interactive Documentation

### Swagger UI

Access interactive API documentation at `/api-docs/`:

- Try out endpoints directly in the browser
- View request/response examples
- Test authentication

### ReDoc

Access alternative documentation at `/api-docs/redoc/`:

- Clean, readable documentation
- Search functionality
- Code examples

---

## SDKs

Official SDKs are available:

- **Python**: `pip install datahub-interoperability`
- **JavaScript/TypeScript**: `npm install @datahub/interoperability-sdk`

See [SDK Documentation](./SDK_DOCUMENTATION.md) for details.

---

## Examples

### Create an Asset

```bash
curl -X POST https://api.hub.example.com/api/v1/assets/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Data",
    "description": "Customer information dataset",
    "domain": "marketing"
  }'
```

### List Assets with Filters

```bash
curl -X GET "https://api.hub.example.com/api/v1/assets/?status=ACTIVE&domain=marketing" \
  -H "Authorization: Bearer <token>"
```

### Upload a File

```bash
# 1. Initialize upload
curl -X POST https://api.hub.example.com/api/v1/files/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "data.csv",
    "size": 1024,
    "content_type": "text/csv"
  }'

# 2. Upload to pre-signed URL
curl -X PUT "<upload_url>" \
  -H "Content-Type: text/csv" \
  --data-binary @data.csv

# 3. Complete upload
curl -X POST "https://api.hub.example.com/api/v1/files/{file_id}/complete/" \
  -H "Authorization: Bearer <token>"
```

---

## Support

For API support:

- **Documentation**: https://docs.hub.example.com
- **Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **Email**: api-support@hub.example.com

---

## Changelog

### v1.0.0 (2025-01-15)

- Initial API release
- Authentication endpoints
- Tenant, User, File, Dataset, Asset, Contract management
- Marketplace operations
- Semantic layer endpoints
- Audit logging

---

**Last Updated**: 2025-01-15  
**API Version**: v1.0.0

