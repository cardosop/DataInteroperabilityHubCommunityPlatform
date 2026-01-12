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

## BaaS (Backend as a Service) Platform

The SDK provides comprehensive support for BaaS platform operations, including API key management, usage tracking, and developer portal access.

> **📖 For detailed BaaS usage documentation, see [BAAS_USAGE.md](docs/BAAS_USAGE.md)**

### API Key Management

```python
# Create API key
api_key = await client.baas.create_api_key(
    name="My API Key",
    tier="FREE",  # FREE, PRO, or ENTERPRISE
    expires_at="2025-12-31T23:59:59Z",  # Optional
)
print(f"Created API key: {api_key['id']}")
print(f"API Key value: {api_key['api_key']}")  # Shown only once!

# List API keys
api_keys = await client.baas.list_api_keys(
    tier="PRO",  # Optional filter
    limit=20,
    offset=0,
)

# Get API key details
api_key = await client.baas.get_api_key(api_key_id)

# Update API key
updated = await client.baas.update_api_key(
    api_key_id,
    name="Updated Name",
    tier="PRO",  # Optional
    expires_at="2026-12-31T23:59:59Z",  # Optional
)

# Revoke API key
await client.baas.revoke_api_key(api_key_id)
```

### Usage Tracking

```python
# Get usage statistics
stats = await client.baas.get_usage_statistics(
    api_key_id="optional-api-key-id",
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-01-31T23:59:59Z",
)

# Get usage by endpoint
endpoint_stats = await client.baas.get_usage_by_endpoint(
    api_key_id="optional-api-key-id",
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-01-31T23:59:59Z",
)

# Get usage by tenant
tenant_stats = await client.baas.get_usage_by_tenant(
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-01-31T23:59:59Z",
)
```

### Developer Portal

```python
# Get API documentation
docs = await client.baas.get_api_documentation()
print(f"Title: {docs['title']}")
print(f"Version: {docs['version']}")

# Get OpenAPI schema
openapi_json = await client.baas.get_openapi_schema(format="json")
openapi_yaml = await client.baas.get_openapi_schema(format="yaml")

# Get SDK download links
sdks = await client.baas.get_sdk_download_links()
print(f"Python SDK: {sdks['python']['download_url']}")
print(f"JavaScript SDK: {sdks['javascript']['download_url']}")
```

### BaaS Error Handling

The SDK provides specialized BaaS error classes:

```python
from datahub_interoperability.errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
)

try:
    api_key = await client.baas.create_api_key(name="", tier="FREE")
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except NotFoundError as e:
    print(f"API key not found: {e.message}")
except BaaSError as e:
    print(f"BaaS error: {e.message}")
    print(f"Error code: {e.error_code}")
```

## ODH (Open Data Hub) Integration

The SDK provides comprehensive support for ML model management, training, and inference operations with ODH (Open Data Hub) integration.

> **📖 For detailed ODH usage documentation, see [ODH_USAGE.md](docs/ODH_USAGE.md)**
> **📖 For detailed model serving usage documentation, see [MODEL_SERVING_USAGE.md](docs/MODEL_SERVING_USAGE.md)**

### Model Registry

```python
# List models
models = await client.odh.list_models(
    asset_id="optional-asset-id",
    status="TRAINED",
    limit=50,
    offset=0,
)

# Get model details
model = await client.odh.get_model(model_id)

# Create model
model = await client.odh.create_model(
    odh_model_id="my-model-123",
    odh_model_version="1.0.0",
    asset_id="asset-uuid",
    model_type="CLASSIFICATION",
    contract_id="optional-contract-uuid",
)

# Update model
updated = await client.odh.update_model(
    model_id,
    asset_id="new-asset-uuid",
    status="DEPLOYED",
)

# Delete model
await client.odh.delete_model(model_id)

# Get model versions
versions = await client.odh.get_model_versions(model_id)

# Link model to asset
model = await client.odh.link_model_to_asset(model_id, asset_id)

# Link model to dataset
link = await client.odh.link_model_to_dataset(
    model_id,
    dataset_id,
    role="TRAINING",  # TRAINING, VALIDATION, or TEST
)
```

### Training Jobs

```python
# Submit training job
job = await client.training.submit_training_job(
    model_id="model-uuid",
    dataset_id="dataset-uuid",
    config={
        "epochs": 100,
        "batch_size": 32,
        "learning_rate": 0.001,
    },
)

# Get training job details
job = await client.training.get_training_job(job_id)

# List training jobs
jobs = await client.training.list_training_jobs(
    model_id="optional-model-uuid",
    status="RUNNING",
    limit=20,
    offset=0,
)

# Cancel training job
await client.training.cancel_training_job(job_id)

# Get training logs
logs = await client.training.get_training_logs(job_id)
```

### Inference Deployments

```python
# Deploy model
deployment = await client.inference.deploy_model(
    model_id="model-uuid",
    config={
        "replicas": 3,
        "resources": {
            "requests": {"cpu": "500m", "memory": "1Gi"},
        },
    },
)

# Run prediction
prediction = await client.inference.predict(
    deployment_id="deployment-id",
    input_data={
        "feature1": 0.5,
        "feature2": 0.8,
    },
)

# Get deployment details
deployment = await client.inference.get_deployment(deployment_id)

# List deployments
deployments = await client.inference.list_deployments(
    model_id="optional-model-uuid",
    status="DEPLOYED",
    limit=20,
    offset=0,
)

# Undeploy model
await client.inference.undeploy_model(deployment_id)

# Get inference metrics
metrics = await client.inference.get_inference_metrics(deployment_id)
```

### Model Serving

Model serving provides API endpoints for deploying models as production-ready services with contract validation, quality monitoring, and A/B testing capabilities.

> **📖 For detailed model serving usage documentation, see [MODEL_SERVING_USAGE.md](docs/MODEL_SERVING_USAGE.md)**

```python
# Deploy model as API endpoint
serving = await client.model_serving.deploy_model_as_api(
    model_id="model-uuid",
    endpoint="/api/v1/models/my-classifier",  # Optional
)

# Run prediction via API (using model ID directly)
prediction = await client.model_serving.predict_via_api(
    model_id="model-uuid",
    input_data={
        "feature1": 0.5,
        "feature2": 0.8,
    },
)

# List deployed models
deployments = await client.model_serving.list_deployed_models(
    model_id="optional-model-uuid",
    status="READY",
    limit=20,
    offset=0,
)

# Get serving details
serving_details = await client.model_serving.get_model_serving_details(serving_id)

# Get quality metrics
metrics = await client.model_serving.get_model_quality_metrics(serving_id)

# Undeploy model
await client.model_serving.undeploy_model(serving_id)
```

### A/B Testing

A/B testing allows you to compare model variants by splitting traffic between a base model and a variant model.

```python
# Create A/B test
ab_test = await client.model_serving.create_ab_test(
    model_id="base-model-uuid",
    variant_id="variant-model-uuid",
    traffic_split="50:50",  # 50% to base, 50% to variant
)

# List A/B tests
ab_tests = await client.model_serving.list_ab_tests(
    model_id="optional-model-uuid",
    limit=20,
    offset=0,
)

# Get A/B test details with metrics
ab_test_details = await client.model_serving.get_ab_test_details(ab_test_id)
```

### ODH Error Handling

The SDK provides specialized ODH error classes:

```python
from datahub_interoperability.errors import (
    ODHMLValidationError,
    ODHMLNotFoundError,
    ODHMLConflictError,
    ODHMLError,
    ValidationError,
    NotFoundError,
)

try:
    model = await client.odh.create_model(
        odh_model_id="",
        odh_model_version="1.0.0",
        asset_id="invalid-uuid",
        model_type="INVALID_TYPE",
    )
except ODHMLValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Field: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except ODHMLNotFoundError as e:
    print(f"Model not found: {e.message}")
except ODHMLConflictError as e:
    print(f"Conflict: {e.message}")
except ODHMLError as e:
    print(f"ODH error: {e.message}")
```

## Marketplace Integration

The SDK provides comprehensive support for marketplace integration, including connection management, synchronization jobs, mappings, and connector information.

> **📖 For detailed marketplace usage documentation, see [MARKETPLACE_USAGE.md](docs/MARKETPLACE_USAGE.md)**

### Connection Management

Create and manage marketplace connections:

```python
# Create a marketplace connection
connection = await client.marketplace.create_connection(
    marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
    name="My Snowflake Connection",
    config={
        "account": "my-account",
        "user": "my-user",
        "token": "my-token",
    }
)
print(f"Created connection: {connection['id']}")

# List connections
connections = await client.marketplace.list_connections(
    marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
    is_active=True,
)
print(f"Found {len(connections)} active connections")

# Get connection details
connection = await client.marketplace.get_connection(connection["id"])

# Update connection
updated = await client.marketplace.update_connection(
    connection["id"],
    name="Updated Connection Name",
    is_active=True,
)

# Test connection
test_result = await client.marketplace.test_connection(connection["id"])
if test_result.get("success"):
    print("Connection test successful")
else:
    print(f"Connection test failed: {test_result.get('message')}")

# Delete connection
await client.marketplace.delete_connection(connection["id"])
```

### Synchronization Jobs

Sync assets to and from marketplaces:

```python
# Sync assets to marketplace (PUSH)
sync_job = await client.marketplace.sync_assets_to_marketplace(
    connection_id=connection["id"],
    asset_ids=["asset-id-1", "asset-id-2"],
)
print(f"Created sync job: {sync_job['id']}")

# Sync from marketplace (PULL)
sync_job = await client.marketplace.sync_from_marketplace(
    connection_id=connection["id"],
    listing_ids=["listing-id-1", "listing-id-2"],  # Optional: None to sync all
)

# Bidirectional sync
sync_job = await client.marketplace.sync_bidirectional(
    connection_id=connection["id"],
    asset_ids=["asset-id-1"],
    listing_ids=["listing-id-1"],
)

# Get sync job status
sync_job = await client.marketplace.get_sync_job(sync_job["id"])
print(f"Status: {sync_job['status']}")
print(f"Items synced: {sync_job.get('items_synced', 0)}")

# List sync jobs
sync_jobs = await client.marketplace.list_sync_jobs(
    connection_id=connection["id"],
    status="COMPLETED",
    direction="PUSH",
)

# Cancel sync job
await client.marketplace.cancel_sync_job(sync_job["id"])
```

### Mappings

Manage mappings between hub assets and marketplace listings:

```python
# Create mapping
mapping = await client.marketplace.create_mapping(
    connection_id=connection["id"],
    hub_asset_id="hub-asset-id",
    external_listing_id="external-listing-id",
)

# Get mapping
mapping = await client.marketplace.get_mapping(mapping["id"])

# List mappings
mappings = await client.marketplace.list_mappings(
    connection_id=connection["id"],
    asset_id="hub-asset-id",
)

# Update mapping
updated = await client.marketplace.update_mapping(
    mapping["id"],
    sync_metadata={"last_synced": "2025-01-10T10:00:00Z"},
)

# Delete mapping
await client.marketplace.delete_mapping(mapping["id"])
```

### Connector Information

Get information about available marketplace connectors:

```python
# List all connectors
connectors = await client.marketplace.list_connectors()
for connector in connectors:
    print(f"Type: {connector['type']}")
    print(f"Display Name: {connector['display_name']}")
    print(f"Supported Directions: {connector['supported_sync_directions']}")

# Get connector details
connector_info = await client.marketplace.get_connector_info(
    "SNOWFLAKE_DATA_MARKETPLACE"
)
print(f"Capabilities: {connector_info.get('capabilities')}")
print(f"Configuration Requirements: {connector_info.get('configuration_requirements')}")
```

### Marketplace Error Handling

The SDK provides specialized marketplace error classes:

```python
from datahub_interoperability.errors import (
    MarketplaceValidationError,
    MarketplaceConnectionError,
    NotFoundError,
    ConflictError,
)

try:
    connection = await client.marketplace.create_connection(
        marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
        name="My Connection",
        config={"account": "test"},
    )
except MarketplaceValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except MarketplaceConnectionError as e:
    print(f"Connection error: {e.message}")
    print(f"Error code: {e.error_code}")
except ConflictError as e:
    print(f"Conflict: {e.message}")
    # Connection with same name already exists
except NotFoundError as e:
    print(f"Not found: {e.message}")
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

