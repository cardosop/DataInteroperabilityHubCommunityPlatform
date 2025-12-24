# DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.

## Installation

```bash
pip install datahub-interoperability
```

## Quick Start

```python
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    # Initialize client with API key
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Use the client
        assets = await client.get("/assets/")
        print(assets)

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

### API Key

```python
config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token="your-api-key",
)

async with DataHubClient(config) as client:
    assets = await client.get("/assets/")
```

### JWT Token with Auto-Refresh

```python
async def refresh_token():
    # Refresh token logic
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        data = response.json()
        return data["access_token"]

config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token=initial_token,
)

async with DataHubClient(config) as client:
    client.set_token_refresh_callback(refresh_token)
    assets = await client.get("/assets/")
```

## Error Handling

```python
from datahub_interoperability import (
    NotFoundError,
    ValidationError,
    UnauthorizedError,
)

try:
    asset = await client.get("/assets/123/")
except NotFoundError as e:
    print(f"Asset not found: {e.message}")
    print(f"Request ID: {e.request_id}")
except ValidationError as e:
    print(f"Validation errors: {e.details}")
except UnauthorizedError as e:
    print(f"Authentication required: {e.message}")
```

## Retry Logic

The SDK automatically retries transient errors (5xx, network timeouts) with exponential backoff:

```python
config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token="your-api-key",
    max_retries=3,  # Default: 3
    timeout=30.0,   # Default: 30 seconds
)
```

## Examples

### Create Asset

```python
asset = await client.post("/assets/", {
    "key": "my-asset",
    "name": "My Asset",
    "description": "Asset description",
    "domain": "marketing",
})
print(asset)
```

### List Assets with Filters

```python
assets = await client.get("/assets/", params={
    "status": "ACTIVE",
    "domain": "marketing",
    "search": "customer",
    "limit": 20,
    "offset": 0,
})
print(assets)
```

### Upload File

```python
# Initialize upload
file_info = await client.post("/files/init/", {
    "name": "data.csv",
    "size": 1024,
    "content_type": "text/csv",
})

# Upload to pre-signed URL
async with httpx.AsyncClient() as http_client:
    async with open("data.csv", "rb") as f:
        await http_client.put(file_info["upload_url"], content=f.read())

# Complete upload
await client.post(f"/files/{file_info['id']}/complete/")
```

## Configuration

### Environment Variables

```bash
export DATAHUB_BASE_URL=https://api.hub.example.com/api/v1
export DATAHUB_API_TOKEN=your-api-key
```

```python
import os
from datahub_interoperability import DataHubClientConfig

config = DataHubClientConfig(
    base_url=os.getenv("DATAHUB_BASE_URL"),
    api_token=os.getenv("DATAHUB_API_TOKEN"),
)
```

## Type Hints

The SDK provides type hints for better IDE support:

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig
from typing import Dict, Any

async def get_asset(client: DataHubClient, asset_id: str) -> Dict[str, Any]:
    return await client.get(f"/assets/{asset_id}/")
```

## Async Context Manager

The client supports async context manager for automatic cleanup:

```python
async with DataHubClient(config) as client:
    assets = await client.get("/assets/")
    # Client is automatically closed when exiting context
```

## ODPS (Open Data Product Standard) Support

The SDK provides comprehensive support for ODPS contracts, including creation, linking, export, filtering, and helper methods.

> **📖 For detailed ODPS usage documentation, see [ODPS_USAGE.md](docs/ODPS_USAGE.md)**
> **💡 For practical examples, see [examples/odps_usage.py](examples/odps_usage.py)**

### ODPS Contract Creation

#### Product-First Flow (Automatic ODCS Extraction)

Create an ODPS contract and automatically extract the ODCS contract from it:

```python
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

# Returns both ODPS and ODCS contracts
odps_contract = result["odps_contract"]
odcs_contract = result["odcs_contract"]
print(f"Created ODPS contract: {odps_contract['id']}")
print(f"Created ODCS contract: {odcs_contract['id']}")
```

#### Link Flow (Link to Existing ODCS)

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
print(f"Created ODPS contract linked to ODCS: {odps_contract['id']}")
```

### ODPS Export and Download

Export an ODPS contract in JSON or YAML format:

```python
# Export as JSON
odps_json = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="json",
    version="4.1",  # Optional, defaults to contract version
)
print(odps_json)

# Export as YAML
odps_yaml = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="yaml",
)
print(odps_yaml["content"])  # YAML content as string

# Download as file (returns bytes)
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="json",
)
with open("odps_contract.json", "wb") as f:
    f.write(odps_file)
```

### ODPS Linking

Link and unlink ODPS contracts to/from ODCS contracts:

```python
# Link ODPS to ODCS
linked_odps = await client.contracts.link_odps_to_odcs(
    odps_contract_id="odps-id",
    odcs_contract_id="odcs-id",
)
print(f"Linked ODPS {linked_odps['id']} to ODCS")

# Unlink ODPS from ODCS
await client.contracts.unlink_odps_from_odcs(
    odcs_contract_id="odcs-id",
)
print("Unlinked successfully")

# Get all linked contracts
links = await client.contracts.get_linked_contracts(
    contract_id="odps-id",
)
print(f"ODCS link: {links.get('odcs_link')}")
print(f"ODPS link: {links.get('odps_link')}")
```

### ODPS Helper Methods

Access ODPS-specific data from contracts:

```python
# Get contract
contract = await client.contracts.get("odps-contract-id")

# Check if contract is ODPS
if client.contracts.is_odps_contract(contract):
    print("This is an ODPS contract")

    # Get ODPS version
    version = client.contracts.get_odps_version(contract)
    print(f"ODPS version: {version}")

    # Get pricing plans
    pricing_plans = client.contracts.get_pricing_plans(contract)
    if pricing_plans:
        for plan in pricing_plans:
            print(f"Plan: {plan.get('name')} - ${plan.get('price')}")

    # Get access methods
    access_methods = client.contracts.get_access_methods(contract)
    if access_methods:
        for method_name, method_config in access_methods.items():
            print(f"Access method: {method_name}")

    # Get payment gateways
    payment_gateways = client.contracts.get_payment_gateways(contract)
    if payment_gateways:
        for gateway_name, gateway_config in payment_gateways.items():
            print(f"Payment gateway: {gateway_name}")

    # Get product strategy (ODPS 4.1+)
    product_strategy = client.contracts.get_product_strategy(contract)
    if product_strategy:
        print(f"Objectives: {product_strategy.get('objectives')}")

    # Get product details (with language support)
    product_details_en = client.contracts.get_product_details(contract, lang="en")
    print(f"Product name (EN): {product_details_en.get('name')}")

    product_details_fi = client.contracts.get_product_details(contract, lang="fi")
    if product_details_fi:
        print(f"Product name (FI): {product_details_fi.get('name')}")
```

### ODPS Filtering

Filter contracts by ODPS-specific criteria:

```python
# Filter by spec type
odps_contracts = await client.contracts.list(spec_type="ODPS")
print(f"Found {odps_contracts['count']} ODPS contracts")

# Filter by ODPS version
odps_41_contracts = await client.contracts.list(odps_version="4.1")
print(f"Found {odps_41_contracts['count']} ODPS 4.1 contracts")

# Filter ODCS contracts with ODPS links
linked_odcs = await client.contracts.list(has_odps_link=True)
print(f"Found {linked_odcs['count']} ODCS contracts with ODPS links")

# Filter ODCS contracts without ODPS links
unlinked_odcs = await client.contracts.list(has_odps_link=False)
print(f"Found {unlinked_odcs['count']} ODCS contracts without ODPS links")

# Combine multiple filters
filtered = await client.contracts.list(
    spec_type="ODPS",
    odps_version="4.1",
    owner_email="owner@example.com",
    page=1,
    page_size=20,
)
```

### ODPS Error Handling

The SDK provides specialized ODPS error classes:

```python
from datahub_interoperability.errors import (
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
)

try:
    result = await client.contracts.create_odps(
        original_raw=invalid_odps_content,
        extract_odcs=True,
    )
except ODPSValidationError as e:
    print(f"ODPS validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except ODPSExportError as e:
    print(f"ODPS export failed: {e.message}")
    print(f"Context: {e.context}")
except ODPSLinkingError as e:
    print(f"ODPS linking failed: {e.message}")
    print(f"Details: {e.details}")
```

## Contract Management

### List Contracts

List contracts with comprehensive filtering:

```python
# Basic listing
contracts = await client.contracts.list()

# With filters
contracts = await client.contracts.list(
    page=1,
    page_size=50,
    owner_email="owner@example.com",
    tag="production",
    spec_type="ODPS",  # ODPS-specific filter
    odps_version="4.1",  # ODPS-specific filter
)
```

### Get Contract

```python
contract = await client.contracts.get("contract-id")
print(contract["status"])
print(contract["original_spec_type"])
```

### Create Contract

```python
odcs_content = """{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "my-contract",
  "schema": {
    "fields": [{"name": "id", "type": "string"}]
  }
}"""

contract = await client.contracts.create(
    original_raw=odcs_content,
    original_format="JSON",
)
```

### Update Contract

```python
updated = await client.contracts.update(
    contract_id="contract-id",
    original_raw=updated_content,
)
```

### Validate Contract

```python
validation_result = await client.contracts.validate("contract-id")
if validation_result["validation_status"] == "VALID":
    print("Contract is valid")
else:
    print(f"Errors: {validation_result.get('errors', [])}")
```

## License

MIT

