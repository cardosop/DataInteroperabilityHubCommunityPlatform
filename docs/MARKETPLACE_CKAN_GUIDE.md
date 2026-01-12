# CKAN Marketplace Integration Guide

## Overview

This guide covers integration with CKAN (Comprehensive Knowledge Archive Network) instances. CKAN is an open-source data management platform used by many government and organizational data portals.

## Marketplace Type

- **Type**: `CKAN_INSTANCE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "base_url": "https://data.example.com",
  "api_key": "your-ckan-api-key"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | string | Yes | Base URL of the CKAN instance (e.g., `https://data.example.com`) |
| `api_key` | string | Yes | CKAN API key for authentication |

### Optional Configuration

```json
{
  "base_url": "https://data.example.com",
  "api_key": "your-ckan-api-key",
  "instance_id": "optional-instance-identifier",
  "organization": "default-organization",
  "verify_ssl": true
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | No | Optional identifier for this CKAN instance |
| `organization` | string | No | Default organization to publish datasets to |
| `verify_ssl` | boolean | No | Whether to verify SSL certificates (default: true) |

## Creating a CKAN Connection

### Step 1: Obtain API Key

1. Log in to your CKAN instance
2. Navigate to your user profile
3. Generate or copy your API key
4. Ensure the API key has permissions to:
   - Create/update datasets (for PUSH)
   - Read datasets (for PULL)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "CKAN_INSTANCE",
  "name": "My CKAN Data Portal",
  "config": {
    "base_url": "https://data.example.com",
    "api_key": "your-ckan-api-key",
    "organization": "my-organization"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## CKAN-Specific Features

### Dataset Publishing (PUSH)

When syncing assets to CKAN:

1. **Dataset Creation**: Assets are published as CKAN datasets
2. **Resource Mapping**: Hub asset resources are mapped to CKAN resources
3. **Metadata Mapping**: Asset metadata is mapped to CKAN dataset fields:
   - `title` → CKAN dataset title
   - `description` → CKAN dataset notes
   - `domain` → CKAN dataset groups/tags
   - `tags` → CKAN dataset tags

### Dataset Discovery (PULL)

When syncing from CKAN:

1. **Dataset Discovery**: Lists datasets from the CKAN instance
2. **Resource Download**: Downloads resources from CKAN datasets
3. **Metadata Extraction**: Extracts CKAN metadata to Hub asset format

## CKAN-Specific Limitations

1. **Organization Requirements**: Some CKAN instances require datasets to belong to an organization
2. **Resource Formats**: CKAN supports various formats, but some may require conversion
3. **File Size Limits**: CKAN instances may have file size limits for resource uploads
4. **API Rate Limits**: CKAN instances may enforce rate limits on API calls
5. **Authentication**: API key must have sufficient permissions for desired operations

## Best Practices

1. **Use Organizations**: Specify an organization in config for better dataset organization
2. **Verify Permissions**: Ensure API key has create/read permissions before syncing
3. **Handle Large Files**: For large resources, consider using external URLs instead of direct uploads
4. **Monitor Rate Limits**: Be aware of CKAN instance rate limits when syncing many assets
5. **Test with Small Datasets**: Start with small datasets to validate the connection

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Unauthorized"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure the organization exists in CKAN or remove organization from config

**Issue**: Resource upload fails
- **Solution**: Check file size limits and resource format compatibility

**Issue**: PULL sync returns no datasets
- **Solution**: Verify API key has read permissions and check organization filters

## Additional Resources

- [CKAN API Documentation](https://docs.ckan.org/en/latest/api/)
- [CKAN DataStore API](https://docs.ckan.org/en/latest/maintaining/datastore.html)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
