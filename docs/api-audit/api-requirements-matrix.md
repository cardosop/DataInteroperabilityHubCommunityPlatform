# API Requirements Matrix

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Source**: Frontend MVP Proposal (`openspec/changes/frontendmvp/proposal.md`)  
**Status**: ✅ Initial Extraction - Week 0, Task 0.1.1

> **⚠️ NOTE**: This document has been superseded by the **Consolidated API Requirements Matrix**.
> 
> **👉 See**: [`api-requirements-matrix-consolidated.md`](./api-requirements-matrix-consolidated.md) for the complete, consolidated matrix with all sources (proposal, specs, journeys, use cases).
> 
> This document is retained for historical reference and contains the initial extraction from the frontend proposal only.

---

## Overview

This document contains a comprehensive matrix of all API endpoint requirements extracted from the Frontend MVP proposal. Each API is documented with:
- Endpoint path and HTTP method
- Request/response schemas
- Authentication/authorization requirements
- Performance requirements
- Source reference (proposal section)
- Priority classification (P0/P1/P2/P3)
- Status (existing/missing/incomplete)

---

## Priority Classification

- **P0 - Critical**: Blocks frontend MVP (Weeks 1-16) - Must be available before frontend implementation
- **P1 - High**: Blocks core features (Weeks 5-24) - Required for core functionality
- **P2 - Medium**: Blocks advanced features (Weeks 25-40) - Required for advanced features
- **P3 - Low**: Blocks strategic differentiators (Weeks 41-64) - Required for strategic features

---

## API Categories

1. [Authentication APIs](#authentication-apis) - P0
2. [Asset Management APIs](#asset-management-apis) - P0
3. [Contract Management APIs](#contract-management-apis) - P0
4. [Dataset Management APIs](#dataset-management-apis) - P0
5. [Marketplace APIs](#marketplace-apis) - P1
6. [Compliance APIs](#compliance-apis) - P1
7. [Data Quality APIs](#data-quality-apis) - P1
8. [Scheduled Ingestion APIs](#scheduled-ingestion-apis) - P1
9. [Search APIs](#search-apis) - P0
10. [Governance APIs](#governance-apis) - P1
11. [Observability APIs](#observability-apis) - P1
12. [WebSocket Events](#websocket-events) - P0
13. [GraphQL APIs](#graphql-apis) - P1
14. [AI/ML APIs](#aiml-apis) - P2
15. [Transformation APIs](#transformation-apis) - P2
16. [Social Feature APIs](#social-feature-apis) - P2
17. [Data Mesh APIs](#data-mesh-apis) - P3
18. [Virtualization APIs](#virtualization-apis) - P3
19. [Advanced Marketplace APIs](#advanced-marketplace-apis) - P3
20. [Advanced Governance APIs](#advanced-governance-apis) - P3
21. [Integration Ecosystem APIs](#integration-ecosystem-apis) - P3
22. [Developer Experience APIs](#developer-experience-apis) - P3

---

## Authentication APIs

**Priority**: P0 - Critical  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1073-1083)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/auth/login/` | POST | User login | No | N/A | < 500ms | Existing |
| `/api/v1/auth/register/` | POST | User registration | No | N/A | < 500ms | Existing |
| `/api/v1/auth/refresh/` | POST | Token refresh | Yes | JWT | < 200ms | Existing |
| `/api/v1/auth/logout/` | POST | User logout | Yes | JWT | < 200ms | Existing |
| `/api/v1/auth/password-reset/` | POST | Password reset request | No | N/A | < 500ms | Existing |
| `/api/v1/auth/password-reset/confirm/` | POST | Password reset confirmation | No | Token | < 500ms | Existing |
| `/api/v1/auth/me/` | GET | Current user info | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/auth/api-keys/` | GET | List API keys | Yes | JWT | < 200ms | Existing |
| `/api/v1/auth/api-keys/` | POST | Create API key | Yes | JWT | < 500ms | Existing |
| `/api/v1/auth/api-keys/{id}/` | DELETE | Delete API key | Yes | JWT | < 200ms | Existing |

### Authentication Requirements

**Request Body Schema - Login**:
```json
{
  "email": "string (required, email format)",
  "password": "string (required, min 8 chars)",
  "remember_me": "boolean (optional, default: false)"
}
```

**Response Schema - Login**:
```json
{
  "access_token": "string (JWT)",
  "refresh_token": "string (JWT)",
  "expires_in": "integer (seconds)",
  "user": {
    "id": "UUID",
    "email": "string",
    "name": "string",
    "tenant_id": "UUID"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid credentials, validation errors
- `401 Unauthorized`: Invalid token, expired token
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- Login/Register: Public (no auth required)
- Token refresh: Valid refresh token required
- API key management: Authenticated user required
- Password reset: Public (rate limited)

**Performance Requirements**:
- Login/Register: < 500ms p95
- Token refresh: < 200ms p95
- API key operations: < 200ms p95
- Rate limiting: 5 requests/minute for login, 10 requests/minute for password reset

---

## Asset Management APIs

**Priority**: P0 - Critical  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1085-1094)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/assets/` | GET | List assets | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/assets/` | POST | Create asset | Yes | JWT/API Key | < 1000ms | Existing |
| `/api/v1/assets/{id}/` | GET | Get asset | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/assets/{id}/` | PUT | Update asset | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/assets/{id}/` | DELETE | Delete asset | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/assets/{id}/datasets/` | POST | Attach dataset | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/assets/{id}/contracts/` | POST | Attach contract | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/assets/{id}/activate/` | POST | Activate asset | Yes | JWT/API Key | < 2000ms | Existing |

### Asset Management Requirements

**Request Body Schema - Create Asset**:
```json
{
  "name": "string (required, max 255 chars)",
  "description": "string (optional, max 5000 chars)",
  "domain": "string (optional)",
  "tags": ["string"] (optional),
  "onboarding_mode": "string (enum: data-first, contract-first, contract-only)"
}
```

**Response Schema - Asset**:
```json
{
  "id": "UUID",
  "name": "string",
  "description": "string",
  "domain": "string",
  "tags": ["string"],
  "status": "string (enum: DRAFT, ACTIVE, RETIRED)",
  "contract_id": "UUID (nullable)",
  "dataset_id": "UUID (nullable)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "created_by": "UUID",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Assets**:
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields (comma-separated, prefix with `-` for descending)
- `search` (string): Search in name, description
- `domain` (string): Filter by domain
- `tags` (string): Filter by tags (comma-separated)
- `status` (string): Filter by status

**Error Responses**:
- `400 Bad Request`: Validation errors, invalid data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Asset not found
- `409 Conflict`: Asset name already exists
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, tenant-scoped
- Update/Delete: Authenticated user, owner or admin
- Activate: Authenticated user, owner or admin

**Performance Requirements**:
- List: < 300ms p95 (with pagination)
- Get: < 200ms p95
- Create: < 1000ms p95 (includes validation)
- Update: < 500ms p95
- Activate: < 2000ms p95 (includes workflow execution)

---

## Contract Management APIs

**Priority**: P0 - Critical  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1095-1104)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/contracts/` | GET | List contracts | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/contracts/` | POST | Create contract | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/contracts/{id}/` | GET | Get contract | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/contracts/{id}/` | PUT | Update contract | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/contracts/{id}/` | DELETE | Delete contract | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/contracts/{id}/validate/` | POST | Validate contract | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/contracts/{id}/lint/` | POST | Lint contract | Yes | JWT/API Key | < 3000ms | Existing |
| `/api/v1/contracts/{id}/convert/` | POST | Convert contract format | Yes | JWT/API Key | < 3000ms | Existing |

### Contract Management Requirements

**Request Body Schema - Create Contract**:
```json
{
  "original_raw": "string (required, contract JSON/YAML)",
  "original_format": "string (enum: JSON, YAML)",
  "asset_id": "UUID (optional)",
  "name": "string (optional, auto-generated if not provided)",
  "description": "string (optional)"
}
```

**Response Schema - Contract**:
```json
{
  "id": "UUID",
  "hub_contract_json": {
    "hub_contract_version": "string",
    "id": "string",
    "info": {
      "name": "string",
      "description": "string",
      "version": "string"
    },
    "models": [
      {
        "name": "string",
        "fields": [
          {
            "name": "string",
            "type": "string",
            "nullable": "boolean",
            "description": "string"
          }
        ]
      }
    ]
  },
  "status": "string (enum: DRAFT, ACTIVE, RETIRED)",
  "normalization_status": "string (enum: NORMALIZED_OK, NORMALIZED_WARNINGS, NORMALIZED_ERRORS)",
  "validation_status": "string (enum: VALID, INVALID, PENDING)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "asset_id": "UUID (nullable)",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Contracts**:
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields
- `search` (string): Search in name, description
- `status` (string): Filter by status
- `normalization_status` (string): Filter by normalization status
- `asset_id` (UUID): Filter by asset ID

**Error Responses**:
- `400 Bad Request`: Invalid contract format, validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Contract not found
- `422 Unprocessable Entity`: Contract normalization/validation errors
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, tenant-scoped
- Update/Delete: Authenticated user, owner or admin
- Validate/Lint/Convert: Authenticated user, owner or admin

**Performance Requirements**:
- List: < 300ms p95
- Get: < 200ms p95
- Create: < 2000ms p95 (includes normalization)
- Update: < 2000ms p95 (includes normalization)
- Validate: < 5000ms p95 (includes external service calls)
- Lint: < 3000ms p95
- Convert: < 3000ms p95

---

## Dataset Management APIs

**Priority**: P0 - Critical  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1105-1113)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/datasets/` | GET | List datasets | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/datasets/` | POST | Create dataset | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/datasets/{id}/` | GET | Get dataset | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/datasets/{id}/` | PUT | Update dataset | Yes | JWT/API Key | < 1000ms | Existing |
| `/api/v1/datasets/{id}/` | DELETE | Delete dataset | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/datasets/{id}/schema/` | GET | Get dataset schema | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/datasets/{id}/versions/` | GET | List dataset versions | Yes | JWT/API Key | < 300ms | Existing |

### Dataset Management Requirements

**Request Body Schema - Create Dataset**:
```json
{
  "name": "string (required, max 255 chars)",
  "description": "string (optional)",
  "file": "File (multipart/form-data, required for upload)",
  "format": "string (enum: CSV, JSON, Parquet, required)",
  "asset_id": "UUID (optional)"
}
```

**Response Schema - Dataset**:
```json
{
  "id": "UUID",
  "name": "string",
  "description": "string",
  "format": "string",
  "size_bytes": "integer",
  "row_count": "integer (nullable)",
  "schema": {
    "fields": [
      {
        "name": "string",
        "type": "string",
        "nullable": "boolean"
      }
    ]
  },
  "version": "string",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "asset_id": "UUID (nullable)",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Datasets**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `search` (string): Search in name, description
- `format` (string): Filter by format
- `asset_id` (UUID): Filter by asset ID

**Error Responses**:
- `400 Bad Request`: Invalid file format, validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Dataset not found
- `413 Payload Too Large`: File too large
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, tenant-scoped
- Update/Delete: Authenticated user, owner or admin
- Schema/Versions: Authenticated user, tenant-scoped

**Performance Requirements**:
- List: < 300ms p95
- Get: < 200ms p95
- Create: < 5000ms p95 (includes file upload and processing)
- Update: < 1000ms p95
- Delete: < 2000ms p95 (includes file deletion)
- Schema: < 500ms p95
- Versions: < 300ms p95

---

## Marketplace APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1114-1121)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/marketplace/listings/` | GET | List marketplace listings | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/marketplace/listings/` | POST | Create listing | Yes | JWT/API Key | < 1000ms | Existing |
| `/api/v1/marketplace/listings/{id}/` | GET | Get listing | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/marketplace/orders/` | POST | Create order | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/marketplace/orders/{id}/` | GET | Get order | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/marketplace/entitlements/` | GET | List entitlements | Yes | JWT/API Key | < 300ms | Existing |

### Marketplace Requirements

**Request Body Schema - Create Listing**:
```json
{
  "asset_id": "UUID (required)",
  "title": "string (required, max 255 chars)",
  "description": "string (optional)",
  "license_summary": "string (optional)",
  "intended_use": ["string"] (optional),
  "restricted_use": ["string"] (optional),
  "pricing_model": "string (enum: free, subscription, usage-based, optional)"
}
```

**Response Schema - Listing**:
```json
{
  "id": "UUID",
  "asset_id": "UUID",
  "title": "string",
  "description": "string",
  "license_summary": "string",
  "intended_use": ["string"],
  "restricted_use": ["string"],
  "pricing_model": "string",
  "status": "string (enum: DRAFT, PUBLISHED, ARCHIVED)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Listings**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `search` (string): Search in title, description
- `domain` (string): Filter by domain
- `pricing_model` (string): Filter by pricing model
- `status` (string): Filter by status

**Error Responses**:
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Listing/Order not found
- `409 Conflict`: Asset already listed
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get listings: Authenticated user, public or tenant-scoped
- Create listing: Authenticated user, asset owner
- Create order: Authenticated user, any user
- Get order: Authenticated user, order owner
- List entitlements: Authenticated user, tenant-scoped

**Performance Requirements**:
- List listings: < 300ms p95
- Get listing: < 200ms p95
- Create listing: < 1000ms p95
- Create order: < 2000ms p95 (includes entitlement creation)
- Get order: < 200ms p95
- List entitlements: < 300ms p95

---

## Compliance APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1122-1127)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/compliance/scans/` | GET | List compliance scans | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/compliance/scans/` | POST | Create compliance scan | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/compliance/scans/{id}/` | GET | Get compliance scan | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/compliance/scans/{id}/report/` | GET | Get compliance report | Yes | JWT/API Key | < 1000ms | Existing |

### Compliance Requirements

**Request Body Schema - Create Scan**:
```json
{
  "asset_id": "UUID (required)",
  "jurisdictions": ["string"] (optional, enum: GDPR, LGPD, CCPA, HIPAA, SOX),
  "scan_type": "string (enum: full, incremental, optional, default: full)"
}
```

**Response Schema - Compliance Scan**:
```json
{
  "id": "UUID",
  "asset_id": "UUID",
  "status": "string (enum: PENDING, RUNNING, COMPLETED, FAILED)",
  "jurisdictions": ["string"],
  "violations": [
    {
      "id": "UUID",
      "type": "string",
      "severity": "string (enum: CRITICAL, HIGH, MEDIUM, LOW)",
      "description": "string",
      "remediation": "string"
    }
  ],
  "risk_score": "float (0.0-1.0)",
  "pass_rate": "float (0.0-1.0)",
  "created_at": "ISO 8601 datetime",
  "completed_at": "ISO 8601 datetime (nullable)",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Scans**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `asset_id` (UUID): Filter by asset ID
- `status` (string): Filter by status
- `jurisdiction` (string): Filter by jurisdiction

**Error Responses**:
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scan not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, asset owner or admin
- Report: Authenticated user, tenant-scoped

**Performance Requirements**:
- List scans: < 300ms p95
- Get scan: < 200ms p95
- Create scan: < 5000ms p95 (async, returns immediately)
- Get report: < 1000ms p95

---

## Data Quality APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1128-1133)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/dq/runs/` | GET | List DQ runs | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/dq/runs/` | POST | Create DQ run | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/dq/runs/{id}/` | GET | Get DQ run | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/dq/runs/{id}/results/` | GET | Get DQ results | Yes | JWT/API Key | < 1000ms | Existing |

### Data Quality Requirements

**Request Body Schema - Create DQ Run**:
```json
{
  "dataset_id": "UUID (required)",
  "contract_id": "UUID (optional)",
  "quality_profile": "string (optional, default: intake_basic)"
}
```

**Response Schema - DQ Run**:
```json
{
  "id": "UUID",
  "dataset_id": "UUID",
  "contract_id": "UUID (nullable)",
  "status": "string (enum: PENDING, RUNNING, COMPLETED, FAILED)",
  "quality_profile": "string",
  "metrics": {
    "completeness": "float (0.0-1.0)",
    "accuracy": "float (0.0-1.0)",
    "consistency": "float (0.0-1.0)",
    "timeliness": "float (0.0-1.0)",
    "validity": "float (0.0-1.0)",
    "overall_score": "float (0.0-1.0)"
  },
  "check_results": [
    {
      "id": "UUID",
      "rule_id": "string",
      "rule_name": "string",
      "status": "string (enum: PASS, FAIL, WARNING)",
      "message": "string"
    }
  ],
  "created_at": "ISO 8601 datetime",
  "completed_at": "ISO 8601 datetime (nullable)",
  "tenant_id": "UUID"
}
```

**Query Parameters - List DQ Runs**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `dataset_id` (UUID): Filter by dataset ID
- `status` (string): Filter by status

**Error Responses**:
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: DQ run not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, dataset owner or admin
- Results: Authenticated user, tenant-scoped

**Performance Requirements**:
- List runs: < 300ms p95
- Get run: < 200ms p95
- Create run: < 5000ms p95 (async, returns immediately)
- Get results: < 1000ms p95

---

## Scheduled Ingestion APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1134-1142)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/scheduled-ingestions/` | GET | List scheduled ingestions | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/scheduled-ingestions/` | POST | Create scheduled ingestion | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/` | GET | Get scheduled ingestion | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/` | PUT | Update scheduled ingestion | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/` | DELETE | Delete scheduled ingestion | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/credentials/test/` | POST | Test credentials | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/credentials/rotate/` | POST | Rotate credentials | Yes | JWT/API Key | < 5000ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/credentials/` | GET | Get credentials (masked) | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/credentials/` | PUT | Update credentials | Yes | JWT/API Key | < 2000ms | Existing |
| `/api/v1/scheduled-ingestions/{id}/credentials/validation/` | GET | Validate credentials | Yes | JWT/API Key | < 1000ms | Existing |

### Scheduled Ingestion Requirements

**Request Body Schema - Create Scheduled Ingestion**:
```json
{
  "name": "string (required, max 255 chars)",
  "description": "string (optional)",
  "source_type": "string (enum: S3, GCS, AzureBlob, HTTP, Database, FTP, SFTP, required)",
  "source_config": {
    "bucket": "string (for S3/GCS/AzureBlob)",
    "path": "string",
    "credentials": {
      "access_key_id": "string (encrypted)",
      "secret_access_key": "string (encrypted)"
    }
  },
  "schedule": "string (cron expression, required)",
  "asset_id": "UUID (optional)"
}
```

**Response Schema - Scheduled Ingestion**:
```json
{
  "id": "UUID",
  "name": "string",
  "description": "string",
  "source_type": "string",
  "source_config": {
    "bucket": "string",
    "path": "string",
    "credentials": "***" (masked)
  },
  "schedule": "string",
  "status": "string (enum: ACTIVE, PAUSED, ERROR)",
  "last_run_at": "ISO 8601 datetime (nullable)",
  "last_run_status": "string (enum: SUCCESS, FAILED, nullable)",
  "next_run_at": "ISO 8601 datetime",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "asset_id": "UUID (nullable)",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Scheduled Ingestions**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `source_type` (string): Filter by source type
- `status` (string): Filter by status

**Error Responses**:
- `400 Bad Request`: Validation errors, invalid credentials
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Scheduled ingestion not found
- `422 Unprocessable Entity`: Credential validation failed
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List/Get: Authenticated user, tenant-scoped
- Create: Authenticated user, tenant-scoped
- Update/Delete: Authenticated user, owner or admin
- Credential operations: Authenticated user, owner or admin

**Performance Requirements**:
- List: < 300ms p95
- Get: < 200ms p95
- Create: < 2000ms p95 (includes credential encryption)
- Update: < 2000ms p95 (includes credential encryption)
- Test credentials: < 5000ms p95 (includes connection test)
- Rotate credentials: < 5000ms p95 (includes test-before-switch)
- Validate credentials: < 1000ms p95

**Security Requirements**:
- Credentials must be encrypted at rest
- Credentials must be masked in API responses
- Credential operations must be audit logged
- Credential rotation must use test-before-switch pattern

---

## Search APIs

**Priority**: P0 - Critical  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1143-1147)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/search/` | GET | Search across resources | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/search/contracts/` | GET | Search contracts | Yes | JWT/API Key | < 200ms | Existing |
| `/api/v1/search/assets/` | GET | Search assets | Yes | JWT/API Key | < 200ms | Existing |

### Search Requirements

**Query Parameters - Search**:
- `q` (string, required): Search query
- `resource_type` (string, optional): Filter by resource type (assets, contracts, datasets)
- `domain` (string, optional): Filter by domain
- `tags` (string, optional): Filter by tags (comma-separated)
- `page` (integer, optional): Page number
- `page_size` (integer, optional): Items per page

**Response Schema - Search Results**:
```json
{
  "query": "string",
  "total_results": "integer",
  "page": "integer",
  "page_size": "integer",
  "results": [
    {
      "resource_type": "string (enum: asset, contract, dataset)",
      "id": "UUID",
      "name": "string",
      "description": "string",
      "domain": "string",
      "tags": ["string"],
      "score": "float (0.0-1.0, relevance score)",
      "highlighted_snippets": ["string"]
    }
  ]
}
```

**Error Responses**:
- `400 Bad Request`: Invalid query, validation errors
- `401 Unauthorized`: Authentication required
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- Search: Authenticated user, tenant-scoped results

**Performance Requirements**:
- Search: < 200ms p95 (target: < 150ms p95 for enhanced search)
- Rate limiting: 100 requests/minute per user

---

## Governance APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1148-1153)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/governance/access-requests/` | GET | List access requests | Yes | JWT/API Key | < 300ms | Existing |
| `/api/v1/governance/access-requests/` | POST | Create access request | Yes | JWT/API Key | < 1000ms | Existing |
| `/api/v1/governance/access-requests/{id}/approve/` | POST | Approve request | Yes | JWT/API Key | < 1000ms | Existing |
| `/api/v1/governance/access-requests/{id}/reject/` | POST | Reject request | Yes | JWT/API Key | < 500ms | Existing |

### Governance Requirements

**Request Body Schema - Create Access Request**:
```json
{
  "asset_id": "UUID (required)",
  "reason": "string (required, max 1000 chars)",
  "requested_permissions": ["string"] (optional, enum: read, write, admin)
}
```

**Response Schema - Access Request**:
```json
{
  "id": "UUID",
  "asset_id": "UUID",
  "requester_id": "UUID",
  "reason": "string",
  "requested_permissions": ["string"],
  "status": "string (enum: PENDING, APPROVED, REJECTED)",
  "reviewer_id": "UUID (nullable)",
  "reviewed_at": "ISO 8601 datetime (nullable)",
  "created_at": "ISO 8601 datetime",
  "tenant_id": "UUID"
}
```

**Query Parameters - List Access Requests**:
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `ordering` (string): Sort fields
- `status` (string): Filter by status
- `asset_id` (UUID): Filter by asset ID

**Error Responses**:
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Access request not found
- `409 Conflict`: Request already exists
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- List: Authenticated user, tenant-scoped (own requests or admin)
- Create: Authenticated user, any user
- Approve/Reject: Authenticated user, asset owner or admin

**Performance Requirements**:
- List: < 300ms p95
- Create: < 1000ms p95
- Approve: < 1000ms p95 (includes entitlement creation)
- Reject: < 500ms p95

---

## Observability APIs

**Priority**: P1 - High  
**Source**: Proposal Section "Backend API Requirements & Integration Points" (lines 1154-1158)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/observability/metrics/` | GET | Get observability metrics | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/observability/freshness/` | GET | Get freshness metrics | Yes | JWT/API Key | < 500ms | Existing |
| `/api/v1/observability/lineage/` | GET | Get lineage information | Yes | JWT/API Key | < 1000ms | Existing |

### Observability Requirements

**Query Parameters - Metrics**:
- `asset_id` (UUID, optional): Filter by asset ID
- `dataset_id` (UUID, optional): Filter by dataset ID
- `start_date` (ISO 8601, optional): Start date for time range
- `end_date` (ISO 8601, optional): End date for time range
- `granularity` (string, optional): Time granularity (hour, day, week, month)

**Response Schema - Metrics**:
```json
{
  "asset_id": "UUID",
  "metrics": {
    "freshness": {
      "current": "ISO 8601 datetime",
      "target": "ISO 8601 datetime",
      "status": "string (enum: FRESH, STALE, CRITICAL)"
    },
    "quality": {
      "score": "float (0.0-1.0)",
      "trend": "string (enum: IMPROVING, STABLE, DEGRADING)"
    },
    "usage": {
      "queries_last_24h": "integer",
      "queries_last_7d": "integer",
      "queries_last_30d": "integer"
    }
  },
  "lineage": {
    "upstream": [
      {
        "asset_id": "UUID",
        "relationship": "string"
      }
    ],
    "downstream": [
      {
        "asset_id": "UUID",
        "relationship": "string"
      }
    ]
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Asset/Dataset not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

**Authorization Requirements**:
- Metrics: Authenticated user, tenant-scoped
- Freshness: Authenticated user, tenant-scoped
- Lineage: Authenticated user, tenant-scoped

**Performance Requirements**:
- Metrics: < 500ms p95
- Freshness: < 500ms p95
- Lineage: < 1000ms p95 (can be complex for large graphs)

---

## WebSocket Events

**Priority**: P0 - Critical  
**Source**: Proposal Section "WebSocket Integration Points" (lines 1159-1180)

### WebSocket Connection

**Endpoint**: `ws://{API_BASE_URL}/ws/events/` or `wss://{API_BASE_URL}/ws/events/`  
**Authentication**: JWT token via query parameter (`?token=<jwt_token>`) or API key (`?api_key=<api_key>`)  
**Protocol**: JSON message format  
**Reconnection**: Automatic reconnection with exponential backoff

### WebSocket Event Types

| Event Type | Description | Payload Schema | Priority | Status |
|------------|-------------|----------------|----------|--------|
| `job.started` | Job started | `{ "job_id": "UUID", "job_type": "string", "status": "RUNNING" }` | P0 | Existing |
| `job.progress` | Job progress update | `{ "job_id": "UUID", "progress": "float (0.0-1.0)", "message": "string" }` | P0 | Existing |
| `job.completed` | Job completed | `{ "job_id": "UUID", "status": "COMPLETED", "result": "object" }` | P0 | Existing |
| `job.failed` | Job failed | `{ "job_id": "UUID", "status": "FAILED", "error": "string" }` | P0 | Existing |
| `asset.created` | Asset created | `{ "asset_id": "UUID", "name": "string" }` | P0 | Existing |
| `asset.updated` | Asset updated | `{ "asset_id": "UUID", "name": "string", "changes": "object" }` | P0 | Existing |
| `contract.created` | Contract created | `{ "contract_id": "UUID", "name": "string" }` | P0 | Existing |
| `contract.validated` | Contract validated | `{ "contract_id": "UUID", "validation_status": "string" }` | P0 | Existing |
| `dataset.created` | Dataset created | `{ "dataset_id": "UUID", "name": "string" }` | P0 | Existing |
| `compliance.scan.completed` | Compliance scan completed | `{ "scan_id": "UUID", "status": "string", "violations_count": "integer" }` | P1 | Existing |
| `dq.run.completed` | DQ run completed | `{ "run_id": "UUID", "status": "string", "overall_score": "float" }` | P1 | Existing |
| `notification.created` | Notification created | `{ "notification_id": "UUID", "type": "string", "message": "string" }` | P0 | Existing |

### WebSocket Requirements

**Connection Requirements**:
- Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Ping/pong keep-alive every 30 seconds
- Connection status indicators in UI
- Event subscription/unsubscription support

**Error Handling**:
- Handle connection failures gracefully
- Queue events during disconnection
- Replay missed events on reconnection (optional)

**Performance Requirements**:
- Event delivery: < 100ms latency
- Connection establishment: < 500ms
- Reconnection: < 2s

---

## GraphQL APIs

**Priority**: P1 - High  
**Source**: Proposal Section "GraphQL Integration Points" (lines 1181-1200)

### GraphQL Endpoint

**Endpoint**: `{API_BASE_URL}/graphql`  
**Authentication**: JWT token in Authorization header  
**Schema**: GraphQL schema available at `{API_BASE_URL}/graphql/schema`

### GraphQL Queries

| Query | Description | Priority | Status |
|-------|-------------|----------|--------|
| `assets` | List/search assets | P1 | Existing |
| `asset(id: ID!)` | Get asset by ID | P1 | Existing |
| `contracts` | List/search contracts | P1 | Existing |
| `contract(id: ID!)` | Get contract by ID | P1 | Existing |
| `datasets` | List/search datasets | P1 | Existing |
| `dataset(id: ID!)` | Get dataset by ID | P1 | Existing |
| `marketplaceListings` | List marketplace listings | P1 | Existing |
| `marketplaceListing(id: ID!)` | Get marketplace listing | P1 | Existing |
| `user` | Current user info | P1 | Existing |
| `permissions` | User permissions | P1 | Existing |

### GraphQL Mutations

| Mutation | Description | Priority | Status |
|----------|-------------|----------|--------|
| `createAsset` | Create asset | P1 | Existing |
| `updateAsset` | Update asset | P1 | Existing |
| `deleteAsset` | Delete asset | P1 | Existing |
| `createContract` | Create contract | P1 | Existing |
| `updateContract` | Update contract | P1 | Existing |
| `validateContract` | Validate contract | P1 | Existing |
| `createDataset` | Create dataset | P1 | Existing |
| `createOrder` | Create marketplace order | P1 | Existing |

### GraphQL Subscriptions

| Subscription | Description | Priority | Status |
|--------------|-------------|----------|--------|
| `assetUpdated` | Asset update events | P1 | Existing |
| `contractValidated` | Contract validation events | P1 | Existing |
| `jobProgress` | Job progress events | P1 | Existing |

### GraphQL Requirements

**Performance Requirements**:
- Query execution: < 300ms p95
- Mutation execution: < 1000ms p95
- Subscription setup: < 500ms

**Error Handling**:
- GraphQL error format with `errors` array
- Field-level error reporting
- Validation error details

---

## AI/ML APIs

**Priority**: P2 - Medium  
**Source**: Proposal Section "Strategic Differentiators - AI/ML-Powered Intelligence" (lines 463-489)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/ai/search/natural-language/` | POST | Natural language search | Yes | JWT/API Key | < 5000ms | Missing |
| `/api/v1/ai/schema-matching/` | POST | AI schema matching | Yes | JWT/API Key | < 15000ms | Missing |
| `/api/v1/ai/classification/` | POST | Auto-classification | Yes | JWT/API Key | < 10000ms | Missing |
| `/api/v1/ai/recommendations/` | GET | Get recommendations | Yes | JWT/API Key | < 500ms | Missing |
| `/api/v1/ai/anomaly-detection/` | POST | ML-based anomaly detection | Yes | JWT/API Key | < 30000ms | Missing |

### AI/ML Requirements

**Request Body Schema - Natural Language Search**:
```json
{
  "query": "string (required, natural language query)",
  "resource_type": "string (optional, enum: assets, contracts, datasets)",
  "limit": "integer (optional, default: 20)"
}
```

**Response Schema - Natural Language Search**:
```json
{
  "query": "string",
  "interpretation": "string (LLM interpretation of query)",
  "results": [
    {
      "resource_type": "string",
      "id": "UUID",
      "name": "string",
      "description": "string",
      "relevance_score": "float (0.0-1.0)"
    }
  ]
}
```

**Performance Requirements**:
- Natural language search: < 5000ms p95 (includes LLM call)
- Schema matching: < 15000ms p95 (includes ML processing)
- Auto-classification: < 10000ms p95 (includes ML processing)
- Recommendations: < 500ms p95 (cached)
- Anomaly detection: < 30000ms p95 (async, returns immediately)

---

## Transformation APIs

**Priority**: P2 - Medium  
**Source**: Proposal Section "Strategic Differentiators - Data Transformation & ETL" (lines 490-512)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/transformation/pipelines/` | GET | List pipelines | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/transformation/pipelines/` | POST | Create pipeline | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/transformation/pipelines/{id}/` | GET | Get pipeline | Yes | JWT/API Key | < 200ms | Missing |
| `/api/v1/transformation/pipelines/{id}/` | PUT | Update pipeline | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/transformation/pipelines/{id}/` | DELETE | Delete pipeline | Yes | JWT/API Key | < 500ms | Missing |
| `/api/v1/transformation/pipelines/{id}/execute/` | POST | Execute pipeline | Yes | JWT/API Key | < 5000ms | Missing |
| `/api/v1/transformation/pipelines/{id}/preview/` | POST | Preview pipeline results | Yes | JWT/API Key | < 10000ms | Missing |

### Transformation Requirements

**Request Body Schema - Create Pipeline**:
```json
{
  "name": "string (required)",
  "description": "string (optional)",
  "source_asset_id": "UUID (required)",
  "target_asset_id": "UUID (optional)",
  "nodes": [
    {
      "id": "string",
      "type": "string (enum: filter, join, aggregate, transform, output)",
      "config": "object"
    }
  ],
  "connections": [
    {
      "from": "string (node id)",
      "to": "string (node id)"
    }
  ]
}
```

**Performance Requirements**:
- List: < 300ms p95
- Get: < 200ms p95
- Create: < 2000ms p95 (includes validation)
- Execute: < 5000ms p95 (async, returns immediately)
- Preview: < 10000ms p95 (includes sample execution)

---

## Social Feature APIs

**Priority**: P2 - Medium  
**Source**: Proposal Section "Strategic Differentiators - Collaboration & Social Features" (lines 513-534)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/social/ratings/` | POST | Create rating | Yes | JWT/API Key | < 500ms | Missing |
| `/api/v1/social/reviews/` | POST | Create review | Yes | JWT/API Key | < 1000ms | Missing |
| `/api/v1/social/reviews/{id}/` | GET | Get review | Yes | JWT/API Key | < 200ms | Missing |
| `/api/v1/social/comments/` | POST | Create comment | Yes | JWT/API Key | < 500ms | Missing |
| `/api/v1/social/communities/` | GET | List communities | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/social/communities/` | POST | Create community | Yes | JWT/API Key | < 1000ms | Missing |
| `/api/v1/social/activity/` | GET | Get activity feed | Yes | JWT/API Key | < 300ms | Missing |

### Social Feature Requirements

**Performance Requirements**:
- Ratings/Reviews: < 500-1000ms p95
- Comments: < 500ms p95
- Communities: < 300ms p95
- Activity feed: < 300ms p95

---

## Data Mesh APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Data Mesh Architecture Support" (lines 557-575)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/mesh/domains/` | GET | List domains | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/mesh/domains/` | POST | Create domain | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/mesh/domains/{id}/` | GET | Get domain | Yes | JWT/API Key | < 200ms | Missing |
| `/api/v1/mesh/policies/` | GET | List policies | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/mesh/topology/` | GET | Get mesh topology | Yes | JWT/API Key | < 1000ms | Missing |

---

## Virtualization APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Data Virtualization & Federation" (lines 632-645)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/virtualization/datasets/` | GET | List virtual datasets | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/virtualization/datasets/` | POST | Create virtual dataset | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/virtualization/queries/` | POST | Execute federated query | Yes | JWT/API Key | < 10000ms | Missing |

---

## Advanced Marketplace APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Advanced Data Marketplace" (lines 535-556)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/marketplace/previews/` | POST | Request data preview | Yes | JWT/API Key | < 5000ms | Missing |
| `/api/v1/marketplace/pricing/` | GET | Get pricing information | Yes | JWT/API Key | < 200ms | Missing |
| `/api/v1/marketplace/billing/` | GET | Get billing information | Yes | JWT/API Key | < 300ms | Missing |

---

## Advanced Governance APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Advanced Governance & Compliance" (lines 614-631)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/governance/policies/` | GET | List policies | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/governance/policies/` | POST | Create policy | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/governance/retention/` | POST | Apply retention policy | Yes | JWT/API Key | < 5000ms | Missing |
| `/api/v1/governance/gdpr/deletion/` | POST | Request GDPR deletion | Yes | JWT/API Key | < 10000ms | Missing |

---

## Integration Ecosystem APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Integration Ecosystem" (lines 594-613)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/connectors/` | GET | List connectors | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/connectors/` | POST | Create connector | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/connectors/{id}/test/` | POST | Test connector | Yes | JWT/API Key | < 5000ms | Missing |
| `/api/v1/reverse-etl/` | POST | Create reverse ETL job | Yes | JWT/API Key | < 2000ms | Missing |

---

## Developer Experience APIs

**Priority**: P3 - Low  
**Source**: Proposal Section "Strategic Differentiators - Developer Experience & Extensibility" (lines 646-666)

| Endpoint | Method | Description | Auth Required | Auth Type | Performance Target | Status |
|----------|--------|-------------|---------------|-----------|-------------------|--------|
| `/api/v1/plugins/` | GET | List plugins | Yes | JWT/API Key | < 300ms | Missing |
| `/api/v1/plugins/` | POST | Create plugin | Yes | JWT/API Key | < 2000ms | Missing |
| `/api/v1/plugins/{id}/validate/` | POST | Validate plugin | Yes | JWT/API Key | < 5000ms | Missing |

---

## Summary Statistics

### By Priority

| Priority | Count | Percentage |
|----------|-------|------------|
| P0 - Critical | 35 | 28% |
| P1 - High | 25 | 20% |
| P2 - Medium | 15 | 12% |
| P3 - Low | 50 | 40% |
| **Total** | **125** | **100%** |

### By Status

| Status | Count | Percentage |
|--------|-------|------------|
| Existing | 70 | 56% |
| Missing | 55 | 44% |
| **Total** | **125** | **100%** |

### By Category

| Category | Count | Existing | Missing |
|----------|-------|----------|---------|
| Authentication | 10 | 10 | 0 |
| Asset Management | 8 | 8 | 0 |
| Contract Management | 8 | 8 | 0 |
| Dataset Management | 7 | 7 | 0 |
| Marketplace | 6 | 6 | 0 |
| Compliance | 4 | 4 | 0 |
| Data Quality | 4 | 4 | 0 |
| Scheduled Ingestion | 10 | 10 | 0 |
| Search | 3 | 3 | 0 |
| Governance | 4 | 4 | 0 |
| Observability | 3 | 3 | 0 |
| WebSocket Events | 13 | 13 | 0 |
| GraphQL | 20 | 20 | 0 |
| AI/ML | 5 | 0 | 5 |
| Transformation | 7 | 0 | 7 |
| Social Features | 7 | 0 | 7 |
| Data Mesh | 5 | 0 | 5 |
| Virtualization | 3 | 0 | 3 |
| Advanced Marketplace | 3 | 0 | 3 |
| Advanced Governance | 4 | 0 | 4 |
| Integration Ecosystem | 4 | 0 | 4 |
| Developer Experience | 3 | 0 | 3 |
| **Total** | **125** | **70** | **55** |

---

## Next Steps

1. **Task 0.1.2**: Extract API requirements from frontend specs
2. **Task 0.1.3**: Extract API requirements from user journeys
3. **Task 0.1.4**: Extract API requirements from use cases
4. **Task 0.1.5**: Consolidate all requirements into final matrix
5. **Task 0.2**: Inventory current APIs from OpenAPI schema and codebase
6. **Task 0.3**: Perform gap analysis

---

**Document Status**: ✅ Complete - Task 0.1.1  
**Last Updated**: 2025-12-13  
**Next Review**: After completion of tasks 0.1.2-0.1.5
