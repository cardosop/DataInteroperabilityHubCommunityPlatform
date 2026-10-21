# ODPS (Open Data Product Standard) Usage Guide

This guide provides comprehensive documentation for using ODPS functionality in the DataHub Interoperability Python SDK.

## Table of Contents

1. [Introduction](#introduction)
2. [ODPS Concepts](#odps-concepts)
3. [Getting Started](#getting-started)
4. [ODPS Contract Creation](#odps-contract-creation)
5. [ODPS Export and Download](#odps-export-and-download)
6. [ODPS Linking](#odps-linking)
7. [ODPS Helper Methods](#odps-helper-methods)
8. [ODPS Filtering](#odps-filtering)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)
11. [Examples](#examples)

## Introduction

The Open Data Product Standard (ODPS) is a specification for defining data products with marketplace features, including pricing plans, access methods, payment gateways, and product strategy. The DataHub SDK provides comprehensive support for creating, managing, and working with ODPS contracts.

### Key Features

- **Product-First Flow**: Automatically extract ODCS contracts from ODPS documents
- **Link Flow**: Link ODPS contracts to existing ODCS contracts
- **Export/Download**: Export ODPS contracts in JSON or YAML format
- **Helper Methods**: Extract specific ODPS data (pricing, access methods, etc.)
- **Filtering**: Filter contracts by ODPS-specific criteria
- **Error Handling**: Specialized error classes for ODPS operations

## ODPS Concepts

### ODPS vs ODCS

- **ODPS (Open Data Product Standard)**: Defines data products with marketplace features (pricing, access methods, payment gateways)
- **ODCS (Open Data Contract Standard)**: Defines data contracts (schema, quality, lineage)

ODPS contracts can contain an embedded ODCS contract in the `product.contract.spec` field, or they can be linked to a separate ODCS contract.

### ODPS Versions

The SDK supports ODPS version 4.1 and later. Version information is used for validation and documentation purposes.

### Product-First vs Link Flow

**Product-First Flow** (`extract_odcs=True`):
- Create ODPS contract with embedded ODCS specification
- Automatically extract and create separate ODCS contract
- Both contracts are created in a single operation

**Link Flow** (`link_odcs_id` provided):
- Create ODPS contract linked to existing ODCS contract
- ODPS contract references the ODCS contract via link
- Useful when ODCS contract already exists

## Getting Started

### Installation

```bash
pip install datahub-interoperability
```

### Basic Setup

```python
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Use ODPS functionality
        contracts_api = client.contracts
        # ... your code here

if __name__ == "__main__":
    asyncio.run(main())
```

## ODPS Contract Creation

### Product-First Flow

Create an ODPS contract and automatically extract the ODCS contract:

```python
odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "my-product",
        "name": "My Data Product"
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
    }
  }
}"""

result = await client.contracts.create_odps(
    original_raw=odps_content,
    extract_odcs=True,  # Automatically extract ODCS
    original_format="JSON",
    odps_version="4.1",
)

odps_contract = result["odps_contract"]
odcs_contract = result["odcs_contract"]
```

**Returns:**
- `odps_contract`: The created ODPS contract
- `odcs_contract`: The extracted ODCS contract
- `workflow_instance_id`: Optional workflow instance ID

### Link Flow

Create an ODPS contract linked to an existing ODCS contract:

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

**Note:** The `product.contract.spec` field is not required in the Link flow, as the ODCS contract already exists.

### Parameters

- `original_raw` (required): ODPS document content as JSON or YAML string
- `extract_odcs` (optional): If `True`, extract ODCS from ODPS (Product-First flow)
- `link_odcs_id` (optional): ODCS contract ID to link to (Link flow)
- `original_format` (optional): Format of ODPS document ("JSON" or "YAML"). Auto-detected if not provided
- `odps_version` (optional): ODPS version (e.g., "4.1"). Used for validation/documentation
- `resolve_external_refs` (optional): If `True`, resolve external `$ref` references (default: `True`)
- `asset_id` (optional): Asset ID to attach contracts to

**Mutually Exclusive:** `extract_odcs` and `link_odcs_id` cannot both be provided. One must be specified.

## ODPS Export and Download

### Export ODPS Contract

Export an ODPS contract in JSON or YAML format:

```python
# Export as JSON
odps_json = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="json",
    version="4.1",  # Optional, defaults to contract version
)

# Export as YAML
odps_yaml = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="yaml",
)
# YAML is returned as dict with "content" key containing YAML string
yaml_content = odps_yaml["content"]
```

### Download ODPS Contract

Download an ODPS contract as a file (returns bytes):

```python
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="json",  # or "yaml"
)

# Save to file
with open("odps_contract.json", "wb") as f:
    f.write(odps_file)
```

### Parameters

- `contract_id` (required): ODPS contract ID (UUID format)
- `format` (required): Export format ("json" or "yaml")
- `version` (optional): ODPS version to export (defaults to contract version)

## ODPS Linking

### Link ODPS to ODCS

Link an ODPS contract to an ODCS contract:

```python
linked_odps = await client.contracts.link_odps_to_odcs(
    odps_contract_id="odps-id",
    odcs_contract_id="odcs-id",
)
```

### Unlink ODPS from ODCS

Unlink an ODPS contract from an ODCS contract:

```python
await client.contracts.unlink_odps_from_odcs(
    odcs_contract_id="odcs-id",
)
```

### Get Linked Contracts

Get all contracts linked to a contract:

```python
links = await client.contracts.get_linked_contracts(
    contract_id="odps-id",  # or odcs-id
)

odcs_link = links.get("odcs_link")  # ODCS contract ID if linked
odps_link = links.get("odps_link")  # ODPS contract ID if linked
```

## ODPS Helper Methods

Helper methods extract specific ODPS data from contract objects:

### Check if Contract is ODPS

```python
contract = await client.contracts.get("contract-id")
is_odps = client.contracts.is_odps_contract(contract)
```

### Get ODPS Version

```python
version = client.contracts.get_odps_version(contract)
# Returns: "4.1" or None
```

### Get Pricing Plans

```python
pricing_plans = client.contracts.get_pricing_plans(contract)
# Returns: List of pricing plan dictionaries or None

if pricing_plans:
    for plan in pricing_plans:
        print(f"Plan: {plan.get('name')}")
        print(f"Price: ${plan.get('price')} {plan.get('currency')}")
        print(f"Billing: {plan.get('billingPeriod')}")
```

**Pricing Plan Structure:**
- `planID`: Unique plan identifier
- `name`: Plan name
- `description`: Plan description
- `price`: Price amount
- `currency`: Currency code (e.g., "USD")
- `billingPeriod`: Billing period (e.g., "monthly", "yearly")
- `features`: List of plan features

### Get Access Methods

```python
access_methods = client.contracts.get_access_methods(contract)
# Returns: Dictionary of access methods or None

if access_methods:
    for method_name, method_config in access_methods.items():
        method_type = method_config.get("type")  # e.g., "REST", "FILE"
        if method_type == "REST":
            endpoint = method_config.get("endpoint")
            auth = method_config.get("authentication")
```

**Access Method Types:**
- `REST`: REST API access
- `FILE`: File download access
- `STREAMING`: Streaming access
- `WEBHOOK`: Webhook-based access

### Get Payment Gateways

```python
payment_gateways = client.contracts.get_payment_gateways(contract)
# Returns: Dictionary of payment gateways or None

if payment_gateways:
    for gateway_name, gateway_config in payment_gateways.items():
        enabled = gateway_config.get("enabled", False)
        if enabled:
            print(f"{gateway_name} is enabled")
```

**Common Payment Gateways:**
- `stripe`: Stripe payment gateway
- `paypal`: PayPal payment gateway
- `bank_transfer`: Bank transfer

### Get Product Strategy (ODPS 4.1+)

```python
product_strategy = client.contracts.get_product_strategy(contract)
# Returns: Product strategy dictionary or None

if product_strategy:
    objectives = product_strategy.get("objectives", [])
    target_audience = product_strategy.get("targetAudience", [])
    value_proposition = product_strategy.get("valueProposition")
```

**Product Strategy Structure:**
- `objectives`: List of product objectives
- `targetAudience`: List of target audience segments
- `valueProposition`: Value proposition description

### Get Product Details

```python
# Get English product details (default)
product_details = client.contracts.get_product_details(contract, lang="en")

# Get Finnish product details
product_details_fi = client.contracts.get_product_details(contract, lang="fi")

if product_details:
    product_id = product_details.get("productID")
    name = product_details.get("name")
    description = product_details.get("description")
    category = product_details.get("category")
    tags = product_details.get("tags", [])
```

**Product Details Structure:**
- `productID`: Unique product identifier
- `name`: Product name
- `description`: Product description
- `category`: Product category
- `tags`: List of product tags

## ODPS Filtering

Filter contracts using ODPS-specific criteria:

### Filter by Spec Type

```python
# Get all ODPS contracts
odps_contracts = await client.contracts.list(spec_type="ODPS")

# Get all ODCS contracts
odcs_contracts = await client.contracts.list(spec_type="ODCS")
```

### Filter by ODPS Version

```python
# Get all ODPS 4.1 contracts
odps_41_contracts = await client.contracts.list(odps_version="4.1")
```

### Filter by ODPS Link Status

```python
# Get ODCS contracts with ODPS links
linked_odcs = await client.contracts.list(has_odps_link=True)

# Get ODCS contracts without ODPS links
unlinked_odcs = await client.contracts.list(has_odps_link=False)
```

### Combine Filters

```python
# Combine multiple filters
filtered = await client.contracts.list(
    spec_type="ODPS",
    odps_version="4.1",
    owner_email="owner@example.com",
    page=1,
    page_size=20,
)
```

**Available Filters:**
- `spec_type`: Filter by contract spec type ("ODPS" or "ODCS")
- `odps_version`: Filter by ODPS version (e.g., "4.1")
- `has_odps_link`: Filter ODCS contracts by ODPS link presence (`True` or `False`)
- Standard filters: `owner_email`, `tag`, `page`, `page_size`, etc.

## Error Handling

The SDK provides specialized ODPS error classes:

### ODPSValidationError

Raised when ODPS validation fails:

```python
from datahub_interoperability.errors import ODPSValidationError

try:
    await client.contracts.create_odps(
        original_raw=invalid_odps,
        extract_odcs=True,
    )
except ODPSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
```

**Error Attributes:**
- `message`: Error message
- `error_code`: Error code (e.g., "REQUIRED_FIELD_MISSING", "INVALID_VALUE")
- `field_path`: JSON path to the field with error
- `expected`: Expected value or format
- `actual`: Actual value received
- `http_status`: HTTP status code
- `request_id`: Request ID for debugging
- `context`: Additional error context

### ODPSExportError

Raised when ODPS export fails:

```python
from datahub_interoperability.errors import ODPSExportError

try:
    await client.contracts.export_odps(
        contract_id="invalid-id",
        format="json",
    )
except ODPSExportError as e:
    print(f"Export failed: {e.message}")
    print(f"Context: {e.context}")
```

### ODPSLinkingError

Raised when ODPS linking fails:

```python
from datahub_interoperability.errors import ODPSLinkingError

try:
    await client.contracts.link_odps_to_odcs(
        odps_contract_id="odps-id",
        odcs_contract_id="invalid-odcs-id",
    )
except ODPSLinkingError as e:
    print(f"Linking failed: {e.message}")
    print(f"Details: {e.details}")
```

## Best Practices

### 1. Always Validate Input

Use the SDK's built-in validation, but also validate your ODPS content before sending:

```python
# Validate ODPS content structure before creating
if not odps_content or len(odps_content.strip()) < 10:
    raise ValueError("Invalid ODPS content")

# Use proper error handling
try:
    result = await client.contracts.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
    )
except ODPSValidationError as e:
    # Handle validation errors
    logger.error(f"ODPS validation failed: {e.message}")
    raise
```

### 2. Use Appropriate Flow

- **Product-First Flow**: Use when creating new data products with embedded contracts
- **Link Flow**: Use when ODCS contract already exists and you want to add marketplace features

### 3. Handle Missing Optional Fields

ODPS helper methods return `None` for missing optional fields:

```python
pricing_plans = client.contracts.get_pricing_plans(contract)
if pricing_plans:
    # Process pricing plans
    pass
else:
    # Handle missing pricing plans
    logger.warning("No pricing plans found")
```

### 4. Use Filtering Efficiently

Combine filters to reduce API calls:

```python
# Efficient: Single API call with multiple filters
contracts = await client.contracts.list(
    spec_type="ODPS",
    odps_version="4.1",
    owner_email="owner@example.com",
)

# Inefficient: Multiple API calls
all_odps = await client.contracts.list(spec_type="ODPS")
filtered = [c for c in all_odps["results"] if c.get("original_spec_version") == "4.1"]
```

### 5. Error Handling Strategy

Implement comprehensive error handling:

```python
from datahub_interoperability.errors import (
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
    NotFoundError,
)

try:
    result = await client.contracts.create_odps(...)
except ODPSValidationError as e:
    # Handle validation errors (user input issues)
    handle_validation_error(e)
except ODPSExportError as e:
    # Handle export errors (server-side issues)
    handle_export_error(e)
except ODPSLinkingError as e:
    # Handle linking errors (relationship issues)
    handle_linking_error(e)
except NotFoundError as e:
    # Handle not found errors
    handle_not_found_error(e)
except Exception as e:
    # Handle unexpected errors
    handle_unexpected_error(e)
```

### 6. Use Async Context Manager

Always use the async context manager for proper resource cleanup:

```python
async with DataHubClient(config) as client:
    # Use client
    result = await client.contracts.create_odps(...)
    # Client is automatically closed when exiting context
```

## Examples

See `examples/odps_usage.py` for comprehensive examples covering:

- ODPS contract creation (Product-First and Link flows)
- ODPS export and download
- ODPS helper methods usage
- ODPS filtering
- ODPS linking operations
- Error handling

### Quick Example

```python
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Create ODPS contract
        result = await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
        )

        odps_id = result["odps_contract"]["id"]

        # Get pricing plans
        contract = await client.contracts.get(odps_id)
        pricing_plans = client.contracts.get_pricing_plans(contract)

        # Export ODPS
        odps_json = await client.contracts.export_odps(
            contract_id=odps_id,
            format="json",
        )

if __name__ == "__main__":
    asyncio.run(main())
```

## Additional Resources

- [ODPS Specification](https://opendataproducts.org/)
- [SDK API Reference](README.md)
- [Examples](examples/odps_usage.py)
- [Error Handling Guide](README.md#error-handling)

