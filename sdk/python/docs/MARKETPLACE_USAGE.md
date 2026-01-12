# Marketplace Integration Usage Guide

This guide provides comprehensive documentation for using marketplace integration functionality in the DataHub Interoperability Python SDK.

## Table of Contents

1. [Introduction](#introduction)
2. [Marketplace Concepts](#marketplace-concepts)
3. [Getting Started](#getting-started)
4. [Connection Management](#connection-management)
5. [Synchronization Jobs](#synchronization-jobs)
6. [Mappings](#mappings)
7. [Connector Information](#connector-information)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [Common Workflows](#common-workflows)
11. [Examples](#examples)

## Introduction

The Marketplace Integration API enables you to connect your DataHub to external marketplaces, synchronize assets and listings, and manage the relationships between your hub assets and external marketplace listings.

### Key Features

- **Connection Management**: Create, update, test, and delete marketplace connections
- **Synchronization Jobs**: Sync assets to marketplaces (PUSH), sync from marketplaces (PULL), and bidirectional sync
- **Mappings**: Track relationships between hub assets and external marketplace listings
- **Connector Information**: Discover available marketplace connectors and their capabilities
- **Error Handling**: Specialized error classes for marketplace operations

## Marketplace Concepts

### Marketplace Types

Supported marketplace types include:
- `SNOWFLAKE_DATA_MARKETPLACE`: Snowflake Data Marketplace
- `AWS_DATA_EXCHANGE`: AWS Data Exchange
- `GCP_MARKETPLACE`: Google Cloud Marketplace
- `DATABRICKS_MARKETPLACE`: Databricks Marketplace
- `CKAN`: CKAN-based marketplaces
- `DADOS_GOV_BR`: Dados.gov.br (Brazilian open data portal)

### Sync Directions

- **PUSH**: Sync hub assets to external marketplace (publish your data)
- **PULL**: Sync from external marketplace to hub (discover external data)
- **BIDIRECTIONAL**: Sync in both directions simultaneously

### Connection Configuration

Each marketplace type requires specific configuration parameters. Common parameters include:
- Authentication credentials (API keys, tokens, etc.)
- Connection endpoints
- Marketplace-specific settings

## Getting Started

### Installation

```bash
pip install datahub-interoperability
```

### Basic Setup

```python
import asyncio
import os
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Use marketplace functionality
        marketplace_api = client.marketplace
        # ... your code here

if __name__ == "__main__":
    asyncio.run(main())
```

## Connection Management

### Create Connection

Create a new marketplace connection:

```python
connection = await client.marketplace.create_connection(
    marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
    name="Production Snowflake Connection",
    config={
        "account": "my-account",
        "user": "my-user",
        "token": "my-token",
        "warehouse": "COMPUTE_WH",  # Optional
        "role": "ACCOUNTADMIN",      # Optional
        "database": "MARKETPLACE",   # Optional
    }
)

print(f"Created connection: {connection['id']}")
print(f"Marketplace type: {connection['marketplace_type']}")
print(f"Name: {connection['name']}")
print(f"Active: {connection['is_active']}")
```

**Parameters:**
- `marketplace_type` (str, required): Type of marketplace (e.g., "SNOWFLAKE_DATA_MARKETPLACE")
- `name` (str, required): Connection name (must be unique within tenant)
- `config` (Dict[str, Any], required): Marketplace-specific configuration

**Returns:** Connection dictionary with `id`, `marketplace_type`, `name`, `is_active`, `created_at`, etc.

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `MarketplaceConnectionError`: If connection creation fails
- `ConflictError`: If connection with same name already exists

### List Connections

List all marketplace connections with optional filtering:

```python
# List all connections
connections = await client.marketplace.list_connections()
print(f"Total connections: {len(connections)}")

# Filter by marketplace type
snowflake_connections = await client.marketplace.list_connections(
    marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
)
print(f"Snowflake connections: {len(snowflake_connections)}")

# Filter by active status
active_connections = await client.marketplace.list_connections(
    is_active=True,
)
print(f"Active connections: {len(active_connections)}")

# Pagination
connections = await client.marketplace.list_connections(
    limit=10,
    offset=0,
)
```

**Parameters:**
- `marketplace_type` (Optional[str]): Filter by marketplace type
- `is_active` (Optional[bool]): Filter by active status
- `limit` (Optional[int]): Maximum number of results
- `offset` (Optional[int]): Number of results to skip

**Returns:** List of connection dictionaries

### Get Connection

Retrieve a specific connection by ID:

```python
connection = await client.marketplace.get_connection("connection-id")
print(f"Connection: {connection['name']}")
print(f"Status: {'Active' if connection['is_active'] else 'Inactive'}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID

**Returns:** Connection dictionary

**Raises:**
- `MarketplaceValidationError`: If connection_id is invalid
- `NotFoundError`: If connection is not found

### Update Connection

Update connection details:

```python
# Update connection name
updated = await client.marketplace.update_connection(
    connection_id="connection-id",
    name="Updated Connection Name",
)

# Update configuration
updated = await client.marketplace.update_connection(
    connection_id="connection-id",
    config={
        "account": "new-account",
        "user": "new-user",
        "token": "new-token",
    },
)

# Update active status
updated = await client.marketplace.update_connection(
    connection_id="connection-id",
    is_active=False,  # Deactivate connection
)

# Update multiple fields
updated = await client.marketplace.update_connection(
    connection_id="connection-id",
    name="New Name",
    is_active=True,
)
```

**Parameters:**
- `connection_id` (str, required): Connection UUID
- `name` (Optional[str]): Updated connection name
- `config` (Optional[Dict[str, Any]]): Updated configuration
- `is_active` (Optional[bool]): Updated active status

**Returns:** Updated connection dictionary

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If connection is not found

### Test Connection

Test a connection to verify credentials and connectivity:

```python
test_result = await client.marketplace.test_connection("connection-id")

if test_result.get("success"):
    print("Connection test successful")
    print(f"Tested at: {test_result.get('tested_at')}")
    if "details" in test_result:
        print(f"Response time: {test_result['details'].get('response_time_ms')}ms")
else:
    print(f"Connection test failed: {test_result.get('message')}")
    if "error" in test_result:
        print(f"Error: {test_result['error']}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID

**Returns:** Test result dictionary with `success`, `message`, `tested_at`, and optional `details`

**Raises:**
- `MarketplaceValidationError`: If connection_id is invalid
- `NotFoundError`: If connection is not found
- `MarketplaceConnectionError`: If connection test fails

### Delete Connection

Delete a marketplace connection:

```python
await client.marketplace.delete_connection("connection-id")
print("Connection deleted successfully")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID

**Raises:**
- `MarketplaceValidationError`: If connection_id is invalid
- `NotFoundError`: If connection is not found

## Synchronization Jobs

### Sync Assets to Marketplace (PUSH)

Publish hub assets to an external marketplace:

```python
sync_job = await client.marketplace.sync_assets_to_marketplace(
    connection_id="connection-id",
    asset_ids=[
        "asset-id-1",
        "asset-id-2",
        "asset-id-3",
    ],
)

print(f"Created sync job: {sync_job['id']}")
print(f"Direction: {sync_job['direction']}")
print(f"Status: {sync_job['status']}")
print(f"Connection: {sync_job['connection']['name']}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID
- `asset_ids` (List[str], required): List of hub asset UUIDs to sync

**Returns:** Sync job dictionary with `id`, `direction`, `status`, `connection`, `created_at`, etc.

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If connection is not found

### Sync from Marketplace (PULL)

Import listings from an external marketplace:

```python
# Sync all listings
sync_job = await client.marketplace.sync_from_marketplace(
    connection_id="connection-id",
)

# Sync specific listings
sync_job = await client.marketplace.sync_from_marketplace(
    connection_id="connection-id",
    listing_ids=[
        "listing-id-1",
        "listing-id-2",
    ],
)

print(f"Created sync job: {sync_job['id']}")
print(f"Direction: {sync_job['direction']}")
print(f"Status: {sync_job['status']}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID
- `listing_ids` (Optional[List[str]]): List of listing IDs to sync (None to sync all)

**Returns:** Sync job dictionary

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If connection is not found

### Bidirectional Sync

Sync in both directions simultaneously:

```python
sync_job = await client.marketplace.sync_bidirectional(
    connection_id="connection-id",
    asset_ids=["asset-id-1", "asset-id-2"],
    listing_ids=["listing-id-1", "listing-id-2"],
)

print(f"Created bidirectional sync job: {sync_job['id']}")
print(f"Direction: {sync_job['direction']}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID
- `asset_ids` (List[str], required): List of hub asset UUIDs to sync to marketplace
- `listing_ids` (List[str], required): List of listing IDs to sync from marketplace

**Returns:** Sync job dictionary

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If connection is not found

### Get Sync Job

Retrieve sync job status and progress:

```python
sync_job = await client.marketplace.get_sync_job("sync-job-id")

print(f"Status: {sync_job['status']}")
print(f"Direction: {sync_job['direction']}")
print(f"Items synced: {sync_job.get('items_synced', 0)}")
print(f"Items failed: {sync_job.get('items_failed', 0)}")

if sync_job.get('errors'):
    print("Errors:")
    for error in sync_job['errors']:
        print(f"  - {error}")

if sync_job.get('completed_at'):
    print(f"Completed at: {sync_job['completed_at']}")
else:
    print("Job is still running")
```

**Parameters:**
- `sync_job_id` (str, required): Sync job UUID

**Returns:** Sync job dictionary with progress information

**Raises:**
- `MarketplaceValidationError`: If sync_job_id is invalid
- `NotFoundError`: If sync job is not found

### List Sync Jobs

List sync jobs with optional filtering:

```python
# List all sync jobs
sync_jobs = await client.marketplace.list_sync_jobs()

# Filter by connection
sync_jobs = await client.marketplace.list_sync_jobs(
    connection_id="connection-id",
)

# Filter by status
completed_jobs = await client.marketplace.list_sync_jobs(
    status="COMPLETED",
)

# Filter by direction
push_jobs = await client.marketplace.list_sync_jobs(
    direction="PUSH",
)

# Combine filters
sync_jobs = await client.marketplace.list_sync_jobs(
    connection_id="connection-id",
    status="PENDING",
    direction="PUSH",
    limit=10,
    offset=0,
)
```

**Parameters:**
- `connection_id` (Optional[str]): Filter by connection ID
- `status` (Optional[str]): Filter by status (e.g., "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
- `direction` (Optional[str]): Filter by direction ("PUSH", "PULL", "BIDIRECTIONAL")
- `limit` (Optional[int]): Maximum number of results
- `offset` (Optional[int]): Number of results to skip

**Returns:** List of sync job dictionaries

### Cancel Sync Job

Cancel a running sync job:

```python
await client.marketplace.cancel_sync_job("sync-job-id")
print("Sync job cancelled successfully")
```

**Parameters:**
- `sync_job_id` (str, required): Sync job UUID

**Raises:**
- `MarketplaceValidationError`: If sync_job_id is invalid
- `NotFoundError`: If sync job is not found

## Mappings

Mappings track the relationship between hub assets and external marketplace listings.

### Create Mapping

Create a mapping between a hub asset and an external listing:

```python
mapping = await client.marketplace.create_mapping(
    connection_id="connection-id",
    hub_asset_id="hub-asset-id",
    external_listing_id="external-listing-id",
)

print(f"Created mapping: {mapping['id']}")
print(f"Hub asset: {mapping['hub_asset_id']}")
print(f"External listing: {mapping['external_listing_id']}")
```

**Parameters:**
- `connection_id` (str, required): Connection UUID
- `hub_asset_id` (str, required): Hub asset UUID
- `external_listing_id` (str, required): External marketplace listing ID

**Returns:** Mapping dictionary with `id`, `connection_id`, `hub_asset_id`, `external_listing_id`, etc.

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If connection or asset is not found

### Get Mapping

Retrieve a mapping by ID:

```python
mapping = await client.marketplace.get_mapping("mapping-id")
print(f"Mapping: {mapping['id']}")
print(f"Hub asset: {mapping['hub_asset_id']}")
print(f"External listing: {mapping['external_listing_id']}")
if mapping.get('sync_metadata'):
    print(f"Last synced: {mapping['sync_metadata'].get('last_synced_at')}")
```

**Parameters:**
- `mapping_id` (str, required): Mapping UUID

**Returns:** Mapping dictionary

**Raises:**
- `MarketplaceValidationError`: If mapping_id is invalid
- `NotFoundError`: If mapping is not found

### List Mappings

List mappings with optional filtering:

```python
# List all mappings
mappings = await client.marketplace.list_mappings()

# Filter by connection
mappings = await client.marketplace.list_mappings(
    connection_id="connection-id",
)

# Filter by asset
mappings = await client.marketplace.list_mappings(
    asset_id="hub-asset-id",
)

# Pagination
mappings = await client.marketplace.list_mappings(
    connection_id="connection-id",
    limit=20,
    offset=0,
)
```

**Parameters:**
- `connection_id` (Optional[str]): Filter by connection ID
- `asset_id` (Optional[str]): Filter by hub asset ID
- `limit` (Optional[int]): Maximum number of results
- `offset` (Optional[int]): Number of results to skip

**Returns:** List of mapping dictionaries

### Update Mapping

Update mapping metadata:

```python
updated = await client.marketplace.update_mapping(
    mapping_id="mapping-id",
    sync_metadata={
        "last_synced_at": "2025-01-10T10:00:00Z",
        "sync_count": 5,
        "last_sync_status": "SUCCESS",
    },
)
```

**Parameters:**
- `mapping_id` (str, required): Mapping UUID
- `sync_metadata` (Optional[Dict[str, Any]]): Sync metadata to update

**Returns:** Updated mapping dictionary

**Raises:**
- `MarketplaceValidationError`: If parameters are invalid
- `NotFoundError`: If mapping is not found

### Delete Mapping

Delete a mapping:

```python
await client.marketplace.delete_mapping("mapping-id")
print("Mapping deleted successfully")
```

**Parameters:**
- `mapping_id` (str, required): Mapping UUID

**Raises:**
- `MarketplaceValidationError`: If mapping_id is invalid
- `NotFoundError`: If mapping is not found

## Connector Information

### List Connectors

Get information about all available marketplace connectors:

```python
connectors = await client.marketplace.list_connectors()

for connector in connectors:
    print(f"Type: {connector['type']}")
    print(f"Display Name: {connector['display_name']}")
    print(f"Status: {connector['status']}")
    print(f"Supported Directions: {connector['supported_sync_directions']}")
    print(f"Description: {connector.get('description', 'N/A')}")
    print("---")
```

**Returns:** List of connector information dictionaries

### Get Connector Info

Get detailed information about a specific connector:

```python
connector_info = await client.marketplace.get_connector_info(
    "SNOWFLAKE_DATA_MARKETPLACE"
)

print(f"Type: {connector_info['type']}")
print(f"Display Name: {connector_info['display_name']}")
print(f"Status: {connector_info['status']}")
print(f"Supported Directions: {connector_info['supported_sync_directions']}")

if connector_info.get('capabilities'):
    capabilities = connector_info['capabilities']
    print(f"Discovery: {capabilities.get('discovery', False)}")
    print(f"Harvest: {capabilities.get('harvest', False)}")
    print(f"Push: {capabilities.get('push', False)}")
    print(f"Pull: {capabilities.get('pull', False)}")

if connector_info.get('configuration_requirements'):
    reqs = connector_info['configuration_requirements']
    print(f"Required fields: {reqs.get('required', [])}")
    print(f"Optional fields: {reqs.get('optional', [])}")
```

**Parameters:**
- `connector_type` (str, required): Connector type (e.g., "SNOWFLAKE_DATA_MARKETPLACE")

**Returns:** Connector information dictionary with capabilities and configuration requirements

**Raises:**
- `MarketplaceValidationError`: If connector_type is invalid
- `NotFoundError`: If connector type is not found

## Error Handling

The SDK provides specialized error classes for marketplace operations:

```python
from datahub_interoperability.errors import (
    MarketplaceValidationError,
    MarketplaceConnectionError,
    NotFoundError,
    ConflictError,
    ValidationError,
)

try:
    connection = await client.marketplace.create_connection(
        marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
        name="My Connection",
        config={"account": "test"},
    )
except MarketplaceValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except MarketplaceConnectionError as e:
    print(f"Connection error: {e.message}")
    print(f"Error code: {e.code}")
    print(f"HTTP status: {e.http_status}")
    if e.details:
        print(f"Details: {e.details}")
except ConflictError as e:
    print(f"Conflict: {e.message}")
    # Connection with same name already exists
    # Handle by updating existing connection or using different name
except NotFoundError as e:
    print(f"Not found: {e.message}")
    print(f"Request ID: {e.request_id}")
except ValidationError as e:
    print(f"General validation error: {e.message}")
    if e.details:
        print(f"Details: {e.details}")
```

### Error Types

- **MarketplaceValidationError**: Parameter validation failures (invalid UUID, missing required fields, etc.)
- **MarketplaceConnectionError**: Connection-related errors (test failures, API errors, etc.)
- **NotFoundError**: Resource not found (connection, sync job, mapping, etc.)
- **ConflictError**: Resource conflicts (duplicate connection names, etc.)
- **ValidationError**: General validation errors

## Best Practices

### Connection Management

1. **Always test connections** before using them for sync operations:
   ```python
   test_result = await client.marketplace.test_connection(connection_id)
   if not test_result.get("success"):
       raise Exception(f"Connection test failed: {test_result.get('message')}")
   ```

2. **Use descriptive connection names** that indicate purpose and environment:
   ```python
   name = f"Snowflake Production - {tenant_name}"
   ```

3. **Store sensitive credentials securely** - never hardcode in code:
   ```python
   config = {
       "account": os.getenv("SNOWFLAKE_ACCOUNT"),
       "user": os.getenv("SNOWFLAKE_USER"),
       "token": os.getenv("SNOWFLAKE_TOKEN"),
   }
   ```

4. **Deactivate instead of delete** when temporarily disabling connections:
   ```python
   await client.marketplace.update_connection(connection_id, is_active=False)
   ```

### Synchronization

1. **Monitor sync job progress** for long-running operations:
   ```python
   sync_job = await client.marketplace.sync_assets_to_marketplace(...)

   while sync_job['status'] in ['PENDING', 'RUNNING']:
       await asyncio.sleep(5)
       sync_job = await client.marketplace.get_sync_job(sync_job['id'])
       print(f"Progress: {sync_job.get('items_synced', 0)} items synced")
   ```

2. **Handle sync errors** gracefully:
   ```python
   sync_job = await client.marketplace.get_sync_job(sync_job_id)
   if sync_job['status'] == 'FAILED':
       errors = sync_job.get('errors', [])
       for error in errors:
           print(f"Error: {error}")
   ```

3. **Use mappings** to track relationships between hub assets and external listings:
   ```python
   # After successful sync, create mapping
   mapping = await client.marketplace.create_mapping(
       connection_id=connection_id,
       hub_asset_id=asset_id,
       external_listing_id=listing_id,
   )
   ```

### Error Handling

1. **Always handle specific error types** for better error messages:
   ```python
   try:
       connection = await client.marketplace.create_connection(...)
   except MarketplaceValidationError as e:
       # Handle validation errors
       pass
   except ConflictError as e:
       # Handle conflicts (e.g., duplicate names)
       pass
   ```

2. **Log errors with context** for debugging:
   ```python
   import logging

   try:
       sync_job = await client.marketplace.sync_assets_to_marketplace(...)
   except Exception as e:
       logging.error(f"Sync failed for connection {connection_id}: {e}", exc_info=True)
   ```

## Common Workflows

### Workflow 1: Setup and Test Connection

```python
async def setup_marketplace_connection(client, marketplace_type, name, config):
    """Setup and test a marketplace connection"""
    # Create connection
    connection = await client.marketplace.create_connection(
        marketplace_type=marketplace_type,
        name=name,
        config=config,
    )

    # Test connection
    test_result = await client.marketplace.test_connection(connection['id'])
    if not test_result.get("success"):
        # Delete failed connection
        await client.marketplace.delete_connection(connection['id'])
        raise Exception(f"Connection test failed: {test_result.get('message')}")

    print(f"Connection {connection['id']} created and tested successfully")
    return connection
```

### Workflow 2: Publish Assets to Marketplace

```python
async def publish_assets_to_marketplace(client, connection_id, asset_ids):
    """Publish hub assets to marketplace and track mappings"""
    # Create sync job
    sync_job = await client.marketplace.sync_assets_to_marketplace(
        connection_id=connection_id,
        asset_ids=asset_ids,
    )

    # Wait for completion
    while sync_job['status'] in ['PENDING', 'RUNNING']:
        await asyncio.sleep(5)
        sync_job = await client.marketplace.get_sync_job(sync_job['id'])

    if sync_job['status'] == 'COMPLETED':
        print(f"Successfully synced {sync_job.get('items_synced', 0)} assets")
        # Create mappings for synced assets
        # (In real implementation, you'd get listing IDs from sync job results)
    else:
        print(f"Sync failed: {sync_job.get('errors', [])}")

    return sync_job
```

### Workflow 3: Discover External Listings

```python
async def discover_external_listings(client, connection_id):
    """Discover and import listings from external marketplace"""
    # Sync from marketplace
    sync_job = await client.marketplace.sync_from_marketplace(
        connection_id=connection_id,
    )

    # Monitor progress
    while sync_job['status'] in ['PENDING', 'RUNNING']:
        await asyncio.sleep(5)
        sync_job = await client.marketplace.get_sync_job(sync_job['id'])
        print(f"Discovered {sync_job.get('items_synced', 0)} listings so far")

    if sync_job['status'] == 'COMPLETED':
        print(f"Discovery complete: {sync_job.get('items_synced', 0)} listings")

    return sync_job
```

### Workflow 4: Manage Mappings

```python
async def manage_asset_mappings(client, connection_id, asset_id):
    """Get and update mappings for an asset"""
    # List mappings for asset
    mappings = await client.marketplace.list_mappings(
        connection_id=connection_id,
        asset_id=asset_id,
    )

    for mapping in mappings:
        print(f"Mapping: {mapping['id']}")
        print(f"External listing: {mapping['external_listing_id']}")

        # Update sync metadata
        await client.marketplace.update_mapping(
            mapping['id'],
            sync_metadata={
                "last_synced_at": datetime.utcnow().isoformat(),
                "sync_count": mapping.get('sync_metadata', {}).get('sync_count', 0) + 1,
            },
        )

    return mappings
```

## Examples

### Complete Example: Full Marketplace Integration

```python
import asyncio
import os
from datetime import datetime
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    MarketplaceValidationError,
    MarketplaceConnectionError,
    NotFoundError,
)

async def main():
    # Initialize client
    config = DataHubClientConfig(
        base_url=os.getenv("DATAHUB_BASE_URL", "https://api.hub.example.com/api/v1"),
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # 1. List available connectors
        connectors = await client.marketplace.list_connectors()
        print("Available connectors:")
        for connector in connectors:
            print(f"  - {connector['type']}: {connector['display_name']}")

        # 2. Get connector details
        connector_info = await client.marketplace.get_connector_info(
            "SNOWFLAKE_DATA_MARKETPLACE"
        )
        print(f"\nConnector capabilities: {connector_info.get('capabilities')}")

        # 3. Create connection
        try:
            connection = await client.marketplace.create_connection(
                marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
                name=f"Production Connection - {datetime.now().isoformat()}",
                config={
                    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                    "user": os.getenv("SNOWFLAKE_USER"),
                    "token": os.getenv("SNOWFLAKE_TOKEN"),
                },
            )
            print(f"\nCreated connection: {connection['id']}")
        except ConflictError:
            # Connection with same name exists, list and use existing
            connections = await client.marketplace.list_connections(
                marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
            )
            connection = connections[0] if connections else None
            if not connection:
                raise Exception("No connection available")
            print(f"\nUsing existing connection: {connection['id']}")

        # 4. Test connection
        test_result = await client.marketplace.test_connection(connection['id'])
        if not test_result.get("success"):
            print(f"Connection test failed: {test_result.get('message')}")
            return
        print("Connection test successful")

        # 5. Sync assets to marketplace
        asset_ids = ["asset-id-1", "asset-id-2"]
        sync_job = await client.marketplace.sync_assets_to_marketplace(
            connection_id=connection['id'],
            asset_ids=asset_ids,
        )
        print(f"\nCreated sync job: {sync_job['id']}")

        # 6. Monitor sync job
        while sync_job['status'] in ['PENDING', 'RUNNING']:
            await asyncio.sleep(5)
            sync_job = await client.marketplace.get_sync_job(sync_job['id'])
            print(f"Status: {sync_job['status']}, Items synced: {sync_job.get('items_synced', 0)}")

        if sync_job['status'] == 'COMPLETED':
            print(f"\nSync completed: {sync_job.get('items_synced', 0)} items synced")
        else:
            print(f"\nSync failed: {sync_job.get('errors', [])}")

        # 7. List mappings
        mappings = await client.marketplace.list_mappings(
            connection_id=connection['id'],
        )
        print(f"\nTotal mappings: {len(mappings)}")

        # 8. Cleanup (optional)
        # await client.marketplace.delete_connection(connection['id'])

if __name__ == "__main__":
    asyncio.run(main())
```

### Example: Error Handling

```python
async def robust_connection_creation(client, marketplace_type, name, config):
    """Create connection with comprehensive error handling"""
    try:
        connection = await client.marketplace.create_connection(
            marketplace_type=marketplace_type,
            name=name,
            config=config,
        )
        return connection
    except MarketplaceValidationError as e:
        print(f"Validation error: {e.message}")
        if e.field_path:
            print(f"Field: {e.field_path}")
            print(f"Expected: {e.expected}")
            print(f"Actual: {e.actual}")
        raise
    except ConflictError as e:
        print(f"Conflict: Connection with name '{name}' already exists")
        # Option 1: Get existing connection
        connections = await client.marketplace.list_connections()
        for conn in connections:
            if conn.get('name') == name:
                return conn
        # Option 2: Use different name
        new_name = f"{name} - {datetime.now().isoformat()}"
        return await client.marketplace.create_connection(
            marketplace_type=marketplace_type,
            name=new_name,
            config=config,
        )
    except MarketplaceConnectionError as e:
        print(f"Connection error: {e.message}")
        print(f"Error code: {e.code}")
        if e.details:
            print(f"Details: {e.details}")
        raise
```

## Additional Resources

- [SDK API Reference](../README.md)
- [Marketplace Integration API Reference](../../../docs/MARKETPLACE_API_REFERENCE.md)
- [Error Handling Guide](../README.md#error-handling)
- [Examples](../examples/)
