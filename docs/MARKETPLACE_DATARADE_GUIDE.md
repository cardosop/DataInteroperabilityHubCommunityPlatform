# DataRade Marketplace Integration Guide

## Overview

This guide covers integration with DataRade, a data marketplace platform for discovering and trading data products.

## Marketplace Type

- **Type**: `DATARADE_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: DataRade API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.datarade.com",
  "api_key": "your-datarade-api-key"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | DataRade API endpoint (default: `https://api.datarade.com`) |
| `api_key` | string | Yes | DataRade API key |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.datarade.com",
  "api_key": "your-datarade-api-key",
  "organization_id": "your-organization-id",
  "environment": "production"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organization_id` | string | No | DataRade organization ID |
| `environment` | string | No | Environment (production, sandbox) |

## Creating a DataRade Connection

### Step 1: Prepare DataRade Account

1. Ensure you have a DataRade account with API access
2. Generate API key:
   - Go to Account Settings → API Keys
   - Generate new API key
   - Note down the API key
3. Note your organization ID (if applicable)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DATARADE_MARKETPLACE",
  "name": "My DataRade Marketplace",
  "config": {
    "api_endpoint": "https://api.datarade.com",
    "api_key": "your-datarade-api-key",
    "organization_id": "your-organization-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## DataRade-Specific Features

### Product Publishing (PUSH)

When syncing assets to DataRade:

1. **Product Creation**: Assets are published as DataRade products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Pricing Configuration**: Supports various pricing models

### Product Discovery (PULL)

When syncing from DataRade:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses product data
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## DataRade-Specific Limitations

1. **Account Requirements**: Requires DataRade account with API access
2. **API Key Management**: API keys must be managed securely
3. **Organization Scope**: Products may be organization-scoped
4. **Pricing Models**: Supports specific pricing models
5. **Subscription Model**: PULL operations require product subscription

## Best Practices

1. **API Key Security**: Store API keys securely
2. **Organization Management**: Use organization ID for better organization
3. **Metadata Quality**: Ensure complete metadata for discoverability
4. **Pricing Configuration**: Configure appropriate pricing models

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct or remove from config

**Issue**: Product creation fails
- **Solution**: Check product requirements and account permissions

## Additional Resources

- [DataRade API Documentation](https://docs.datarade.com/api)
- [DataRade Marketplace Documentation](https://docs.datarade.com/marketplace)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
