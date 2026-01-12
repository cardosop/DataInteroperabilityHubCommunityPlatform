# BaaS (Backend as a Service) Usage Guide

This guide provides comprehensive documentation for using BaaS functionality in the DataHub Interoperability Python SDK.

## Table of Contents

1. [Introduction](#introduction)
2. [BaaS Concepts](#baas-concepts)
3. [Getting Started](#getting-started)
4. [API Key Management](#api-key-management)
5. [Usage Tracking](#usage-tracking)
6. [Developer Portal](#developer-portal)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Examples](#examples)

## Introduction

The BaaS (Backend as a Service) platform provides API key management, usage tracking, and developer portal access for building applications on top of the DataHub platform. The SDK provides comprehensive support for all BaaS operations.

### Key Features

- **API Key Management**: Create, list, update, and revoke API keys with tier-based access control
- **Usage Tracking**: Monitor API usage statistics by API key, endpoint, and tenant
- **Developer Portal**: Access API documentation, OpenAPI schemas, and SDK download links
- **Quota Management**: Check rate limits and remaining quota for API keys
- **Tier-Based Access**: FREE, PRO, and ENTERPRISE tiers with different rate limits

## BaaS Concepts

### API Keys

API keys are authentication credentials that allow applications to access the DataHub API. Each API key:
- Has a unique name and ID (UUID format)
- Belongs to a tier (FREE, PRO, ENTERPRISE)
- Can have an optional expiration date (ISO format)
- Can be revoked (soft delete) for security
- The plaintext key value is shown only once during creation

### API Tiers

- **FREE**: 1,000 requests/hour, 10,000 requests/day, 10,000 requests/month
- **PRO**: 10,000 requests/hour, 100,000 requests/day, 100,000 requests/month
- **ENTERPRISE**: Unlimited requests (custom limits)

### Usage Tracking

Usage tracking provides insights into API consumption:
- **Statistics**: Total requests, successful requests, failed requests, success rate, average response time
- **By Endpoint**: Usage breakdown by API endpoint and HTTP method
- **By Tenant**: Aggregated usage across all API keys for a tenant (admin only)
- **Time Ranges**: Filter usage by date ranges (ISO format)

### Developer Portal

The developer portal provides resources for API integration:
- **API Documentation**: Overview of API endpoints, authentication, and rate limiting
- **OpenAPI Schema**: Complete API specification in JSON or YAML format
- **SDK Downloads**: Download links for Python and JavaScript SDKs

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
        # Access BaaS API
        baas_api = client.baas
        # ... your code here

if __name__ == "__main__":
    asyncio.run(main())
```

## API Key Management

### Create API Key

Create a new API key for API access.

```python
# Create API key with default FREE tier
api_key = await client.baas.create_api_key(
    name="My API Key",
)

# Create API key with PRO tier
api_key = await client.baas.create_api_key(
    name="Production Key",
    tier="PRO",
)

# Create API key with expiration date
from datetime import datetime, timezone, timedelta
expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

api_key = await client.baas.create_api_key(
    name="Temporary Key",
    tier="FREE",
    expires_at=expires_at,
)

# Access API key data
print(f"API Key ID: {api_key['id']}")
print(f"API Key Value: {api_key['api_key']}")  # Shown only once!
print(f"Tier: {api_key['tier']}")
print(f"Created At: {api_key['created_at']}")

# Important: Save the API key value securely
# It cannot be retrieved later
```

**Response Structure**:
```python
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "My API Key",
    "api_key": "dh_live_abc123xyz789...",  # Shown only once!
    "tier": "FREE",
    "expires_at": None,  # or ISO date string
    "created_at": "2025-01-12T10:30:00Z"
}
```

### List API Keys

List all API keys with optional filtering.

```python
# List all API keys
api_keys = await client.baas.list_api_keys()

# List API keys with tier filter
pro_keys = await client.baas.list_api_keys(tier="PRO")

# List API keys with pagination
api_keys = await client.baas.list_api_keys(
    limit=20,
    offset=0,
)

# Process API keys
for api_key in api_keys:
    print(f"ID: {api_key['id']}")
    print(f"Name: {api_key['name']}")
    print(f"Tier: {api_key['tier']}")
    print(f"Status: {'ACTIVE' if api_key.get('is_active') else 'INACTIVE'}")
    print(f"Expires At: {api_key.get('expires_at', 'Never')}")
```

**Response Structure**:
```python
[
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "My API Key",
        "tier": "FREE",
        "is_active": True,
        "expires_at": None,
        "created_at": "2025-01-12T10:30:00Z"
        # Note: api_key field is NOT included for security
    },
    ...
]
```

### Get API Key Details

Get detailed information about a specific API key.

```python
api_key_id = "123e4567-e89b-12d3-a456-426614174000"

# Get API key details
api_key = await client.baas.get_api_key(api_key_id)

print(f"ID: {api_key['id']}")
print(f"Name: {api_key['name']}")
print(f"Tier: {api_key['tier']}")
print(f"Status: {'ACTIVE' if api_key.get('is_active') else 'INACTIVE'}")
print(f"Expires At: {api_key.get('expires_at', 'Never')}")
print(f"Created At: {api_key['created_at']}")
print(f"Updated At: {api_key.get('updated_at')}")

# Security: API key value is never included in get response
```

**Note**: The API key value is never returned in the `get_api_key` response for security reasons. Only metadata is provided.

### Update API Key

Update API key name, tier, or expiration date.

```python
api_key_id = "123e4567-e89b-12d3-a456-426614174000"

# Update API key name
updated = await client.baas.update_api_key(
    api_key_id,
    name="Updated Name",
)

# Update API key tier
updated = await client.baas.update_api_key(
    api_key_id,
    tier="PRO",
)

# Update expiration date
from datetime import datetime, timezone, timedelta
new_expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

updated = await client.baas.update_api_key(
    api_key_id,
    expires_at=new_expires_at,
)

# Update multiple fields
updated = await client.baas.update_api_key(
    api_key_id,
    name="Updated Name",
    tier="PRO",
    expires_at=new_expires_at,
)

print(f"Updated API key: {updated['id']}")
print(f"New name: {updated['name']}")
print(f"New tier: {updated['tier']}")
```

**Note**: At least one field (`name`, `tier`, or `expires_at`) must be provided.

### Revoke API Key

Revoke (soft delete) an API key to prevent further API access.

```python
api_key_id = "123e4567-e89b-12d3-a456-426614174000"

# Revoke API key
await client.baas.revoke_api_key(api_key_id)

print("API key revoked successfully")
```

**Note**: Revoked API keys are soft-deleted and cannot be used for authentication, but their metadata is retained for audit purposes.

### Check Quota

Check rate limit and remaining quota for an API key.

```python
api_key_id = "123e4567-e89b-12d3-a456-426614174000"

# Check quota
quota = await client.baas.check_quota(api_key_id)

print(f"Tier: {quota['tier']}")
print(f"Rate Limit (per hour): {quota['rate_limit_per_hour']}")
print(f"Rate Limit (per day): {quota['rate_limit_per_day']}")
print(f"Current Usage (hour): {quota['current_usage_hour']}")
print(f"Remaining (hour): {quota['remaining_hour']}")
print(f"Current Usage (day): {quota['current_usage_day']}")
print(f"Remaining (day): {quota['remaining_day']}")
```

**Response Structure**:
```python
{
    "api_key_id": "123e4567-e89b-12d3-a456-426614174000",
    "tier": "FREE",
    "rate_limit_per_hour": 1000,
    "rate_limit_per_day": 10000,
    "max_requests_per_month": 10000,
    "current_usage_hour": 150,
    "current_usage_day": 1200,
    "current_usage_month": 8500,
    "remaining_hour": 850,
    "remaining_day": 8800,
    "remaining_month": 1500
}
```

## Usage Tracking

### Get Usage Statistics

Get overall API usage statistics with optional filtering.

```python
# Get all usage statistics
stats = await client.baas.get_usage_stats()

# Get usage statistics for specific API key
stats = await client.baas.get_usage_stats(
    api_key_id="123e4567-e89b-12d3-a456-426614174000",
)

# Get usage statistics for date range
from datetime import datetime, timezone
start_date = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
end_date = datetime(2025, 1, 31, tzinfo=timezone.utc).isoformat()

stats = await client.baas.get_usage_stats(
    start_date=start_date,
    end_date=end_date,
)

# Process statistics
print(f"Total Requests: {stats['total_requests']}")
print(f"Successful Requests: {stats['success_count']}")
print(f"Failed Requests: {stats['error_count']}")
print(f"Success Rate: {stats['success_rate']}%")
print(f"Average Response Time: {stats['avg_response_time_ms']}ms")
```

**Response Structure**:
```python
{
    "total_requests": 15234,
    "success_count": 14890,
    "error_count": 344,
    "success_rate": 97.7,
    "avg_response_time_ms": 145,
    "total_request_bytes": 5242880,
    "total_response_bytes": 10485760
}
```

### Get Usage by Endpoint

Get usage statistics broken down by API endpoint.

```python
# Get usage by endpoint
endpoint_stats = await client.baas.get_usage_by_endpoint()

# Get usage by endpoint for specific API key
endpoint_stats = await client.baas.get_usage_by_endpoint(
    api_key_id="123e4567-e89b-12d3-a456-426614174000",
)

# Get usage by endpoint for date range
endpoint_stats = await client.baas.get_usage_by_endpoint(
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-01-31T23:59:59Z",
)

# Process endpoint statistics
for endpoint_stat in endpoint_stats:
    print(f"Endpoint: {endpoint_stat['endpoint']}")
    print(f"Method: {endpoint_stat['method']}")
    print(f"Requests: {endpoint_stat['request_count']}")
    print(f"Success: {endpoint_stat['success_count']}")
    print(f"Failed: {endpoint_stat['error_count']}")
    print(f"Avg Response Time: {endpoint_stat['avg_response_time_ms']}ms")
```

**Response Structure**:
```python
[
    {
        "endpoint": "/api/v1/assets/",
        "method": "GET",
        "request_count": 5234,
        "success_count": 5120,
        "error_count": 114,
        "avg_response_time_ms": 120
    },
    ...
]
```

### Get Usage by Tenant

Get aggregated usage statistics for the entire tenant (admin only).

```python
# Get usage by tenant
tenant_stats = await client.baas.get_usage_by_tenant()

# Get usage by tenant for date range
tenant_stats = await client.baas.get_usage_by_tenant(
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-01-31T23:59:59Z",
)

# Process tenant statistics
for tenant_stat in tenant_stats:
    print(f"Tenant ID: {tenant_stat['tenant_id']}")
    print(f"Tenant Name: {tenant_stat['tenant_name']}")
    print(f"Total Requests: {tenant_stat['total_requests']}")
    print(f"Success Count: {tenant_stat['success_count']}")
    print(f"Error Count: {tenant_stat['error_count']}")
    print(f"Avg Response Time: {tenant_stat['avg_response_time_ms']}ms")
```

**Response Structure**:
```python
[
    {
        "tenant_id": "tenant-uuid",
        "tenant_name": "Tenant Name",
        "total_requests": 50000,
        "success_count": 49000,
        "error_count": 1000,
        "avg_response_time_ms": 150
    },
    ...
]
```

## Developer Portal

### Get API Documentation

Get API documentation overview.

```python
# Get API documentation as JSON
docs_json = await client.baas.get_api_docs(format="json")
docs_data = json.loads(docs_json)

print(f"Title: {docs_data['title']}")
print(f"Version: {docs_data['version']}")
print(f"Endpoints: {docs_data['endpoints']}")
print(f"Authentication: {docs_data['authentication']}")
print(f"Rate Limiting: {docs_data['rate_limiting']}")

# Get API documentation as HTML
docs_html = await client.baas.get_api_docs(format="html")
# Save to file or display in browser
with open("api-docs.html", "w") as f:
    f.write(docs_html)
```

**Response Structure (JSON)**:
```python
{
    "title": "Data Interoperability Hub API Documentation",
    "version": "1.0.0",
    "description": "REST API for the Data Interoperability Hub platform",
    "base_url": "https://api.hub.example.com",
    "endpoints": {
        "openapi_schema": "https://api.hub.example.com/api/v1/baas/docs/openapi.json",
        "openapi_yaml": "https://api.hub.example.com/api-docs/openapi.yaml",
        "swagger_ui": "https://api.hub.example.com/api-docs/",
        "redoc": "https://api.hub.example.com/api-docs/redoc/",
        "sdks": "https://api.hub.example.com/api/v1/baas/docs/sdks/"
    },
    "authentication": {
        "type": "API Key",
        "header": "X-API-Key or Authorization: ApiKey <key>",
        "description": "Include your API key in the X-API-Key header or Authorization header"
    },
    "rate_limiting": {
        "description": "Rate limits are applied per tier (FREE, PRO, ENTERPRISE)",
        "tiers": {
            "FREE": "1000 requests/hour",
            "PRO": "10000 requests/hour",
            "ENTERPRISE": "Unlimited"
        }
    }
}
```

### Get OpenAPI Schema

Get the OpenAPI 3.0 schema for the API.

```python
# Get OpenAPI schema as JSON (dictionary)
openapi_json = await client.baas.get_openapi_schema(format="json")

print(f"OpenAPI Version: {openapi_json['openapi']}")
print(f"Info: {openapi_json['info']}")
print(f"Paths: {list(openapi_json['paths'].keys())}")

# Get OpenAPI schema as YAML (string)
openapi_yaml = await client.baas.get_openapi_schema(format="yaml")

# Save to file
with open("openapi.yaml", "w") as f:
    f.write(openapi_yaml)
```

**Note**: YAML format requires PyYAML. If not installed, a `BaaSValidationError` will be raised with installation instructions.

**Response Structure (JSON)**:
```python
{
    "openapi": "3.0.3",
    "info": {
        "title": "Data Interoperability Hub API",
        "version": "1.0.0"
    },
    "paths": {
        "/api/v1/assets/": {
            "get": {
                "summary": "List assets",
                ...
            }
        },
        ...
    }
}
```

### Get SDK Download Links

Get download links for SDKs in various languages.

```python
# Get SDK download links
sdks = await client.baas.get_sdk_download_links()

# Access Python SDK
if "python" in sdks:
    python_sdk = sdks["python"]
    print(f"Python SDK Name: {python_sdk['name']}")
    print(f"Download URL: {python_sdk['download_url']}")
    print(f"Install Command: {python_sdk['install_command']}")

# Access JavaScript SDK
if "javascript" in sdks:
    js_sdk = sdks["javascript"]
    print(f"JavaScript SDK Name: {js_sdk['name']}")
    print(f"Download URL: {js_sdk['download_url']}")
    print(f"Install Command: {js_sdk['install_command']}")
```

**Response Structure**:
```python
{
    "python": {
        "name": "Python SDK",
        "language": "python",
        "download_url": "https://api.hub.example.com/api/v1/baas/docs/sdks/python/",
        "install_command": "pip install datahub-sdk",
        "documentation": "https://api.hub.example.com/api/v1/baas/docs/sdks/python/"
    },
    "javascript": {
        "name": "JavaScript/TypeScript SDK",
        "language": "javascript",
        "download_url": "https://api.hub.example.com/api/v1/baas/docs/sdks/javascript/",
        "install_command": "npm install @datahub/sdk",
        "documentation": "https://api.hub.example.com/api/v1/baas/docs/sdks/javascript/"
    }
}
```

## Error Handling

### BaaS Error Classes

The SDK provides specialized BaaS error classes:

```python
from datahub_interoperability.errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
    ForbiddenError,
)
```

### Common Error Scenarios

#### Invalid API Key ID

```python
try:
    api_key = await client.baas.get_api_key("invalid-id")
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except NotFoundError as e:
    print(f"API key not found: {e.message}")
```

#### Empty API Key Name

```python
try:
    api_key = await client.baas.create_api_key(name="")
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
```

#### Invalid Expiration Date

```python
try:
    api_key = await client.baas.create_api_key(
        name="Key",
        expires_at="2020-01-01"  # Past date
    )
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
```

#### Missing Update Fields

```python
try:
    updated = await client.baas.update_api_key(api_key_id)
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    # Error: At least one field (name, tier, expires_at) must be provided
```

#### YAML Format Unavailable

```python
try:
    openapi_yaml = await client.baas.get_openapi_schema(format="yaml")
except BaaSValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    # Error: yaml format requires PyYAML package
    # Install with: pip install pyyaml
```

### Error Response Structure

All BaaS errors follow a consistent structure:

```python
try:
    result = await client.baas.create_api_key(name="")
except BaaSValidationError as e:
    # Error attributes
    print(e.message)        # Human-readable error message
    print(e.error_code)     # Machine-readable error code
    print(e.field_path)     # JSON path to invalid field
    print(e.expected)       # Expected value/type
    print(e.actual)         # Actual value/type
    print(e.details)        # Additional error details
except BaaSError as e:
    # Base BaaS error
    print(e.message)
    print(e.error_code)
    print(e.http_status)
    print(e.request_id)
    print(e.details)
```

## Best Practices

### API Key Security

1. **Store Securely**: Save API keys in environment variables or secure key management systems
2. **Never Commit**: Never commit API keys to version control
3. **Rotate Regularly**: Rotate API keys periodically for security
4. **Use Expiration**: Set expiration dates for temporary API keys
5. **Revoke Unused**: Revoke API keys that are no longer needed

```python
import os

# Store API key in environment variable
api_key = os.getenv("DATAHUB_API_KEY")

# Use in client configuration
config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token=api_key,
)
```

### Usage Monitoring

1. **Monitor Regularly**: Check usage statistics regularly to identify trends
2. **Set Alerts**: Set up alerts for approaching rate limits
3. **Track by Endpoint**: Monitor endpoint usage to optimize API calls
4. **Review Quota**: Check quota before making large batches of requests

```python
# Check quota before making requests
quota = await client.baas.check_quota(api_key_id)
if quota['remaining_hour'] < 100:
    print("Warning: Approaching rate limit")
    # Implement backoff or wait

# Monitor usage after operations
stats = await client.baas.get_usage_stats(api_key_id=api_key_id)
print(f"Success rate: {stats['success_rate']}%")
if stats['success_rate'] < 95:
    print("Warning: Low success rate")
```

### Error Handling

1. **Handle Validation Errors**: Always validate input before API calls
2. **Check Quota**: Check quota before operations to avoid rate limit errors
3. **Retry Logic**: Implement retry logic for transient errors
4. **Log Errors**: Log errors with context for debugging

```python
async def create_api_key_safely(client, name: str, tier: str = "FREE"):
    """Create API key with comprehensive error handling"""
    try:
        # Validate input
        if not name or not name.strip():
            raise ValueError("API key name cannot be empty")

        # Create API key
        api_key = await client.baas.create_api_key(name=name, tier=tier)

        # Log success
        print(f"Created API key: {api_key['id']}")

        return api_key
    except BaaSValidationError as e:
        print(f"Validation error: {e.message}")
        print(f"Field: {e.field_path}")
        raise
    except BaaSError as e:
        print(f"BaaS error: {e.message}")
        print(f"Error code: {e.error_code}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

## Examples

### Example 1: Complete API Key Lifecycle

```python
import asyncio
from datetime import datetime, timezone, timedelta
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def api_key_lifecycle():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # 1. Create API key
        api_key = await client.baas.create_api_key(
            name="Production Key",
            tier="PRO",
        )
        api_key_id = api_key['id']
        api_key_value = api_key['api_key']
        print(f"Created API key: {api_key_id}")
        print(f"API Key value: {api_key_value}")  # Save this!

        # 2. List API keys
        api_keys = await client.baas.list_api_keys(tier="PRO")
        print(f"Found {len(api_keys)} PRO tier API keys")

        # 3. Get API key details
        api_key_details = await client.baas.get_api_key(api_key_id)
        print(f"API Key Name: {api_key_details['name']}")
        print(f"Tier: {api_key_details['tier']}")

        # 4. Check quota
        quota = await client.baas.check_quota(api_key_id)
        print(f"Rate Limit (hour): {quota['rate_limit_per_hour']}")
        print(f"Remaining (hour): {quota['remaining_hour']}")

        # 5. Update API key
        expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        updated = await client.baas.update_api_key(
            api_key_id,
            expires_at=expires_at,
        )
        print(f"Updated expiration: {updated.get('expires_at')}")

        # 6. Monitor usage
        stats = await client.baas.get_usage_stats(api_key_id=api_key_id)
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {stats['success_rate']}%")

        # 7. Revoke API key (when no longer needed)
        # await client.baas.revoke_api_key(api_key_id)
        # print("API key revoked")

if __name__ == "__main__":
    asyncio.run(api_key_lifecycle())
```

### Example 2: Usage Monitoring Dashboard

```python
async def usage_dashboard():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Get overall statistics
        stats = await client.baas.get_usage_stats()
        print("=== Overall Statistics ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {stats['success_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']}ms")

        # Get usage by endpoint
        endpoint_stats = await client.baas.get_usage_by_endpoint()
        print("\n=== Top Endpoints ===")
        sorted_endpoints = sorted(
            endpoint_stats,
            key=lambda x: x['request_count'],
            reverse=True
        )[:10]

        for endpoint_stat in sorted_endpoints:
            print(f"{endpoint_stat['endpoint']} ({endpoint_stat['method']})")
            print(f"  Requests: {endpoint_stat['request_count']}")
            print(f"  Success Rate: {(endpoint_stat['success_count'] / endpoint_stat['request_count'] * 100):.1f}%")
            print(f"  Avg Response Time: {endpoint_stat['avg_response_time_ms']}ms")

        # Get quota for all API keys
        api_keys = await client.baas.list_api_keys()
        print("\n=== API Key Quotas ===")
        for api_key in api_keys:
            quota = await client.baas.check_quota(api_key['id'])
            print(f"{api_key['name']} ({api_key['tier']})")
            print(f"  Used: {quota['current_usage_hour']}/{quota['rate_limit_per_hour']} (hour)")
            print(f"  Remaining: {quota['remaining_hour']} (hour)")

if __name__ == "__main__":
    asyncio.run(usage_dashboard())
```

### Example 3: Developer Portal Integration

```python
async def developer_portal_integration():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Get API documentation
        docs_json = await client.baas.get_api_docs(format="json")
        docs_data = json.loads(docs_json)

        print("=== API Documentation ===")
        print(f"Title: {docs_data['title']}")
        print(f"Version: {docs_data['version']}")
        print(f"\nEndpoints:")
        for key, url in docs_data['endpoints'].items():
            print(f"  {key}: {url}")

        # Get OpenAPI schema
        openapi_json = await client.baas.get_openapi_schema(format="json")
        print(f"\n=== OpenAPI Schema ===")
        print(f"Version: {openapi_json['openapi']}")
        print(f"Paths: {len(openapi_json['paths'])} endpoints")

        # Save OpenAPI schema to file
        with open("openapi.json", "w") as f:
            json.dump(openapi_json, f, indent=2)
        print("Saved OpenAPI schema to openapi.json")

        # Get SDK download links
        sdks = await client.baas.get_sdk_download_links()
        print(f"\n=== Available SDKs ===")
        for lang, sdk_info in sdks.items():
            print(f"{lang}:")
            print(f"  Name: {sdk_info['name']}")
            print(f"  Install: {sdk_info['install_command']}")
            print(f"  Download: {sdk_info['download_url']}")

if __name__ == "__main__":
    asyncio.run(developer_portal_integration())
```

### Example 4: Error Handling and Retry Logic

```python
import asyncio
from datahub_interoperability.errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
    RateLimitError,
)

async def create_api_key_with_retry(client, name: str, max_retries: int = 3):
    """Create API key with retry logic for rate limit errors"""
    for attempt in range(max_retries):
        try:
            # Check quota before creating
            # (Note: This requires an existing API key, so skip for first key)

            # Create API key
            api_key = await client.baas.create_api_key(name=name)
            return api_key
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                raise
        except BaaSValidationError as e:
            print(f"Validation error: {e.message}")
            print(f"Field: {e.field_path}")
            raise
        except BaaSError as e:
            print(f"BaaS error: {e.message}")
            print(f"Error code: {e.error_code}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

    raise Exception("Failed to create API key after retries")

if __name__ == "__main__":
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        api_key = await create_api_key_with_retry(client, "My API Key")
        print(f"Created API key: {api_key['id']}")
```

## Additional Resources

- **[SDK README](../README.md)** - Complete SDK documentation
- **[ODPS Usage Guide](ODPS_USAGE.md)** - ODPS contract management
- **[Marketplace Usage Guide](MARKETPLACE_USAGE.md)** - Marketplace integration
- **[API Reference](../../../docs/API_REFERENCE.md)** - Complete API documentation
