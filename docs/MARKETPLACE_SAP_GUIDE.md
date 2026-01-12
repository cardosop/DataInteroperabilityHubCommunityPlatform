# SAP Data Marketplace Integration Guide

## Overview

This guide covers integration with SAP Data Marketplace, a platform for discovering and accessing data products within the SAP ecosystem.

## Marketplace Type

- **Type**: `SAP_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: SAP OAuth 2.0 / API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.sap.com/data-marketplace",
  "client_id": "your-sap-client-id",
  "client_secret": "your-sap-client-secret",
  "tenant_id": "your-sap-tenant-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | SAP Data Marketplace API endpoint |
| `client_id` | string | Yes | SAP OAuth client ID |
| `client_secret` | string | Yes | SAP OAuth client secret |
| `tenant_id` | string | Yes | SAP tenant ID |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.sap.com/data-marketplace",
  "client_id": "your-sap-client-id",
  "client_secret": "your-sap-client-secret",
  "tenant_id": "your-sap-tenant-id",
  "environment": "production",
  "region": "us-east"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `environment` | string | No | SAP environment (production, sandbox) |
| `region` | string | No | SAP region (default: us-east) |

## Creating an SAP Data Marketplace Connection

### Step 1: Prepare SAP Account

1. Ensure you have an SAP account with Data Marketplace access
2. Create OAuth application in SAP Cloud Platform
3. Grant necessary scopes:
   - `DataMarketplace.Read`
   - `DataMarketplace.Write`
   - `DataMarketplace.Publish`
4. Note down client ID, client secret, and tenant ID

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SAP_DATA_MARKETPLACE",
  "name": "My SAP Data Marketplace",
  "config": {
    "api_endpoint": "https://api.sap.com/data-marketplace",
    "client_id": "your-sap-client-id",
    "client_secret": "your-sap-client-secret",
    "tenant_id": "your-sap-tenant-id",
    "environment": "production"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## SAP Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to SAP:

1. **Product Creation**: Assets are published as SAP Data Marketplace products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **SAP Integration**: Integrates with SAP Data Intelligence for data delivery

### Product Discovery (PULL)

When syncing from SAP:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses data via SAP Data Intelligence
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## SAP Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires SAP account with Data Marketplace access
2. **OAuth Authentication**: Requires OAuth 2.0 setup
3. **SAP Integration**: Requires SAP Data Intelligence for data delivery
4. **Region Constraints**: Operations are region-specific
5. **Subscription Model**: PULL operations require product subscription
6. **Certification**: Products may require certification before publishing

## Best Practices

1. **OAuth Security**: Store OAuth credentials securely
2. **Environment Management**: Use separate connections for production and sandbox
3. **Metadata Quality**: Ensure complete metadata for product discoverability
4. **SAP Integration**: Understand SAP Data Intelligence integration requirements
5. **Certification Process**: Understand product certification requirements

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify OAuth client ID and secret are correct

**Issue**: PUSH sync fails with "Product creation failed"
- **Solution**: Check product certification requirements and account permissions

**Issue**: Subscription fails
- **Solution**: Verify subscription has necessary permissions and quotas

## Additional Resources

- [SAP Data Marketplace Documentation](https://help.sap.com/docs/data-marketplace)
- [SAP Data Intelligence Documentation](https://help.sap.com/docs/data-intelligence)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
