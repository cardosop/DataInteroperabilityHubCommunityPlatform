# Data Contracts & Standards

> ODPS/ODCS integration, migration, business rules, and semantic operations
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

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


---

# ODPS Creation Flows Guide

Complete engineering-grade guide for ODPS (Open Data Product Standard) creation flows in the Data Interoperability Hub.

**Last Updated**: 2026-03-22
**Version**: 1.0.0

## Table of Contents

1. [Overview](#overview)
2. [Product-First Flow](#product-first-flow)
3. [Technical-First Flow](#technical-first-flow)
4. [Data-First Flow](#data-first-flow)
5. [Flow Comparison](#flow-comparison)
6. [Use Cases](#use-cases)
7. [Flow Diagrams](#flow-diagrams)
8. [Code Examples](#code-examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Data Interoperability Hub supports three primary creation flows for ODPS contracts, each optimized for different use cases and workflows:

1. **Product-First Flow**: Start with ODPS product definition, extract ODCS contract
2. **Technical-First Flow**: Start with ODCS contract, generate/link ODPS product
3. **Data-First Flow**: Start with data asset, attach contracts

### Key Concepts

- **ODPS (Open Data Product Standard)**: Marketplace-focused specification (product information, pricing, access methods)
- **ODCS (Open Data Contract Standard)**: Technical specification (schema, quality, compliance)
- **HubContract**: Normalized internal representation combining both ODPS and ODCS data
- **Bidirectional Linking**: ODPS ↔ ODCS links maintained in both contracts

### Flow Selection Guide

| Flow | When to Use | Primary Entry Point |
|------|-------------|-------------------|
| **Product-First** | Product/marketplace information is primary | ODPS document with embedded ODCS |
| **Technical-First** | Technical contract is primary | ODCS contract creation |
| **Data-First** | Data asset is primary | Asset creation with file upload |

---

## Product-First Flow

The Product-First flow starts with an ODPS product definition and automatically extracts the embedded ODCS contract.

### Flow Overview

```
ODPS Document (with embedded ODCS)
    ↓
Parse & Validate ODPS
    ↓
Resolve $ref References
    ↓
Extract ODCS Contract
    ↓
Validate ODCS Contract
    ↓
Normalize ODCS → HubContract (Technical)
    ↓
Normalize ODPS → HubContract (Marketplace)
    ↓
Create ODCS Contract Record
    ↓
Create ODPS Contract Record
    ↓
Link Contracts Bidirectionally
    ↓
Index for Search
    ↓
Semantic Mapping (RDF)
```

### Workflow Steps

The Product-First flow is implemented by `ProductCreationWorkflow`:

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

### Requirements

- ODPS document must have `product.contract` field
- `product.contract` must contain one of:
  - `spec`: Inline ODCS contract
  - `$ref`: Reference to ODCS contract (resolved during workflow)
  - `contractURL`: External contract URL (not yet supported)

### Example ODPS Document

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

### REST API Example

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"customer-analytics-contract\",\"schema\":{\"fields\":[{\"name\":\"customer_id\",\"type\":\"string\"}]}}}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

### Python SDK Example

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
            "productID": "customer-analytics",
            "name": "Customer Analytics Dataset"
          }
        },
        "contract": {
          "spec": {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "customer-analytics-contract",
            "schema": {
              "fields": [{"name": "customer_id", "type": "string"}]
            }
          }
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

### CLI Example

```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --resolve-external-refs
```

### Error Handling

- **Missing `product.contract`**: Returns `400 Bad Request` with error code `REQUIRED_FIELD_MISSING`
- **Invalid ODCS in `product.contract.spec`**: Returns `400 Bad Request` with validation errors
- **External `$ref` resolution failure**: Retries up to 3 times with exponential backoff (1s, 2s, 4s)
- **Workflow failure**: Automatic rollback of created contracts

---

## Technical-First Flow

The Technical-First flow starts with an ODCS contract and optionally generates or links an ODPS product.

### Flow Overview

```
ODCS Contract Document
    ↓
Parse & Validate ODCS
    ↓
Normalize ODCS → HubContract
    ↓
Create ODCS Contract Record
    ↓
[Optional] Generate ODPS from HubContract
    OR
[Optional] Link Existing ODPS Contract
    ↓
[If Generated] Create ODPS Contract Record
    ↓
[If Generated/Linked] Link Contracts Bidirectionally
    ↓
Index for Search
    ↓
Semantic Mapping (RDF)
```

### Workflow Steps

The Technical-First flow is implemented by `ContractCreationWorkflow`:

1. **Validate Input**: Validate ODCS contract structure
2. **Normalize Contract**: Normalize ODCS → HubContract
3. **Validate HubContract**: Validate HubContract schema
4. **Create Contract Record**: Create ODCS contract record
5. **Link ODPS** (optional): Generate ODPS or link existing ODPS
6. **Link Data File** (optional): Link data file (create Asset)
7. **Index for Search**: Index for search
8. **Semantic Mapping**: Map contract to RDF (async job)
9. **Send Notifications**: Send email notifications
10. **Audit Logging**: Create audit events

### ODPS Generation Options

When creating an ODCS contract, you can specify ODPS action:

- **`generate`**: Auto-generate ODPS from HubContract
- **`link`**: Link to existing ODPS contract
- **`none`** (default): Skip ODPS creation/linking

### Example: Generate ODPS

**REST API:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"customer-analytics-contract\",\"schema\":{\"fields\":[{\"name\":\"customer_id\",\"type\":\"string\"}]}}",
    "original_format": "JSON",
    "original_spec_type": "ODCS",
    "odps_action": "generate"
  }'
```

**Python SDK:**
```python
from hub.apps.contracts.services import ContractService

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Create ODCS contract
odcs_contract = contract_service.create_contract(
    original_raw=odcs_content,
    original_format="JSON",
    original_spec_type="ODCS"
)

# Auto-generate ODPS from ODCS
odps_contract = contract_service.auto_generate_odps_for_odcs(
    odcs_contract_id=str(odcs_contract.id),
    target_odps_version="4.1"
)
```

**CLI:**
```bash
# Create ODCS contract
datahub contracts create \
  --file contract.odcs.json \
  --spec-type odcs

# Generate ODPS from ODCS
datahub contracts generate-odps \
  --contract-id <odcs-contract-id> \
  --version 4.1
```

### Example: Link Existing ODPS

**REST API:**
```bash
curl -X POST https://api.example.com/api/v1/contracts/{odcs-contract-id}/link-odps/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"}}}}",
    "original_format": "JSON"
  }'
```

**Python SDK:**
```python
# Link ODPS to existing ODCS
odps_contract = await client.contracts.create_odps(
    original_raw=odps_content,
    link_odcs_id=str(odcs_contract.id),
    original_format="JSON"
)
```

**CLI:**
```bash
datahub contracts link-odps \
  --odcs-id <odcs-contract-id> \
  --odps-file product.odps.json
```

### Generated ODPS Structure

When ODPS is auto-generated from ODCS, it includes:

- **Product Details**: Extracted from HubContract.info
- **Marketplace Data**: Mapped from HubContract.marketplace.x_odps.* (if present)
- **Contract Reference**: Links to original ODCS contract

### Error Handling

- **ODCS validation failure**: Returns `400 Bad Request` with validation errors
- **ODPS generation failure**: Returns `400 Bad Request` with generation errors
- **ODPS linking failure**: Returns `400 Bad Request` with linking validation errors
- **Workflow failure**: Automatic rollback of created contracts

---

## Data-First Flow

The Data-First flow starts with a data asset (file upload) and optionally generates contracts from the data schema.

### Flow Overview

```
Data File Upload
    ↓
Infer Schema from Data
    ↓
Generate ODCS Contract from Schema
    ↓
Validate Generated ODCS
    ↓
Normalize ODCS → HubContract
    ↓
Create ODCS Contract Record
    ↓
Create Asset Record
    ↓
[Optional] Generate/Link ODPS
    ↓
Attach Contracts to Asset
    ↓
Run Data Quality Checks
    ↓
Run Compliance Checks
    ↓
Activate Asset (if auto_activate=True)
    ↓
Index for Search
    ↓
Semantic Mapping (RDF)
```

### Workflow Steps

The Data-First flow is implemented by `AssetCreationWorkflow`:

1. **Infer Schema**: Infer schema from data file (CSV, JSON, Parquet, etc.)
2. **Generate ODCS**: Generate ODCS contract from inferred schema
3. **Validate ODCS**: Validate generated ODCS contract
4. **Normalize ODCS**: Normalize ODCS → HubContract
5. **Create ODCS Contract**: Create ODCS contract record
6. **Create Asset Record**: Create asset record
7. **Attach Contract**: Attach contract to asset
8. **Link ODPS** (optional): Generate or link ODPS contract
9. **Run Data Quality Checks**: Execute data quality rules
10. **Run Compliance Checks**: Execute compliance rules
11. **Activate Asset**: Activate asset if all checks pass
12. **Index for Search**: Index asset and contracts
13. **Semantic Mapping**: Map asset and contracts to RDF

### Example: Data-First with Auto-Generated Contracts

**REST API:**
```bash
# Step 1: Upload file
curl -X POST https://api.example.com/api/v1/files/upload/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@data.csv" \
  -F "name=customer-data"

# Step 2: Create asset with auto-generated contracts
curl -X POST https://api.example.com/api/v1/assets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "<file-uuid>",
    "name": "Customer Analytics Dataset",
    "key": "customer-analytics",
    "auto_generate_contracts": true,
    "odps_action": "generate"
  }'
```

**Python SDK:**
```python
# Upload file
file_result = await client.files.upload(
    file_path="data.csv",
    name="customer-data"
)

# Create asset with auto-generated contracts
asset = await client.assets.create(
    file_id=file_result["id"],
    name="Customer Analytics Dataset",
    key="customer-analytics",
    auto_generate_contracts=True,
    odps_action="generate"
)
```

**CLI:**
```bash
# Upload file and create asset
datahub assets create \
  --file data.csv \
  --name "Customer Analytics Dataset" \
  --key customer-analytics \
  --auto-generate-contracts \
  --odps-action generate
```

### Example: Data-First with Existing Contracts

**REST API:**
```bash
# Create asset and attach existing contracts
curl -X POST https://api.example.com/api/v1/assets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "<file-uuid>",
    "name": "Customer Analytics Dataset",
    "key": "customer-analytics",
    "contract_id": "<odcs-contract-id>",
    "odps_contract_id": "<odps-contract-id>"
  }'
```

### Schema Inference

The Data-First flow supports schema inference for:

- **CSV**: Column names, types, nullability
- **JSON**: Structure, nested objects, arrays
- **Parquet**: Column types, nullability, metadata
- **Excel**: Multiple sheets, column types

### Error Handling

- **Schema inference failure**: Returns `400 Bad Request` with inference errors
- **ODCS generation failure**: Returns `400 Bad Request` with generation errors
- **Data quality check failure**: Asset remains in DRAFT status
- **Compliance check failure**: Asset remains in DRAFT status
- **Workflow failure**: Automatic rollback of created records

---

## Flow Comparison

| Aspect | Product-First | Technical-First | Data-First |
|--------|--------------|-----------------|------------|
| **Primary Entry Point** | ODPS document | ODCS contract | Data file |
| **ODCS Source** | Embedded in ODPS | Direct input | Generated from schema |
| **ODPS Source** | Direct input | Generated/Linked | Generated/Linked |
| **Use Case** | Marketplace-first | Technical-first | Data-first |
| **Complexity** | Medium | Low-Medium | High |
| **Workflow** | ProductCreationWorkflow | ContractCreationWorkflow | AssetCreationWorkflow |
| **Contract Linking** | Automatic | Optional | Optional |
| **Schema Inference** | No | No | Yes |
| **Data Quality Checks** | No | No | Yes |
| **Compliance Checks** | No | No | Yes |

---

## Use Cases

### Product-First Flow Use Cases

1. **Marketplace Product Creation**: Creating products for data marketplaces
2. **Product Catalog Management**: Managing product catalogs with embedded contracts
3. **API-First Products**: Products exposed via APIs with embedded contracts
4. **Multi-Language Products**: Products with multilingual descriptions

### Technical-First Flow Use Cases

1. **Contract-First Development**: Starting with technical contracts
2. **Legacy Contract Migration**: Migrating existing ODCS contracts to ODPS
3. **Incremental Productization**: Adding marketplace features to technical contracts
4. **Contract Reuse**: Reusing technical contracts across multiple products

### Data-First Flow Use Cases

1. **Data Discovery**: Discovering and cataloging existing data assets
2. **Schema Inference**: Automatically generating contracts from data
3. **Data Quality Management**: Managing data quality with contracts
4. **Compliance Management**: Ensuring compliance with contracts

---

## Flow Diagrams

### Product-First Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Product-First Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                           │
│  │ ODPS Document│                                           │
│  │ (with ODCS)  │                                           │
│  └──────┬───────┘                                           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Parse & Validate │                                        │
│  │ ODPS             │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Resolve $ref     │                                        │
│  │ References       │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Extract ODCS     │                                        │
│  │ Contract         │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ├──────────────────┐                                 │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ Normalize    │  │ Normalize    │                         │
│  │ ODCS         │  │ ODPS         │                         │
│  └──────┬───────┘  └──────┬───────┘                         │
│         │                  │                                 │
│         ├──────────────────┘                                 │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Create Contracts │                                        │
│  │ (ODCS + ODPS)    │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Link Contracts    │                                        │
│  │ Bidirectionally  │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Index & Map       │                                        │
│  │ (Search + RDF)   │                                        │
│  └──────────────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Technical-First Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Technical-First Flow                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                           │
│  │ ODCS Contract│                                           │
│  └──────┬───────┘                                           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Parse & Validate │                                        │
│  │ ODCS             │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Normalize ODCS   │                                        │
│  │ → HubContract    │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Create ODCS      │                                        │
│  │ Contract Record  │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ├──────────────────┐                                 │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ Generate     │  │ Link        │                         │
│  │ ODPS          │  │ ODPS        │                         │
│  │ (Optional)    │  │ (Optional)   │                         │
│  └──────┬───────┘  └──────┬───────┘                         │
│         │                  │                                 │
│         └────────┬─────────┘                                 │
│                  │                                           │
│                  ▼                                           │
│         ┌──────────────────┐                                 │
│         │ Link Contracts   │                                 │
│         │ Bidirectionally  │                                 │
│         └──────┬───────────┘                                 │
│                │                                             │
│                ▼                                             │
│         ┌──────────────────┐                                 │
│         │ Index & Map      │                                 │
│         │ (Search + RDF)   │                                 │
│         └──────────────────┘                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data-First Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Data-First Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                           │
│  │ Data File    │                                           │
│  │ Upload       │                                           │
│  └──────┬───────┘                                           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Infer Schema     │                                        │
│  │ from Data        │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Generate ODCS   │                                        │
│  │ from Schema      │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Validate &       │                                        │
│  │ Normalize ODCS   │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Create ODCS      │                                        │
│  │ Contract Record  │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │ Create Asset     │                                        │
│  │ Record           │                                        │
│  └──────┬───────────┘                                        │
│         │                                                    │
│         ├──────────────────┐                                 │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ Generate/    │  │ Run Data     │                         │
│  │ Link ODPS    │  │ Quality      │                         │
│  │ (Optional)    │  │ Checks       │                         │
│  └──────┬───────┘  └──────┬───────┘                         │
│         │                  │                                 │
│         └────────┬─────────┘                                 │
│                  │                                           │
│                  ▼                                           │
│         ┌──────────────────┐                                 │
│         │ Run Compliance   │                                 │
│         │ Checks           │                                 │
│         └──────┬───────────┘                                 │
│                │                                             │
│                ▼                                             │
│         ┌──────────────────┐                                 │
│         │ Activate Asset    │                                 │
│         │ (if checks pass) │                                 │
│         └──────┬───────────┘                                 │
│                │                                             │
│                ▼                                             │
│         ┌──────────────────┐                                 │
│         │ Index & Map      │                                 │
│         │ (Search + RDF)   │                                 │
│         └──────────────────┘                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Examples

### Complete Product-First Example

```python
from datahub_interoperability import DataHubClient, Config
import json

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

odps_document = {
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
}

async with DataHubClient(config) as client:
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_document),
        extract_odcs=True,
        original_format="JSON",
        resolve_external_refs=True
    )

    print(f"ODPS Contract ID: {result['odps_contract']['id']}")
    print(f"ODCS Contract ID: {result['odcs_contract']['id']}")
    print(f"Workflow Instance ID: {result['workflow_instance_id']}")
```

### Complete Technical-First Example

```python
from hub.apps.contracts.services import ContractService

odcs_document = {
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

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Create ODCS contract
odcs_contract = contract_service.create_contract(
    original_raw=json.dumps(odcs_document),
    original_format="JSON",
    original_spec_type="ODCS"
)

# Auto-generate ODPS from ODCS
odps_contract = contract_service.auto_generate_odps_for_odcs(
    odcs_contract_id=str(odcs_contract.id),
    target_odps_version="4.1"
)

print(f"ODCS Contract ID: {odcs_contract.id}")
print(f"ODPS Contract ID: {odps_contract.id}")
```

### Complete Data-First Example

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    # Step 1: Upload file
    file_result = await client.files.upload(
        file_path="customer_data.csv",
        name="customer-data"
    )

    # Step 2: Create asset with auto-generated contracts
    asset = await client.assets.create(
        file_id=file_result["id"],
        name="Customer Analytics Dataset",
        key="customer-analytics",
        auto_generate_contracts=True,
        odps_action="generate",
        auto_activate=True
    )

    print(f"Asset ID: {asset['id']}")
    print(f"ODCS Contract ID: {asset['contracts']['odcs']['id']}")
    print(f"ODPS Contract ID: {asset['contracts']['odps']['id']}")
```

---

## Best Practices

### Product-First Flow Best Practices

1. **Always include `product.contract`**: Required for ODCS extraction
2. **Use inline `spec`**: Prefer inline ODCS over `$ref` for better performance
3. **Complete marketplace data**: Include pricing plans, access methods, payment gateways
4. **Multilingual support**: Use `product.details` with language codes
5. **Version specification**: Always specify ODPS version

### Technical-First Flow Best Practices

1. **Validate ODCS first**: Ensure ODCS contract is valid before generating ODPS
2. **Marketplace metadata**: Add marketplace metadata to HubContract for better ODPS generation
3. **Incremental approach**: Start with ODCS, add ODPS later if needed
4. **Contract reuse**: Reuse ODCS contracts across multiple ODPS products
5. **Version management**: Keep ODCS and ODPS versions aligned

### Data-First Flow Best Practices

1. **Schema validation**: Review inferred schema before generating contracts
2. **Data quality rules**: Add data quality rules to generated ODCS contracts
3. **Compliance checks**: Configure compliance rules for data assets
4. **Incremental activation**: Use `auto_activate=False` for manual review
5. **Contract refinement**: Refine auto-generated contracts with domain knowledge

---

## Troubleshooting

### Product-First Flow Issues

**Issue: Missing `product.contract`**

**Error:**
```
REQUIRED_FIELD_MISSING: product.contract is required but missing
```

**Solution:**
Add `product.contract` field with `spec`, `$ref`, or `contractURL`.

**Issue: Invalid ODCS in `product.contract.spec`**

**Error:**
```
ODCS_VALIDATION_ERROR: schema.fields is required
```

**Solution:**
Ensure `product.contract.spec` contains valid ODCS contract with required fields.

### Technical-First Flow Issues

**Issue: ODPS generation fails**

**Error:**
```
ODPS_NORMALIZATION_ERROR: Failed to generate ODPS from HubContract
```

**Solution:**
1. Verify HubContract has marketplace metadata
2. Check HubContract structure is valid
3. Review normalization errors

**Issue: ODPS linking fails**

**Error:**
```
ODPS_LINKING_ERROR: Contract linking validation failed
```

**Solution:**
1. Verify ODPS contract exists
2. Check tenant matches
3. Review linking validation errors

### Data-First Flow Issues

**Issue: Schema inference fails**

**Error:**
```
SCHEMA_INFERENCE_ERROR: Failed to infer schema from data
```

**Solution:**
1. Verify file format is supported
2. Check file is not corrupted
3. Review file structure

**Issue: Data quality checks fail**

**Error:**
```
DATA_QUALITY_CHECK_FAILED: Asset remains in DRAFT status
```

**Solution:**
1. Review data quality check results
2. Fix data quality issues
3. Re-run data quality checks

---

## Additional Resources

- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md) - Comprehensive migration guide
- [ODPS Examples](ODPS_EXAMPLES.md) - Complete examples for all scenarios
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md) - User guide for marketplace integrations
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Workflow Engine Documentation](../hub/apps/orchestration/README.md) - Workflow engine details

---

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Maintained By**: Data Interoperability Hub Team

---

# ODPS Migration Guide

Complete engineering-grade guide for migrating ODPS and ODCS contracts in the Data Interoperability Hub.

**Last Updated**: 2026-03-22
**Version**: 1.0.0

## Table of Contents

1. [Overview](#overview)
2. [Migrating from ODCS-only to ODPS+ODCS](#migrating-from-odcs-only-to-odpsodcs)
3. [Migrating ODPS Versions](#migrating-odps-versions)
4. [Migrating ODCS Versions](#migrating-odcs-versions)
5. [Best Practices for Migration](#best-practices-for-migration)
6. [Common Migration Issues](#common-migration-issues)
7. [Migration Tools and Commands](#migration-tools-and-commands)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers three types of migrations:

1. **ODCS-only → ODPS+ODCS**: Migrating existing ODCS contracts to include ODPS products
2. **ODPS Version Migration**: Upgrading ODPS contracts from one version to another (e.g., 4.0 → 4.1)
3. **ODCS Version Migration**: Upgrading ODCS contracts from one version to another (e.g., 2.2.2 → 3.0.2)

### Migration Principles

- **Data Preservation**: All data is preserved during migration
- **Bidirectional Linking**: ODPS ↔ ODCS links maintained throughout
- **Validation**: Comprehensive validation ensures migration success
- **Rollback Support**: Rollback capabilities for all migration types
- **Incremental Migration**: Support for batch and incremental migrations

---

## Migrating from ODCS-only to ODPS+ODCS

This migration creates ODPS contracts from existing ODCS contracts, enabling marketplace features while preserving all technical contract data.

### When to Migrate

Migrate when you want to:
- Add marketplace capabilities to existing technical contracts
- Enable product catalog features
- Support data product lifecycle management
- Prepare for marketplace integrations

### Migration Process

The migration process is documented in detail in [ODCS_TO_ODPS_MIGRATION_GUIDE.md](ODCS_TO_ODPS_MIGRATION_GUIDE.md).

**Quick Summary:**

1. **Dry Run**: Always start with a dry run
2. **Validate Prerequisites**: Check contracts meet migration requirements
3. **Execute Migration**: Run migration command
4. **Validate Results**: Verify migration success
5. **Review Report**: Review validation report

### Migration Command

```bash
# Single contract migration
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --validate \
    --validation-report-path /tmp/migration_report.json

# Batch migration (tenant-specific)
python manage.py migrate_contracts_to_odps \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

### What Gets Migrated

- **ODCS Contract**: Preserved as-is
- **HubContract**: All data preserved
- **ODPS Contract**: Generated from HubContract with marketplace focus
- **Bidirectional Links**: ODPS ↔ ODCS links established

### Rollback

```bash
python manage.py rollback_odps_migration \
    --contract-id <contract-uuid>
```

**See**: [ODCS_TO_ODPS_MIGRATION_GUIDE.md](ODCS_TO_ODPS_MIGRATION_GUIDE.md) for complete details.

---

## Migrating ODPS Versions

Migrating ODPS contracts from one version to another (e.g., 4.0 → 4.1).

### Supported ODPS Versions

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **4.1** | ✅ Current | `ODPSNormalizerV4_1` | Latest stable, recommended for new contracts |
| **4.0** | ✅ Supported | `ODPSNormalizerV4_0` | Previous stable, fully supported |
| **1.x** | ✅ Supported (Legacy) | `ODPSNormalizerV1_X` | Legacy versions, gracefully degrades newer features |

### Version Detection

ODPS versions are detected from the `version` field in the document:

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1"  // Version 4.1
}
```

### Migrating from ODPS 4.0 to 4.1

#### Key Differences

**ODPS 4.1 New Features:**
- **Product Strategy**: `product.productStrategy` (objectives, strategic alignment, KPIs)
- **Enhanced Payment Gateways**: Improved payment gateway support
- **Enhanced Marketplace**: Improved marketplace features

**ODPS 4.0 Limitations:**
- No `productStrategy` support
- Limited payment gateway features

#### Migration Steps

**Step 1: Export Current ODPS 4.0 Contract**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.0" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o contract_4.0.odps.json
```

**Step 2: Update Version and Schema**

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",  // Updated schema
  "version": "4.1",  // Updated version
  "product": {
    // ... existing product data ...
    "productStrategy": {  // New in 4.1 (optional)
      "objectives": [...],
      "strategicAlignment": "...",
      "productKPIs": [...]
    }
  }
}
```

**Step 3: Create New ODPS 4.1 Contract**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "<updated-odps-4.1-content>",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Step 4: Link to Existing ODCS Contract**

If the ODCS contract should remain linked:

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odcs-contract-id}/link-odps/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odps_contract_id": "<new-odps-4.1-contract-id>"
  }'
```

**Step 5: Archive Old ODPS 4.0 Contract**

```bash
# Update old contract status to ARCHIVED
curl -X PATCH "https://api.example.com/api/v1/contracts/{old-odps-4.0-id}/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ARCHIVED"
  }'
```

#### Python SDK Example

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    # Step 1: Export ODPS 4.0 contract
    odps_40 = await client.contracts.export_odps(
        contract_id="odps-4.0-contract-id",
        format="json",
        version="4.0"
    )

    # Step 2: Update to 4.1
    odps_41_content = odps_40["content"]
    odps_41_content["schema"] = "https://opendataproducts.org/schema/v4.1"
    odps_41_content["version"] = "4.1"

    # Add productStrategy if needed (optional)
    if "productStrategy" not in odps_41_content.get("product", {}):
        odps_41_content["product"]["productStrategy"] = {
            "objectives": [],
            "strategicAlignment": "",
            "productKPIs": []
        }

    # Step 3: Create new ODPS 4.1 contract
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_41_content),
        extract_odcs=False,  # Keep existing ODCS
        original_format="JSON"
    )

    # Step 4: Link to existing ODCS
    odcs_contract_id = odps_40.get("linked_odcs_id")
    if odcs_contract_id:
        await client.contracts.link_odps_to_odcs(
            odcs_id=odcs_contract_id,
            odps_id=result["odps_contract"]["id"]
        )
```

### Graceful Degradation

ODPS 4.0 contracts continue to work with ODPS 4.1 normalizer:

- **Missing `productStrategy`**: Silently skipped (not available in 4.0)
- **Missing payment gateway features**: Gracefully handled
- **All 4.0 features**: Fully supported

### Migration Validation

After migration, validate the new contract:

```bash
python manage.py validate_migration \
    --contract-ids <new-odps-4.1-contract-id> \
    --format json \
    --report-path /tmp/validation_report.json
```

---

## Migrating ODCS Versions

Migrating ODCS contracts from one version to another (e.g., 2.2.2 → 3.0.2).

### Supported ODCS Versions

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **3.0.2** | ✅ Current | `ODCSNormalizerV3_0_2` | Latest stable, recommended for new contracts |
| **3.0.1** | ✅ Supported | `ODCSNormalizerV3_0_1` | Previous stable, fully supported |
| **3.0.0** | ✅ Supported | `ODCSNormalizerV3_0_0` | Initial 3.x release, fully supported |
| **2.2.2** | ✅ Supported (Legacy) | `ODCSNormalizerV2_2_2` | Legacy version, gracefully degrades 3.x features |

**See**: [ODCS_VERSION_SUPPORT.md](ODCS_VERSION_SUPPORT.md) for complete version details.

### Migrating from ODCS 2.2.2 to 3.0.2

#### Key Differences

**ODCS 3.0.2 New Features:**
- Enhanced marketplace features
- Enhanced lifecycle features
- Improved schema support
- Enhanced quality rules and compliance features

**ODCS 2.2.2 Limitations:**
- Limited marketplace features
- Limited lifecycle features
- Older schema format

#### Migration Steps

**Step 1: Export Current ODCS 2.2.2 Contract**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odcs&version=2.2.2" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o contract_2.2.2.odcs.json
```

**Step 2: Update apiVersion**

```yaml
# Before (ODCS 2.2.2)
apiVersion: odcs.io/v2.2.2
kind: DataContract
id: my-contract
# ... rest of contract ...

# After (ODCS 3.0.2)
apiVersion: odcs.io/v3.0.2  # Updated version
kind: DataContract
id: my-contract
# ... rest of contract ...
```

**Step 3: Update Schema Format (if needed)**

ODCS 3.0.2 uses a different schema format:

```yaml
# ODCS 2.2.2 format
schema:
  type: object
  properties:
    field1:
      type: string

# ODCS 3.0.2 format
schema:
  fields:
    - name: field1
      type: string
      nullable: false
```

**Step 4: Create New ODCS 3.0.2 Contract**

```bash
curl -X POST https://api.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "<updated-odcs-3.0.2-content>",
    "original_format": "JSON",
    "original_spec_type": "ODCS"
  }'
```

**Step 5: Link to Existing ODPS Contract (if exists)**

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odps-contract-id}/link-odcs/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odcs_contract_id": "<new-odcs-3.0.2-contract-id>"
  }'
```

**Step 6: Archive Old ODCS 2.2.2 Contract**

```bash
curl -X PATCH "https://api.example.com/api/v1/contracts/{old-odcs-2.2.2-id}/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ARCHIVED"
  }'
```

#### Python SDK Example

```python
from hub.apps.contracts.services import ContractService

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Step 1: Export ODCS 2.2.2 contract
odcs_222_contract = contract_service.get_contract(
    contract_id="odcs-2.2.2-contract-id",
    tenant_id=tenant_id
)

# Step 2: Parse and update version
import json
odcs_222_content = json.loads(odcs_222_contract.original_raw)
odcs_222_content["apiVersion"] = "odcs.io/v3.0.2"

# Step 3: Update schema format if needed
# (Convert from 2.2.2 format to 3.0.2 format)

# Step 4: Create new ODCS 3.0.2 contract
odcs_302_contract = contract_service.create_contract(
    original_raw=json.dumps(odcs_222_content),
    original_format="JSON",
    original_spec_type="ODCS"
)

# Step 5: Link to existing ODPS if exists
odps_contract_id = odcs_222_contract.hub_contract_json.get(
    "extensions", {}
).get("x_odps", {}).get("odps_link")

if odps_contract_id:
    await client.contracts.link_odps_to_odcs(
        odcs_id=str(odcs_302_contract.id),
        odps_id=odps_contract_id
    )
```

### Graceful Degradation

ODCS 2.2.2 contracts continue to work with ODCS 3.0.2 normalizer:

- **Missing 3.x features**: Gracefully handled
- **All 2.2.2 features**: Fully supported
- **Backward compatibility**: Maintained

### Migration Validation

After migration, validate the new contract:

```bash
python manage.py validate_migration \
    --contract-ids <new-odcs-3.0.2-contract-id> \
    --format json \
    --report-path /tmp/validation_report.json
```

---

## Best Practices for Migration

### Pre-Migration

1. **Always Test First**: Run migration in test/staging environment
2. **Backup Database**: Create full backup before migration
3. **Start Small**: Migrate one contract first, then small batches
4. **Use Dry Run**: Always use `--dry-run` first
5. **Validate Prerequisites**: Check contract eligibility before migration

### During Migration

1. **Monitor Progress**: Watch migration output for errors
2. **Use Validation**: Always use `--validate` flag
3. **Save Reports**: Save validation reports for audit
4. **Batch Appropriately**: Use appropriate batch sizes
5. **Tenant Isolation**: Migrate by tenant when possible

### Post-Migration

1. **Validate Results**: Always run validation after migration
2. **Review Reports**: Thoroughly review validation reports
3. **Test Functionality**: Verify features work correctly
4. **Monitor Logs**: Check for errors or warnings
5. **Document Changes**: Document what was migrated

### Version Migration Specific

1. **Review Version Differences**: Understand what changed between versions
2. **Test New Features**: Verify new features work correctly
3. **Update Documentation**: Update any documentation referencing versions
4. **Plan Rollback**: Understand rollback procedure before migrating
5. **Incremental Migration**: Migrate versions incrementally when possible

---

## Common Migration Issues

### Issue 1: Contract Not Eligible for Migration

**Symptoms:**
```
Contract <uuid> not found or not eligible
```

**Causes:**
- Contract type mismatch
- Contract lacks required data
- Contract already migrated

**Solutions:**
1. Verify contract type matches migration type
2. Check contract has required fields
3. Check if contract already has links

### Issue 2: Version Mismatch Errors

**Symptoms:**
```
Version mismatch: Expected 4.1, got 4.0
```

**Solutions:**
1. Update contract version field
2. Update schema URL
3. Verify version format matches expected format

### Issue 3: Data Loss During Migration

**Symptoms:**
```
Validation completed with X error(s)
Data loss detected in HubContract comparison
```

**Solutions:**
1. Review validation report for missing sections
2. Verify HubContract structure is complete
3. Check normalization status
4. Consider rolling back if critical data loss

### Issue 4: Broken Links After Migration

**Symptoms:**
```
Link validation failed: ODPS contract does not link back to ODCS contract
```

**Solutions:**
1. Verify links exist in both contracts
2. Check tenant matches
3. Manually restore links if needed
4. Re-run validation

### Issue 5: Schema Format Mismatch

**Symptoms:**
```
Schema validation failed: Invalid schema format
```

**Solutions:**
1. Convert schema format to target version
2. Review version-specific schema documentation
3. Use schema conversion tools if available

---

## Migration Tools and Commands

### ODCS to ODPS Migration

```bash
# Single contract
python manage.py migrate_contracts_to_odps \
    --contract-id <uuid> \
    --validate

# Batch migration
python manage.py migrate_contracts_to_odps \
    --tenant-id <uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate

# Rollback
python manage.py rollback_odps_migration \
    --contract-id <uuid>
```

### Validation

```bash
# Validate migration
python manage.py validate_migration \
    --contract-ids <id1>,<id2> \
    --format json \
    --report-path /tmp/report.json
```

### Export/Import

```bash
# Export contract
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Import contract
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"original_raw": "...", "original_format": "JSON"}'
```

---

## Troubleshooting

### Migration Fails with Validation Error

**Diagnosis:**
```bash
# Check contract structure
python manage.py shell
>>> from hub.apps.contracts.models import Contract
>>> contract = Contract.objects.get(id='<uuid>')
>>> print(contract.hub_contract_json)
```

**Solutions:**
1. Verify contract structure is valid
2. Check required fields are present
3. Review validation errors
4. Fix contract structure and retry

### Migration Performance Issues

**Symptoms:**
- Migration takes too long
- Timeout errors
- Database connection issues

**Solutions:**
1. Reduce batch size
2. Migrate by tenant
3. Check database performance
4. Use smaller batches

### Rollback Fails

**Symptoms:**
```
Rollback failed: Contract not found
```

**Solutions:**
1. Check contract existence
2. Verify contract IDs match
3. Manual cleanup if needed
4. Review database state

---

## Additional Resources

- [ODCS to ODPS Migration Guide](ODCS_TO_ODPS_MIGRATION_GUIDE.md) - Detailed ODCS→ODPS migration guide
- [ODCS Version Support](ODCS_VERSION_SUPPORT.md) - Complete ODCS version documentation
- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Creation Flows](ODPS_CREATION_FLOWS.md) - Creation flow documentation
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [API Reference](API_REFERENCE.md) - Complete API documentation

---

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Maintained By**: Data Interoperability Hub Team

---

# ODPS Examples

Complete engineering-grade examples for ODPS (Open Data Product Standard) in the Data Interoperability Hub.

**Last Updated**: 2026-03-22
**Version**: 1.0.0

## Table of Contents

1. [ODPS 4.1 Example Files](#odps-41-example-files)
2. [ODPS Creation Examples](#odps-creation-examples)
3. [ODPS Linking Examples](#odps-linking-examples)
4. [ODPS Export Examples](#odps-export-examples)
5. [ODPS $ref Examples](#odps-ref-examples)
6. [ODPS Marketplace Examples](#odps-marketplace-examples)

---

## ODPS 4.1 Example Files

### Complete ODPS 4.1 Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics-v1",
        "name": "Customer Analytics Dataset",
        "description": "Comprehensive customer analytics data including purchase history, demographics, and behavior patterns",
        "productVersion": "1.0.0",
        "tags": ["analytics", "customer", "e-commerce"],
        "categories": ["Business Intelligence", "Customer Data"]
      },
      "fr": {
        "productID": "customer-analytics-v1",
        "name": "Dataset d'Analyse Client",
        "description": "Données complètes d'analyse client incluant l'historique d'achat, la démographie et les modèles de comportement"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "customer-analytics-contract",
        "name": "Customer Analytics Contract",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "customer_id",
              "type": "string",
              "nullable": false,
              "description": "Unique customer identifier"
            },
            {
              "name": "purchase_date",
              "type": "date",
              "nullable": false,
              "description": "Date of purchase"
            },
            {
              "name": "amount",
              "type": "number",
              "nullable": false,
              "description": "Purchase amount in USD"
            },
            {
              "name": "product_category",
              "type": "string",
              "nullable": true,
              "description": "Product category"
            }
          ]
        },
        "quality": {
          "rules": [
            {
              "name": "non_null_customer_id",
              "type": "not_null",
              "field": "customer_id",
              "description": "Customer ID must not be null"
            },
            {
              "name": "positive_amount",
              "type": "greater_than",
              "field": "amount",
              "value": 0,
              "description": "Purchase amount must be positive"
            }
          ]
        },
        "compliance": {
          "rules": [
            {
              "name": "gdpr_compliance",
              "type": "GDPR",
              "description": "GDPR compliance required"
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
          "description": "Basic access to customer analytics data",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "1000 records/month",
            "Basic analytics",
            "Email support"
          ]
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "description": "Premium access with advanced features",
          "price": 29.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Priority support",
            "API access"
          ]
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST_API",
          "endpoint": "https://api.example.com/customer-analytics",
          "protocol": "HTTPS",
          "authentication": "Bearer Token",
          "rateLimit": "1000 requests/hour"
        },
        "download": {
          "type": "FILE_DOWNLOAD",
          "format": "CSV",
          "maxSize": "100MB"
        }
      },
      "paymentGateways": {
        "stripe": {
          "type": "STRIPE",
          "enabled": true,
          "publicKey": "pk_test_..."
        },
        "paypal": {
          "type": "PAYPAL",
          "enabled": true
        }
      },
      "license": {
        "type": "COMMERCIAL",
        "summary": "Commercial license for customer analytics data"
      },
      "intendedUse": [
        "Business Intelligence",
        "Customer Analysis",
        "Marketing Analytics"
      ],
      "restrictedUse": [
        "Resale",
        "Competitive Intelligence"
      ]
    },
    "productStrategy": {
      "objectives": [
        {
          "objectiveID": "obj-1",
          "name": "Increase Revenue",
          "description": "Generate revenue through data product sales",
          "target": "100K USD/year",
          "deadline": "2026-12-31"
        }
      ],
      "strategicAlignment": "Revenue Growth",
      "productKPIs": [
        {
          "kpiID": "kpi-1",
          "name": "Monthly Recurring Revenue",
          "metric": "MRR",
          "target": "10K USD",
          "current": "5K USD"
        },
        {
          "kpiID": "kpi-2",
          "name": "Customer Acquisition",
          "metric": "New Customers",
          "target": "100/month",
          "current": "50/month"
        }
      ]
    }
  }
}
```

### Minimal ODPS 4.1 Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "simple-product",
        "name": "Simple Product"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "simple-contract",
        "schema": {
          "fields": [
            {"name": "id", "type": "string"}
          ]
        }
      }
    }
  }
}
```

---

## ODPS Creation Examples

### Product-First Flow Example

**REST API:**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"customer-analytics-contract\",\"schema\":{\"fields\":[{\"name\":\"customer_id\",\"type\":\"string\"}]}}}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config
import json

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

odps_document = {
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
}

async with DataHubClient(config) as client:
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_document),
        extract_odcs=True,
        original_format="JSON",
        resolve_external_refs=True
    )

    print(f"ODPS Contract ID: {result['odps_contract']['id']}")
    print(f"ODCS Contract ID: {result['odcs_contract']['id']}")
    print(f"Workflow Instance ID: {result['workflow_instance_id']}")
```

**CLI:**

```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --resolve-external-refs
```

### Technical-First Flow Example

**Python SDK:**

```python
from hub.apps.contracts.services import ContractService

odcs_document = {
    "apiVersion": "odcs/v3",
    "kind": "DataContract",
    "id": "customer-analytics-contract",
    "schema": {
        "fields": [
            {"name": "customer_id", "type": "string"},
            {"name": "purchase_date", "type": "date"},
            {"name": "amount", "type": "number"}
        ]
    }
}

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Create ODCS contract
odcs_contract = contract_service.create_contract(
    original_raw=json.dumps(odcs_document),
    original_format="JSON",
    original_spec_type="ODCS"
)

# Auto-generate ODPS from ODCS
odps_contract = contract_service.auto_generate_odps_for_odcs(
    odcs_contract_id=str(odcs_contract.id),
    target_odps_version="4.1"
)

print(f"ODCS Contract ID: {odcs_contract.id}")
print(f"ODPS Contract ID: {odps_contract.id}")
```

### Data-First Flow Example

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    # Step 1: Upload file
    file_result = await client.files.upload(
        file_path="customer_data.csv",
        name="customer-data"
    )

    # Step 2: Create asset with auto-generated contracts
    asset = await client.assets.create(
        file_id=file_result["id"],
        name="Customer Analytics Dataset",
        key="customer-analytics",
        auto_generate_contracts=True,
        odps_action="generate",
        auto_activate=True
    )

    print(f"Asset ID: {asset['id']}")
    print(f"ODCS Contract ID: {asset['contracts']['odcs']['id']}")
    print(f"ODPS Contract ID: {asset['contracts']['odps']['id']}")
```

---

## ODPS Linking Examples

### Link ODPS to Existing ODCS

**REST API:**

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odcs-contract-id}/link-odps/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}",
    "original_format": "JSON"
  }'
```

**Python SDK:**

```python
odps_document = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "linked-product",
                "name": "Linked Product"
            }
        }
    }
}

# Create ODPS and link to existing ODCS
odps_contract = await client.contracts.create_odps(
    original_raw=json.dumps(odps_document),
    link_odcs_id="existing-odcs-contract-id",
    original_format="JSON"
)

print(f"ODPS Contract ID: {odps_contract['id']}")
print(f"Linked to ODCS Contract ID: existing-odcs-contract-id")
```

**CLI:**

```bash
datahub contracts link-odps \
  --odcs-id <odcs-contract-id> \
  --odps-file product.odps.json
```

### Verify Bidirectional Linking

**Python SDK:**

```python
# Get ODPS contract
odps_contract = await client.contracts.get_contract(
    contract_id="odps-contract-id"
)

# Check ODCS link
odcs_link = odps_contract["hub_contract_json"]["extensions"]["x_odps"]["odcs_link"]
print(f"ODPS links to ODCS: {odcs_link}")

# Get ODCS contract
odcs_contract = await client.contracts.get_contract(
    contract_id=odcs_link
)

# Check ODPS link
odps_link = odcs_contract["hub_contract_json"]["extensions"]["x_odps"]["odps_link"]
print(f"ODCS links to ODPS: {odps_link}")
```

---

## ODPS Export Examples

### Export as JSON

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python SDK:**

```python
odps_json = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="json",
    version="4.1"
)

print(odps_json["content"])
```

**CLI:**

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format json \
  --version 4.1
```

### Export as YAML

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python SDK:**

```python
odps_yaml = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="yaml"
)

print(odps_yaml["content"])
```

**CLI:**

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format yaml
```

### Download as File

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.json
```

**Python SDK:**

```python
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="json"
)

with open("product.odps.json", "wb") as f:
    f.write(odps_file)
```

**CLI:**

```bash
datahub contracts download <contract-id> \
  --format odps \
  --output-format json \
  --output product.odps.json
```

---

## ODPS $ref Examples

### Internal Reference Example

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "definitions": {
    "customerSchema": {
      "fields": [
        {"name": "customer_id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "email", "type": "string"}
      ]
    }
  },
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "customer-analytics-contract",
        "schema": {
          "$ref": "#/definitions/customerSchema"
        }
      }
    }
  }
}
```

### Local Reference Example

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
    "contract": {
      "$ref": "./contracts/customer-schema.json"
    }
  }
}
```

**File: `./contracts/customer-schema.json`**

```json
{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "customer-schema",
  "schema": {
    "fields": [
      {"name": "customer_id", "type": "string"},
      {"name": "name", "type": "string"},
      {"name": "email", "type": "string"}
    ]
  }
}
```

### External Reference Example

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
    "contract": {
      "$ref": "https://schemas.example.com/data-contracts/customer-v1.json"
    }
  }
}
```

**REST API with External Ref Resolution:**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"}},\"contract\":{\"$ref\":\"https://schemas.example.com/data-contracts/customer-v1.json\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Python SDK:**

```python
odps_document = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "customer-analytics",
                "name": "Customer Analytics Dataset"
            }
        },
        "contract": {
            "$ref": "https://schemas.example.com/data-contracts/customer-v1.json"
        }
    }
}

result = await client.contracts.create_odps(
    original_raw=json.dumps(odps_document),
    extract_odcs=True,
    original_format="JSON",
    resolve_external_refs=True  # Enable external ref resolution
)
```

---

## ODPS Marketplace Examples

### Complete Marketplace Configuration

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
      "pricingPlans": [
        {
          "planID": "free",
          "name": "Free Plan",
          "description": "Free access with limited features",
          "price": 0,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "100 records/month",
            "Basic analytics",
            "Community support"
          ]
        },
        {
          "planID": "basic",
          "name": "Basic Plan",
          "description": "Basic access to customer analytics data",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "1000 records/month",
            "Basic analytics",
            "Email support"
          ]
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "description": "Premium access with advanced features",
          "price": 29.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Priority support",
            "API access"
          ]
        },
        {
          "planID": "enterprise",
          "name": "Enterprise Plan",
          "description": "Enterprise access with custom features",
          "price": 99.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Dedicated support",
            "API access",
            "Custom integrations",
            "SLA guarantee"
          ]
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST_API",
          "endpoint": "https://api.example.com/customer-analytics",
          "protocol": "HTTPS",
          "authentication": "Bearer Token",
          "rateLimit": "1000 requests/hour",
          "documentation": "https://docs.example.com/api/customer-analytics"
        },
        "download": {
          "type": "FILE_DOWNLOAD",
          "format": "CSV",
          "maxSize": "100MB",
          "compression": "gzip"
        },
        "streaming": {
          "type": "STREAMING",
          "protocol": "WebSocket",
          "endpoint": "wss://stream.example.com/customer-analytics"
        }
      },
      "paymentGateways": {
        "stripe": {
          "type": "STRIPE",
          "enabled": true,
          "publicKey": "pk_test_...",
          "supportedCurrencies": ["USD", "EUR", "GBP"]
        },
        "paypal": {
          "type": "PAYPAL",
          "enabled": true,
          "supportedCurrencies": ["USD", "EUR"]
        },
        "bank_transfer": {
          "type": "BANK_TRANSFER",
          "enabled": true,
          "instructions": "Contact sales@example.com for bank transfer details"
        }
      },
      "license": {
        "type": "COMMERCIAL",
        "summary": "Commercial license for customer analytics data",
        "terms": "https://example.com/license/customer-analytics"
      },
      "intendedUse": [
        "Business Intelligence",
        "Customer Analysis",
        "Marketing Analytics",
        "Data Science Research"
      ],
      "restrictedUse": [
        "Resale",
        "Competitive Intelligence",
        "Illegal Activities"
      ]
    }
  }
}
```

### Marketplace Integration Example

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

odps_document = {
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
            "pricingPlans": [
                {
                    "planID": "basic",
                    "name": "Basic Plan",
                    "price": 9.99,
                    "currency": "USD",
                    "billingPeriod": "monthly"
                }
            ],
            "accessMethods": {
                "api": {
                    "type": "REST_API",
                    "endpoint": "https://api.example.com/customer-analytics"
                }
            },
            "paymentGateways": {
                "stripe": {
                    "type": "STRIPE",
                    "enabled": True
                }
            }
        }
    }
}

async with DataHubClient(config) as client:
    # Create ODPS contract
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_document),
        extract_odcs=True,
        original_format="JSON"
    )

    # Sync to marketplace
    marketplace_result = await client.marketplace.sync_product(
        product_id=result["odps_contract"]["id"],
        marketplace_type="SNOWFLAKE"
    )

    print(f"Product synced to marketplace: {marketplace_result['listing_id']}")
```

---

## Additional Resources

- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Creation Flows](ODPS_CREATION_FLOWS.md) - Detailed creation flow documentation
- [ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md) - Comprehensive migration guide
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md) - User guide for marketplace integrations
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) - Marketplace use cases and scenarios
- [API Reference](API_REFERENCE.md) - Complete API documentation

---

**Document Version**: 1.0.0
**Last Updated**: 2026-03-22
**Maintained By**: Data Interoperability Hub Team

---

# ODCS to ODPS Migration Guide

**Version**: 1.0
**Last Updated**: 2026-03-22
**Status**: Production Ready

## Table of Contents

1. [Overview](#overview)
2. [When to Run Migration](#when-to-run-migration)
3. [Prerequisites](#prerequisites)
4. [Migration Process](#migration-process)
5. [Rollback Process](#rollback-process)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Reference](#reference)

---

## Overview

This guide provides comprehensive instructions for migrating existing Open Data Contract Standard (ODCS) contracts to Open Data Product Standard (ODPS) contracts. The migration process:

- **Creates ODPS contracts** from ODCS contracts with marketplace metadata
- **Preserves all data** from the original HubContract
- **Establishes bidirectional links** between ODPS and ODCS contracts
- **Maintains marketplace metadata** throughout the migration
- **Supports validation** to ensure migration success
- **Provides rollback capabilities** if needed

### Key Concepts

- **ODCS (Open Data Contract Standard)**: The original contract format
- **ODPS (Open Data Product Standard)**: The target contract format (version 4.1)
- **HubContract**: The normalized internal representation of contracts
- **Bidirectional Linking**: ODPS ↔ ODCS links maintained in both contracts
- **Marketplace Metadata**: License, pricing, access methods, and payment gateway information

---

## When to Run Migration

### Migration Strategy: Opt-In

Migration is **opt-in** and should be performed when:

1. **You want to leverage ODPS features** such as:
   - Enhanced marketplace capabilities
   - Improved product catalog integration
   - Better support for data product lifecycle management

2. **You have ODCS contracts with marketplace metadata** that would benefit from ODPS format

3. **You're preparing for future features** that require ODPS contracts

### Migration Modes

The migration supports three execution modes:

#### 1. Per-Contract Migration (Recommended for Testing)

Migrate a single contract for testing or validation:

```bash
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --dry-run
```

**Use Cases:**
- Testing migration on a single contract
- Validating migration process before batch execution
- Migrating specific contracts on-demand

#### 2. Batch Migration (Recommended for Production)

Migrate multiple contracts in batches:

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --tenant-id <tenant-uuid> \
    --skip-linked
```

**Use Cases:**
- Migrating all eligible contracts for a tenant
- Production migrations with controlled batch sizes
- Systematic migration of contract portfolios

#### 3. Full Migration (Use with Caution)

Migrate all eligible contracts across all tenants:

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --skip-linked
```

**Use Cases:**
- System-wide migrations
- Initial migration setup
- **Warning**: Only use after thorough testing

### Migration Eligibility

A contract is eligible for migration if:

1. ✅ **Contract type**: Must be `ODCS` (original_spec_type = ODCS)
2. ✅ **HubContract exists**: Must have `hub_contract_json` populated
3. ✅ **Marketplace metadata**: Must have marketplace fields (configurable via `--min-marketplace-fields`)
4. ✅ **Not already migrated**: Must not already have an ODPS link (unless `--skip-linked` is not used)

### When NOT to Migrate

Do **NOT** migrate if:

- ❌ Contract is in active use and migration might cause disruption
- ❌ Contract has critical dependencies that require ODCS format
- ❌ You haven't tested the migration process in a staging environment
- ❌ You don't have a rollback plan in place
- ❌ Contract lacks marketplace metadata (unless you plan to add it later)

---

## Prerequisites

### System Requirements

1. **Docker Compose Environment**
   ```bash
   # Verify services are running
   docker compose -f docker-compose.dev.yml ps
   ```

2. **Database Access**
   - Database must be accessible
   - Sufficient database permissions for contract creation
   - Transaction support enabled

3. **Service Dependencies**
   - API service must be running
   - Redis (for async tasks) must be running
   - All required services operational

### Pre-Migration Checklist

Before running migration, verify:

- [ ] **Backup Database**: Create a full database backup
  ```bash
  # Example backup command (adjust for your setup)
  pg_dump -h localhost -U postgres -d hub > backup_before_migration_$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Test Environment**: Run migration in test/staging first
- [ ] **Review Contracts**: Identify contracts to migrate
- [ ] **Check Marketplace Data**: Verify contracts have marketplace metadata
- [ ] **Validate HubContract**: Ensure HubContract data is complete
- [ ] **Plan Rollback**: Understand rollback procedure
- [ ] **Notify Stakeholders**: Inform relevant teams about migration

### Required Permissions

- **Database**: Read/write access to `contracts` table
- **API Service**: Ability to execute management commands
- **Tenant Context**: Access to tenant data (if using `--tenant-id`)

### Contract Requirements

For a contract to be successfully migrated, it must have:

1. **Valid HubContract JSON**:
   ```json
   {
     "hub_contract_version": "1.0.0",
     "id": "contract-id",
     "info": { ... },
     "schema": { ... },
     "marketplace": {
       "license_summary": "...",
       "intended_use": [...],
       "restricted_use": [...],
       "x_odps": {
         "pricing_plans": [...],
         "access_methods": {...},
         "payment_gateways": {...}
       }
     }
   }
   ```

2. **Original ODCS Contract**: `original_raw` field must contain valid ODCS contract

3. **Marketplace Fields**: At least one marketplace field (configurable)

---

## Migration Process

### Step 1: Dry Run (Always Start Here)

**Always perform a dry run first** to validate the migration without making changes:

```bash
python manage.py migrate_contracts_to_odps \
    --dry-run \
    --contract-id <contract-uuid>
```

**Dry run output includes:**
- Number of contracts that would be migrated
- Validation results
- Any errors or warnings
- Estimated impact

### Step 2: Validate Prerequisites

Check that contracts meet migration requirements:

```bash
# Check specific contract
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --dry-run \
    --min-marketplace-fields 1
```

Review the output to ensure:
- Contract is eligible
- Marketplace metadata is present
- No blocking issues

### Step 3: Execute Migration

#### Option A: Single Contract Migration

```bash
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

#### Option B: Batch Migration (Tenant-Specific)

```bash
python manage.py migrate_contracts_to_odps \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

#### Option C: Full Batch Migration

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --skip-linked \
    --target-odps-version 4.1 \
    --min-marketplace-fields 1 \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

### Step 4: Validate Migration

After migration, validate the results:

```bash
# Validate all migrations
python manage.py validate_migration \
    --format text \
    --report-path /tmp/validation_report.json

# Validate specific contracts
python manage.py validate_migration \
    --contract-ids <id1>,<id2>,<id3> \
    --format json \
    --report-path /tmp/validation_report.json

# Validate tenant-specific migrations
python manage.py validate_migration \
    --tenant-id <tenant-uuid> \
    --format text
```

**Validation checks:**
- ✅ All contracts migrated successfully
- ✅ No data loss (HubContract comparison)
- ✅ Links are correct (bidirectional validation)
- ✅ Marketplace metadata preserved
- ✅ Statistics and report generation

### Step 5: Review Migration Report

Review the validation report:

```bash
# View text report
cat /tmp/validation_report.json | python -m json.tool

# Or use the text format
python manage.py validate_migration --format text
```

**Report includes:**
- Total contracts processed
- Migration success rate
- Issues found (errors, warnings)
- Data loss detection
- Link validation results
- Marketplace metadata preservation status

### Step 6: Verify in Application

1. **Check Contract Links**: Verify bidirectional links in UI/API
2. **Verify Marketplace Data**: Confirm marketplace metadata is accessible
3. **Test ODPS Features**: Test any ODPS-specific features
4. **Monitor Logs**: Check for any errors or warnings

---

## Rollback Process

### When to Rollback

Rollback should be performed if:

- ❌ Migration validation reveals critical issues
- ❌ Data loss is detected
- ❌ Links are broken or incorrect
- ❌ Marketplace metadata is missing or corrupted
- ❌ Application errors occur after migration
- ❌ Business requirements change

### Rollback Prerequisites

Before rolling back:

- [ ] **Backup Current State**: Create backup of current database state
- [ ] **Review Impact**: Understand what will be rolled back
- [ ] **Plan Restoration**: Know how to restore if needed
- [ ] **Notify Stakeholders**: Inform relevant teams

### Rollback Steps

#### Step 1: Dry Run Rollback

**Always start with a dry run:**

```bash
python manage.py rollback_odps_migration \
    --dry-run \
    --contract-id <contract-uuid>
```

#### Step 2: Execute Rollback

##### Option A: Single Contract Rollback

```bash
python manage.py rollback_odps_migration \
    --contract-id <contract-uuid>
```

##### Option B: Batch Rollback (Tenant-Specific)

```bash
python manage.py rollback_odps_migration \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-unlinked
```

##### Option C: Full Batch Rollback

```bash
python manage.py rollback_odps_migration \
    --batch-size 100 \
    --skip-unlinked
```

#### Step 3: Verify Rollback

After rollback, verify:

1. **ODPS Links Removed**: Check that ODCS contracts no longer have ODPS links
2. **ODPS Contracts Deleted**: Verify ODPS contracts are removed
3. **ODCS Contracts Intact**: Ensure ODCS contracts are unchanged
4. **No Orphaned Data**: Check for any orphaned references

```bash
# Validate rollback (check that contracts are unlinked)
python manage.py validate_migration \
    --contract-ids <contract-uuid> \
    --format text
```

**Expected result**: Contract should show as "NOT MIGRATED"

### Rollback What It Does

The rollback process:

1. **Removes ODPS Links**: Removes `odps_link` from ODCS contracts
2. **Removes ODCS Links**: Removes `odcs_link` from ODPS contracts
3. **Deletes ODPS Contracts**: Deletes ODPS contracts created during migration
4. **Validates State**: Verifies that rollback completed successfully

### Rollback Limitations

⚠️ **Important Notes:**

- Rollback **cannot restore** ODCS contracts if they were modified during migration
- Rollback **deletes** ODPS contracts permanently (ensure backups exist)
- Rollback **does not restore** previous ODPS links if they existed before migration
- Rollback **requires** ODPS contracts to exist (cannot rollback if already deleted)

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Contract Not Eligible for Migration

**Symptoms:**
```
Contract <uuid> not found or not eligible
```

**Causes:**
- Contract is not ODCS type
- Contract lacks HubContract JSON
- Contract lacks marketplace metadata
- Contract already has ODPS link

**Solutions:**

1. **Check Contract Type**:
   ```bash
   # Verify contract type
   python manage.py shell
   >>> from hub.apps.contracts.models import Contract
   >>> contract = Contract.objects.get(id='<uuid>')
   >>> print(contract.original_spec_type)  # Should be 'ODCS'
   ```

2. **Check HubContract**:
   ```bash
   >>> print(contract.hub_contract_json is not None)  # Should be True
   ```

3. **Check Marketplace Metadata**:
   ```bash
   >>> marketplace = contract.hub_contract_json.get('marketplace', {})
   >>> print(marketplace)  # Should have marketplace fields
   ```

4. **Check Existing Links**:
   ```bash
   >>> extensions = contract.hub_contract_json.get('extensions', {})
   >>> x_odps = extensions.get('x_odps', {})
   >>> print(x_odps.get('odps_link'))  # Should be None if not migrated
   ```

#### Issue 2: Migration Fails with Validation Error

**Symptoms:**
```
Validation error: ODPS normalization failed
```

**Causes:**
- Invalid HubContract structure
- Missing required fields
- Marketplace metadata format issues

**Solutions:**

1. **Validate HubContract**:
   ```bash
   python manage.py shell
   >>> from hub.apps.contracts.typed_models import validate_hub_contract_dict
   >>> result, errors = validate_hub_contract_dict(contract.hub_contract_json)
   >>> print(errors)  # Review validation errors
   ```

2. **Check Marketplace Format**:
   - Ensure `marketplace.license_summary` is a string
   - Ensure `marketplace.intended_use` is an array
   - Ensure `marketplace.restricted_use` is an array
   - Ensure `marketplace.x_odps` structure is correct

3. **Fix HubContract**:
   - Update HubContract JSON to fix validation errors
   - Re-run migration

#### Issue 3: Data Loss Detected During Validation

**Symptoms:**
```
Validation completed with X error(s)
Data loss detected in HubContract comparison
```

**Causes:**
- HubContract sections missing in ODPS
- Field transformations during normalization
- Marketplace metadata not preserved

**Solutions:**

1. **Review Validation Report**:
   ```bash
   python manage.py validate_migration \
       --contract-ids <uuid> \
       --format json \
       --report-path /tmp/report.json
   # Review missing_sections and differences
   ```

2. **Check Missing Sections**:
   - Review which sections are missing
   - Determine if missing sections are critical
   - Consider if sections were intentionally transformed

3. **Verify Marketplace Metadata**:
   ```bash
   # Compare marketplace data
   python manage.py shell
   >>> odcs_marketplace = odcs_contract.hub_contract_json.get('marketplace', {})
   >>> odps_marketplace = odps_contract.hub_contract_json.get('marketplace', {})
   >>> # Compare fields
   ```

4. **If Critical Data Loss**:
   - Consider rolling back the migration
   - Investigate root cause
   - Fix HubContract or migration logic
   - Re-run migration

#### Issue 4: Broken Links After Migration

**Symptoms:**
```
Link validation failed: ODPS contract does not link back to ODCS contract
```

**Causes:**
- Bidirectional links not established correctly
- Links removed or corrupted
- Contract deletion

**Solutions:**

1. **Verify Links**:
   ```bash
   python manage.py shell
   >>> # Check ODCS → ODPS link
   >>> odcs_extensions = odcs_contract.hub_contract_json.get('extensions', {})
   >>> odcs_x_odps = odcs_extensions.get('x_odps', {})
   >>> print(odcs_x_odps.get('odps_link'))

   >>> # Check ODPS → ODCS link
   >>> odps_extensions = odps_contract.hub_contract_json.get('extensions', {})
   >>> odps_x_odps = odps_extensions.get('x_odps', {})
   >>> print(odps_x_odps.get('odcs_link'))
   ```

2. **Fix Links Manually** (if needed):
   ```bash
   >>> # Restore ODCS → ODPS link
   >>> odcs_x_odps['odps_link'] = str(odps_contract.id)
   >>> odcs_contract.save(update_fields=['hub_contract_json'])

   >>> # Restore ODPS → ODCS link
   >>> odps_x_odps['odcs_link'] = str(odcs_contract.id)
   >>> odps_contract.save(update_fields=['hub_contract_json'])
   ```

3. **Re-run Validation**:
   ```bash
   python manage.py validate_migration --contract-ids <uuid>
   ```

#### Issue 5: Migration Performance Issues

**Symptoms:**
- Migration takes too long
- Timeout errors
- Database connection issues

**Solutions:**

1. **Reduce Batch Size**:
   ```bash
   python manage.py migrate_contracts_to_odps \
       --batch-size 10  # Reduce from default 100
   ```

2. **Migrate by Tenant**:
   ```bash
   # Migrate one tenant at a time
   python manage.py migrate_contracts_to_odps \
       --tenant-id <tenant-uuid> \
       --batch-size 50
   ```

3. **Check Database Performance**:
   - Monitor database connections
   - Check for locks
   - Review slow queries

4. **Use Smaller Batches**:
   - Process contracts in smaller batches
   - Add delays between batches if needed

#### Issue 6: Rollback Fails

**Symptoms:**
```
Rollback failed: Contract not found
```

**Causes:**
- ODPS contract already deleted
- Contract ID mismatch
- Database state inconsistent

**Solutions:**

1. **Check Contract Existence**:
   ```bash
   python manage.py shell
   >>> from hub.apps.contracts.models import Contract
   >>> try:
   ...     contract = Contract.objects.get(id='<uuid>')
   ...     print(f"Contract exists: {contract.original_spec_type}")
   ... except Contract.DoesNotExist:
   ...     print("Contract not found")
   ```

2. **Manual Cleanup** (if needed):
   ```bash
   >>> # Remove links manually
   >>> odcs_contract.hub_contract_json['extensions']['x_odps'].pop('odps_link', None)
   >>> odcs_contract.save(update_fields=['hub_contract_json'])
   ```

3. **Verify State**:
   ```bash
   python manage.py validate_migration --contract-ids <uuid>
   ```

### Getting Help

If you encounter issues not covered here:

1. **Check Logs**:
   ```bash
   docker compose -f docker-compose.dev.yml logs api-service | grep -i migration
   ```

2. **Review Validation Report**:
   - Check validation report for detailed error messages
   - Review statistics for patterns

3. **Contact Support**:
   - Provide migration command used
   - Include validation report
   - Share relevant logs
   - Describe steps to reproduce

---

## Best Practices

### Pre-Migration

1. **Always Test First**: Run migration in test/staging environment
2. **Backup Database**: Create full backup before migration
3. **Start Small**: Migrate one contract first, then small batches
4. **Use Dry Run**: Always use `--dry-run` first
5. **Validate Prerequisites**: Check contract eligibility before migration

### During Migration

1. **Monitor Progress**: Watch migration output for errors
2. **Use Validation**: Always use `--validate` flag
3. **Save Reports**: Save validation reports for audit
4. **Batch Appropriately**: Use appropriate batch sizes
5. **Tenant Isolation**: Migrate by tenant when possible

### Post-Migration

1. **Validate Results**: Always run validation after migration
2. **Review Reports**: Thoroughly review validation reports
3. **Test Functionality**: Verify ODPS features work correctly
4. **Monitor Logs**: Check for errors or warnings
5. **Document Changes**: Document what was migrated

### Rollback Planning

1. **Plan Before Migrating**: Understand rollback procedure
2. **Test Rollback**: Test rollback in staging first
3. **Keep Backups**: Maintain database backups
4. **Document State**: Document pre-migration state
5. **Have Rollback Ready**: Know rollback command before migrating

---

## Reference

### Command Reference

#### Migration Command

```bash
python manage.py migrate_contracts_to_odps [OPTIONS]

Options:
  --dry-run                    Run in dry-run mode (no changes)
  --contract-id UUID           Migrate specific contract
  --batch-size INT             Batch size (default: 100)
  --tenant-id UUID             Migrate for specific tenant
  --skip-linked                Skip contracts with existing ODPS links
  --target-odps-version STR    Target ODPS version (default: 4.1)
  --min-marketplace-fields INT Minimum marketplace fields (default: 1)
  --validate                   Run validation after migration
  --validation-report-path PATH Save validation report to file
```

#### Validation Command

```bash
python manage.py validate_migration [OPTIONS]

Options:
  --tenant-id UUID             Validate for specific tenant
  --contract-ids STR           Comma-separated contract IDs
  --report-path PATH           Save report to file
  --format [text|json]         Output format (default: text)
  --include-statistics         Include statistics (default: True)
```

#### Rollback Command

```bash
python manage.py rollback_odps_migration [OPTIONS]

Options:
  --dry-run                    Run in dry-run mode (no changes)
  --contract-id UUID           Rollback specific contract
  --batch-size INT             Batch size (default: 100)
  --tenant-id UUID             Rollback for specific tenant
  --skip-unlinked              Skip contracts without ODPS links
```

### Migration Flow Diagram

```
┌─────────────────┐
│  ODCS Contract  │
│  (with          │
│  marketplace)   │
└────────┬────────┘
         │
         │ migrate_contracts_to_odps
         │
         ▼
┌─────────────────┐
│  Generate ODPS  │
│  from HubContract│
└────────┬────────┘
         │
         │ create ODPS contract
         │
         ▼
┌─────────────────┐
│  ODPS Contract  │
│  (normalized)   │
└────────┬────────┘
         │
         │ link_odps_to_odcs
         │
         ▼
┌─────────────────┐
│  Bidirectional  │
│  Links Created  │
│  ODPS ↔ ODCS    │
└────────┬────────┘
         │
         │ validate_migration
         │
         ▼
┌─────────────────┐
│  Validation     │
│  Report         │
└─────────────────┘
```

### Related Documentation

- **Migration Script**: `hub/apps/contracts/management/commands/migrate_contracts_to_odps.py`
- **Validation Module**: `hub/apps/contracts/migration_validation.py`
- **Rollback Script**: `hub/apps/contracts/management/commands/rollback_odps_migration.py`
- **ODPS Generator**: `hub/apps/contracts/odps_generator.py`
- **Linking Validation**: `hub/apps/contracts/linking_validation.py`

### Support and Feedback

For questions, issues, or feedback:

1. Check this documentation first
2. Review validation reports
3. Check application logs
4. Contact the development team

---

**Document Version**: 1.0
**Last Updated**: 2026-03-22
**Maintained By**: Data Interoperability Hub Team























---

# ODCS Version Support

Complete guide for Open Data Contract Standard (ODCS) version support in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [Supported Versions](#supported-versions)
3. [Version-Specific Features](#version-specific-features)
4. [Graceful Degradation](#graceful-degradation)
5. [Version Detection](#version-detection)
6. [Normalization Behavior](#normalization-behavior)
7. [Migration Guidance](#migration-guidance)
8. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub supports multiple versions of the Open Data Contract Standard (ODCS) to ensure backward compatibility and smooth migration paths. Each version is handled by a dedicated normalizer that understands version-specific features and gracefully handles missing features from newer versions.

### Key Principles

- **Backward Compatibility**: Older ODCS versions continue to be supported
- **Graceful Degradation**: Missing features from newer versions are handled without errors
- **Version-Specific Normalizers**: Each version has a dedicated normalizer for optimal handling
- **Consistent Output**: All versions normalize to the same HubContract format

---

## Supported Versions

The following ODCS versions are fully supported:

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **3.0.2** | ✅ Current (Baseline) | `ODCSNormalizerV3_0_2` | Latest stable version, recommended for new contracts |
| **3.0.1** | ✅ Supported | `ODCSNormalizerV3_0_1` | Previous stable version, fully supported |
| **3.0.0** | ✅ Supported | `ODCSNormalizerV3_0_0` | Initial 3.x release, fully supported |
| **3.0.0-preview** | ✅ Supported | `ODCSNormalizerV3_0_0_Preview` | Preview version, gracefully handles incomplete features |
| **2.2.2** | ✅ Supported (Legacy) | `ODCSNormalizerV2_2_2` | Legacy version, gracefully degrades 3.x features |

### Version Detection

ODCS versions are detected from the `apiVersion` field in the contract:

```yaml
apiVersion: odcs.io/v3.0.2  # Version 3.0.2
apiVersion: odcs.io/v3.0.1  # Version 3.0.1
apiVersion: odcs.io/v3.0.0  # Version 3.0.0
apiVersion: odcs.io/v3.0.0-preview  # Version 3.0.0-preview
apiVersion: odcs.io/v2.2.2  # Version 2.2.2
```

---

## Version-Specific Features

### ODCS 3.0.2 (Current/Baseline)

**Status**: Current stable version, recommended for new contracts

**Features**:
- Full support for all ODCS 3.x features
- Enhanced marketplace features
- Enhanced lifecycle features
- Complete schema support
- All quality rules and compliance features

**Normalizer**: `ODCSNormalizerV3_0_2`

**Example**:
```yaml
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.1

**Status**: Fully supported, previous stable version

**Features**:
- Full support for ODCS 3.0.1 features
- Graceful degradation for 3.0.2+ features (if present, they are ignored)
- All core ODCS 3.x functionality

**Normalizer**: `ODCSNormalizerV3_0_1`

**Graceful Degradation**:
- If 3.0.2-specific features are present, they are logged but not processed
- Normalization continues with available 3.0.1 features
- No errors are raised for missing 3.0.2 features

**Example**:
```yaml
apiVersion: odcs.io/v3.0.1
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.0

**Status**: Fully supported, initial 3.x release

**Features**:
- Full support for ODCS 3.0.0 features
- Graceful degradation for 3.0.1+ and 3.0.2+ features
- Core ODCS 3.x functionality

**Normalizer**: `ODCSNormalizerV3_0_0`

**Graceful Degradation**:
- If 3.0.1+ or 3.0.2+ features are present, they are logged but not processed
- Normalization continues with available 3.0.0 features
- No errors are raised for missing newer features

**Example**:
```yaml
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.0-preview

**Status**: Supported, preview version

**Features**:
- Support for ODCS 3.0.0-preview features
- Graceful handling of incomplete or experimental features
- May have missing optional fields compared to stable versions

**Normalizer**: `ODCSNormalizerV3_0_0_Preview`

**Special Considerations**:
- Preview versions may have incomplete feature sets
- Experimental features may change
- Missing optional fields are handled gracefully
- Warnings may be generated for incomplete contracts

**Example**:
```yaml
apiVersion: odcs.io/v3.0.0-preview
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 2.2.2 (Legacy)

**Status**: Supported for backward compatibility

**Features**:
- Full support for ODCS 2.2.2 features
- Graceful degradation for all 3.x features:
  - Enhanced marketplace features (limited support)
  - Enhanced lifecycle features (limited support)
  - Other 3.x-specific features

**Normalizer**: `ODCSNormalizerV2_2_2`

**Graceful Degradation**:
- 3.x-specific features are not processed
- Core 2.2.2 features are normalized correctly
- No errors are raised for missing 3.x features
- Contracts normalize successfully to HubContract format

**Example**:
```yaml
apiVersion: odcs.io/v2.2.2
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

---

## Graceful Degradation

The normalization system implements graceful degradation to ensure that older ODCS versions can be normalized successfully even when they lack features present in newer versions.

### How It Works

1. **Version Detection**: The system detects the ODCS version from the `apiVersion` field
2. **Normalizer Selection**: A version-specific normalizer is selected
3. **Feature Mapping**: Only features available in that version are processed
4. **Missing Features**: Features from newer versions are ignored (not errors)
5. **Consistent Output**: All versions produce valid HubContract output

### Degradation Strategy by Version

#### ODCS 3.0.1 → 3.0.2 Features

- **Behavior**: 3.0.2-specific features are logged but not processed
- **Result**: Normalization succeeds with available 3.0.1 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`

#### ODCS 3.0.0 → 3.0.1+/3.0.2+ Features

- **Behavior**: 3.0.1+ and 3.0.2+ features are logged but not processed
- **Result**: Normalization succeeds with available 3.0.0 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`

#### ODCS 2.2.2 → 3.x Features

- **Behavior**: All 3.x-specific features are gracefully ignored
- **Result**: Normalization succeeds with available 2.2.2 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
- **Note**: Enhanced marketplace and lifecycle features have limited support

#### ODCS 3.0.0-preview → Missing Features

- **Behavior**: Missing optional features are handled gracefully
- **Result**: Normalization succeeds with available preview features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
- **Note**: Warnings may be generated for incomplete contracts

### Example: Graceful Degradation in Action

**ODCS 3.0.1 Contract with 3.0.2 Feature**:
```yaml
apiVersion: odcs.io/v3.0.1
kind: DataContract
id: my-contract
name: My Contract
# 3.0.2-specific feature (will be ignored)
newFeature: "value"
schema:
  fields:
    - name: id
      type: string
```

**Result**:
- ✅ Normalization succeeds
- ⚠️ Warning logged: "3.0.2-specific feature 'newFeature' ignored in 3.0.1 contract"
- ✅ HubContract created with available 3.0.1 features
- ✅ Status: `NORMALIZED_WITH_WARNINGS`

---

## Version Detection

### Automatic Detection

The system automatically detects ODCS version from the contract:

```python
from hub.apps.contracts.spec_detection import detect_spec_type

contract_data = {
    "apiVersion": "odcs.io/v3.0.2",
    "kind": "DataContract",
    # ... rest of contract
}

spec_type, spec_version = detect_spec_type(contract_data)
# spec_type = "ODCS"
# spec_version = "3.0.2"
```

### Manual Version Specification

You can also specify the version explicitly:

```python
from hub.apps.contracts.normalization import normalize_contract

result = normalize_contract(
    raw_contract=contract_json_string,
    format="json",
    spec_type="ODCS"  # Optional, auto-detected if not provided
)
```

---

## Normalization Behavior

### Normalization Flow

1. **Version Detection**: Extract version from `apiVersion` field
2. **Normalizer Selection**: Select version-specific normalizer
3. **Contract Validation**: Validate contract structure
4. **Feature Mapping**: Map version-specific features to HubContract
5. **Graceful Degradation**: Handle missing features gracefully
6. **Output Generation**: Produce normalized HubContract

### Normalization Status

All versions can produce the following statuses:

- **`NORMALIZED_OK`**: Successfully normalized with no warnings
- **`NORMALIZED_WITH_WARNINGS`**: Normalized successfully but with warnings (e.g., missing optional features)
- **`NORMALIZATION_FAILED`**: Normalization failed (e.g., invalid contract structure)

### Consistent Output Format

All ODCS versions normalize to the same HubContract format:

```json
{
  "hub_contract_version": "1.0.0",
  "id": "my-contract",
  "info": {
    "name": "My Contract",
    "version": "1.0.0"
  },
  "schema": {
    "fields": [
      {
        "name": "id",
        "data_type": "string",
        "nullable": false
      }
    ]
  },
  "normalization": {
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2"
  }
}
```

---

## Migration Guidance

### Upgrading from Older Versions

#### From ODCS 2.2.2 to 3.0.0+

1. **Update `apiVersion`**: Change from `odcs.io/v2.2.2` to `odcs.io/v3.0.2`
2. **Review Features**: Check for 3.x-specific features you want to use
3. **Test Normalization**: Ensure normalization works correctly
4. **Update Documentation**: Update any documentation referencing version

#### From ODCS 3.0.0 to 3.0.2

1. **Update `apiVersion`**: Change from `odcs.io/v3.0.0` to `odcs.io/v3.0.2`
2. **Review New Features**: Check for 3.0.2-specific features
3. **Test Normalization**: Ensure all features work correctly

#### From ODCS 3.0.0-preview to 3.0.2

1. **Update `apiVersion`**: Change from `odcs.io/v3.0.0-preview` to `odcs.io/v3.0.2`
2. **Review Experimental Features**: Some preview features may have changed
3. **Test Thoroughly**: Preview versions may have had experimental features
4. **Update Contract**: Ensure contract matches stable 3.0.2 specification

### Backward Compatibility

- **Older versions remain supported**: No need to upgrade immediately
- **Gradual migration**: Migrate at your own pace
- **No breaking changes**: Older versions continue to work

---

## Best Practices

### Version Selection

1. **New Contracts**: Use ODCS 3.0.2 (latest stable)
2. **Existing Contracts**: Keep current version unless you need new features
3. **Preview Versions**: Avoid in production; use for testing only

### Contract Structure

1. **Always specify `apiVersion`**: Required for version detection
2. **Include `kind` field**: Required for ODCS contracts
3. **Version consistency**: Ensure `apiVersion` matches contract structure

### Normalization

1. **Check normalization status**: Always check `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
2. **Review warnings**: Warnings indicate missing optional features
3. **Handle errors**: `NORMALIZATION_FAILED` indicates contract issues

### Testing

1. **Test with your version**: Ensure your ODCS version normalizes correctly
2. **Test backward compatibility**: Older versions should still work
3. **Test graceful degradation**: Verify missing features don't cause errors

---

## Version Support Matrix

| Feature | 3.0.2 | 3.0.1 | 3.0.0 | 3.0.0-preview | 2.2.2 |
|---------|-------|-------|-------|---------------|-------|
| Core Schema | ✅ | ✅ | ✅ | ✅ | ✅ |
| Info Section | ✅ | ✅ | ✅ | ✅ | ✅ |
| Quality Rules | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Lifecycle | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Marketplace | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Compliance | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Enhanced Marketplace (3.0.2+) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Enhanced Lifecycle (3.0.2+) | ✅ | ❌ | ❌ | ❌ | ❌ |

**Legend**:
- ✅ Fully supported
- ⚠️ Limited support or graceful degradation
- ❌ Not available (gracefully ignored)

---

## References

- **ODCS Specification**: https://bitol-io.github.io/open-data-contract-standard/
- **ODCS 3.0.2**: https://bitol-io.github.io/open-data-contract-standard/v3.0.2/
- **Normalization Guide**: See [DEVELOPER_GUIDE_NORMALIZATION.md](deprecated-doc/feature-docs/DEVELOPER_GUIDE_NORMALIZATION.md)
- **Backward Compatibility Tests**: See `hub/apps/contracts/tests/test_odcs_backward_compatibility.py`

---

## Support

For questions or issues with ODCS version support:

1. **Check this documentation**: Review version-specific features and graceful degradation
2. **Review test suite**: See backward compatibility tests for examples
3. **Check normalization status**: Review warnings and errors in normalization results
4. **Contact support**: Reach out to the development team for assistance

---

**Last Updated**: 2026-03-22
**Maintained By**: Data Interoperability Hub Team


---

# Contract Standards Version Compatibility

This document describes the contract specification versions supported by Meshant,
including normalizer classes, export support, and known breaking changes.

## ODCS (Open Data Contract Standard)

| Spec Version | Normalizer Class | Export | Validation Schema | Status |
|---|---|---|---|---|
| 2.2.2 | `ODCSNormalizerBase` (v2 path) | `ODCSGeneratorV2_2_2` | datacontract-cli | Supported (legacy) |
| 3.0.0 | `ODCSNormalizerV3_0_0` | `ODCSGeneratorV3_0_0` | datacontract-cli | Supported |
| 3.0.0-preview | `ODCSNormalizerV3_0_0` (fallback) | `ODCSGeneratorV3_0_0_Preview` | datacontract-cli | Supported (legacy) |
| 3.0.1 | `ODCSNormalizerV3_0_1` | `ODCSGeneratorV3_0_1` | datacontract-cli | Supported |
| 3.0.2 | `ODCSNormalizerV3_0_2` | `ODCSGeneratorV3_0_2` | datacontract-cli | Supported (default export) |
| 3.1.0 | `ODCSNormalizerV3_1_0` | `ODCSGeneratorV3_1_0` | datacontract-cli | Supported |

### ODCS v3.1.0 Breaking Changes

Meshant handles these automatically during normalization:

1. **`team` restructured** from `list[{name, email, role}]` to `{members: [{name, email, role, id, description}]}`.
   Both shapes detected and mapped to `HubContract.info.owners` + `HubContract.team`.

2. **`exclusiveMaximum` / `exclusiveMinimum` type change** in `logicalTypeOptions`:
   boolean (JSON Schema draft-07) to numeric (draft-2019-09).
   Wrapped as `{"value": N, "type": "numeric_bound"}` in HubContract.

3. **`slaDefaultElement` removed** (deprecated since v3.0.2).
   Emits a normalization warning if present; not mapped.

### ODCS v3.1.0 New Fields

| Field | HubContract Location | Description |
|---|---|---|
| `relationships[]` | `models[].relationships`, `schema.relationships` | Cross-field/cross-model relationships |
| `id` (on objects/properties) | `element_id` | Stable cross-link identifier |
| `dataGranularityDescription` | `data_granularity_description` | Already supported pre-v3.1.0 |
| `quality.library[]` | `quality.rules[]` (with library types) | Built-in metric types: rowCount, nullValues, etc. |
| `logicalType: timestamp/time` | `logicalType` on field | Extended from date-only |
| `logicalTypeOptions.timezone` | `logicalTypeOptions` | Timezone for timestamp/time types |
| Server types | `servers[].type` | HiveServer, ImpalaServer, ActianZenServer |

### Export Downgrade Paths

| From | To | Dropped Features | Warning Header |
|---|---|---|---|
| 3.1.0 | 3.0.x | relationships, element IDs, team object format | `X-Export-Downgrade-Warnings` |
| 3.1.0 | 2.2.2 | relationships, element IDs, team format, quality library | `X-Export-Downgrade-Warnings` |
| 3.0.x | 2.2.2 | Handled by existing generators | N/A |

**Upgrade paths (e.g., 2.2.2 to 3.1.0) are not supported** — data would be incomplete.

## ODPS (Open Data Product Standard)

### Pre-Bitol Lineage (Original ODPS)

| Spec Version | Normalizer Class | Export | Status |
|---|---|---|---|
| 1.x | `ODPSNormalizerBase` | `generate_odps_from_hubcontract` | Supported (legacy) |
| 2.x | `ODPSNormalizerBase` | `generate_odps_from_hubcontract` | Supported (legacy) |
| 3.x | `ODPSNormalizerBase` | `generate_odps_from_hubcontract` | Supported (legacy) |
| 4.0 | `ODPSNormalizerV4_0` | `generate_odps_from_hubcontract` | Supported |
| 4.1 | `ODPSNormalizerV4_1` | `generate_odps_from_hubcontract` | Supported |
| 4.2 | `ODPSNormalizerV4_2` | `generate_odps_from_hubcontract` | Supported (Phase 46) |

### Bitol LF Lineage (ODPS under Linux Foundation)

| Spec Version | Internal Version | Normalizer | Export | Status |
|---|---|---|---|---|
| bitol-0.9.0 | `ODPS_BITOL` | `ODPSBitolNormalizerV1_0_0` | `generate_odps_from_hubcontract` | Supported |
| bitol-1.0.0 | `ODPS_BITOL` | `ODPSBitolNormalizerV1_0_0` | `generate_odps_from_hubcontract` | Supported (Phase 26) |

### ODPS Lineage Split

The Open Data Product Standard split into two lineages in 2025:

- **Pre-Bitol** (v1.x through v4.2): Original specification maintained by the ODPS community.
  Discriminator: `apiVersion: vN.N.N` + `kind: DataProduct`.

- **Bitol LF** (bitol-0.9.0, bitol-1.0.0): Fork maintained by the Bitol project under the Linux Foundation.
  Discriminator: `apiVersion: v1.0.0` + `kind: DataProduct` + Bitol schema URL
  (`https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json`).

Meshant detects both lineages automatically via schema URL presence in the `$schema` field.
Internal spec type constants: `ODPS` (pre-Bitol) vs `ODPS_BITOL` (Bitol LF).

## Configuration

Supported versions are configured via environment variables:

```env
ODCS_VERSIONS_SUPPORTED=2.2.2,3.0.0,3.0.1,3.0.2,3.1.0
ODPS_VERSIONS_SUPPORTED=1.x,2.x,3.x,4.0,4.1,4.2,bitol-0.9.0,bitol-1.0.0
```

These defaults are set in `hub/settings.py` and can be overridden in
`.env.production` or `.env.dev`.

---

# Business Rules Framework Guide

**Version:** 1.0
**Last Updated:** 2025-01-XX
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Framework Features](#framework-features)
4. [Business Rules Classes](#business-rules-classes)
5. [REST API alignment](#rest-api-alignment)
6. [Getting Started](#getting-started)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Business Rules Framework provides a standardized, production-grade approach to validation and business logic enforcement across all services in the Data Interoperability Hub. It ensures consistency, observability, and maintainability through:

- **Standardized Validation Results**: Consistent `ValidationResult` structure across all rules
- **Rule Execution Context**: Tenant-aware, user-aware validation with resource tracking
- **Built-in Observability**: Caching, metrics, tracing, and structured logging
- **Rule Composition**: Combine multiple rules with dependency resolution
- **Registry System**: Decorator-based registration with auto-discovery

### Key Benefits

- ✅ **Consistency**: All business rules follow the same patterns and interfaces
- ✅ **Observability**: Built-in metrics, tracing, and logging for all rule executions
- ✅ **Performance**: Automatic caching of validation results
- ✅ **Maintainability**: Centralized framework reduces code duplication
- ✅ **Testability**: Standardized structure makes testing straightforward
- ✅ **Scalability**: Registry system enables rule orchestration and dependency management

---

## Architecture

### Framework Components

```
hub/apps/core/business_rules/
├── base.py          # Base class, ValidationResult, RuleExecutionContext
├── registry.py      # Rule registry, registration decorators, dependency resolution
└── __init__.py      # Public API exports
```

### Core Classes

#### `BusinessRules` (Abstract Base Class)

The foundation for all business rules implementations. Provides:

- Standardized initialization with tenant/user context
- Built-in caching, metrics, tracing, and logging
- Rule execution orchestration via `execute()` method
- Rule composition via `compose()` method

**Location**: `hub/apps/core/business_rules/base.py`

#### `ValidationResult` (Dataclass)

Standardized result structure for all validations:

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
```

**Features**:
- Boolean evaluation (`if result:`)
- Result combination (`result.combine(other_result)`)
- String representation for debugging

#### `RuleExecutionContext` (Dataclass)

Context for rule execution:

```python
@dataclass
class RuleExecutionContext:
    tenant_id: Optional[str]
    user_id: Optional[str]
    resource: Optional[Any]
    metadata: Dict[str, Any]
```

**Features**:
- Cache key generation
- Context serialization for logging
- Resource tracking

#### `BusinessRulesRegistry`

Central registry for all business rules:

- Decorator-based registration (`@register_rule`)
- Auto-discovery of rules
- Dependency resolution and execution ordering
- Rule orchestration

**Location**: `hub/apps/core/business_rules/registry.py`

---

## Framework Features

### 1. Caching

**Purpose**: Improve performance by caching validation results

**How It Works**:
- Cache keys are generated from rule name, context, and arguments
- Only valid results are cached (errors are not cached)
- Cache TTL is configurable per rule (default: 300 seconds)
- Uses Django's cache framework (Redis in production)

**Configuration**:

```python
# In settings.py
CACHE_TTL_BUSINESS_RULES = 300  # 5 minutes default

# Per-rule override
class MyBusinessRules(BusinessRules):
    def get_cache_ttl(self) -> int:
        return 600  # 10 minutes for this rule
```

**Usage**:

```python
# Enable caching (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_caching=True)

# Disable caching
rules = MyBusinessRules(tenant_id="tenant-1", enable_caching=False)

# Override per-execution
result = rules.execute(context=ctx, use_cache=False)
```

**Cache Key Format**:
```
business_rules:validation:{rule_name}:{context_hash}:{args_hash}
```

**Cache Invalidation**:
- Automatic expiration after TTL
- Manual invalidation via cache key patterns
- Only valid results cached (invalid results bypass cache)

### 2. Metrics

**Purpose**: Monitor rule execution performance and outcomes

**Metrics Collected**:

1. **`business_rules_executions_total`** (Counter)
   - Total number of rule executions
   - Labels: `rule_name`, `result` (valid/invalid/error)

2. **`business_rules_duration_seconds`** (Histogram)
   - Execution duration in seconds
   - Labels: `rule_name`, `result`

3. **`business_rules_results_total`** (Counter)
   - Validation results with error/warning counts
   - Labels: `rule_name`, `result`, `has_errors`, `has_warnings`

**Implementation**: OpenTelemetry metrics with Prometheus exporter

**Configuration**:

```python
# Enable metrics (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_metrics=True)

# Disable metrics
rules = MyBusinessRules(tenant_id="tenant-1", enable_metrics=False)
```

**Accessing Metrics**:
- Prometheus endpoint: `/metrics`
- Grafana dashboards (if configured)
- OpenTelemetry collector

**Example Metrics Output**:
```
business_rules_executions_total{rule_name="ODPSBusinessRules",result="valid"} 1250
business_rules_executions_total{rule_name="ODPSBusinessRules",result="invalid"} 45
business_rules_duration_seconds{rule_name="ODPSBusinessRules",result="valid"} 0.023
business_rules_results_total{rule_name="ODPSBusinessRules",result="valid",has_errors="false",has_warnings="false"} 1200
```

### 3. Tracing

**Purpose**: Distributed tracing for rule execution across services

**How It Works**:
- Creates OpenTelemetry spans for each rule execution
- Spans include rule name, tenant_id, user_id, and execution details
- Spans are linked to parent traces (if available)
- Error information is recorded in spans

**Span Attributes**:
- `business_rules.rule_name`: Name of the rule
- `business_rules.tenant_id`: Tenant ID (if available)
- `business_rules.user_id`: User ID (if available)
- `business_rules.is_valid`: Validation result
- `business_rules.error_count`: Number of errors
- `business_rules.warning_count`: Number of warnings
- `business_rules.duration_seconds`: Execution duration

**Configuration**:

```python
# Enable tracing (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_tracing=True)

# Disable tracing
rules = MyBusinessRules(tenant_id="tenant-1", enable_tracing=False)
```

**Viewing Traces**:
- Jaeger UI (if configured)
- OpenTelemetry collector
- Cloud observability platforms (if configured)

**Example Trace**:
```
business_rules.ODPSBusinessRules
├── tenant_id: "tenant-1"
├── user_id: "user-123"
├── is_valid: true
├── error_count: 0
├── warning_count: 1
└── duration_seconds: 0.023
```

### 4. Structured Logging

**Purpose**: Comprehensive logging for debugging and auditing

**Log Levels**:
- **INFO**: Successful validations
- **WARNING**: Invalid validations (with errors)
- **DEBUG**: Detailed execution information

**Log Fields**:
- `rule_name`: Name of the rule
- `tenant_id`: Tenant ID
- `user_id`: User ID
- `is_valid`: Validation result
- `error_count`: Number of errors
- `warning_count`: Number of warnings
- `duration_seconds`: Execution duration
- `cached`: Whether result was from cache
- `resource_type`: Type of resource being validated
- `resource_id`: ID of resource being validated
- `errors`: List of error messages (if any)
- `warnings`: List of warning messages (if any)

**Configuration**:

```python
# Enable logging (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_logging=True)

# Disable logging
rules = MyBusinessRules(tenant_id="tenant-1", enable_logging=False)
```

**Example Log Entry**:
```json
{
  "event": "Business rule executed",
  "rule_name": "ODPSBusinessRules",
  "tenant_id": "tenant-1",
  "user_id": "user-123",
  "is_valid": true,
  "error_count": 0,
  "warning_count": 1,
  "duration_seconds": 0.023,
  "cached": false,
  "resource_type": "Contract",
  "resource_id": "contract-456",
  "warnings": ["ODPS version 1.0.0 is deprecated, consider upgrading"]
}
```

---

## Business Rules Classes

The framework includes **23 business rules classes** across all services:

### Contract Business Rules

#### 1. `ODPSBusinessRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_validation`
**Tags**: `["odps", "contracts", "validation"]`

**Purpose**: Validates ODPS (Open Data Product Standard) documents

**Validation Capabilities**:
- ODPS document structure validation
- ODPS version compatibility validation
- ODPS-ODCS linking rules validation
- Comprehensive ODPS contract validation

**Key Methods**:
- `validate_odps_structure(odps_doc, strict=False)`
- `validate_odps_version(odps_doc, required_version=None)`
- `validate_odps_contract(contract, strict=False)`

#### 2. `ODPSLinkingRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_linking_validation`
**Tags**: `["odps", "linking", "validation"]`

**Purpose**: Validates ODPS-ODCS linking rules

**Validation Capabilities**:
- Link existence validation
- Circular reference detection
- Referential integrity validation

#### 3. `ODPSExportRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_export_validation`
**Tags**: `["odps", "export", "validation"]`

**Purpose**: Validates ODPS export operations

**Validation Capabilities**:
- Export format validation
- Data completeness validation
- Fidelity validation (round-trip consistency)

#### 4. `ODPSNormalizationRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_normalization_validation`
**Tags**: `["odps", "normalization", "validation"]`

**Purpose**: Validates contract normalization

**Validation Capabilities**:
- Normalization eligibility validation
- Normalization status validation
- Fidelity validation (data loss prevention)

#### 5. `ContractsBusinessRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `contracts_lifecycle_validation`
**Tags**: `["contracts", "lifecycle", "validation"]`

**Purpose**: Validates contract lifecycle operations

**Validation Capabilities**:
- Contract creation validation
- Contract update validation
- Contract deletion validation
- Version compatibility validation

### Data Mesh Business Rules

#### 6. `DataMeshBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `data_mesh_domain_validation`
**Tags**: `["mesh", "domain", "validation"]`

**Purpose**: Validates data mesh domain operations

**Validation Capabilities**:
- Domain structure validation
- Domain boundaries validation
- Ownership transfer validation
- Policy conflict detection
- Domain resource quota validation

**Key Methods**:
- `validate_domain_structure(domain)`
- `validate_boundaries(domain)`
- `validate_ownership_transfer(from_domain, to_domain, assets)`
- `validate_policy_conflicts(domain, policies)`

#### 7. `PolicyBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `policy_validation` (implicit)
**Tags**: `["mesh", "policy", "validation"]`

**Purpose**: Validates policy application and compliance

**Validation Capabilities**:
- Policy application validation
- Compliance checking
- Violation detection

**Key Methods**:
- `validate_policy_application(domain, policy)`
- `check_compliance(domain, policies)`
- `detect_violations(domain, asset=None)`

#### 8. `TopologyBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `topology_validation` (implicit)
**Tags**: `["mesh", "topology", "validation"]`

**Purpose**: Calculates topology and health metrics

**Validation Capabilities**:
- Relationship calculation between domains
- Health metrics calculation

**Key Methods**:
- `calculate_relationships(domains)`
- `calculate_health_metrics(domain)`

### Virtualization Business Rules

#### 10. `VirtualizationBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `virtualization_dataset_validation`
**Tags**: `["virtualization", "dataset", "validation"]`

**Purpose**: Validates virtual datasets

**Validation Capabilities**:
- Query syntax validation for different query types
- Schema alignment validation
- Source compatibility validation
- Cross-source compatibility validation

**Key Methods**:
- `validate_query_syntax(query, query_type)`
- `validate_schema_alignment(virtual_dataset, sources)`
- `validate_source_compatibility(virtual_dataset, source)`

#### 11. `QueryExecutionBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `query_execution_validation` (implicit)
**Tags**: `["virtualization", "query", "execution"]`

**Purpose**: Validates query execution decisions

**Validation Capabilities**:
- Query optimization strategies
- Execution mode selection (SYNC vs ASYNC)
- Timeout validation

**Key Methods**:
- `validate_execution_mode(query, context)`
- `validate_timeout(query, timeout)`

#### 12. `ResultBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `result_validation` (implicit)
**Tags**: `["virtualization", "result", "validation"]`

**Purpose**: Validates query result handling

**Validation Capabilities**:
- Result caching configuration validation
- Pagination parameter validation

**Key Methods**:
- `validate_result_caching(cache_enabled, cache_ttl, result_size)`
- `validate_pagination(page, page_size)`

### Orchestration Business Rules

#### 13. `OrchestrationBusinessRules`
**Location**: `hub/apps/orchestration/business_rules.py`
**Rule Name**: `orchestration_validation`
**Tags**: `["orchestration", "validation", "workflow", "step"]`

**Purpose**: Validates workflow orchestration operations

**Validation Capabilities**:
- Workflow instance validation
- Workflow step validation
- Tenant context consistency
- User permissions and access validation
- State management validation (persistence, recovery, consistency)

**Key Methods**:
- `validate_workflow_instance(workflow, tenant, user)`
- `validate_workflow_step(step, tenant, user)`
- `validate_tenant_context(workflow, step, tenant)`

### Service Business Rules

#### 14. `NotificationsBusinessRules`
**Location**: `hub/apps/notifications/business_rules.py`
**Rule Name**: `notifications_validation`
**Tags**: `["notifications", "validation"]`

**Purpose**: Validates notification operations

**Validation Capabilities**:
- Notification creation validation
- Delivery validation
- Template validation
- Recipients validation
- Tenant context validation
- User permissions validation

#### 15. `SearchBusinessRules`
**Location**: `hub/apps/search/business_rules.py`
**Rule Name**: `search_validation`
**Tags**: `["search", "validation", "query", "index"]`

**Purpose**: Validates search operations

**Validation Capabilities**:
- Search query validation
- Index validation
- Search operation validation

#### 16. `SemanticBusinessRules`
**Location**: `hub/apps/semantic/business_rules.py`
**Rule Name**: `semantic_validation`
**Tags**: `["semantic", "validation", "mapping", "sparql", "rdf"]`

**Purpose**: Validates semantic operations

**Validation Capabilities**:
- Semantic mapping validation
- SPARQL query validation
- Semantic resource validation
- Tenant context validation

#### 17. `WebhooksBusinessRules`
**Location**: `hub/apps/webhooks/business_rules.py`
**Rule Name**: `webhooks_validation`
**Tags**: `["webhooks", "validation", "subscription", "delivery"]`

**Purpose**: Validates webhook operations

**Validation Capabilities**:
- Webhook subscription validation
- Webhook delivery validation
- Tenant context validation

#### 18. `ScheduledIngestionBusinessRules`
**Location**: `hub/apps/scheduled_ingestion/business_rules.py`
**Rule Name**: `scheduled_ingestion_validation`
**Tags**: `["scheduled_ingestion", "validation", "ingestion"]`

**Purpose**: Validates scheduled ingestion operations

**Validation Capabilities**:
- Schedule validation
- Ingestion run validation
- Source validation
- Tenant context validation

#### 19. `FilesBusinessRules`
**Location**: `hub/apps/files/business_rules.py`
**Rule Name**: `files_validation`
**Tags**: `["files", "validation", "storage"]`

**Purpose**: Validates file operations

**Validation Capabilities**:
- File validation
- Tenant context validation
- File access permissions validation

#### 20. `JobsBusinessRules`
**Location**: `hub/apps/jobs/business_rules.py`
**Rule Name**: `jobs_validation`
**Tags**: `["jobs", "validation"]`

**Purpose**: Validates job operations

**Validation Capabilities**:
- Job creation validation
- Job execution validation
- Status transition validation
- Tenant context validation
- Resource relationships validation

#### 21. `ComplianceBusinessRules`
**Location**: `hub/apps/compliance/business_rules.py`
**Rule Name**: `compliance_validation`
**Tags**: `["compliance", "validation", "risk_assessment"]`

**Purpose**: Validates compliance operations

**Validation Capabilities**:
- Compliance run validation
- Risk assessment validation
- Tenant context validation
- Resource relationships validation

#### 22. `DQBusinessRules`
**Location**: `hub/apps/dq/business_rules.py`
**Rule Name**: `dq_validation`
**Tags**: `["dq", "data_quality", "validation"]`

**Purpose**: Validates data quality operations

**Validation Capabilities**:
- Data quality run validation
- Check configuration validation
- Tenant context validation
- Dataset relationships validation

#### 23. `GovernanceBusinessRules`
**Location**: `hub/apps/governance/business_rules.py`
**Rule Name**: `governance_validation`
**Tags**: `["governance", "validation"]`

**Purpose**: Validates governance operations

**Validation Capabilities**:
- Governance policy validation
- Access request validation
- Classification validation
- Access control validation

#### 24. `MarketplaceBusinessRules`
**Location**: `hub/apps/marketplace/business_rules.py`
**Rule Name**: `marketplace_validation`
**Tags**: `["marketplace", "validation"]`

**Purpose**: Validates marketplace operations

**Validation Capabilities**:
- Marketplace listing validation
- Order validation
- Entitlement validation
- Access control validation

#### 25. `DatasetsBusinessRules`
**Location**: `hub/apps/datasets/business_rules.py`
**Rule Name**: `datasets_validation`
**Tags**: `["datasets", "validation"]`

**Purpose**: Validates dataset operations

**Validation Capabilities**:
- Dataset structure validation
- Schema validation
- Tenant context validation
- Version management validation

#### 26. `AssetsBusinessRules`
**Location**: `hub/apps/assets/business_rules.py`
**Rule Name**: `assets_validation`
**Tags**: `["assets", "validation"]`

**Purpose**: Validates asset operations

**Validation Capabilities**:
- Asset lifecycle validation
- Asset structure validation
- Tenant context validation
- Access permissions validation

#### 27. `MarketplaceIntegrationBusinessRules`
**Location**: `hub/apps/integrations/business_rules.py`
**Rule Name**: `marketplace_integration_validation`
**Tags**: `["integrations", "marketplace", "validation"]`

**Purpose**: Validates marketplace connection, sync, and mapping operations

**Validation Capabilities**:
- Connection name and config validation
- Sync job validation
- Mapping validation
- Tenant context validation

#### 28. `SocialBusinessRules`
**Location**: `hub/apps/social/business_rules.py`
**Rule Name**: `social_rating_validation`
**Tags**: `["social", "rating", "validation"]`

**Purpose**: Validates social operations (e.g. ratings)

**Validation Capabilities**:
- Rating: asset ACTIVE and in tenant, user in tenant, rating 1–5
- Tenant context validation

---

## REST API alignment

All REST create/update/delete operations for the apps below go through a **service layer** that invokes the same business rules as workflows. Validation failures return **400** (or the appropriate HTTP error) with `error`, `code` (e.g. `BUSINESS_RULES_VALIDATION`), and `details`; no mutation occurs. This ensures a single source of truth for domain rules and consistent behaviour whether the caller uses REST or workflows.

### Per-app alignment table

| App | REST entry points | Business rule class | Rule methods / validation type | Layer |
|-----|-------------------|---------------------|--------------------------------|-------|
| **Assets** | `POST/PATCH/DELETE /api/v1/assets/` | `AssetsBusinessRules` | `validate(asset=..., validation_type=...)` | Asset views → service (create/update/delete) |
| **Contracts** | `POST/PATCH/DELETE /api/v1/contracts/` | `ContractsBusinessRules` | `validate(contract=..., validation_type=...)` | ContractViewSet → ContractService |
| **Datasets** | `POST/PATCH/DELETE /api/v1/datasets/` | `DatasetsBusinessRules` | `validate(dataset=..., validation_type=...)` | DatasetViewSet → DatasetService |
| **Marketplace** | `POST/PATCH/DELETE /api/v1/marketplace/listings/`, `orders/`, `entitlements/` | `MarketplaceBusinessRules` | Listing/order/entitlement validation | Marketplace views → MarketplaceService |
| **Files** | `POST/PATCH/DELETE /api/v1/files/` | `FilesBusinessRules` | `validate(file=..., validation_type=...)` | FileViewSet → FileService |
| **Governance** | `POST /api/v1/governance/access-requests/`, `.../{id}/approve/`, `.../{id}/reject/` | `GovernanceBusinessRules` | `validate(access_request=...)`, approval/rejection | Access_request_views → GovernanceService |
| **Compliance** | `POST /api/v1/compliance/runs/` | `ComplianceBusinessRules` | `validate(compliance_run=..., validation_type=compliance_run)` | ComplianceRunViewSet create → ComplianceService |
| **DQ** | `POST /api/v1/dq/runs/` | `DQBusinessRules` | `validate(dq_run=..., validation_type=dq_run)` | DQRunViewSet create → DQService |
| **Mesh** | `POST/PATCH/DELETE /api/v1/mesh/domains/` | `DataMeshBusinessRules` | `validate(domain=..., validation_type=structure)` | DomainViewSet → DataMeshService |
| **Virtualization** | `POST/PATCH /api/v1/virtualization/datasets/` | `VirtualizationBusinessRules` | `validate(virtual_dataset=..., validation_type=all)` | VirtualDatasetViewSet → VirtualizationService |
| **Scheduled ingestion** | `POST/PATCH/DELETE /api/v1/scheduled-ingestions/` | `ScheduledIngestionBusinessRules` | `validate(schedule=..., validation_type=schedule)` | ScheduledIngestionViewSet create → IngestionService |
| **Integrations** | `POST/PATCH/DELETE /api/v1/integrations/marketplace/connections/` | `MarketplaceIntegrationBusinessRules` | `validate(connection=..., validation_type=connection)` | MarketplaceConnectionViewSet → MarketplaceIntegrationService |
| **Social** | `POST /api/v1/ratings/` (and reviews/comments/communities as implemented) | `SocialBusinessRules` | `validate(asset=..., user=..., tenant=..., rating_value=..., validation_type=rating)` | RatingViewSet create → SocialService |

### Error response contract

When a business rule rejects a request, the API returns **400 Bad Request** with a JSON body:

- **`error`**: Human-readable message (e.g. from `ValidationError.message`).
- **`code`**: Machine-readable code (e.g. `BUSINESS_RULES_VALIDATION`, `VALIDATION_ERROR`).
- **`details`**: Optional dict with rule-specific context (e.g. `validation_type`, field-level details).

Views catch `ServiceValidationError` (or the service base `ValidationError`) and return this shape; they do not re-raise as DRF `ValidationError` without the `code` field.

### Tests

Integration tests that assert REST → business rules alignment (no mocks) live in:

- **`tests.integration.test_rest_business_rules_alignment`**

Run the Phase 18.7 alignment tests (see `openspec/changes/workflows1/tasks.md`):

```bash
./scripts/run_phase18_rest_business_rules_tests.sh --no-keepdb   # first run or fresh DB
./scripts/run_phase18_rest_business_rules_tests.sh               # reuse DB (--keepdb)
```

---

## Serializers and domain validation

**Serializers are responsible for input shape and format only.** Domain validation (e.g. “name cannot be empty”, “at least one resource required”, “asset must be ACTIVE”) stays in **business rules** invoked from the **service layer**; it must not be duplicated in serializers.

### Principle

| Responsibility | Where it lives | Examples |
|----------------|----------------|----------|
| **Input shape/format** | Serializers | Field types, `required`, `allow_blank`, max length, choice lists, JSON structure. |
| **Domain rules** | Business rules (called by services) | “Name cannot be empty”, “Asset must be ACTIVE for rating”, “At least one of asset_id/dataset_id/file_id required”, “Connection name unique per tenant”. |

### Why

- **Single source of truth**: Workflows and REST both call the same service → same business rules. No divergence between “serializer validation” and “workflow validation”.
- **Consistent errors**: Failures from business rules return 400 with `code` (e.g. `BUSINESS_RULES_VALIDATION`) and `details`; serializer-only validation typically does not set `code`.
- **Testability**: Integration tests can assert that invalid domain data is rejected by the service and returns the expected 400 body.

### Implementation note

For create/update payloads where “empty/whitespace name” or similar is a **domain** rule: serializers use `allow_blank=True` (or pass-through in `validate_*`) so that the value reaches the service; the service then calls the business rule, which rejects it and raises `ValidationError` with `code=BUSINESS_RULES_VALIDATION`. The view catches that and returns 400 with `error`, `code`, and `details`. Serializers do **not** raise `ValidationError` for those domain rules so that the response format and code remain consistent.

---

## Getting Started

### Creating a New Business Rules Class

1. **Import the base class**:

```python
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
```

2. **Create your business rules class**:

```python
@register_rule(
    rule_name="my_service_validation",
    description="Validates my service operations",
    tags=["my_service", "validation"],
    priority=10
)
class MyServiceBusinessRules(BusinessRules):
    """Business rules validator for my service operations."""

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "MyServiceBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            ValidationResult instance
        """
        # Extract resources from context or kwargs
        resource = kwargs.get('resource') or (context.resource if context else None)

        if not resource:
            return ValidationResult(
                is_valid=False,
                errors=["Resource is required"],
            )

        # Perform validation
        errors = []
        warnings = []
        details = {}

        # Your validation logic here
        if not resource.is_valid():
            errors.append("Resource is invalid")

        # Return result
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
```

3. **Use your business rules**:

```python
# Create instance
rules = MyServiceBusinessRules(
    tenant_id="tenant-1",
    user_id="user-123"
)

# Create context
context = rules.create_context(
    resource=my_resource,
    metadata={"operation": "create"}
)

# Execute validation
result = rules.execute(context=context)

# Check result
if result:
    print("Validation passed!")
else:
    print(f"Validation failed: {result.errors}")
```

### Using the Registry

```python
from hub.apps.core.business_rules.registry import get_registry

# Get registry
registry = get_registry()

# Get all rules
all_rules = registry.get_all_rules()

# Get rule by name
rule_metadata = registry.get_rule("my_service_validation")

# Get rules by tag
validation_rules = registry.get_rule_by_tag("validation")

# Execute multiple rules
results = registry.execute_rules(
    rule_names=["rule1", "rule2"],
    tenant_id="tenant-1",
    user_id="user-123",
    short_circuit=True  # Stop on first error
)
```

---

## Workflow Integration

### Overview

Business rules are seamlessly integrated with the Workflow Orchestration system to provide comprehensive validation at every workflow step. This integration ensures consistent validation, error handling, and observability across all workflow operations.

**Related Documentation**: [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md)

### Integration Points

Business rules are integrated at three key points in workflow execution:

1. **Pre-Step Validation**: Before executing a workflow step
2. **Post-Step Validation**: After executing a workflow step  
3. **Compensation Validation**: During workflow rollback

### OrchestrationBusinessRules

The `OrchestrationBusinessRules` class provides workflow-specific validation methods:

#### `validate_workflow_step_execution()`

Validates that a workflow step can execute in the current workflow state.

**Usage**:
```python
from hub.apps.orchestration.business_rules import OrchestrationBusinessRules

business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_step_execution(
    workflow=workflow_instance,
    step=workflow_step,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step cannot execute: {', '.join(result.errors)}")
```

**Validates**:
- Workflow status is RUNNING
- Step status allows execution (PENDING or RUNNING)
- Step index matches workflow current_step_index
- Workflow state is consistent
- Tenant context is valid
- User permissions are valid

#### `validate_step_input()`

Validates step input data structure and schema.

**Usage**:
```python
result = business_rules.validate_step_input(
    workflow=workflow_instance,
    step=workflow_step,
    step_input=task_input,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step input invalid: {', '.join(result.errors)}")
```

**Validates**:
- Input is a dictionary
- Input is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)
- Input size is reasonable (<10MB)

#### `validate_step_output()`

Validates step output data structure and schema.

**Usage**:
```python
result = business_rules.validate_step_output(
    workflow=workflow_instance,
    step=workflow_step,
    step_output=step_result,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step output invalid: {', '.join(result.errors)}")
```

**Validates**:
- Output is a dictionary
- Output is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)
- Output size is reasonable (<10MB)

#### `validate_workflow_state()`

Validates workflow state consistency.

**Usage**:
```python
result = business_rules.validate_workflow_state(
    workflow=workflow_instance,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Workflow state invalid: {', '.join(result.errors)}")
```

**Validates**:
- Workflow state_data is consistent
- Step indices match workflow current_step_index
- Completed steps are in correct order
- State transitions are valid
- State data is JSON serializable

### Workflow Integration Patterns

#### Pattern 1: Using OrchestrationBusinessRules in Workflow Engine

The `WorkflowEngine` automatically uses `OrchestrationBusinessRules` for validation:

```python
# In WorkflowEngine._execute_task_step()
business_rules = OrchestrationBusinessRules(
    tenant_id=str(tenant.id) if tenant else None,
    user_id=str(user.id) if user else None
)

# Pre-step validation
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)

# Execute step
result = task_func(task_input, instance, step)

# Post-step validation
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
```

#### Pattern 2: Using Service-Specific Business Rules in Task Functions

Task functions can use service-specific business rules for domain validation:

```python
def create_contract_task(
    input_data: Dict[str, Any],
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Create contract with business rules validation"""
    
    from hub.apps.contracts.business_rules import ContractsBusinessRules
    
    # Get tenant and user context
    tenant = instance.tenant
    user = instance.created_by
    
    # Create service-specific business rules
    contract_rules = ContractsBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate contract creation
    contract_data = input_data.get("contract_data")
    validation_result = contract_rules.validate_contract_creation(
        contract_data=contract_data,
        tenant=tenant,
        user=user
    )
    
    if not validation_result.is_valid:
        raise ValueError(
            f"Contract validation failed: {', '.join(validation_result.errors)}"
        )
    
    # Log warnings if any
    if validation_result.warnings:
        logger.warning(
            f"Contract validation warnings: {', '.join(validation_result.warnings)}"
        )
    
    # Create contract
    contract = create_contract(contract_data)
    
    return {
        "contract_id": str(contract.id),
        "contract_status": contract.status
    }
```

#### Pattern 3: Compensation Validation

Compensation validates using business rules but does not block rollback:

```python
def _compensate_step(
    self,
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Compensate a workflow step with business rules validation"""
    
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate compensation step (warnings don't block)
    compensation_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )
    
    if compensation_result.warnings:
        logger.warning(
            f"Compensation validation warnings: {', '.join(compensation_result.warnings)}"
        )
    
    # Execute compensation logic
    compensation_result = self._execute_compensation_task(instance, step, compensation_def)
    
    return {
        "status": "compensated",
        "result": compensation_result,
        "validation": {
            "is_valid": compensation_result.is_valid,
            "warnings": compensation_result.warnings
        }
    }
```

### Validation Patterns

#### Pattern 1: Pre-Step Validation

Always validate workflow state and step input before execution:

```python
# Validate workflow state
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
if not workflow_state_result.is_valid:
    raise WorkflowExecutionError(
        f"Workflow state invalid: {', '.join(workflow_state_result.errors)}"
    )

# Validate step input
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
if not step_input_result.is_valid:
    raise WorkflowExecutionError(
        f"Step input invalid: {', '.join(step_input_result.errors)}"
    )
```

#### Pattern 2: Post-Step Validation

Always validate step output and workflow state after execution:

```python
# Execute step
result = task_func(task_input, instance, step)

# Validate step output
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
if not step_output_result.is_valid:
    raise WorkflowExecutionError(
        f"Step output invalid: {', '.join(step_output_result.errors)}"
    )

# Validate workflow state
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
if not post_workflow_state_result.is_valid:
    raise WorkflowExecutionError(
        f"Workflow state invalid: {', '.join(post_workflow_state_result.errors)}"
    )
```

#### Pattern 3: Service-Specific Validation in Task Functions

Use service-specific business rules for domain validation:

```python
def my_task_function(input_data, instance, step):
    from hub.apps.my_service.business_rules import MyServiceBusinessRules
    
    my_rules = MyServiceBusinessRules(
        tenant_id=str(instance.tenant.id),
        user_id=str(instance.created_by.id)
    )
    
    # Validate domain-specific logic
    validation_result = my_rules.validate_my_operation(
        resource=input_data.get("resource"),
        tenant=instance.tenant,
        user=instance.created_by
    )
    
    if not validation_result.is_valid:
        raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
    
    # Perform operation
    return {"result": "success"}
```

### Best Practices

#### 1. Always Use Business Rules for Validation

**Do**:
```python
# Use business rules for validation
business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_state(instance, tenant, user)
if not result.is_valid:
    raise WorkflowExecutionError(...)
```

**Don't**:
```python
# Don't skip validation or duplicate validation logic
if instance.status != WorkflowStatus.RUNNING:
    raise WorkflowExecutionError("Invalid status")
```

#### 2. Use Service-Specific Business Rules in Task Functions

**Do**:
```python
# Use service-specific business rules for domain validation
from hub.apps.contracts.business_rules import ContractsBusinessRules

contract_rules = ContractsBusinessRules(tenant_id=tenant_id, user_id=user_id)
validation_result = contract_rules.validate_contract_creation(contract_data)
if not validation_result.is_valid:
    raise ValueError(f"Contract validation failed: {', '.join(validation_result.errors)}")
```

**Don't**:
```python
# Don't duplicate validation logic in task functions
if not contract_data.get("name"):
    raise ValueError("Contract name is required")
```

#### 3. Handle Validation Warnings Appropriately

**Do**:
```python
# Log warnings but don't block execution
if validation_result.warnings:
    logger.warning(f"Validation warnings: {', '.join(validation_result.warnings)}")
```

**Don't**:
```python
# Don't treat warnings as errors
if validation_result.warnings:
    raise WorkflowExecutionError("Validation warnings found")
```

#### 4. Include Validation Context in Error Messages

**Do**:
```python
# Use _format_validation_error for consistent error messages
error_message = self._format_validation_error(
    "workflow state validation",
    validation_result,
    instance,
    step
)
raise WorkflowExecutionError(error_message)
```

**Don't**:
```python
# Don't create generic error messages
raise WorkflowExecutionError("Validation failed")
```

### Observability

Workflow validation with business rules provides comprehensive observability:

- **Metrics**: Validation success/failure rates, duration, cache hit rates
- **Events**: Validation results included in workflow events
- **Logs**: Structured logging with validation context
- **Traces**: Validation spans in distributed traces

See [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md#observability) for details.

---

## Advanced Usage

### Rule Composition

Combine multiple rules into a single validation:

```python
def validate_tenant(context: RuleExecutionContext) -> ValidationResult:
    """Validate tenant."""
    # Your validation logic
    return ValidationResult(is_valid=True)

def validate_user(context: RuleExecutionContext) -> ValidationResult:
    """Validate user."""
    # Your validation logic
    return ValidationResult(is_valid=True)

# Compose rules
rules = MyServiceBusinessRules()
context = rules.create_context()

result = rules.compose(
    validate_tenant,
    validate_user,
    context=context,
    short_circuit=True  # Stop on first error
)
```

### Custom Cache TTL

```python
class MyBusinessRules(BusinessRules):
    def get_cache_ttl(self) -> int:
        return 600  # 10 minutes
```

### Dependency Resolution

Rules can declare dependencies:

```python
@register_rule(
    rule_name="dependent_rule",
    depends_on=["prerequisite_rule"],
    priority=20
)
class DependentRule(BusinessRules):
    # ...
```

The registry will automatically resolve execution order:

```python
registry = get_registry()
execution_order = registry.resolve_execution_order(
    rule_names=["dependent_rule", "prerequisite_rule"]
)
# Returns: ["prerequisite_rule", "dependent_rule"]
```

### Disabling Framework Features

```python
# Disable all features
rules = MyBusinessRules(
    tenant_id="tenant-1",
    enable_caching=False,
    enable_metrics=False,
    enable_tracing=False,
    enable_logging=False
)

# Disable specific feature per execution
result = rules.execute(context=ctx, use_cache=False)
```

---

## Best Practices

### 1. Always Use the Framework

✅ **DO**: Extend `BusinessRules` base class
❌ **DON'T**: Create custom validation classes outside the framework

### 2. Use Rule Execution Context

✅ **DO**: Use `RuleExecutionContext` for tenant/user context
❌ **DON'T**: Pass tenant_id/user_id as separate parameters

### 3. Return Comprehensive Results

✅ **DO**: Include errors, warnings, and details in `ValidationResult`
❌ **DON'T**: Return only boolean values

### 4. Register Rules

✅ **DO**: Use `@register_rule` decorator
❌ **DON'T**: Create unregistered rules

### 5. Use Descriptive Rule Names

✅ **DO**: Use descriptive, unique rule names
❌ **DON'T**: Use generic names like "validation"

### 6. Add Tags

✅ **DO**: Add relevant tags for categorization
❌ **DON'T**: Leave tags empty

### 7. Handle Errors Gracefully

✅ **DO**: Catch exceptions and return ValidationResult with error
❌ **DON'T**: Let exceptions propagate unhandled

### 8. Use Caching Appropriately

✅ **DO**: Cache expensive validations
❌ **DON'T**: Cache validations that change frequently

### 9. Provide Context in Errors

✅ **DO**: Include context in error messages
❌ **DON'T**: Return generic error messages

### 10. Test Your Rules

✅ **DO**: Write comprehensive tests for all validation paths
❌ **DON'T**: Skip testing edge cases

---

## Troubleshooting

### Common Issues

#### 1. Rule Not Found

**Problem**: `ValueError: Rule 'my_rule' not found`

**Solution**: Ensure rule is registered with `@register_rule` decorator

#### 2. Circular Dependencies

**Problem**: `ValueError: Circular dependency detected`

**Solution**: Review rule dependencies and remove circular references

#### 3. Cache Not Working

**Problem**: Results not being cached

**Solution**:
- Check `enable_caching=True` in initialization
- Verify cache backend is configured (Redis in production)
- Check cache TTL settings

#### 4. Metrics Not Appearing

**Problem**: Metrics not showing in Prometheus

**Solution**:
- Verify `enable_metrics=True` in initialization
- Check OpenTelemetry configuration
- Verify Prometheus exporter is configured

#### 5. Traces Not Showing

**Problem**: Traces not appearing in Jaeger

**Solution**:
- Verify `enable_tracing=True` in initialization
- Check OpenTelemetry configuration
- Verify trace exporter is configured

### Debugging Tips

1. **Enable Debug Logging**:
```python
import logging
logging.getLogger('hub.apps.core.business_rules').setLevel(logging.DEBUG)
```

2. **Check Registry State**:
```python
registry = get_registry()
all_rules = registry.get_all_rules()
print(all_rules)
```

3. **Inspect Validation Results**:
```python
result = rules.execute(context=ctx)
print(result)  # String representation
print(result.details)  # Detailed information
```

4. **Verify Cache Keys**:
```python
cache_key = rules._get_cache_key("MyRule", context)
print(cache_key)
```

---

## Additional Resources

- **Framework Review**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`
- **Base Class**: `hub/apps/core/business_rules/base.py`
- **Registry**: `hub/apps/core/business_rules/registry.py`
- **Tests**: `hub/apps/core/business_rules/tests/`

---

**Document Status**: ✅ Complete
**Last Updated**: 2026-03-22 (REST API alignment and Serializers sections added for Phase 18.8)
**Maintained By**: Data Interoperability Hub Team


---

# Business Rules Framework Review

**Date:** 2025-12-30
**Task:** 9.7.2.1.1 - Review existing business rules framework
**Status:** ✅ Complete
**Last Updated:** 2025-01-XX
**Framework Status:** ✅ Fully Implemented and Documented

## Framework Completion Status

The Business Rules Framework has been fully implemented and is now production-ready:

- ✅ **Base Class**: `hub/apps/core/business_rules/base.py` - Complete with caching, metrics, tracing, and logging
- ✅ **Registry**: `hub/apps/core/business_rules/registry.py` - Complete with decorator-based registration and dependency resolution
- ✅ **Business Rules Classes**: 23 classes implemented across all services
- ✅ **Framework Features**: Caching, metrics (Prometheus/OpenTelemetry), tracing (OpenTelemetry), structured logging
- ✅ **Documentation**: Comprehensive guide available at `docs/BUSINESS_RULES_FRAMEWORK_GUIDE.md`

For detailed usage instructions and examples, see: **[Business Rules Framework Guide](BUSINESS_RULES_FRAMEWORK_GUIDE.md)**

## Executive Summary

This document provides a comprehensive review of the existing business rules framework implementation across the Data Interoperability Hub codebase. The review identifies framework gaps, documents requirements, and provides recommendations for framework completion.

## Current State Analysis

### Existing Implementations

The codebase contains multiple business rules implementations across different modules:

1. **ODPSBusinessRules** (`hub/apps/contracts/business_rules.py`)
   - ODPS document structure validation
   - ODPS version validation
   - ODPS-ODCS linking validation
   - ODPS contract validation

2. **ODPSLinkingRules** (`hub/apps/contracts/business_rules.py`)
   - ODPS → ODCS link validation
   - Circular reference detection
   - Referential integrity validation

3. **ODPSExportRules** (`hub/apps/contracts/business_rules.py`)
   - Export format validation
   - Data completeness validation
   - Fidelity validation (round-trip consistency)

4. **DataMeshBusinessRules** (`hub/apps/mesh/business_rules.py`)
   - Domain structure validation
   - Ownership transfer validation
   - Boundaries validation
   - Policy conflict detection

5. **PolicyBusinessRules** (`hub/apps/mesh/business_rules.py`)
   - Policy application validation
   - Compliance checking
   - Violation detection

6. **TopologyBusinessRules** (`hub/apps/mesh/business_rules.py`)
   - Relationship calculation
   - Health metrics calculation

7. **TransformationBusinessRules** (`hub/apps/transformation/business_rules.py`)
   - Pipeline structure validation
   - Node compatibility validation
   - Schema alignment validation
   - Asset compatibility validation
   - Cross-tenant operation validation
   - Pipeline execution permission validation

8. **VirtualizationBusinessRules** (`hub/apps/virtualization/business_rules.py`)
   - Query syntax validation
   - Schema alignment validation
   - Source compatibility validation
   - Cross-source compatibility validation

9. **QueryExecutionBusinessRules** (`hub/apps/virtualization/business_rules.py`)
   - Query optimization
   - Execution mode selection (SYNC vs ASYNC)
   - Timeout validation

10. **ResultBusinessRules** (`hub/apps/virtualization/business_rules.py`)
    - Result caching validation
    - Pagination parameter validation

### Common Patterns Identified

All implementations share common patterns:

1. **ValidationResult Pattern**: All use a `ValidationResult` dataclass with:
   - `is_valid: bool`
   - `errors: List[str]`
   - `warnings: List[str]`
   - `details: Dict[str, Any]`

2. **Initialization Pattern**: All accept optional `tenant_id` and `user_id`:
   ```python
   def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None)
   ```

3. **Validation Method Pattern**: All validation methods:
   - Return `ValidationResult`
   - Accept `raise_on_error: bool = False` parameter
   - Collect errors and warnings in lists
   - Provide detailed context in `details` dictionary
   - Raise exceptions when `raise_on_error=True` and validation fails

4. **Error Handling Pattern**: Consistent use of:
   - `ValidationError` from `hub.apps.core.services.base`
   - Comprehensive error messages with context
   - Warning messages for non-critical issues

## Framework Gaps Identified

### 1. Missing Base Class

**Issue**: Documentation references `hub.apps.core.business_rules.base.BusinessRules`, but this base class does not exist.

**Impact**:
- Code duplication (ValidationResult defined in each module)
- No common interface for business rules
- Inconsistent patterns across implementations
- Difficult to extend or maintain

**Evidence**:
- `docs/BUSINESS_LOGIC_INTEGRATION.md` line 291: `from hub.apps.core.business_rules.base import BusinessRules`
- `docs/ARCHITECTURE.md` line 318: References centralized framework
- No `hub/apps/core/business_rules/` directory exists

### 2. ValidationResult Duplication

**Issue**: `ValidationResult` dataclass is duplicated in every business rules module.

**Impact**:
- Code duplication (DRY violation)
- Inconsistent implementations (some have `details`, some don't)
- Maintenance burden (changes must be applied to multiple files)

**Evidence**:
- `hub/apps/contracts/business_rules.py` lines 32-42: ValidationResult without `details`
- `hub/apps/mesh/business_rules.py` lines 30-51: ValidationResult with `details`
- `hub/apps/transformation/business_rules.py` lines 45-54: ValidationResult with `details`
- `hub/apps/virtualization/business_rules.py` lines 30-51: ValidationResult with `details`

### 3. No Common Utilities

**Issue**: No shared utilities for common validation patterns.

**Impact**:
- Repeated validation logic across modules
- Inconsistent validation behavior
- Difficult to maintain validation standards

**Examples of Duplicated Logic**:
- Tenant ID validation
- User permission checking
- Cross-tenant access validation
- Schema structure validation

### 4. Inconsistent Error Handling

**Issue**: Error handling patterns vary across implementations.

**Impact**:
- Inconsistent error messages
- Different exception types used
- Unpredictable error behavior

**Evidence**:
- Some use `ValidationError` from `hub.apps.core.services.base`
- Some use `DjangoValidationError`
- Some use custom exceptions
- Error message formats vary

### 5. No Framework Documentation

**Issue**: No comprehensive documentation for:
- How to create new business rules classes
- Framework conventions and patterns
- Best practices for validation
- Testing guidelines

**Impact**:
- Difficult for new developers to understand framework
- Inconsistent implementations
- Knowledge gaps

### 6. No Type Hints/Protocols

**Issue**: No common interface/protocol for business rules classes.

**Impact**:
- Cannot enforce consistent API
- Difficult to create generic business rules utilities
- Type checking limitations

### 7. No Framework-Level Testing

**Issue**: No tests for framework completeness or consistency.

**Impact**:
- Cannot verify framework compliance
- Cannot detect breaking changes
- Difficult to maintain quality standards

## Framework Requirements

### 1. Base Class Requirements

**Requirement**: Create `hub/apps/core/business_rules/base.py` with:

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Standard validation result structure."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def __init__(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}

    def __bool__(self):
        return self.is_valid

class BusinessRules(ABC):
    """Base class for all business rules implementations."""

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @abstractmethod
    def validate(self, *args, **kwargs) -> ValidationResult:
        """Main validation method (to be implemented by subclasses)."""
        pass

    def _create_result(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Helper method to create ValidationResult."""
        return ValidationResult(
            is_valid=is_valid,
            errors=errors or [],
            warnings=warnings or [],
            details=details or {}
        )

    def _validate_tenant_context(
        self,
        entity_tenant_id: Optional[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Validate tenant context consistency."""
        errors = []
        if self.tenant_id and entity_tenant_id:
            if str(entity_tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: entity tenant ({entity_tenant_id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )
        return errors
```

### 2. Common Utilities Requirements

**Requirement**: Create `hub/apps/core/business_rules/utils.py` with:

- Tenant validation utilities
- User permission checking utilities
- Cross-tenant access validation utilities
- Schema validation utilities
- Error message formatting utilities
- Logging utilities

### 3. Error Handling Requirements

**Requirement**: Standardize error handling:

- Use `ValidationError` from `hub.apps.core.services.base` consistently
- Standardize error message formats
- Provide context in error details
- Support `raise_on_error` parameter consistently

### 4. Documentation Requirements

**Requirement**: Create comprehensive documentation:

- Framework overview and architecture
- How to create new business rules classes
- Framework conventions and patterns
- Best practices for validation
- Testing guidelines
- Migration guide for existing implementations

### 5. Testing Requirements

**Requirement**: Create framework-level tests:

- Test base class functionality
- Test ValidationResult behavior
- Test common utilities
- Test framework compliance (all implementations follow patterns)
- Test error handling consistency

### 6. Type Safety Requirements

**Requirement**: Add type hints and protocols:

- Type hints for all public methods
- Protocol for business rules interface
- Type checking support

## Recommendations

### Immediate Actions

1. **Create Base Class**: Implement `hub/apps/core/business_rules/base.py` with `BusinessRules` base class and `ValidationResult` dataclass.

2. **Create Common Utilities**: Implement `hub/apps/core/business_rules/utils.py` with shared validation utilities.

3. **Update Documentation**: Create comprehensive framework documentation.

4. **Create Framework Tests**: Implement tests for framework completeness and compliance.

### Migration Strategy

1. **Phase 1**: Create base class and utilities (non-breaking)
2. **Phase 2**: Migrate existing implementations to use base class (gradual)
3. **Phase 3**: Update all implementations to use common utilities
4. **Phase 4**: Add framework-level tests
5. **Phase 5**: Update documentation and create developer guide

### Long-Term Improvements

1. **Framework Registry**: Create registry for business rules classes
2. **Validation Chains**: Support chaining multiple validations
3. **Validation Caching**: Cache validation results where appropriate
4. **Validation Metrics**: Track validation performance and outcomes
5. **Validation Rules Engine**: Support rule-based validation configuration

## Conclusion

The business rules framework has a solid foundation with consistent patterns across implementations. However, the lack of a base class and common utilities creates code duplication and maintenance challenges. Implementing the recommended base class and utilities will:

- Reduce code duplication
- Improve consistency
- Simplify maintenance
- Enable framework-level features
- Improve developer experience

The framework is ready for consolidation and enhancement.


---

# Semantic Operations Runbook

## Fuseki TDB2 Backup & Restore

### Daily Automated Backup
- **Schedule**: 02:00 UTC daily via Kubernetes CronJob (`backup-fuseki-tdb2`)
- **Storage**: `s3://{BACKUP_S3_BUCKET}/fuseki/{date}/backup.nq.gz` (KMS encrypted, STANDARD_IA)
- **Retention**: 30 days

### Manual Backup
```bash
# Trigger backup via Fuseki HTTP API
curl -X POST http://fuseki:3030/$/backup/hub \
  -u admin:${FUSEKI_ADMIN_PASSWORD} \
  -o /tmp/fuseki-backup.nq.gz
```

### Restore from Backup
```bash
# 1. Stop semantic-service to prevent writes
kubectl scale deployment hub-semantic --replicas=0

# 2. Clear existing dataset
curl -X POST http://fuseki:3030/hub/update \
  -u admin:${FUSEKI_ADMIN_PASSWORD} \
  -d "update=DROP ALL"

# 3. Upload backup
curl -X POST http://fuseki:3030/hub/data \
  -u admin:${FUSEKI_ADMIN_PASSWORD} \
  -H "Content-Type: application/n-quads" \
  -T /tmp/fuseki-backup.nq.gz

# 4. Restart semantic-service
kubectl scale deployment hub-semantic --replicas=2
```

## Named Graph Migration

### migrate_triples_to_named_graphs
When migrating from default graph to per-tenant named graphs:

```bash
python hub/manage.py migrate_triples_to_named_graphs --dry-run
python hub/manage.py migrate_triples_to_named_graphs --batch-size=500
```

## SHACL Shape Updates

1. Edit shapes in `services/semantic-service/shapes/*.ttl`
2. Run `python services/semantic-service/generate_ontology.py` if ontology changed
3. Verify: `python services/semantic-service/generate_ontology.py --check`
4. Deploy — semantic-service reloads shapes at startup
5. Existing triples are NOT retroactively validated (validation is at ingestion time)

## Ontology Version Bumps

1. Update `services/semantic-service/ontology.py` — increment `owl:versionInfo`
2. Run `python services/semantic-service/generate_ontology.py`
3. Commit both `ontology.py` and `ontology.ttl`
4. CI `ontology-sync` job validates they match before deploy

## Incident Response

### Fuseki Down
- **Alert**: `SemanticFusekiDown` (CRITICAL, 15m)
- **Impact**: Semantic queries fail; ingestion queued
- **Actions**:
  1. Check pod status: `kubectl get pods -l app.kubernetes.io/component=fuseki`
  2. Check logs: `kubectl logs -l app.kubernetes.io/component=fuseki --tail=100`
  3. Common causes: OOM (check JVM heap), disk full (check PVC), config error
  4. Restart: `kubectl rollout restart statefulset hub-fuseki`

### Tenant Isolation Breach
- **Alert**: `SemanticTenantIsolationViolation` (CRITICAL P1, immediate)
- **Impact**: Data leaked across tenant boundaries
- **Actions**:
  1. **Immediately** disable semantic-service: `kubectl scale deployment hub-semantic --replicas=0`
  2. Identify affected tenants from `tenant_isolation_violations_total` metric labels
  3. Audit named graphs: check `tdb2:unionDefaultGraph` is `false` in config
  4. Review recent code changes to `fuseki_client.py` query scoping
  5. Restore from pre-incident backup if data contamination confirmed
  6. Post-incident: add regression test, update SHACL shapes

---

## Phase 117+ Business Rules (Added)

### Compensation Patterns (ML-3)

The compensation handler registry maps script names to handler functions for Saga-pattern workflow rollback:

```python
class WorkflowCompensation:
    def __init__(self):
        self._compensation_handlers: Dict[str, Callable] = {}

    def register_compensation_handler(self, script_name, handler):
        self._compensation_handlers[script_name] = handler

    def _execute_compensation_script(self, instance, step, compensation_def):
        handler = self._compensation_handlers.get(script)
        if handler:
            return handler(instance, step, compensation_def)
        return {"status": "handler_not_found"}
```

Registered handlers execute with full context; unregistered scripts return `handler_not_found` status.

### Webhook Delivery Rules

| Rule | Value |
|------|-------|
| Retry intervals | 1min, 5min, 30min, 2hr, 24hr |
| Max retries | 5 |
| SSRF prevention | Block private IPs (10.x, 172.16-31.x, 192.168.x, 127.x, ::1) |
| Payload signing | HMAC-SHA256 with tenant-specific secret |
| Delivery timeout | 10 seconds per attempt |
| Async delivery | Via RQ background job (worker-light pool) |

### Billing Rules

| Rule | Enforcement |
|------|-------------|
| Subscription create | Validate plan exists, is active, tenant not already subscribed |
| Subscription upgrade | Always allowed (new plan tier >= current) |
| Subscription downgrade (B2) | `DOWNGRADE_LIMIT_EXCEEDED` if current usage exceeds new plan limits |
| Subscription cancel | Allowed; access continues until `current_period_end` |
| Plan transitions | Only `VALID_TRANSITIONS` allowed (ACTIVE→PAST_DUE→CANCELLED, TRIALING→ACTIVE/CANCELLED) |
| Fail-closed (B1) | SubscriptionStatusMiddleware returns 503 on DB outage for mutations |
| Circuit breaker (B6) | StripeCircuitBreaker: 5 failures in 60s → open 30s |

### Scheduled Ingestion Rules

| Rule | Description |
|------|-------------|
| Incremental state | `last_successful_cursor` tracks position for incremental syncs |
| DLQ routing | Failed records sent to dead letter queue with error context |
| Retry policy | 3 retries with exponential backoff per record |
| Cost tracking | Each run records usage via `BillingService.record_usage("ingestion_runs", 1)` |

---

## Phase 117+ Governance & Security Rules (Added)

### G1: ABAC Cache Invalidation

- **Trigger**: `AccessPolicy` post_save/post_delete Django signal
- **Action**: Increment `abac_cache_version_{tenant_id}` in cache
- **Effect**: All cached policy evaluations for tenant become stale (version mismatch)
- **Cache key format**: `abac_policies_{tenant_id}_{resource_type}_{resource_id}_v{version}`

### G2: Field-Level Masking Audit

- **Trigger**: `ABACEngine.evaluate_access()` returns `masking_required=True`
- **Action**: `create_audit_event(action="FIELD_MASKING_APPLIED")`
- **Details logged**: masked_fields, policy_id, masking_strategies, user_id
- **Non-blocking**: Wrapped in try/except — audit failure does not block access evaluation

### G5: Classification Propagation

- **Trigger**: `link_model_to_dataset()` creates model-dataset link
- **Action**: `propagate_classification(source_type="DATASET", target_type="ASSET")`
- **Logic**: Find highest-priority classification on source → update_or_create on target with provenance
- **Priority order**: PUBLIC(1) < INTERNAL(2) < CONFIDENTIAL(3) < RESTRICTED(4) < PII(5) < PHI/PCI(6)

### M1: Marketplace Order Lifecycle

```
Order.REQUESTED → APPROVED (manual) → FULFILLED (entitlement created)
Order.REQUESTED → APPROVED (auto, for FREE_AUTO_APPROVE) → FULFILLED
Order.REQUESTED → REJECTED
Order.REQUESTED → CANCELLED (by requester)
```

- Entitlement grants cross-tenant READ access to listing's asset
- Entitlement has optional `expires_at` for time-limited access

### M3: Cross-Tenant Entitlement Enforcement

- **Check**: `require_entitlement(consumer_tenant_id, asset_id)` before cross-tenant resource access
- **Scope**: Dataset download, file download, virtual dataset query, scheduled ingestion cross-tenant source
- **Enforcement**: 403 Forbidden if no active entitlement exists

### ML-7: Cross-Tenant Training Guard

- **Rule**: `model.tenant_id == dataset.tenant_id` validated in `ODHIntegrationBusinessRules`
- **Effect**: Training on another tenant's dataset requires explicit entitlement
- **Enforcement**: `ValidationError("MODEL_DATASET_LINKING_INVALID")` if tenant mismatch

### Integration-5: Workflow Plan Limit Audit

Orchestration workflows enforce plan limits via business rules validation in their first step:

| Workflow | Limit Key Checked |
|----------|-------------------|
| Asset creation | `max_assets` |
| Dataset creation | `max_datasets` |
| Version creation | `max_datasets` (versions are datasets) |
| Compliance reporting | `max_compliance_runs_per_month` |
| Data quality | `max_dq_runs_per_month` |
| Virtualization | `max_virtual_datasets` |
| Model inference | `max_ml_inference_requests_per_month` |
| ML training | `max_ml_training_jobs_per_month` |
| Transformation | `max_transformation_pipelines` |
