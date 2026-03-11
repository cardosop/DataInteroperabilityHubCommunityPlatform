# API Endpoints Reference

Complete reference for all API endpoints in the Data Interoperability Hub API v1.

## Standard Error Response Format

All API endpoints return errors in a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

**Status Codes:**
- `400 Bad Request`: Validation errors (code: `VALIDATION_ERROR` or `VALIDATION_FAILED`)
- `403 Forbidden`: Permission denied (code: `PERMISSION_DENIED` or `AUTH_FORBIDDEN`)
- `404 Not Found`: Resource not found (code: `NOT_FOUND`)
- `409 Conflict`: Resource conflict (code: `CONFLICT_ERROR` or `CONFLICT`)
- `429 Too Many Requests`: Rate limit exceeded (code: `RATE_LIMIT_EXCEEDED`)
- `500 Internal Server Error`: Server error (code: `INTERNAL_ERROR`)

**Error Response Fields:**
- `error` (string): Human-readable error message
- `code` (string): Machine-readable error code (e.g., `VALIDATION_ERROR`, `NOT_FOUND`)
- `details` (object): Optional dictionary with additional error context (field-level errors, validation details, etc.)

**Example Error Responses:**

```json
{
  "error": "Invalid request data",
  "code": "VALIDATION_ERROR",
  "details": {
    "field_errors": [
      {
        "field": "name",
        "message": "This field is required.",
        "code": "VALIDATION_ERROR"
      }
    ]
  }
}
```

```json
{
  "error": "Resource not found",
  "code": "NOT_FOUND",
  "details": {}
}
```

---

## Table of Contents

1. [Contracts](#contracts)
2. [Lineage](#lineage)
3. [Assets](#assets)
4. [Datasets](#datasets)
5. [Compliance](#compliance)
6. [Search](#search)
7. [Observability](#observability)
8. [Versioning](#versioning)
9. [Workflows](#workflows)
10. [Marketplace (listings and data preview)](#marketplace-listings-and-data-preview)
11. [Authentication](#authentication)
12. [Tenants (useronboardfix)](#tenants-useronboardfix)
13. [Billing (useronboardfix)](#billing-useronboardfix)
14. [Users (useronboardfix)](#users-useronboardfix)
15. [BaaS Platform Endpoints](#baas-platform-endpoints)
16. [ODH Integration Endpoints](#odh-integration-endpoints)
17. [Scheduled Ingestion](#scheduled-ingestion)
18. [Scheduled Ingestion Internal Worker API](#scheduled-ingestion-internal-worker-api)
19. [Scheduled Export](#scheduled-export)
20. [Scheduled Export Internal Worker API](#scheduled-export-internal-worker-api)

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

## ODPS (Open Data Product Standard) Endpoints

### Create ODPS Product (Product-First Flow)

**POST** `/api/v1/contracts/products/`

Create an ODPS product contract using the Product-First flow. This automatically extracts an ODCS contract from the ODPS product.contract field and creates both contracts with bidirectional linking.

**Request Body:**
```json
{
  "original_raw": "ODPS document content (JSON or YAML string)",
  "original_format": "JSON" | "YAML",
  "resolve_external_refs": true,
  "asset_id": "optional-asset-uuid",
  "odps_version": "4.1"
}
```

**Request Body Fields:**
- `original_raw` (string, required): ODPS document content as JSON or YAML string
- `original_format` (string, required): Format of ODPS document - "JSON" or "YAML"
- `resolve_external_refs` (boolean, optional): Whether to resolve external $ref references (default: true)
- `asset_id` (UUID, optional): Asset ID to attach contracts to
- `odps_version` (string, optional): ODPS version (e.g., "4.1"). Used for validation/documentation. Version in document takes precedence

**Response (201 Created):**
```json
{
  "odps_contract": {
    "id": "odps-contract-uuid",
    "original_spec_type": "ODPS",
    "original_spec_version": "4.1",
    "status": "DRAFT",
    "normalization_status": "NORMALIZED_OK",
    "hub_contract_json": {...},
    "created_at": "2025-01-15T10:30:00Z"
  },
  "odcs_contract": {
    "id": "odcs-contract-uuid",
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2",
    "status": "DRAFT",
    "normalization_status": "NORMALIZED_OK",
    "hub_contract_json": {...},
    "created_at": "2025-01-15T10:30:00Z"
  },
  "workflow_instance_id": "workflow-instance-uuid"
}
```

**Example Request:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"my-product\",\"name\":\"My Data Product\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"my-contract\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Error Responses:**
- `400 Bad Request`: Invalid ODPS document or missing required fields
- `500 Internal Server Error`: Workflow execution failed

**Notes:**
- The Product-First flow automatically extracts the ODCS contract from `product.contract.spec` in the ODPS document
- Both contracts are created with bidirectional linking stored in `hub_contract_json.extensions.x_odps`
- The workflow instance ID can be used to track the creation process

---

## Export Endpoints

### Export Contract

**GET** `/api/v1/contracts/{id}/export/`

Export a contract in various formats (ODPS, ODCS, or HubContract).

**Path Parameters:**
- `id` (UUID): Contract UUID

**Query Parameters:**
- `format` (string, optional): Export format - `odps`, `odcs`, or `hubcontract` (default: `hubcontract`)
- `output_format` (string, optional): Output format - `json` or `yaml` (default: `json`)
- `version` (string, optional): ODPS version (e.g., `4.1`). Only used for ODPS format export (default: `4.1`)

**Response (200 OK):**

The response format depends on the requested format:

**HubContract Format (JSON):**
```json
{
  "hub_contract_version": "1.0.0",
  "id": "contract-1",
  "info": {"name": "Contract 1"},
  "schema": {"fields": [...]},
  ...
}
```

**HubContract Format (YAML):**
Content-Type: `application/x-yaml`
```
hub_contract_version: 1.0.0
id: contract-1
info:
  name: Contract 1
schema:
  fields: []
...
```

**ODPS Format (JSON):**
```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "marketplace": {
      "pricingPlans": [...]
    }
  }
}
```

**ODPS Format (YAML):**
Content-Type: `application/x-yaml`
```
schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: customer-analytics
      name: Customer Analytics Dataset
  marketplace:
    pricingPlans: []
...
```

**ODCS Format (JSON):**
```json
{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "contract-1",
  "name": "Contract 1",
  "schema": {
    "fields": [...]
  }
}
```

**ODCS Format (YAML):**
Content-Type: `application/x-yaml`
```
apiVersion: odcs/v3
kind: DataContract
id: contract-1
name: Contract 1
schema:
  fields: []
...
```

**Example Requests:**
```bash
# Export as ODPS JSON
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export as ODPS YAML
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Export as HubContract JSON
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=hubcontract&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Invalid format parameter or contract cannot be exported in requested format
- `404 Not Found`: Contract not found

**Notes:**
- ODPS export generates ODPS format from HubContract (may embed original ODCS if available)
- ODCS export prefers `original_raw` if available, otherwise attempts to generate from HubContract
- HubContract export returns the normalized `hub_contract_json` directly

### Download Contract

**GET** `/api/v1/contracts/{id}/download/`

Download a contract as a file in various formats. Similar to export but returns a downloadable file with appropriate Content-Disposition header.

**Path Parameters:**
- `id` (UUID): Contract UUID

**Query Parameters:**
- `format` (string, optional): Export format - `odps`, `odcs`, or `hubcontract` (default: `hubcontract`)
- `output_format` (string, optional): Output format - `json` or `yaml` (default: `json`)
- `version` (string, optional): ODPS version (e.g., `4.1`). Only used for ODPS format (default: `4.1`)

**Response (200 OK):**

Returns the contract content as a downloadable file with appropriate Content-Type and Content-Disposition headers.

**Example Request:**
```bash
# Download as ODPS JSON file
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.json

# Download as ODPS YAML file
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.yaml
```

**Error Responses:**
- `400 Bad Request`: Invalid format parameter or contract cannot be exported in requested format
- `404 Not Found`: Contract not found

**Notes:**
- Same format options as export endpoint
- Returns file with appropriate filename in Content-Disposition header
- Useful for downloading contracts for local storage or sharing

---

## Linking Endpoints

### Link ODPS to ODCS Contract

**POST** `/api/v1/contracts/{id}/link-odps/`

Link an ODPS contract to an ODCS contract. The contract specified by `{id}` must be an ODCS contract. You can either link to an existing ODPS contract or create a new one.

**Path Parameters:**
- `id` (UUID): ODCS contract UUID

**Request Body (Link to Existing ODPS):**
```json
{
  "odps_contract_id": "existing-odps-contract-uuid"
}
```

**Request Body (Create New ODPS and Link):**
```json
{
  "original_raw": "ODPS document content (JSON or YAML string)",
  "original_format": "JSON" | "YAML",
  "resolve_external_refs": true,
  "odps_version": "4.1"
}
```

**Request Body Fields:**
- `odps_contract_id` (UUID, optional): Existing ODPS contract ID to link to (mutually exclusive with `original_raw`)
- `original_raw` (string, optional): ODPS document content to create new ODPS contract (mutually exclusive with `odps_contract_id`)
- `original_format` (string, required if `original_raw` provided): Format of ODPS document - "JSON" or "YAML"
- `resolve_external_refs` (boolean, optional): Whether to resolve external $ref references (default: true, only used if `original_raw` provided)
- `odps_version` (string, optional): ODPS version (e.g., "4.1"). Only used if `original_raw` provided

**Response (200 OK):**
```json
{
  "id": "odps-contract-uuid",
  "original_spec_type": "ODPS",
  "original_spec_version": "4.1",
  "status": "DRAFT",
  "normalization_status": "NORMALIZED_OK",
  "hub_contract_json": {
    "extensions": {
      "x_odps": {
        "odcs_link": "odcs-contract-uuid"
      }
    }
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Example Request (Link to Existing):**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/link-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odps_contract_id": "existing-odps-contract-uuid"
  }'
```

**Example Request (Create New and Link):**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/link-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Error Responses:**
- `400 Bad Request`: Contract is not ODCS type, invalid request body, or validation error
- `404 Not Found`: Contract or ODPS contract not found
- `500 Internal Server Error`: Linking operation failed

**Notes:**
- The contract specified by `{id}` must be an ODCS contract
- Bidirectional linking is automatically established in both contracts' `hub_contract_json.extensions.x_odps`
- If creating a new ODPS contract, it will be normalized and linked in a single operation

### Unlink ODPS from ODCS Contract

**POST** `/api/v1/contracts/{id}/unlink-odps/`

Remove the bidirectional link between an ODCS contract and its linked ODPS contract.

**Path Parameters:**
- `id` (UUID): ODCS contract UUID

**Response (200 OK):**
```json
{
  "message": "ODPS contract unlinked successfully"
}
```

**Example Request:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-id}/unlink-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Contract is not ODCS type or no link exists
- `404 Not Found`: Contract not found
- `500 Internal Server Error`: Unlinking operation failed

**Notes:**
- The contract specified by `{id}` must be an ODCS contract
- Removes the link from both the ODCS and ODPS contracts
- The contracts themselves are not deleted, only the link is removed

### List Contract Links

**GET** `/api/v1/contracts/{id}/links/`

Get all links for a contract (both ODPS and ODCS links).

**Path Parameters:**
- `id` (UUID): Contract UUID (can be ODPS or ODCS)

**Response (200 OK):**
```json
{
  "odps_link": {
    "id": "odps-contract-uuid",
    "original_spec_type": "ODPS",
    "original_spec_version": "4.1",
    "status": "DRAFT",
    "hub_contract_json": {...},
    ...
  },
  "odcs_link": null
}
```

**Response for ODPS Contract:**
```json
{
  "odps_link": null,
  "odcs_link": {
    "id": "odcs-contract-uuid",
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2",
    "status": "DRAFT",
    "hub_contract_json": {...},
    ...
  }
}
```

**Example Request:**
```bash
curl -X GET https://api.example.com/api/v1/contracts/{id}/links/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `404 Not Found`: Contract not found

**Notes:**
- Returns `null` for links that don't exist
- For ODCS contracts, returns the linked ODPS contract (if any)
- For ODPS contracts, returns the linked ODCS contract (if any)
- Both links are stored in `hub_contract_json.extensions.x_odps`

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

## Compliance

### List Compliance Runs

**GET** `/api/v1/compliance/runs/`

List all compliance runs with filtering, sorting, and pagination.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 50, max: 100)
- `ordering` (string): Sort fields (comma-separated, prefix with `-` for descending)
- `asset_id` (UUID): Filter by asset ID
- `dataset_id` (UUID): Filter by dataset ID
- `file_id` (UUID): Filter by file ID
- `status` (string): Filter by status (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`)
- `scan_mode` (string): Filter by scan mode (`internal`, `external`)
- `limit` (integer): Maximum number of results (alternative to pagination)
- `offset` (integer): Number of results to skip (alternative to pagination)

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://localhost:8000/api/v1/compliance/runs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "dataset_id": null,
      "file_id": null,
      "status": "SUCCEEDED",
      "scan_mode": "internal",
      "overall_status": "PASS",
      "risk_level": "LOW",
      "allowed_to_store": true,
      "regulations": ["GDPR", "LGPD"],
      "created_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:30:05Z",
      "completed_at": "2025-01-15T10:35:00Z",
      "job": {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "status": "COMPLETED"
      }
    }
  ]
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/?asset_id=660e8400-e29b-41d4-a716-446655440001&status=SUCCEEDED" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions

### Create Compliance Run

**POST** `/api/v1/compliance/runs/`

Create a new compliance run for an asset, dataset, or file.

**Request Body:**
```json
{
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": "770e8400-e29b-41d4-a716-446655440003",
  "file_id": "880e8400-e29b-41d4-a716-446655440004",
  "scan_mode": "internal",
  "applicable_regulations": ["GDPR", "HIPAA"]
}
```

**Request Body Parameters:**
- `asset_id` (UUID, optional): Asset ID to scan
- `dataset_id` (UUID, optional): Dataset ID to scan
- `file_id` (UUID, optional): File ID to scan (scan-only mode)
- `scan_mode` (string, required): Scan mode - `internal` (full scan) or `external` (scan-only)
- `applicable_regulations` (array of strings, optional): List of regulations to check (e.g., `["GDPR", "HIPAA", "LGPD", "CCPA", "SOX"]`)

**Note:** At least one of `asset_id`, `dataset_id`, or `file_id` must be provided.

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": null,
  "file_id": null,
  "status": "PENDING",
  "scan_mode": "internal",
  "regulations": ["GDPR", "LGPD"],
  "created_at": "2025-01-15T10:30:00Z",
  "job": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "status": "PENDING"
  }
}
```

**Example Request:**
```bash
curl -X POST "https://api.example.com/api/v1/compliance/runs/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "660e8400-e29b-41d4-a716-446655440001",
    "scan_mode": "internal",
    "applicable_regulations": ["GDPR", "HIPAA"]
  }'
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or missing required fields
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Asset, dataset, or file not found

### Get Compliance Run

**GET** `/api/v1/compliance/runs/{id}/`

Retrieve a specific compliance run by ID.

**Path Parameters:**
- `id` (UUID): Compliance run UUID

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": null,
  "file_id": null,
  "status": "SUCCEEDED",
  "scan_mode": "internal",
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "regulations": ["GDPR", "LGPD"],
  "detected_categories_json": {
    "EMAIL": 10,
    "PHONE": 5,
    "SSN": 2
  },
  "column_findings_json": [
    {
      "column": "email",
      "category": "EMAIL",
      "risk_level": "LOW"
    }
  ],
  "regulation_mapping_json": {
    "GDPR": {
      "status": "COMPLIANT",
      "violations": []
    }
  },
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "completed_at": "2025-01-15T10:35:00Z",
  "job": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "status": "COMPLETED",
    "started_at": "2025-01-15T10:30:05Z",
    "completed_at": "2025-01-15T10:35:00Z"
  }
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/550e8400-e29b-41d4-a716-446655440000/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Compliance run not found

### Get Compliance Run Results

**GET** `/api/v1/compliance/runs/{id}/results/`

Get detailed compliance scan results for a completed compliance run.

**Path Parameters:**
- `id` (UUID): Compliance run UUID

**Response (200 OK):**
```json
{
  "compliance_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "detected_categories": {
    "EMAIL": 10,
    "PHONE": 5,
    "SSN": 2
  },
  "column_findings": [
    {
      "column": "email",
      "category": "EMAIL",
      "risk_level": "LOW",
      "confidence": 0.95
    },
    {
      "column": "phone_number",
      "category": "PHONE",
      "risk_level": "MEDIUM",
      "confidence": 0.87
    }
  ],
  "regulation_mapping": {
    "GDPR": {
      "status": "COMPLIANT",
      "violations": [],
      "requirements_met": 15,
      "requirements_total": 15
    },
    "HIPAA": {
      "status": "COMPLIANT",
      "violations": [],
      "requirements_met": 12,
      "requirements_total": 12
    }
  },
  "metadata": {
    "scan_duration_seconds": 295.5,
    "rows_scanned": 100000,
    "columns_scanned": 25
  }
}
```

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/compliance/runs/550e8400-e29b-41d4-a716-446655440000/results/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Error Responses:**
- `400 Bad Request`: Compliance run not completed yet
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Compliance run not found

**Notes:**
- Results are only available for completed compliance runs (`status` = `SUCCEEDED` or `FAILED`)
- For runs with `status` = `PENDING` or `RUNNING`, this endpoint returns `400 Bad Request`
- Results include detailed PII detection, risk assessment, and regulatory compliance mapping

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

### Get Lineage

**GET** `/api/v1/observability/lineage/`

Get contract-level lineage (delegates to contract lineage service; tenant isolation enforced).

**Query Parameters:**
- `contract_id` (UUID, required): Contract UUID to retrieve lineage for.

**Response (200 OK):**
```json
{
  "contracts": [
    { "namespace": "ns1", "name": "upstream-contract", "id": "up-1" }
  ],
  "entries": [
    { "type": "derived", "source": "up-1", "target": "self" }
  ]
}
```

**Response (400 Bad Request)** — missing `contract_id`, invalid UUID format, or user has no tenant:
```json
{ "error": "contract_id query parameter is required" }
```
or (invalid UUID format for `contract_id`):
```json
{ "error": "Invalid UUID format for contract_id", "code": "INVALID_UUID" }
```
or (user has no tenant):
```json
{ "error": "User must belong to a tenant to view observability data" }
```

**Response (404 Not Found)** — contract not found or not accessible (e.g. different tenant):
```json
{ "error": "Contract not found", "code": "NOT_FOUND" }
```

---

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

## Versioning

Minimal Versioning API for listing and comparing contract and dataset versions (Phase 2 Gap Remediation). All endpoints require authentication and are tenant-scoped.

### List Versions

**GET** `/api/v1/versioning/versions/`

List versions for a resource (contract or dataset) by asset id.

**Query Parameters:**
- `resource_type` (string, required): `contract` or `dataset`
- `resource_id` (UUID, required): Asset UUID

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "resource_type": "contract",
      "version": 2,
      "semantic_version": "3.0.2",
      "created_at": "2025-01-15T10:00:00Z",
      "is_current": null
    }
  ]
}
```

**Error Responses:**
- `400`: Missing or invalid `resource_type` / `resource_id`; user without tenant
- `401`: Unauthenticated

### Get Version

**GET** `/api/v1/versioning/versions/{id}/`

Retrieve a single version (contract or dataset) by id.

**Response (200 OK):** Object with `id`, `resource_type`, `version`, `semantic_version`, `created_at`, `updated_at`, `is_current`, and optionally `status`, `original_spec_version`.

**Error Responses:**
- `404`: Version not found or not in tenant
- `401`: Unauthenticated

### Compare Versions

**GET** `/api/v1/versioning/compare/`

Compare two versions (same resource type).

**Query Parameters:**
- `resource_type` (string, required): `contract` or `dataset`
- `id_a` (UUID, required): First version id
- `id_b` (UUID, required): Second version id

**Response (200 OK):**
```json
{
  "id_a": "550e8400-e29b-41d4-a716-446655440001",
  "id_b": "550e8400-e29b-41d4-a716-446655440002",
  "resource_type": "contract",
  "version_a": 1,
  "version_b": 2,
  "created_at_a": "2025-01-15T10:00:00Z",
  "created_at_b": "2025-01-16T11:00:00Z"
}
```

**Error Responses:**
- `400`: Missing `id_a` / `id_b` or invalid `resource_type`
- `404`: One or both versions not found or not in tenant
- `401`: Unauthenticated

---

## Workflows

Workflow definitions and trigger (create/start instance). Tenant required; tenant isolation enforced on trigger.

### List Workflows

**GET** `/api/v1/workflows/`

List workflow definitions with optional filters and pagination.

**Query Parameters:**
- `name` (string, optional): Filter by workflow name
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Page size (default: 50, max: 100)

**Response (200 OK):**
```json
{
  "count": 11,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "version_creation",
      "version": "1.0.0",
      "description": null,
      "is_active": true,
      "dependencies": [],
      "metadata": {},
      "created_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

**Response (400 Bad Request)** — user has no tenant:
```json
{ "error": "User must belong to a tenant to access the Workflows API" }
```

**Response (401 Unauthorized)** — not authenticated.

---

### Get Workflow

**GET** `/api/v1/workflows/{name}/`

Get a workflow definition by name. Optional query `version` for a specific version.

**Query Parameters:**
- `version` (string, optional): Workflow version (e.g. `1.0.0`). If omitted, returns the active version.

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "version_creation",
  "version": "1.0.0",
  "description": null,
  "dsl_json": { "version": "1.0.0", "steps": [...] },
  "is_active": true,
  "dependencies": [],
  "metadata": {},
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**Response (404 Not Found)** — workflow not found:
```json
{ "error": "Workflow not found: {name}", "code": "NOT_FOUND" }
```

---

### Trigger Workflow

**POST** `/api/v1/workflows/{name}/trigger/`

Create a new workflow instance (and optionally start it immediately). Instance is created for the authenticated user's tenant.

**Request Body:**
```json
{
  "input_data": {},
  "start_immediately": false
}
```
- `input_data` (object, optional): Workflow input data; must be a JSON object (default: `{}`)
- `start_immediately` (boolean, optional): If `true`, start the instance after creation (default: `false`)

**Response (201 Created):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "DRAFT",
  "workflow_name": "version_creation",
  "workflow_version": "1.0.0",
  "created_at": "2025-01-15T11:00:00Z"
}
```
When `start_immediately` was `true`, the response may include:
- `started` (boolean): `true` if start succeeded, `false` if start failed
- `start_error` (string, optional): Error message if start was requested but failed (instance remains in DRAFT)

**Response (404 Not Found)** — workflow definition not found:
```json
{ "error": "Workflow definition not found: {name}", "code": "WORKFLOW_NOT_FOUND" }
```

**Response (400 Bad Request)** — user has no tenant, invalid body (e.g. `input_data` not a JSON object), or validation errors.

---

## Marketplace (listings and data preview)

Listings and orders are under `/api/v1/marketplace/`. Data preview is available for published listings (Phase 4 Gap Remediation).

### Data preview (listing)

**GET** `/api/v1/marketplace/listings/{id}/preview/`

Preview sample data, schema, and quality metrics for a **published** listing before purchase. Requires authentication.

**Path Parameters:**
- `id` (UUID): Listing ID.

**Response (200 OK):**
```json
{
  "listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440001",
  "sample_data": {
    "rows": [ { "id": "1", "name": "test1", "value": 100 } ],
    "total_rows": 1000,
    "sample_size": 10
  },
  "quality_metrics": {
    "completeness": 0.95,
    "accuracy": 1.0,
    "freshness": "current",
    "overall_score": 0.95
  },
  "schema": {
    "fields": [
      { "name": "id", "type": "string", "nullable": false },
      { "name": "name", "type": "string", "nullable": false }
    ]
  },
  "trust_signals": { "badges": ["quality_verified"], "quality_sla": "99.5%" },
  "preview_expires_at": "2025-01-15T12:00:00Z"
}
```
- `quality_metrics`: From latest successful DQ run for the asset (null if none).
- `trust_signals`: Optional; from listing `metadata_json.trust_signals` when set.
- `preview_expires_at`: Preview validity (e.g. 1 hour).

**Response (403 Forbidden)** — listing not published:
```json
{ "error": "Preview is only available for published listings" }
```

**Response (400 Bad Request)** — listing has no associated asset (defensive; normal listings always have an asset):
```json
{ "error": "Listing has no associated asset" }
```

**Response (404 Not Found)** — no dataset for the listing's asset:
```json
{ "error": "No dataset found for this asset" }
```

**Response (401 Unauthorized)** — not authenticated.

### Trust signals configuration API

Tenant-scoped CRUD for trust signal definitions (badges, quality SLAs). Supports UC-MKT-ADV-003 (Manage Trust Signals) and UC-MKT-ADV-005 (Configure Data Quality SLAs). Requires authentication; list/retrieve/update/delete are filtered by the request tenant.

**Base path:** `/api/v1/marketplace/config/trust-signals/`

#### List trust signal configs

**GET** `/api/v1/marketplace/config/trust-signals/`

Returns trust signal configs for the current tenant (paginated). Platform admins see all.

**Response (200 OK):** Paginated list of objects: `id`, `tenant_id`, `name`, `kind` (`badge` | `quality_sla`), `config` (JSON), `is_active`, `created_at`, `updated_at`.

#### Create trust signal config

**POST** `/api/v1/marketplace/config/trust-signals/`

**Request Body:**
```json
{
  "name": "quality_verified",
  "kind": "badge",
  "config": { "description": "Quality verified by DQ run" }
}
```
- `name`: string, unique per tenant
- `kind`: `badge` or `quality_sla`
- `config`: JSON object (e.g. `description` for badge; `availability`, `freshness_hours` for quality_sla)
- `is_active`: optional boolean, default true

**Response (201 Created):** Created object with `id`, `tenant_id`, `name`, `kind`, `config`, `is_active`, `created_at`, `updated_at`.

**Response (400 Bad Request):** Validation error (e.g. missing name/kind). Duplicate name per tenant returns `{"error": "A trust signal config with this name already exists for your tenant.", "code": "DUPLICATE_NAME"}`.

#### Retrieve trust signal config

**GET** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (200 OK):** Single config object. **Response (404 Not Found):** Config not found or belongs to another tenant.

#### Update trust signal config

**PUT** `/api/v1/marketplace/config/trust-signals/{id}/`  
**PATCH** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (200 OK):** Updated object. **Response (400 Bad Request):** Duplicate name (same as create; `code`: `DUPLICATE_NAME`). **Response (404 Not Found):** Config not found or belongs to another tenant.

#### Delete trust signal config

**DELETE** `/api/v1/marketplace/config/trust-signals/{id}/`

**Response (204 No Content):** Deleted. **Response (404 Not Found):** Config not found or belongs to another tenant.

**Response (401 Unauthorized):** Not authenticated.

See [FEATURES.md – Trust signals](FEATURES.md#trust-signals).

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

### Get Current User / Update Profile (useronboardfix Phase 7)

**GET** `/api/v1/auth/me/` — Returns current user: `id`, `email`, `name`, `tenant_id`, `roles`, `permissions`, `avatar`, `preferences`, `feature_tenant_switch_enabled`.

**PATCH** `/api/v1/auth/me/` — Partial update. Request body: `{"display_name": "…", "avatar": "…", "preferences": {"theme": "dark"}}`. All fields optional. Requires authentication.

See [API_REFERENCE.md](API_REFERENCE.md#user-profile) for full details.

### List My Tenants (Tenant Switch)

**GET** `/api/v1/auth/me/tenants/`

Returns list of tenants the current user has membership in (from UserTenantMembership). Used for tenant switcher UI.

**Authentication**: Required (JWT token or session)

**Response (200 OK):**
```json
[
  { "id": "uuid", "name": "Tenant A", "slug": "tenant-a" },
  { "id": "uuid", "name": "Tenant B", "slug": "tenant-b" }
]
```

**Response (403 Forbidden):** Feature disabled (`FEATURE_TENANT_SWITCH_ENABLED=false`) or user not authenticated.

### Switch Tenant

**POST** `/api/v1/auth/switch-tenant/`

Switch active tenant context. Validates user has membership in target tenant; returns updated me summary with `tenant_id` overridden.

**Authentication**: Required (JWT token or session)

**Request Body:**
```json
{
  "tenant_id": "uuid-of-target-tenant"
}
```

**Response (200 OK):** Same shape as GET /auth/me/ with `tenant_id` set to the switched tenant.

**Response (400 Bad Request):** Missing or invalid `tenant_id` (not a valid UUID).

**Response (403 Forbidden):** Feature disabled, or user has no membership in target tenant.

**Response (404 Not Found):** Tenant not found.

**Note:** After switching, clients should send `X-Tenant-Id: <tenant_id>` on subsequent requests to scope operations to the switched tenant. See [TENANT_SWITCH_PLAN.md](TENANT_SWITCH_PLAN.md).

---

## Tenants (useronboardfix)

### Get Tenant Usage

**GET** `/api/v1/tenants/me/usage/`

Returns current tenant usage (storage, API calls, limits). Requires TENANT_ADMIN or PLATFORM_ADMIN.

**Response (200 OK):**
```json
{
  "storage_bytes": 1073741824,
  "api_calls_count": 1500,
  "limits": {"storage_bytes": 5368709120, "api_calls_per_month": 10000}
}
```

### Get / Update Tenant Config

**GET** `/api/v1/tenants/me/config/` — Returns tenant configuration (trust signals, versioning, workflows, default_dq_profile, etc.).

**PATCH** `/api/v1/tenants/me/config/` — Update tenant configuration. Request body: partial config object. Requires TENANT_ADMIN or PLATFORM_ADMIN.

---

## Billing (useronboardfix)

### Get Current Subscription

**GET** `/api/v1/billing/subscription/current/` — Returns current subscription (plan, status, limits). See [BILLING.md](BILLING.md).

### Change Subscription Plan

**POST** `/api/v1/billing/subscription/current/change-plan/` — Body: `{"plan_slug": "pro"}`. Requires TENANT_ADMIN or PLATFORM_ADMIN. Runbook: [Subscription plan change failures](RUNBOOKS.md#subscription-plan-change-failures).

### List Plans / Invoices

**GET** `/api/v1/billing/plans/` — List available plans for subscription change.

**GET** `/api/v1/billing/invoices/` — List invoices for tenant.

**GET** `/api/v1/billing/invoices/{id}/` — Get invoice detail.

**GET** `/api/v1/billing/invoices/{id}/download/` — Redirect to invoice PDF or hosted URL.

See [BILLING.md](BILLING.md) for full documentation.

---

## Users (useronboardfix)

### Update User (Admin Edit)

**PUT** `/api/v1/users/{id}/` — Update user (roles, status). Requires TENANT_ADMIN or PLATFORM_ADMIN. Tenant-scoped: tenant admin can only edit users in their tenant.

---

## Marketplace Integration Endpoints

### List Marketplace Connections

**GET** `/api/v1/integrations/marketplace/connections/`

List all marketplace connections for the authenticated user's tenant with filtering, pagination, and search.

**Query Parameters:**
- `marketplace_type` (string, optional): Filter by marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `is_active` (boolean, optional): Filter by active status (`true`/`false`)
- `search` (string, optional): Search in connection name
- `ordering` (string, optional): Order by field (e.g., `name`, `-created_at`). Prefix with `-` for descending
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required (JWT token or API key)

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 10,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Snowflake Production",
      "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
      "is_active": true,
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Connection

**GET** `/api/v1/integrations/marketplace/connections/{id}/`

Get detailed information about a specific marketplace connection.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Connection not found
- `403 Forbidden`: Insufficient permissions

### Create Marketplace Connection

**POST** `/api/v1/integrations/marketplace/connections/`

Create a new marketplace connection.

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "config": {
    "account": "myaccount",
    "username": "user",
    "password": "password",
    "warehouse": "COMPUTE_WH",
    "database": "MARKETPLACE_DB"
  }
}
```

**Request Body Fields:**
- `name` (string, required): Connection name
- `marketplace_type` (string, required): Marketplace type (e.g., `SNOWFLAKE_DATA_MARKETPLACE`, `AWS_DATA_EXCHANGE`)
- `config` (object, required): Marketplace-specific configuration (credentials, endpoints, etc.)

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or validation error
- `403 Forbidden`: Insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded

**Rate Limiting**: 10 requests per hour per user

### Update Marketplace Connection

**PATCH** `/api/v1/integrations/marketplace/connections/{id}/`

Update a marketplace connection (partial update supported).

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "name": "Snowflake Production Updated",
  "config": {
    "warehouse": "NEW_COMPUTE_WH"
  }
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Snowflake Production Updated",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "is_active": true,
  "updated_at": "2025-01-15T11:00:00Z"
}
```

**Rate Limiting**: 20 requests per hour per user

### Delete Marketplace Connection

**DELETE** `/api/v1/integrations/marketplace/connections/{id}/`

Delete a marketplace connection.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (204 No Content)**

**Rate Limiting**: 10 requests per hour per user

### Test Marketplace Connection

**POST** `/api/v1/integrations/marketplace/connections/{id}/test/`

Test a marketplace connection to verify credentials and connectivity.

**Path Parameters:**
- `id` (UUID): Connection UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Connection test successful",
  "tested_at": "2025-01-15T10:35:00Z",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "response_time_ms": 245
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "message": "Connection test failed: Invalid credentials",
  "tested_at": "2025-01-15T10:35:00Z",
  "error": "Authentication failed"
}
```

**Rate Limiting**: 20 requests per hour per user

---

### List Marketplace Sync Jobs

**GET** `/api/v1/integrations/marketplace/sync/`

List all marketplace sync jobs for the authenticated user's tenant.

**Query Parameters:**
- `connection_id` (UUID, optional): Filter by connection ID
- `direction` (string, optional): Filter by sync direction (`PUSH`, `PULL`, `BIDIRECTIONAL`)
- `status` (string, optional): Filter by status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`, `CANCELLED`)
- `ordering` (string, optional): Order by field (e.g., `-created_at`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 25,
  "page": 1,
  "page_size": 50,
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
      "created_at": "2025-01-15T10:00:00Z",
      "completed_at": "2025-01-15T10:05:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Sync Job

**GET** `/api/v1/integrations/marketplace/sync/{id}/`

Get detailed information about a specific marketplace sync job.

**Path Parameters:**
- `id` (UUID): Sync job UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
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
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z",
  "completed_at": "2025-01-15T10:05:00Z"
}
```

### Create Marketplace Sync Job

**POST** `/api/v1/integrations/marketplace/sync/`

Create a new marketplace sync job.

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body (PULL sync):**
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

**Request Body (PUSH sync):**
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

**Request Body Fields:**
- `connection_id` (UUID, required): Connection UUID
- `direction` (string, required): Sync direction (`PUSH`, `PULL`, or `BIDIRECTIONAL`)
- `asset_ids` (array of UUIDs, optional): Hub asset IDs for PUSH sync
- `listing_ids` (array of strings, optional): External listing IDs for PULL sync
- `filters` (object, optional): Filters for PULL sync
- `options` (object, optional): Sync options (dry_run, data_strategy, etc.)

**Response (201 Created):**
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
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z",
  "completed_at": null
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body or validation error
- `404 Not Found`: Connection not found
- `429 Too Many Requests`: Rate limit exceeded

**Rate Limiting**: 10 requests per hour per user

**Note**: Sync jobs are executed asynchronously. Use the GET endpoint to monitor progress.

### Cancel Marketplace Sync Job

**POST** `/api/v1/integrations/marketplace/sync/{id}/cancel/`

Cancel a running marketplace sync job.

**Path Parameters:**
- `id` (UUID): Sync job UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Request Body:**
```json
{
  "reason": "User requested cancellation"
}
```

**Response (200 OK):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "CANCELLED",
  "metadata": {
    "cancellation_reason": "User requested cancellation"
  },
  "updated_at": "2025-01-15T10:03:00Z",
  "completed_at": "2025-01-15T10:03:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Job cannot be cancelled (already completed/failed/cancelled)
- `404 Not Found`: Sync job not found

**Rate Limiting**: 20 requests per hour per user

---

### List Marketplace Mappings

**GET** `/api/v1/integrations/marketplace/mappings/`

List all marketplace mappings for the authenticated user's tenant.

**Query Parameters:**
- `connection_id` (UUID, optional): Filter by connection ID
- `hub_asset_id` (UUID, optional): Filter by hub asset ID
- `external_listing_id` (string, optional): Filter by external listing ID
- `ordering` (string, optional): Order by field (e.g., `-created_at`)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
```json
{
  "count": 50,
  "page": 1,
  "page_size": 50,
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
        "name": "Customer Analytics Dataset"
      },
      "external_listing_id": "SNOWFLAKE_LISTING_123",
      "created_at": "2025-01-15T10:00:00Z",
      "last_synced_at": "2025-01-15T10:05:00Z"
    }
  ]
}
```

**Rate Limiting**: 100 requests per hour per user

### Get Marketplace Mapping

**GET** `/api/v1/integrations/marketplace/mappings/{id}/`

Get detailed information about a specific marketplace mapping.

**Path Parameters:**
- `id` (UUID): Mapping UUID

**Authentication**: Required

**Authorization**: Authenticated user (tenant-scoped)

**Response (200 OK):**
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
    "name": "Customer Analytics Dataset"
  },
  "external_listing_id": "SNOWFLAKE_LISTING_123",
  "external_resource_ids": ["resource1", "resource2"],
  "sync_metadata": {
    "last_sync_status": "SUCCESS",
    "last_sync_errors": []
  },
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z",
  "last_synced_at": "2025-01-15T10:05:00Z"
}
```

### Delete Marketplace Mapping

**DELETE** `/api/v1/integrations/marketplace/mappings/{id}/`

Delete a marketplace mapping.

**Path Parameters:**
- `id` (UUID): Mapping UUID

**Authentication**: Required

**Authorization**: `DATA_PROVIDER` or `TENANT_ADMIN` role + `integrations:write` scope

**Response (204 No Content)**

**Rate Limiting**: 20 requests per hour per user

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
- [Marketplace API Reference](./MARKETPLACE_API_REFERENCE.md) - Complete marketplace API documentation
- [Interactive Documentation](../api-docs/)
- [OpenAPI Schema](../api-docs/openapi.json)
- [Scheduled Ingestion API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_INGESTION.md) - Complete scheduled ingestion API documentation (public and internal worker API)
- [Scheduled Export API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md) - Complete scheduled export API documentation (public and internal worker API)

