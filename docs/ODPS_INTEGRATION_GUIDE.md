# ODPS Integration Guide

Complete engineering-grade guide for integrating with ODPS (Open Data Product Standard) in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [ODPS Ingestion](#odps-ingestion)
3. [Creation Flows](#creation-flows)
4. [Export and Download](#export-and-download)
5. [Workflow Details](#workflow-details)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

The Data Interoperability Hub provides comprehensive support for ODPS (Open Data Product Standard), a marketplace-focused specification that complements ODCS (Open Data Contract Standard) by adding product information, pricing plans, access methods, and payment gateways.

### Key Concepts

- **ODPS (Open Data Product Standard)**: Marketplace specification focusing on product information, pricing, and access methods
- **ODCS (Open Data Contract Standard)**: Technical specification focusing on data schema, quality, and compliance
- **Product-First Flow**: Automatically extracts ODCS contract from ODPS `product.contract` field
- **Link Flow**: Links ODPS contract to an existing ODCS contract

### Supported ODPS Versions

- ODPS 4.1 (primary support)
- ODPS 4.0 (backward compatible)
- Earlier versions (with limitations)

## ODPS Ingestion

ODPS documents can be ingested through multiple interfaces: REST API, CLI, Python SDK, and GraphQL.

### REST API Ingestion

#### Product-First Flow (Automatic ODCS Extraction)

**Endpoint:** `POST /api/v1/contracts/products/`

**Request Body:**
```json
{
  "original_raw": "ODPS document content (JSON or YAML string)",
  "original_format": "JSON" | "YAML",
  "resolve_external_refs": true,
  "asset_id": "optional-asset-uuid"
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

**Response (201 Created):**
```json
{
  "odps_contract": {
    "id": "odps-contract-uuid",
    "original_spec_type": "ODPS",
    "original_spec_version": "4.1",
    "status": "DRAFT",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "odcs_contract": {
    "id": "odcs-contract-uuid",
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2",
    "status": "DRAFT",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "workflow_instance_id": "workflow-instance-uuid"
}
```

#### Link Flow (Link to Existing ODCS)

**Endpoint:** `POST /api/v1/contracts/`

**Request Body:**
```json
{
  "original_raw": "ODPS document content (without product.contract.spec)",
  "original_format": "JSON" | "YAML",
  "original_spec_type": "ODPS",
  "link_odcs_id": "existing-odcs-contract-uuid"
}
```

**Example Request:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}",
    "original_format": "JSON",
    "original_spec_type": "ODPS",
    "link_odcs_id": "existing-odcs-contract-uuid"
  }'
```

**Response (201 Created):**
```json
{
  "id": "odps-contract-uuid",
  "original_spec_type": "ODPS",
  "original_spec_version": "4.1",
  "status": "DRAFT",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### CLI Ingestion

#### Product-First Flow

```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id> \
  --resolve-external-refs
```

**Output:**
```
✓ ODPS contract created: <odps-id>
✓ ODCS contract created: <odcs-id>
Workflow instance: <workflow-instance-id>
```

#### Link Flow

```bash
datahub contracts create-odps \
  --file product.odps.json \
  --link-odcs <odcs-contract-id>
```

**Output:**
```
✓ ODPS contract created: <odps-id>
✓ Linked to ODCS contract: <odcs-contract-id>
```

### Python SDK Ingestion

#### Product-First Flow

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    odps_content = """{
      "schema": "https://opendataproducts.org/schema/v4.1",
      "version": "4.1",
      "product": {
        "details": {
          "en": {
            "productID": "my-product",
            "name": "My Data Product",
            "description": "A comprehensive data product"
          }
        },
        "contract": {
          "spec": {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "my-contract",
            "schema": {
              "fields": [{"name": "id", "type": "string"}]
            }
          }
        },
        "marketplace": {
          "pricingPlans": [
            {
              "planID": "basic",
              "name": "Basic Plan",
              "price": 9.99,
              "currency": "USD",
              "billingPeriod": "monthly"
            }
          ]
        }
      }
    }"""

    result = await client.contracts.create_odps(
        original_raw=odps_content,
        extract_odcs=True,  # Automatically extract ODCS from ODPS
        original_format="JSON",
        odps_version="4.1",
    )

    odps_contract = result["odps_contract"]
    odcs_contract = result["odcs_contract"]
    print(f"Created ODPS contract: {odps_contract['id']}")
    print(f"Created ODCS contract: {odcs_contract['id']}")
```

#### Link Flow

```python
odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "linked-product",
        "name": "Linked Data Product"
      }
    }
  }
}"""

odps_contract = await client.contracts.create_odps(
    original_raw=odps_content,
    link_odcs_id="existing-odcs-contract-id",
    original_format="JSON",
)
```

### GraphQL Ingestion

#### Product-First Flow

```graphql
mutation CreateODPSProduct {
  createODPS(input: {
    originalRaw: "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"my-product\",\"name\":\"My Data Product\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"my-contract\"}}}}}"
    originalFormat: JSON
    extractOdcs: true
    resolveExternalRefs: true
  }) {
    odpsContract {
      id
      originalSpecType
      originalSpecVersion
      status
    }
    odcsContract {
      id
      originalSpecType
      originalSpecVersion
      status
    }
    workflowInstanceId
  }
}
```

#### Link Flow

```graphql
mutation CreateODPSLink {
  createODPS(input: {
    originalRaw: "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}"
    originalFormat: JSON
    linkOdcsId: "existing-odcs-contract-id"
  }) {
    contract {
      id
      originalSpecType
      originalSpecVersion
      status
    }
  }
}
```

## Creation Flows

The Data Interoperability Hub supports two primary creation flows for ODPS contracts.

### Product-First Flow

The Product-First flow automatically extracts and creates an ODCS contract from the ODPS product's embedded contract.

#### Workflow Steps

1. **Parse ODPS**: Parse ODPS document, validate schema, detect version
2. **Resolve References**: Resolve `$ref` references (internal, local, external)
3. **Extract Contract**: Extract ODCS from `product.contract` (required)
4. **Validate ODCS**: Validate extracted ODCS contract
5. **Normalize ODCS**: Normalize ODCS → HubContract (technical)
6. **Normalize ODPS**: Normalize ODPS → HubContract (marketplace)
7. **Create ODCS Contract**: Create ODCS contract record
8. **Create ODPS Contract**: Create ODPS contract record
9. **Link Contracts**: Establish bidirectional link (ODPS ↔ ODCS)
10. **Link Data File** (optional): Link data file (create Asset)
11. **Index for Search**: Index for search (ODPS product + ODCS technical)
12. **Semantic Mapping**: Map ODPS to RDF (async job)

#### Requirements

- ODPS document must have `product.contract` field
- `product.contract` must contain one of:
  - `spec`: Inline ODCS contract
  - `$ref`: Reference to ODCS contract (resolved during workflow)
  - `contractURL`: External contract URL (not yet supported)

#### Example ODPS Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset",
        "description": "Comprehensive customer analytics data"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "customer-analytics-contract",
        "schema": {
          "fields": [
            {"name": "customer_id", "type": "string"},
            {"name": "purchase_date", "type": "date"},
            {"name": "amount", "type": "number"}
          ]
        },
        "quality": {
          "rules": [
            {
              "name": "non_null_customer_id",
              "type": "not_null",
              "field": "customer_id"
            }
          ]
        }
      }
    },
    "marketplace": {
      "pricingPlans": [
        {
          "planID": "basic",
          "name": "Basic Plan",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly"
        }
      ],
      "accessMethods": [
        {
          "methodID": "api",
          "type": "API",
          "endpoint": "https://api.example.com/customer-analytics"
        }
      ]
    }
  }
}
```

#### Error Handling

- **Missing `product.contract`**: Returns `400 Bad Request` with error code `REQUIRED_FIELD_MISSING`
- **Invalid ODCS in `product.contract.spec`**: Returns `400 Bad Request` with validation errors
- **External `$ref` resolution failure**: Retries up to 3 times with exponential backoff (1s, 2s, 4s)
- **Workflow failure**: Automatic rollback of created contracts

### Link Flow

The Link flow creates an ODPS contract and links it to an existing ODCS contract.

#### Workflow Steps

1. **Parse ODPS**: Parse ODPS document, validate schema, detect version
2. **Resolve References**: Resolve `$ref` references (internal, local, external)
3. **Normalize ODPS**: Normalize ODPS → HubContract (marketplace)
4. **Create ODPS Contract**: Create ODPS contract record
5. **Link Contracts**: Establish bidirectional link (ODPS ↔ ODCS)
6. **Index for Search**: Index for search (ODPS product)
7. **Semantic Mapping**: Map ODPS to RDF (async job)

#### Requirements

- ODPS document does not require `product.contract` field
- Existing ODCS contract must exist and be accessible
- ODCS contract must belong to the same tenant

#### Example ODPS Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset",
        "description": "Comprehensive customer analytics data"
      }
    },
    "marketplace": {
      "pricingPlans": [
        {
          "planID": "basic",
          "name": "Basic Plan",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly"
        }
      ]
    }
  }
}
```

#### Error Handling

- **ODCS contract not found**: Returns `404 Not Found` with error code `CONTRACT_NOT_FOUND`
- **ODCS contract belongs to different tenant**: Returns `403 Forbidden` with error code `TENANT_MISMATCH`
- **Invalid ODPS document**: Returns `400 Bad Request` with validation errors

## Export and Download

ODPS contracts can be exported and downloaded in multiple formats: JSON, YAML, and ODPS-specific formats.

### REST API Export

#### Export as JSON

**Endpoint:** `GET /api/v1/contracts/{id}/export/`

**Query Parameters:**
- `format`: `odps` (required for ODPS export)
- `output_format`: `json` (default) or `yaml`
- `version`: ODPS version (e.g., `4.1`, optional, defaults to contract version)

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
The endpoint returns the ODPS document directly as JSON (not wrapped):
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

#### Export as YAML

**Endpoint:** `GET /api/v1/contracts/{id}/export/`

**Query Parameters:**
- `format`: `odps`
- `output_format`: `yaml`
- `version`: ODPS version (optional)

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
The endpoint returns the ODPS document directly as a YAML string (not wrapped):
```
schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: customer-analytics
      name: Customer Analytics Dataset
...
```

### REST API Download

#### Download as JSON File

**Endpoint:** `GET /api/v1/contracts/{id}/download/`

**Query Parameters:**
- `format`: `odps`
- `output_format`: `json` (default) or `yaml`
- `version`: ODPS version (optional)

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.json
```

**Response (200 OK):**
- Content-Type: `application/json`
- Content-Disposition: `attachment; filename="product-{id}.odps.json"`
- Body: ODPS document as JSON string

#### Download as YAML File

**Endpoint:** `GET /api/v1/contracts/{id}/download/`

**Query Parameters:**
- `format`: `odps`
- `output_format`: `yaml`
- `version`: ODPS version (optional)

**Example Request:**
```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.yaml
```

**Response (200 OK):**
- Content-Type: `application/x-yaml`
- Content-Disposition: `attachment; filename="product-{id}.odps.yaml"`
- Body: ODPS document as YAML string

### CLI Export

#### Export as JSON

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format json \
  --version 4.1
```

**Output:**
```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {...}
}
```

#### Export as YAML

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format yaml
```

**Output:**
```yaml
schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: customer-analytics
      name: Customer Analytics Dataset
```

### CLI Download

#### Download as JSON File

```bash
datahub contracts download <contract-id> \
  --format odps \
  --output-format json \
  --output product.odps.json
```

**Output:**
```
✓ Contract downloaded successfully!
Contract ID: <contract-id>
Format: odps
Output Format: json
Saved to: product.odps.json
Size: 1234 bytes
```

#### Download as YAML File

```bash
datahub contracts download <contract-id> \
  --format odps \
  --output-format yaml \
  --output product.odps.yaml
```

**Output:**
```
✓ Contract downloaded successfully!
Contract ID: <contract-id>
Format: odps
Output Format: yaml
Saved to: product.odps.yaml
Size: 1234 bytes
```

### Python SDK Export

#### Export as JSON

```python
odps_json = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="json",
    version="4.1",  # Optional, defaults to contract version
)

print(odps_json["content"])
```

#### Export as YAML

```python
odps_yaml = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="yaml",
)

yaml_content = odps_yaml["content"]
print(yaml_content)
```

### Python SDK Download

#### Download as JSON File

```python
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="json",
)

with open("product.odps.json", "wb") as f:
    f.write(odps_file)
```

#### Download as YAML File

```python
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="yaml",
)

with open("product.odps.yaml", "wb") as f:
    f.write(odps_file)
```

## Workflow Details

### Product Creation Workflow

The Product Creation Workflow (`ProductCreationWorkflow`) orchestrates the complete ODPS product creation process with proper error handling, retry logic, and compensation.

#### Workflow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Product Creation Workflow                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Parse ODPS                                              │
│     ├─ Validate schema                                      │
│     ├─ Detect version                                      │
│     └─ Parse JSON/YAML                                     │
│                                                             │
│  2. Resolve References                                      │
│     ├─ Internal $ref (#/paths/...)                         │
│     ├─ Local $ref (file://...)                             │
│     └─ External $ref (https://...) [retry: 3x]              │
│                                                             │
│  3. Extract Contract                                        │
│     ├─ From product.contract.spec (inline)                 │
│     ├─ From product.contract.$ref (resolved)              │
│     └─ Validate extraction                                  │
│                                                             │
│  4. Validate ODCS                                           │
│     ├─ Schema validation                                    │
│     ├─ Required fields                                     │
│     └─ Type checking                                       │
│                                                             │
│  5. Normalize ODCS → HubContract                            │
│     ├─ Map ODCS fields to HubContract                      │
│     ├─ Extract schema, quality, compliance                │
│     └─ Store in hub_contract_json                          │
│                                                             │
│  6. Normalize ODPS → HubContract                            │
│     ├─ Map ODPS fields to HubContract                      │
│     ├─ Extract marketplace, pricing, access                │
│     └─ Store in hub_contract_json                          │
│                                                             │
│  7. Create ODCS Contract                                    │
│     ├─ Create Contract record                              │
│     ├─ Set original_spec_type=ODCS                        │
│     └─ Store original_raw, hub_contract_json               │
│                                                             │
│  8. Create ODPS Contract                                    │
│     ├─ Create Contract record                              │
│     ├─ Set original_spec_type=ODPS                         │
│     └─ Store original_raw, hub_contract_json               │
│                                                             │
│  9. Link Contracts                                          │
│     ├─ ODPS → ODCS: hub_contract_json.extensions.x_odps.odcs_link │
│     └─ ODCS → ODPS: hub_contract_json.extensions.x_odps.odps_link │
│                                                             │
│  10. Link Data File (optional)                               │
│     ├─ Create Asset if file_id provided                    │
│     └─ Link contracts to asset                             │
│                                                             │
│  11. Index for Search                                       │
│     ├─ Index ODPS contract (marketplace data)              │
│     └─ Index ODCS contract (technical data)                │
│                                                             │
│  12. Semantic Mapping                                       │
│     ├─ Map ODPS to RDF (async)                             │
│     └─ Map ODCS to RDF (async)                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Compensation (Rollback)

If any step fails, the workflow automatically rolls back:

- **Step 7 failure**: Delete created ODCS contract
- **Step 8 failure**: Delete created ODPS contract
- **Step 9 failure**: Remove bidirectional links
- **Step 10 failure**: Delete created asset, unlink contracts

#### Retry Logic

- **External $ref resolution**: 3 retries with exponential backoff (1s, 2s, 4s)
- **Transient errors**: Network timeouts, connection errors, rate limits
- **Non-transient errors**: Schema validation, missing fields (no retry)

### Contract Linking

Contracts are linked bidirectionally through `hub_contract_json.extensions.x_odps`:

**ODPS Contract:**
```json
{
  "extensions": {
    "x_odps": {
      "odcs_link": "odcs-contract-uuid"
    }
  }
}
```

**ODCS Contract:**
```json
{
  "extensions": {
    "x_odps": {
      "odps_link": "odps-contract-uuid"
    }
  }
}
```

## Error Handling

### Error Codes

| Error Code | Description | HTTP Status |
|------------|-------------|-------------|
| `REQUIRED_FIELD_MISSING` | Required field missing in ODPS document | 400 |
| `SCHEMA_VALIDATION_FAILED` | ODPS schema validation failed | 400 |
| `INVALID_DATA_TYPE` | Invalid data type for field | 400 |
| `INVALID_VALUE` | Invalid value for field | 400 |
| `REF_RESOLUTION_FAILED` | Failed to resolve $ref reference | 400 |
| `ODCS_VALIDATION_ERROR` | ODCS contract validation failed | 400 |
| `ODCS_NORMALIZATION_ERROR` | ODCS normalization failed | 400 |
| `ODPS_NORMALIZATION_ERROR` | ODPS normalization failed | 400 |
| `ODPS_LINKING_ERROR` | Contract linking failed | 400 |
| `CONTRACT_NOT_FOUND` | Contract not found | 404 |
| `TENANT_MISMATCH` | Contract belongs to different tenant | 403 |
| `WORKFLOW_EXECUTION_FAILED` | Workflow execution failed | 400 |
| `EXPORT_FAILED` | Export operation failed | 500 |
| `DOWNLOAD_FAILED` | Download operation failed | 500 |

### Error Response Format

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field_path": "/product/contract",
    "context": {
      "field_name": "product.contract",
      "validation_errors": [...]
    }
  }
}
```

### Common Errors

#### Missing `product.contract`

**Error:**
```json
{
  "error": "ODPS product.contract is required but missing",
  "code": "REQUIRED_FIELD_MISSING",
  "details": {
    "field_path": "/product/contract",
    "context": {
      "field_name": "product.contract"
    }
  }
}
```

**Solution:** Add `product.contract` field with either `spec`, `$ref`, or `contractURL`.

#### Invalid ODCS in `product.contract.spec`

**Error:**
```json
{
  "error": "ODCS validation failed: schema.fields is required",
  "code": "ODCS_VALIDATION_ERROR",
  "details": {
    "validation_errors": [
      {
        "path": "/schema/fields",
        "message": "schema.fields is required"
      }
    ]
  }
}
```

**Solution:** Ensure `product.contract.spec` contains a valid ODCS contract with required fields.

#### External $ref Resolution Failure

**Error:**
```json
{
  "error": "Failed to resolve $ref references after 3 attempts: Connection timeout",
  "code": "REF_RESOLUTION_FAILED",
  "details": {
    "ref_path": "/product/contract/$ref",
    "ref_type": "external",
    "attempts": 3,
    "max_retries": 3
  }
}
```

**Solution:** Check network connectivity, verify external URL is accessible, or use inline `spec` instead of `$ref`.

## Best Practices

### ODPS Document Structure

1. **Always include `schema` and `version`**:
   ```json
   {
     "schema": "https://opendataproducts.org/schema/v4.1",
     "version": "4.1"
   }
   ```

2. **Use descriptive `productID`**:
   ```json
   {
     "product": {
       "details": {
         "en": {
           "productID": "customer-analytics-v1",
           "name": "Customer Analytics Dataset"
         }
       }
     }
   }
   ```

3. **Include complete marketplace information**:
   ```json
   {
     "product": {
       "marketplace": {
         "pricingPlans": [...],
         "accessMethods": [...],
         "paymentGateways": [...]
       }
     }
   }
   ```

### Product-First vs Link Flow

- **Use Product-First Flow** when:
  - Creating new products with both technical and marketplace specifications
  - ODCS contract is embedded in ODPS document
  - You want automatic ODCS extraction

- **Use Link Flow** when:
  - ODCS contract already exists
  - You want to add marketplace information to existing technical contract
  - ODCS and ODPS are managed separately

### Reference Resolution

1. **Prefer inline `spec`** over `$ref` for better performance:
   ```json
   {
     "product": {
       "contract": {
         "spec": {
           "apiVersion": "odcs/v3",
           "kind": "DataContract",
           ...
         }
       }
     }
   }
   ```

2. **Use internal `$ref`** for reusable components:
   ```json
   {
     "definitions": {
       "schema": {
         "fields": [...]
       }
     },
     "product": {
       "contract": {
         "$ref": "#/definitions/schema"
       }
     }
   }
   ```

3. **Avoid external `$ref`** when possible (requires network access, retries on failure)

### Export and Download

1. **Specify ODPS version** for consistent exports:
   ```bash
   curl "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.1"
   ```

2. **Use YAML for human-readable exports**:
   ```bash
   datahub contracts export <id> --format odps --output-format yaml
   ```

3. **Use JSON for programmatic consumption**:
   ```bash
   datahub contracts export <id> --format odps --output-format json
   ```

## Troubleshooting

### Workflow Stuck in PENDING

**Symptoms:** Workflow instance status is `PENDING` and not progressing.

**Diagnosis:**
```bash
# Check workflow instance status
curl "https://api.example.com/api/v1/workflows/{workflow-instance-id}/"
```

**Solutions:**
1. Check workflow engine logs for errors
2. Verify tenant and user permissions
3. Check database connectivity
4. Review workflow state_data for errors

### Contracts Not Linked

**Symptoms:** ODPS and ODCS contracts created but not linked.

**Diagnosis:**
```bash
# Check ODPS contract extensions
curl "https://api.example.com/api/v1/contracts/{odps-id}/" | jq '.hub_contract_json.extensions.x_odps'

# Check ODCS contract extensions
curl "https://api.example.com/api/v1/contracts/{odcs-id}/" | jq '.hub_contract_json.extensions.x_odps'
```

**Solutions:**
1. Verify linking step completed in workflow
2. Check for linking validation errors
3. Manually link contracts using link endpoint:
   ```bash
   curl -X POST "https://api.example.com/api/v1/contracts/link-odps/" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"odcs_id": "...", "odps_id": "..."}'
   ```

### Export Returns Empty Content

**Symptoms:** Export endpoint returns 200 OK but content is empty or null.

**Diagnosis:**
```bash
# Check contract has hub_contract_json
curl "https://api.example.com/api/v1/contracts/{id}/" | jq '.hub_contract_json'
```

**Solutions:**
1. Verify contract has `hub_contract_json` (required for ODPS export)
2. Check normalization status (should be `NORMALIZED_OK`)
3. Review normalization errors:
   ```bash
   curl "https://api.example.com/api/v1/contracts/{id}/" | jq '.normalization_errors'
   ```

### External $ref Resolution Timeout

**Symptoms:** Workflow fails with `REF_RESOLUTION_FAILED` after retries.

**Solutions:**
1. Use inline `spec` instead of external `$ref`:
   ```json
   {
     "product": {
       "contract": {
         "spec": {
           "apiVersion": "odcs/v3",
           "kind": "DataContract",
           ...
         }
       }
     }
   }
   ```

2. Disable external ref resolution (if not needed):
   ```bash
   datahub contracts create-odps --file product.odps.json --extract-odcs --no-resolve-external-refs
   ```

3. Verify external URL is accessible and returns valid JSON/YAML

### Version Mismatch Errors

**Symptoms:** Export fails with version mismatch error.

**Solutions:**
1. Specify correct ODPS version in export request:
   ```bash
   curl "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.1"
   ```

2. Verify contract's `original_spec_version` matches requested version

3. Use contract's native version (omit `version` parameter):
   ```bash
   curl "https://api.example.com/api/v1/contracts/{id}/export/?format=odps"
   ```

## ODPS $ref Resolution Guide

ODPS documents support JSON Schema `$ref` references for reusable components, external schemas, and modular contract definitions. The Data Interoperability Hub provides comprehensive support for resolving these references.

### Reference Types

The Hub supports three types of `$ref` references:

#### 1. Internal References (`#/...`)

Internal references point to definitions within the same ODPS document.

**Example:**
```json
{
  "definitions": {
    "schema": {
      "fields": [
        {"name": "id", "type": "string"},
        {"name": "name", "type": "string"}
      ]
    }
  },
  "product": {
    "contract": {
      "$ref": "#/definitions/schema"
    }
  }
}
```

**Use Cases:**
- Reusing schema definitions
- Sharing common structures
- Modular document organization

**Resolution:**
- Resolved immediately during parsing
- No network access required
- No retry logic needed

#### 2. Local References (`./...` or `../...`)

Local references point to files in the local filesystem or allowed directories.

**Example:**
```json
{
  "product": {
    "contract": {
      "$ref": "./contracts/schema.json"
    }
  }
}
```

**Configuration:**
Local references are restricted to allowed directories defined in `hub/apps/contracts/config/odps_refs.yaml`:

```yaml
allowed_base_dirs:
  - "./contracts/refs"
  - "./odps-refs"
```

**Security Features:**
- Path traversal prevention
- Directory allowlist enforcement
- File size limits

**Use Cases:**
- Sharing schemas across multiple ODPS documents
- Organizing contracts in a repository
- Versioning contract components

#### 3. External References (`https://...`)

External references point to URLs accessible over HTTP/HTTPS.

**Example:**
```json
{
  "product": {
    "contract": {
      "$ref": "https://example.com/schemas/data-contract.json"
    }
  }
}
```

**Security Configuration:**
External references are controlled by URL allowlist/denylist in `odps_refs.yaml`:

```yaml
url_allowlist: []  # Empty = allow all (unless in denylist)
url_denylist: []   # Denied URL patterns
```

**Retry Logic:**
- 3 retries with exponential backoff (1s, 2s, 4s)
- Timeout per reference: 5 seconds (configurable)
- Total timeout: 30 seconds (configurable)

**Caching:**
- External references cached in Redis (TTL: 1 hour)
- Reduces redundant network requests
- Improves performance for frequently referenced schemas

**Use Cases:**
- Referencing public schemas
- Sharing contracts across organizations
- Centralized schema management

### Reference Resolution Configuration

Reference resolution can be controlled via:

**REST API:**
```json
{
  "original_raw": "...",
  "original_format": "JSON",
  "resolve_external_refs": true  // Enable/disable external ref resolution
}
```

**CLI:**
```bash
datahub contracts create-odps \
  --file product.odps.json \
  --resolve-external-refs  # Enable external ref resolution
```

**Python SDK:**
```python
result = await client.contracts.create_odps(
    original_raw=odps_content,
    resolve_external_refs=True  # Enable external ref resolution
)
```

### Reference Resolution Errors

**Common Errors:**

1. **Internal Reference Not Found**
   - Error: `REF_RESOLUTION_FAILED`
   - Cause: `$ref` path doesn't exist in document
   - Solution: Verify reference path matches definitions structure

2. **Local Reference Outside Allowed Directory**
   - Error: `REF_RESOLUTION_FAILED`
   - Cause: File path outside allowed directories
   - Solution: Move file to allowed directory or update configuration

3. **External Reference Timeout**
   - Error: `REF_RESOLUTION_FAILED`
   - Cause: Network timeout after retries
   - Solution: Check URL accessibility, network connectivity, or use inline spec

4. **External Reference Denied**
   - Error: `REF_RESOLUTION_FAILED`
   - Cause: URL matches denylist pattern
   - Solution: Update `odps_refs.yaml` configuration or use allowed URL

### Best Practices for $ref Usage

1. **Prefer Internal References** for reusable components within a document
2. **Use Local References** for shared schemas within a repository
3. **Limit External References** to trusted, stable URLs
4. **Test Reference Resolution** before production deployment
5. **Monitor Reference Resolution** performance and failures

## ODPS Semantic Layer Integration

ODPS contracts are automatically mapped to RDF (Resource Description Framework) for semantic interoperability, enabling integration with knowledge graphs, SPARQL queries, and semantic search.

### Semantic Mapping Overview

When an ODPS contract is created or updated, it is automatically mapped to RDF triples and stored in the semantic triple store (Apache Jena Fuseki).

**Mapping Process:**
1. **ODPS Contract Created**: Product creation workflow triggers semantic mapping
2. **RDF Mapping**: ODPS product structure mapped to RDF triples
3. **Triple Store**: RDF triples stored in Fuseki
4. **Semantic Resource**: SemanticResource record created/updated

### RDF Mapping Details

#### Product URI Generation

Each ODPS product receives a unique URI:
```
https://datahub.example.com/product/{product-uuid}
```

#### Multilingual Support

ODPS `product.details` with multiple languages are mapped to RDF literals with language tags:

```turtle
<https://datahub.example.com/product/{uuid}>
    dct:title "Customer Analytics Dataset"@en ;
    dct:title "Dataset d'Analyse Client"@fr ;
    dct:description "Comprehensive customer analytics"@en .
```

#### Marketplace Components

Pricing plans, access methods, and payment gateways are mapped to RDF:

```turtle
<https://datahub.example.com/product/{uuid}>
    hub:hasPricingPlan <https://datahub.example.com/pricing-plan/{plan-id}> ;
    hub:hasAccessMethod <https://datahub.example.com/access-method/{method-id}> .
```

#### Product Strategy (ODPS 4.1+)

Product strategy components (objectives, strategic alignment, KPIs) are mapped:

```turtle
<https://datahub.example.com/product/{uuid}>
    hub:hasProductObjective <https://datahub.example.com/objective/{obj-id}> ;
    hub:strategicAlignment "Revenue Growth" ;
    hub:hasKPI <https://datahub.example.com/kpi/{kpi-id}> .
```

#### ODCS Contract Linking

Linked ODCS contracts are connected via RDF:

```turtle
<https://datahub.example.com/product/{uuid}>
    hub:hasContract <https://datahub.example.com/contract/{odcs-uuid}> .
```

### Semantic Mapping API

#### REST API

**Map ODPS Contract:**
```bash
POST /api/v1/semantic/map/odps
{
  "product": {...},
  "product_uuid": "odps-contract-uuid",
  "odcs_contract_uuid": "odcs-contract-uuid"  // Optional
}
```

**Query Semantic Resources:**
```bash
GET /api/v1/semantic/resources/?contract_id={odps-contract-uuid}
```

#### Python SDK

```python
# Semantic mapping happens automatically during ODPS creation
result = await client.contracts.create_odps(...)

# Query semantic resource
semantic_resource = await client.semantic.get_resource(
    contract_id=result["odps_contract"]["id"]
)
```

### SPARQL Queries

Once mapped to RDF, ODPS products can be queried using SPARQL:

**Example: Find all products with pricing plans:**
```sparql
PREFIX hub: <https://datahub.example.com/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?product ?title ?price
WHERE {
    ?product a hub:DataProduct .
    ?product dct:title ?title .
    ?product hub:hasPricingPlan ?plan .
    ?plan hub:price ?price .
}
```

**Example: Find products by language:**
```sparql
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?product ?title
WHERE {
    ?product dct:title ?title .
    FILTER (LANG(?title) = "en")
}
```

### Semantic Mapping Configuration

Semantic mapping can be controlled via workflow parameters:

**Disable Semantic Mapping:**
```python
result = ProductCreationWorkflow.execute(
    original_raw=odps_content,
    skip_semantic_mapping=True  # Skip semantic mapping step
)
```

**Manual Semantic Mapping:**
```python
from hub.apps.semantic.utils import map_odps_to_semantic

semantic_resource = map_odps_to_semantic(
    contract=odps_contract,
    tenant=tenant,
    use_cache=True
)
```

### Semantic Mapping Metrics

The Hub tracks semantic mapping metrics:

- `odps_semantic_mapping_total`: Total mapping operations
- `odps_semantic_mapping_duration_seconds`: Mapping duration
- `odps_semantic_mapping_success_rate`: Success rate

**Access Metrics:**
```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics | grep odps_semantic
```

### Troubleshooting Semantic Mapping

**Issue: Semantic mapping not triggered**

**Diagnosis:**
```bash
# Check workflow instance
curl "https://api.example.com/api/v1/workflows/{workflow-instance-id}/"
```

**Solutions:**
1. Verify workflow completed successfully
2. Check semantic service is running
3. Review workflow logs for errors

**Issue: RDF mapping incomplete**

**Diagnosis:**
```bash
# Check semantic resource
curl "https://api.example.com/api/v1/semantic/resources/?contract_id={uuid}"
```

**Solutions:**
1. Verify ODPS contract structure is valid
2. Check semantic service logs
3. Retry semantic mapping manually

**Issue: SPARQL queries return no results**

**Solutions:**
1. Verify semantic mapping completed
2. Check Fuseki triple store is accessible
3. Verify SPARQL query syntax
4. Check product URI format matches mapping

## Additional Resources

- [ODPS CLI Usage Guide](../cli/docs/ODPS_USAGE.md) - Complete CLI documentation
- [ODPS Python SDK Usage Guide](../sdk/python/docs/ODPS_USAGE.md) - Complete SDK documentation
- [ODPS Creation Flows Guide](ODPS_CREATION_FLOWS.md) - Detailed creation flow documentation
- [ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md) - Comprehensive migration guide
- [ODPS Examples](ODPS_EXAMPLES.md) - Complete examples for all scenarios
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture and framework
- [Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md) - User guide for marketplace integrations
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) - Marketplace use cases and scenarios
- [Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md) - Marketplace user journey documentation
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [GraphQL API](GRAPHQL_API.md) - GraphQL API documentation
- [Webhook API](WEBHOOK_API.md) - Webhook subscriptions and ODPS event delivery

