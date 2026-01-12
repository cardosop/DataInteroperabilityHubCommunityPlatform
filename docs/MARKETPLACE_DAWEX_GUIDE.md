# Dawex Marketplace Integration Guide

## Overview

This guide covers integration with Dawex, a data exchange platform for discovering and trading data products.

## Marketplace Type

- **Type**: `DAWEX_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Dawex API Key / OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.dawex.com",
  "api_key": "your-dawex-api-key",
  "organization_id": "your-organization-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | Dawex API endpoint (default: `https://api.dawex.com`) |
| `api_key` | string | Yes | Dawex API key |
| `organization_id` | string | Yes | Dawex organization ID |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.dawex.com",
  "api_key": "your-dawex-api-key",
  "organization_id": "your-organization-id",
  "environment": "production",
  "region": "eu-west"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `environment` | string | No | Environment (production, sandbox) |
| `region` | string | No | Dawex region |

## Creating a Dawex Connection

### Step 1: Prepare Dawex Account

1. Ensure you have a Dawex account with API access
2. Generate API key:
   - Go to Account Settings → API Keys
   - Generate new API key
   - Note down the API key
3. Note your organization ID

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DAWEX_MARKETPLACE",
  "name": "My Dawex Marketplace",
  "config": {
    "api_endpoint": "https://api.dawex.com",
    "api_key": "your-dawex-api-key",
    "organization_id": "your-organization-id",
    "environment": "production"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Dawex-Specific Features

### Product Publishing (PUSH)

When syncing assets to Dawex:

1. **Product Creation**: Assets are published as Dawex products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Data Exchange**: Supports Dawex data exchange protocols

### Product Discovery (PULL)

When syncing from Dawex:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses product data via Dawex protocols
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Dawex-Specific Limitations

1. **Account Requirements**: Requires Dawex account with API access
2. **Organization Scope**: Products are organization-scoped
3. **API Key Management**: API keys must be managed securely
4. **Data Exchange Protocols**: Requires understanding of Dawex protocols
5. **Subscription Model**: PULL operations require product subscription

## Best Practices

1. **API Key Security**: Store API keys securely
2. **Organization Management**: Use organization ID for proper scoping
3. **Metadata Quality**: Ensure complete metadata for discoverability
4. **Protocol Understanding**: Understand Dawex data exchange protocols

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct

**Issue**: Product creation fails
- **Solution**: Check product requirements and account permissions

## Additional Resources

- [Dawex API Documentation](https://docs.dawex.com/api)
- [Dawex Marketplace Documentation](https://docs.dawex.com/marketplace)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
