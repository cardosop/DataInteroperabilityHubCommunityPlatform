# BaaS (Backend as a Service) CLI Usage Guide

Complete guide for using BaaS commands in the DataHub CLI.

## Table of Contents

1. [Overview](#overview)
2. [BaaS Concepts](#baas-concepts)
3. [API Key Management](#api-key-management)
4. [Usage Tracking](#usage-tracking)
5. [Developer Portal Documentation](#developer-portal-documentation)
6. [Common Workflows](#common-workflows)
7. [Error Handling](#error-handling)
8. [Troubleshooting](#troubleshooting)

## Overview

The DataHub CLI provides comprehensive support for BaaS (Backend as a Service) platform operations. BaaS enables you to manage API keys, track usage, and access developer portal resources for building applications on top of the DataHub platform.

### Key Features

- **API Key Management**: Create, list, update, and revoke API keys with tier-based access control
- **Usage Tracking**: Monitor API usage statistics by API key, endpoint, and tenant
- **Developer Portal**: Access API documentation, OpenAPI schemas, and SDK download links
- **Tier-Based Access**: FREE, PRO, and ENTERPRISE tiers with different rate limits and features

### API Tiers

- **FREE**: 1,000 requests/hour, 10,000 requests/day, 10,000 requests/month
- **PRO**: 10,000 requests/hour, 100,000 requests/day, 100,000 requests/month
- **ENTERPRISE**: Unlimited requests (custom limits)

## BaaS Concepts

### API Keys

API keys are authentication credentials that allow applications to access the DataHub API. Each API key:
- Has a unique name and ID
- Belongs to a tier (FREE, PRO, ENTERPRISE)
- Can have an optional expiration date
- Can be revoked (soft delete) for security

### Usage Tracking

Usage tracking provides insights into API consumption:
- **Statistics**: Total requests, successful requests, failed requests
- **By Endpoint**: Usage breakdown by API endpoint
- **By Tenant**: Aggregated usage across all API keys for a tenant
- **Time Ranges**: Filter usage by date ranges

### Developer Portal

The developer portal provides resources for API integration:
- **API Documentation**: Overview of API endpoints, authentication, and rate limiting
- **OpenAPI Schema**: Complete API specification in JSON or YAML format
- **SDK Downloads**: Download links for Python and JavaScript SDKs

## API Key Management

### Create API Key

Create a new API key for API access.

```bash
# Create API key with default FREE tier
datahub baas api-keys create --name "My API Key"

# Create API key with PRO tier
datahub baas api-keys create \
  --name "Production Key" \
  --tier PRO

# Create API key with expiration date
datahub baas api-keys create \
  --name "Temporary Key" \
  --tier FREE \
  --expires-at "2025-12-31T23:59:59Z"

# Create API key with JSON output
datahub baas api-keys create \
  --name "My API Key" \
  --format json
```

**Example Output (Table)**:
```
API key created successfully!

⚠️  IMPORTANT: Save this API key securely. It will not be shown again.

ID: 123e4567-e89b-12d3-a456-426614174000
Name: My API Key
API Key: dh_live_abc123xyz789...
Tier: FREE
Created At: 2025-01-12T10:30:00Z

💡 Use this API key with: datahub config set api_key <key>
```

**Example Output (JSON)**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My API Key",
  "api_key": "dh_live_abc123xyz789...",
  "tier": "FREE",
  "expires_at": null,
  "created_at": "2025-01-12T10:30:00Z"
}
```

**Important Notes**:
- The API key value is shown **only once** during creation
- Save the API key securely - it cannot be retrieved later
- Use `datahub config set api_key <key>` to configure it for CLI use

### List API Keys

List all API keys with optional filtering.

```bash
# List all API keys (table format)
datahub baas api-keys list

# List API keys with tier filter
datahub baas api-keys list --tier PRO

# List API keys with pagination
datahub baas api-keys list --limit 10 --offset 20

# List API keys in JSON format
datahub baas api-keys list --format json
```

**Example Output (Table)**:
```
ID                                     Name                          Tier        Status      Expires At
-------------------------------------- ----------------------------- ----------- ----------- --------------------
123e4567-e89b-12d3-a456-426614174000  My API Key                    FREE        ACTIVE      Never
223e4567-e89b-12d3-a456-426614174000  Production Key                PRO         ACTIVE      2025-12-31 23:59
323e4567-e89b-12d3-a456-426614174000  Temporary Key                 FREE        INACTIVE    2025-01-01 00:00

Showing 3 of 3 API keys
```

### Get API Key Details

Get detailed information about a specific API key.

```bash
# Get API key details (table format)
datahub baas api-keys get <api-key-id>

# Get API key details in JSON format
datahub baas api-keys get <api-key-id> --format json
```

**Example Output (Table)**:
```
ID: 123e4567-e89b-12d3-a456-426614174000
Name: My API Key
Tier: FREE
Status: ACTIVE
Expires At: Never
Created At: 2025-01-12T10:30:00Z
Updated At: 2025-01-12T10:30:00Z

Note: API key value is not displayed for security reasons.
```

**Security Note**: The API key value is never displayed in the `get` command for security reasons. Only metadata is shown.

### Update API Key

Update API key name, tier, or expiration date.

```bash
# Update API key name
datahub baas api-keys update <api-key-id> --name "Updated Name"

# Update API key tier
datahub baas api-keys update <api-key-id> --tier PRO

# Update expiration date
datahub baas api-keys update <api-key-id> \
  --expires-at "2026-12-31T23:59:59Z"

# Update multiple fields
datahub baas api-keys update <api-key-id> \
  --name "Updated Name" \
  --tier PRO \
  --expires-at "2026-12-31T23:59:59Z"
```

**Note**: At least one field (`--name`, `--tier`, or `--expires-at`) must be provided.

### Revoke API Key

Revoke (soft delete) an API key to prevent further API access.

```bash
# Revoke API key
datahub baas api-keys revoke <api-key-id>

# Revoke API key with JSON output
datahub baas api-keys revoke <api-key-id> --format json
```

**Example Output**:
```
API key revoked successfully: 123e4567-e89b-12d3-a456-426614174000
```

**Note**: Revoked API keys are soft-deleted and cannot be used for authentication, but their metadata is retained for audit purposes.

## Usage Tracking

### Get Usage Statistics

Get overall API usage statistics with optional filtering.

```bash
# Get usage statistics (table format)
datahub baas usage stats

# Get usage statistics for specific API key
datahub baas usage stats --api-key-id <api-key-id>

# Get usage statistics for date range
datahub baas usage stats \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage statistics in JSON format
datahub baas usage stats --format json
```

**Example Output (Table)**:
```
Period: 2025-01-01 to 2025-01-31
Total Requests: 15,234
Successful Requests: 14,890
Failed Requests: 344
Success Rate: 97.7%
Average Response Time: 145ms
```

### Get Usage by Endpoint

Get usage statistics broken down by API endpoint.

```bash
# Get usage by endpoint (table format)
datahub baas usage by-endpoint

# Get usage by endpoint for specific API key
datahub baas usage by-endpoint --api-key-id <api-key-id>

# Get usage by endpoint for date range
datahub baas usage by-endpoint \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage by endpoint in JSON format
datahub baas usage by-endpoint --format json
```

**Example Output (Table)**:
```
Endpoint                          Requests    Success    Failed    Avg Response Time
--------------------------------- ----------- ---------- ---------- -------------------
/api/v1/assets/                   5,234       5,120      114       120ms
/api/v1/contracts/                 4,567       4,523      44        180ms
/api/v1/files/                     3,123       3,045      78        95ms
/api/v1/baas/api-keys/             2,310       2,202      108       210ms
```

### Get Usage by Tenant

Get aggregated usage statistics for the entire tenant.

```bash
# Get usage by tenant (table format)
datahub baas usage by-tenant

# Get usage by tenant for date range
datahub baas usage by-tenant \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage by tenant in JSON format
datahub baas usage by-tenant --format json
```

## Developer Portal Documentation

### Show API Documentation

Display API documentation overview with links to OpenAPI schema and SDKs.

```bash
# Show API documentation (default: HTML format)
datahub baas docs show

# Show API documentation in JSON format
datahub baas docs show --format json

# Show API documentation in HTML format
datahub baas docs show --format html

# Show API documentation in Markdown format
datahub baas docs show --format markdown
```

**Example Output (HTML)**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Data Interoperability Hub API Documentation</title>
    ...
</head>
<body>
    <h1>Data Interoperability Hub API Documentation</h1>
    <p><strong>Version:</strong> 1.0.0</p>
    ...
</body>
</html>
```

**Example Output (JSON)**:
```json
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

Display the OpenAPI 3.0 schema for the API.

```bash
# Get OpenAPI schema (default: JSON format)
datahub baas docs openapi

# Get OpenAPI schema in JSON format
datahub baas docs openapi --format json

# Get OpenAPI schema in YAML format
datahub baas docs openapi --format yaml
```

**Note**: YAML format requires PyYAML. If not installed, the command will show an error with installation instructions.

**Example Output (JSON)**:
```json
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
    }
  }
}
```

### Get SDK Download Links

Display download links for SDKs in various languages.

```bash
# List SDK download links (default: table format)
datahub baas docs sdks

# List SDK download links in JSON format
datahub baas docs sdks --format json
```

**Example Output (Table)**:
```
Language             Name                           Install Command                    Download URL
-------------------- ------------------------------ ----------------------------------- --------------------------------------------------
python               Python SDK                      pip install datahub-sdk            https://api.hub.example.com/api/v1/baas/docs/sdks/python/
javascript           JavaScript/TypeScript SDK       npm install @datahub/sdk            https://api.hub.example.com/api/v1/baas/docs/sdks/javascript/

💡 Use the download URLs to get SDK code, or use install commands for package managers.
```

**Example Output (JSON)**:
```json
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

## Common Workflows

### Workflow 1: Create API Key and Configure CLI

Complete workflow for creating an API key and using it with the CLI.

```bash
# 1. Create API key
datahub baas api-keys create --name "CLI Key" --tier FREE

# Output shows the API key value - save it!
# API Key: dh_live_abc123xyz789...

# 2. Configure CLI to use the API key
datahub config set api_key dh_live_abc123xyz789...

# 3. Verify configuration
datahub config get

# 4. Test API access
datahub assets list
```

### Workflow 2: Monitor API Usage

Monitor API usage and identify high-traffic endpoints.

```bash
# 1. Get overall usage statistics
datahub baas usage stats

# 2. Get usage breakdown by endpoint
datahub baas usage by-endpoint

# 3. Get usage for specific date range
datahub baas usage stats \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# 4. Get usage for specific API key
datahub baas usage stats --api-key-id <api-key-id>
```

### Workflow 3: Manage API Keys Lifecycle

Complete lifecycle management of API keys.

```bash
# 1. Create API key for development
DEV_KEY_ID=$(datahub baas api-keys create \
  --name "Development Key" \
  --tier FREE \
  --format json | jq -r '.id')

# 2. Create API key for production with expiration
PROD_KEY_ID=$(datahub baas api-keys create \
  --name "Production Key" \
  --tier PRO \
  --expires-at "2025-12-31T23:59:59Z" \
  --format json | jq -r '.id')

# 3. List all API keys
datahub baas api-keys list

# 4. Update production key tier if needed
datahub baas api-keys update $PROD_KEY_ID --tier ENTERPRISE

# 5. Revoke development key when no longer needed
datahub baas api-keys revoke $DEV_KEY_ID
```

### Workflow 4: Access Developer Resources

Access API documentation and SDKs for integration.

```bash
# 1. Get API documentation overview
datahub baas docs show --format json > api-docs.json

# 2. Download OpenAPI schema
datahub baas docs openapi --format json > openapi.json

# 3. Get SDK download links
datahub baas docs sdks --format json > sdks.json

# 4. Use OpenAPI schema with code generators
# (e.g., openapi-generator, swagger-codegen)
```

## Error Handling

### Common Errors

#### Invalid API Key ID

```bash
$ datahub baas api-keys get invalid-id
Error: API key not found: invalid-id
Error Code: API_KEY_NOT_FOUND
Suggestion: Check that the API key ID is correct
```

**Solution**: Verify the API key ID is a valid UUID format.

#### Empty API Key Name

```bash
$ datahub baas api-keys create --name ""
Error: API key name cannot be empty
Error Code: INVALID_NAME
Suggestion: Provide a non-empty name for the API key
```

**Solution**: Provide a non-empty name for the API key.

#### Invalid Expiration Date

```bash
$ datahub baas api-keys create --name "Key" --expires-at "2020-01-01"
Error: Expiration date must be in the future
Error Code: INVALID_EXPIRATION_DATE
Suggestion: Provide a future date in ISO format (e.g., 2025-12-31T23:59:59Z)
```

**Solution**: Use ISO format with future date: `2025-12-31T23:59:59Z`

#### Missing Update Fields

```bash
$ datahub baas api-keys update <api-key-id>
Error: At least one field (--name, --tier, or --expires-at) must be provided
Error Code: MISSING_UPDATE_FIELDS
Suggestion: Provide at least one field to update
```

**Solution**: Provide at least one field to update: `--name`, `--tier`, or `--expires-at`.

#### YAML Format Unavailable

```bash
$ datahub baas docs openapi --format yaml
Error: YAML format requires PyYAML. Please install it with: pip install pyyaml
Error Code: YAML_FORMAT_UNAVAILABLE
Suggestion: Install PyYAML or use JSON format
```

**Solution**: Install PyYAML: `pip install pyyaml` or use JSON format instead.

### Error Response Format

All BaaS errors follow a consistent format:

```json
{
  "error": {
    "message": "Human-readable error message",
    "code": "ERROR_CODE",
    "context": {
      "field": "value"
    },
    "suggestion": "Helpful suggestion for resolution"
  }
}
```

## Troubleshooting

### API Key Not Working

**Symptoms**: API requests fail with authentication errors.

**Solutions**:
1. Verify API key is active:
   ```bash
   datahub baas api-keys get <api-key-id>
   ```
2. Check if API key is revoked:
   ```bash
   datahub baas api-keys list
   ```
3. Verify API key is configured:
   ```bash
   datahub config get
   ```
4. Re-create API key if needed:
   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### Rate Limit Exceeded

**Symptoms**: API requests fail with 429 (Too Many Requests) errors.

**Solutions**:
1. Check current tier limits:
   ```bash
   datahub baas docs show --format json | jq '.rate_limiting.tiers'
   ```
2. Check usage statistics:
   ```bash
   datahub baas usage stats
   ```
3. Upgrade tier if needed:
   ```bash
   datahub baas api-keys update <api-key-id> --tier PRO
   ```

### API Key Expired

**Symptoms**: API requests fail with authentication errors after expiration date.

**Solutions**:
1. Check expiration date:
   ```bash
   datahub baas api-keys get <api-key-id>
   ```
2. Update expiration date:
   ```bash
   datahub baas api-keys update <api-key-id> \
     --expires-at "2026-12-31T23:59:59Z"
   ```
3. Create new API key if update not possible:
   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### OpenAPI Schema Not Loading

**Symptoms**: `datahub baas docs openapi` fails or returns empty.

**Solutions**:
1. Check API connectivity:
   ```bash
   curl http://localhost:8000/api/v1/baas/docs/openapi.json/
   ```
2. Verify authentication:
   ```bash
   datahub config get
   ```
3. Try JSON format:
   ```bash
   datahub baas docs openapi --format json
   ```

## Command Reference

### API Key Commands

| Command | Description | Options |
|---------|-------------|---------|
| `create` | Create new API key | `--name` (required), `--tier`, `--expires-at`, `--format` |
| `list` | List API keys | `--tier`, `--limit`, `--offset`, `--format` |
| `get` | Get API key details | `<api-key-id>`, `--format` |
| `update` | Update API key | `<api-key-id>`, `--name`, `--tier`, `--expires-at`, `--format` |
| `revoke` | Revoke API key | `<api-key-id>`, `--format` |

### Usage Commands

| Command | Description | Options |
|---------|-------------|---------|
| `stats` | Get usage statistics | `--api-key-id`, `--start-date`, `--end-date`, `--format` |
| `by-endpoint` | Get usage by endpoint | `--api-key-id`, `--start-date`, `--end-date`, `--format` |
| `by-tenant` | Get usage by tenant | `--start-date`, `--end-date`, `--format` |

### Documentation Commands

| Command | Description | Options |
|---------|-------------|---------|
| `show` | Show API documentation | `--format json\|html\|markdown` |
| `openapi` | Get OpenAPI schema | `--format json\|yaml` |
| `sdks` | Get SDK download links | `--format json\|table` |

## Additional Resources

- **[CLI README](../README.md)** - Complete CLI documentation
- **[ODPS Usage Guide](ODPS_USAGE.md)** - ODPS contract management
- **[Marketplace Usage Guide](MARKETPLACE_USAGE.md)** - Marketplace integration
- **[API Reference](../../docs/API_REFERENCE.md)** - Complete API documentation
