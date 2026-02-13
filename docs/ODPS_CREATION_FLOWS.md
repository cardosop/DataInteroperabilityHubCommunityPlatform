# ODPS Creation Flows Guide

Complete engineering-grade guide for ODPS (Open Data Product Standard) creation flows in the Data Interoperability Hub.

**Last Updated**: 2026-01-26
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
**Last Updated**: 2026-01-26
**Maintained By**: Data Interoperability Hub Team
