# SDK Documentation

Complete documentation for the Interoperable Data Hub SDKs.

## Table of Contents

1. [Overview](#overview)
2. [Python SDK](#python-sdk)
3. [JavaScript/TypeScript SDK](#javascripttypescript-sdk)
4. [Common Patterns](#common-patterns)
5. [Error Handling](#error-handling)
6. [Best Practices](#best-practices)

---

## Overview

The Interoperable Data Hub provides official SDKs for Python and JavaScript/TypeScript to simplify API integration.

**Available SDKs:**
- **Python**: `datahub-interoperability`
- **JavaScript/TypeScript**: `@datahub/interoperability-sdk`

Both SDKs provide:
- Type-safe API clients
- Automatic authentication handling
- Retry logic with exponential backoff
- Error handling
- Request/response validation

---

## Python SDK

### Installation

```bash
pip install datahub-interoperability
```

### Quick Start

```python
import asyncio
import os
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    # Initialize client
    config = DataHubClientConfig(
        base_url=os.getenv("DATAHUB_BASE_URL", "https://api.hub.example.com/api/v1"),
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )
    
    async with DataHubClient(config) as client:
        # List assets
        assets = await client.get("/assets/")
        print(f"Found {assets['count']} assets")
        
        # Create asset
        asset = await client.post("/assets/", {
            "name": "My Asset",
            "description": "Asset description",
            "domain": "marketing"
        })
        print(f"Created asset: {asset['id']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Authentication

#### API Key

```python
config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token="your-api-key",
)
```

#### JWT Token with Auto-Refresh

```python
async def refresh_token():
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            "https://api.hub.example.com/api/v1/auth/refresh/",
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
    # Token will be automatically refreshed when expired
```

### Methods

#### GET Request

```python
# Simple GET
response = await client.get("/assets/")

# GET with query parameters
response = await client.get("/assets/", params={
    "status": "ACTIVE",
    "domain": "marketing",
    "limit": 20,
    "offset": 0
})
```

#### POST Request

```python
# Create resource
asset = await client.post("/assets/", {
    "name": "My Asset",
    "description": "Description",
    "domain": "marketing"
})
```

#### PATCH Request

```python
# Update resource
updated = await client.patch(f"/assets/{asset_id}/", {
    "description": "Updated description"
})
```

#### DELETE Request

```python
# Delete resource
await client.delete(f"/assets/{asset_id}/")
```

### Error Handling

```python
from datahub_interoperability import (
    NotFoundError,
    ValidationError,
    UnauthorizedError,
    RateLimitError,
)

try:
    asset = await client.get(f"/assets/{asset_id}/")
except NotFoundError as e:
    print(f"Asset not found: {e.message}")
    print(f"Request ID: {e.request_id}")
except ValidationError as e:
    print(f"Validation errors: {e.details}")
except UnauthorizedError as e:
    print(f"Authentication required: {e.message}")
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after: {e.retry_after}")
```

### Configuration

```python
config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token="your-api-key",
    max_retries=3,          # Default: 3
    timeout=30.0,            # Default: 30 seconds
    retry_delay=1.0,        # Default: 1 second
    retry_backoff=2.0,      # Default: 2.0 (exponential)
)
```

### Type Hints

The SDK provides full type hints:

```python
from datahub_interoperability import DataHubClient
from typing import Dict, Any, List

async def get_asset(client: DataHubClient, asset_id: str) -> Dict[str, Any]:
    return await client.get(f"/assets/{asset_id}/")

async def list_assets(client: DataHubClient) -> List[Dict[str, Any]]:
    response = await client.get("/assets/")
    return response["results"]
```

### Examples

#### File Upload

```python
# Initialize upload
file_info = await client.post("/files/", {
    "name": "data.csv",
    "size": 1024,
    "content_type": "text/csv"
})

# Upload to pre-signed URL
import httpx
async with httpx.AsyncClient() as http_client:
    async with open("data.csv", "rb") as f:
        await http_client.put(file_info["upload_url"], content=f.read())

# Complete upload
await client.post(f"/files/{file_info['id']}/complete/")
```

#### Pagination

```python
async def get_all_assets(client: DataHubClient):
    all_assets = []
    url = "/assets/"
    
    while url:
        response = await client.get(url)
        all_assets.extend(response["results"])
        url = response.get("next")
    
    return all_assets
```

---

## JavaScript/TypeScript SDK

### Installation

```bash
npm install @datahub/interoperability-sdk
```

### Quick Start

```typescript
import { DataHubClient } from '@datahub/interoperability-sdk';

// Initialize client
const client = new DataHubClient({
  baseUrl: process.env.DATAHUB_BASE_URL || 'https://api.hub.example.com/api/v1',
  apiToken: process.env.DATAHUB_API_TOKEN,
});

// List assets
const assets = await client.assets.list();
console.log(`Found ${assets.count} assets`);

// Create asset
const asset = await client.assets.create({
  name: 'My Asset',
  description: 'Asset description',
  domain: 'marketing',
});
console.log(`Created asset: ${asset.id}`);
```

### Authentication

#### API Key

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: 'your-api-key',
});
```

#### JWT Token with Auto-Refresh

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: initialToken,
});

// Set token refresh callback
client.setTokenRefreshCallback(async () => {
  const response = await fetch('https://api.hub.example.com/api/v1/auth/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token }),
  });
  const data = await response.json();
  return data.access_token;
});
```

### Methods

#### Assets

```typescript
// List assets
const assets = await client.assets.list({
  status: 'ACTIVE',
  domain: 'marketing',
  limit: 20,
  offset: 0,
});

// Get asset
const asset = await client.assets.get('asset-id');

// Create asset
const newAsset = await client.assets.create({
  name: 'My Asset',
  description: 'Description',
  domain: 'marketing',
});

// Update asset
const updated = await client.assets.update('asset-id', {
  description: 'Updated description',
});

// Delete asset
await client.assets.delete('asset-id');
```

#### Files

```typescript
// Initialize upload
const file = await client.files.initUpload({
  name: 'data.csv',
  size: 1024,
  content_type: 'text/csv',
});

// Upload to pre-signed URL
await fetch(file.upload_url, {
  method: 'PUT',
  body: fileData,
});

// Complete upload
await client.files.completeUpload(file.id);
```

### Error Handling

```typescript
import {
  NotFoundError,
  ValidationError,
  UnauthorizedError,
  RateLimitError,
} from '@datahub/interoperability-sdk';

try {
  const asset = await client.assets.get('asset-id');
} catch (error) {
  if (error instanceof NotFoundError) {
    console.log('Asset not found:', error.message);
    console.log('Request ID:', error.requestId);
  } else if (error instanceof ValidationError) {
    console.log('Validation errors:', error.details);
  } else if (error instanceof UnauthorizedError) {
    console.log('Authentication required:', error.message);
  } else if (error instanceof RateLimitError) {
    console.log('Rate limit exceeded. Retry after:', error.retryAfter);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

### Configuration

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: 'your-api-key',
  maxRetries: 3,        // Default: 3
  timeout: 30000,       // Default: 30000ms
  retryDelay: 1000,    // Default: 1000ms
  retryBackoff: 2.0,    // Default: 2.0 (exponential)
});
```

### TypeScript Support

The SDK is written in TypeScript and provides full type definitions:

```typescript
import { Asset, AssetCreateRequest } from '@datahub/interoperability-sdk';

const request: AssetCreateRequest = {
  name: 'My Asset',
  description: 'Description',
  domain: 'marketing',
};

const asset: Asset = await client.assets.create(request);
```

### Examples

#### Pagination

```typescript
async function getAllAssets(client: DataHubClient): Promise<Asset[]> {
  const allAssets: Asset[] = [];
  let nextUrl: string | null = '/assets/';
  
  while (nextUrl) {
    const response = await client.assets.list({ url: nextUrl });
    allAssets.push(...response.results);
    nextUrl = response.next;
  }
  
  return allAssets;
}
```

#### Batch Operations

```typescript
async function createMultipleAssets(
  client: DataHubClient,
  assetData: AssetCreateRequest[]
): Promise<Asset[]> {
  const results = await Promise.all(
    assetData.map(data => client.assets.create(data))
  );
  return results;
}
```

---

## Common Patterns

### Retry Logic

Both SDKs automatically retry transient errors (5xx, network timeouts) with exponential backoff:

```python
# Python - Configure retries
config = DataHubClientConfig(
    max_retries=5,
    retry_delay=1.0,
    retry_backoff=2.0,
)
```

```typescript
// TypeScript - Configure retries
const client = new DataHubClient({
  maxRetries: 5,
  retryDelay: 1000,
  retryBackoff: 2.0,
});
```

### Request Timeouts

```python
# Python
config = DataHubClientConfig(timeout=60.0)  # 60 seconds
```

```typescript
// TypeScript
const client = new DataHubClient({ timeout: 60000 });  // 60 seconds
```

### Custom Headers

```python
# Python
await client.get("/assets/", headers={"X-Custom-Header": "value"})
```

```typescript
// TypeScript
await client.assets.list({ headers: { "X-Custom-Header": "value" } });
```

---

## Error Handling

### Error Types

Both SDKs provide typed error classes:

- `NotFoundError` - Resource not found (404)
- `ValidationError` - Request validation failed (422)
- `UnauthorizedError` - Authentication required (401)
- `ForbiddenError` - Insufficient permissions (403)
- `RateLimitError` - Rate limit exceeded (429)
- `ServerError` - Server error (5xx)
- `NetworkError` - Network/connection error

### Error Properties

All errors include:
- `message` - Human-readable error message
- `code` - Error code
- `requestId` - Unique request ID for debugging
- `details` - Additional error details (for validation errors)

---

## Best Practices

### 1. Use Environment Variables

```python
# Python
import os
config = DataHubClientConfig(
    base_url=os.getenv("DATAHUB_BASE_URL"),
    api_token=os.getenv("DATAHUB_API_TOKEN"),
)
```

```typescript
// TypeScript
const client = new DataHubClient({
  baseUrl: process.env.DATAHUB_BASE_URL,
  apiToken: process.env.DATAHUB_API_TOKEN,
});
```

### 2. Handle Errors Gracefully

```python
# Python
try:
    asset = await client.get(f"/assets/{asset_id}/")
except NotFoundError:
    # Handle not found
    pass
except ValidationError as e:
    # Log validation errors
    logger.error(f"Validation failed: {e.details}")
```

### 3. Use Async Context Managers (Python)

```python
async with DataHubClient(config) as client:
    # Client is automatically closed when exiting context
    assets = await client.get("/assets/")
```

### 4. Implement Pagination

```python
# Python
async def get_all_assets(client):
    all_assets = []
    url = "/assets/"
    while url:
        response = await client.get(url)
        all_assets.extend(response["results"])
        url = response.get("next")
    return all_assets
```

### 5. Cache Tokens

```python
# Python - Cache and reuse tokens
token_cache = {}

async def get_token():
    if "token" not in token_cache or is_expired(token_cache["token"]):
        token_cache["token"] = await refresh_token()
    return token_cache["token"]
```

---

## Support

- **Python SDK**: https://github.com/your-org/datainteroperabilityhub/tree/main/sdk/python
- **JavaScript SDK**: https://github.com/your-org/datainteroperabilityhub/tree/main/sdk/js
- **Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **Documentation**: https://docs.hub.example.com/sdk

---

**Last Updated**: 2025-01-15  
**SDK Version**: 1.0.0

