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

## License

MIT

