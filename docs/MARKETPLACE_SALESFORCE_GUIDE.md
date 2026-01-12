# Salesforce Data Marketplace Integration Guide

## Overview

This guide covers integration with Salesforce Data Marketplace, a platform for discovering and accessing data products within the Salesforce ecosystem.

## Marketplace Type

- **Type**: `SALESFORCE_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Salesforce OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "instance_url": "https://your-instance.salesforce.com",
  "client_id": "your-salesforce-client-id",
  "client_secret": "your-salesforce-client-secret",
  "username": "your-salesforce-username",
  "password": "your-salesforce-password",
  "security_token": "your-security-token"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_url` | string | Yes | Salesforce instance URL |
| `client_id` | string | Yes | Connected App client ID |
| `client_secret` | string | Yes | Connected App client secret |
| `username` | string | Yes | Salesforce username |
| `password` | string | Yes | Salesforce password |
| `security_token` | string | Yes | Salesforce security token |

### Optional Configuration

```json
{
  "instance_url": "https://your-instance.salesforce.com",
  "client_id": "your-salesforce-client-id",
  "client_secret": "your-salesforce-client-secret",
  "username": "your-salesforce-username",
  "password": "your-salesforce-password",
  "security_token": "your-security-token",
  "api_version": "58.0",
  "sandbox": false
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_version` | string | No | Salesforce API version (default: latest) |
| `sandbox` | boolean | No | Whether using Salesforce sandbox (default: false) |

## Creating a Salesforce Data Marketplace Connection

### Step 1: Prepare Salesforce Account

1. Ensure you have a Salesforce account with Data Marketplace access
2. Create Connected App:
   - Setup → App Manager → New Connected App
   - Enable OAuth Settings
   - Set callback URL
   - Note down client ID and client secret
3. Get security token:
   - Setup → My Personal Information → Reset My Security Token
4. Ensure user has necessary permissions:
   - Data Marketplace Admin
   - API access enabled

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SALESFORCE_DATA_MARKETPLACE",
  "name": "My Salesforce Data Marketplace",
  "config": {
    "instance_url": "https://your-instance.salesforce.com",
    "client_id": "your-salesforce-client-id",
    "client_secret": "your-salesforce-client-secret",
    "username": "your-salesforce-username",
    "password": "your-salesforce-password",
    "security_token": "your-security-token",
    "api_version": "58.0"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Salesforce Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Salesforce:

1. **Product Creation**: Assets are published as Salesforce Data Marketplace products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Salesforce Integration**: Integrates with Salesforce Data Cloud

### Product Discovery (PULL)

When syncing from Salesforce:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses data via Salesforce Data Cloud
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Salesforce Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires Salesforce account with Data Marketplace access
2. **OAuth Setup**: Requires Connected App configuration
3. **Security Token**: Security token is required for authentication
4. **API Version**: API version compatibility must be maintained
5. **Subscription Model**: PULL operations require product subscription
6. **Data Cloud Integration**: Requires Salesforce Data Cloud for data delivery

## Best Practices

1. **Security Token Management**: Store security tokens securely
2. **Connected App Configuration**: Use appropriate OAuth scopes
3. **API Version**: Keep API version up to date
4. **Metadata Quality**: Ensure complete metadata for discoverability
5. **Data Cloud Integration**: Understand Data Cloud integration requirements

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify username, password, and security token are correct

**Issue**: OAuth authentication fails
- **Solution**: Check Connected App configuration and callback URL

**Issue**: PUSH sync fails with "Insufficient permissions"
- **Solution**: Ensure user has Data Marketplace Admin permissions

**Issue**: API version errors
- **Solution**: Update API version in configuration

## Additional Resources

- [Salesforce Data Marketplace Documentation](https://help.salesforce.com/s/articleView?id=sf.data_marketplace.htm)
- [Salesforce Data Cloud Documentation](https://help.salesforce.com/s/articleView?id=sf.data_cloud.htm)
- [Salesforce Connected Apps Documentation](https://help.salesforce.com/s/articleView?id=sf.connected_app_overview.htm)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
