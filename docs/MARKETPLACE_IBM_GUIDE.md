# IBM Data Marketplace Integration Guide

## Overview

This guide covers integration with IBM Data Marketplace, a platform for discovering and accessing data products within the IBM ecosystem.

## Marketplace Type

- **Type**: `IBM_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: IBM Cloud API Key / IAM Token

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_key": "your-ibm-cloud-api-key",
  "region": "us-south",
  "resource_group": "default"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | IBM Cloud API key |
| `region` | string | Yes | IBM Cloud region (e.g., `us-south`) |
| `resource_group` | string | Yes | IBM Cloud resource group |

### Optional Configuration

```json
{
  "api_key": "your-ibm-cloud-api-key",
  "region": "us-south",
  "resource_group": "default",
  "cos_bucket": "marketplace-data-bucket",
  "cos_endpoint": "s3.us-south.cloud-object-storage.appdomain.cloud"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cos_bucket` | string | No | Cloud Object Storage bucket name |
| `cos_endpoint` | string | No | Cloud Object Storage endpoint |

## Creating an IBM Data Marketplace Connection

### Step 1: Prepare IBM Cloud Account

1. Ensure you have an IBM Cloud account with Data Marketplace access
2. Create API key in IBM Cloud:
   - Go to Manage → Access (IAM) → API Keys
   - Create new API key
   - Note down the API key
3. Create resource group for marketplace resources
4. Create Cloud Object Storage instance (if needed)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "IBM_DATA_MARKETPLACE",
  "name": "My IBM Data Marketplace",
  "config": {
    "api_key": "your-ibm-cloud-api-key",
    "region": "us-south",
    "resource_group": "default",
    "cos_bucket": "marketplace-data-bucket"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## IBM Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to IBM:

1. **Product Creation**: Assets are published as IBM Data Marketplace products
2. **Cloud Object Storage**: Uploads asset resources to IBM COS
3. **Metadata Publishing**: Asset metadata is published as product metadata
4. **ODPS Integration**: Uses ODPS contracts for product descriptions

### Product Discovery (PULL)

When syncing from IBM:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **COS Access**: Accesses data from Cloud Object Storage
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## IBM Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires IBM Cloud account with Data Marketplace access
2. **API Key Management**: API keys must be managed securely
3. **Cloud Object Storage**: Data must be stored in IBM COS
4. **Region Constraints**: Operations are region-specific
5. **Subscription Model**: PULL operations require product subscription
6. **Resource Group**: Resources must belong to a resource group

## Best Practices

1. **API Key Security**: Store API keys securely and rotate regularly
2. **Resource Group Organization**: Use dedicated resource groups
3. **COS Organization**: Use bucket prefixes for organization
4. **Cost Monitoring**: Monitor COS storage and data transfer costs
5. **Metadata Quality**: Ensure complete metadata for discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify IBM Cloud API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Resource group not found"
- **Solution**: Ensure resource group exists in IBM Cloud

**Issue**: COS upload fails
- **Solution**: Verify COS bucket exists and API key has object storage permissions

## Additional Resources

- [IBM Data Marketplace Documentation](https://www.ibm.com/docs/en/data-marketplace)
- [IBM Cloud Object Storage Documentation](https://cloud.ibm.com/docs/cloud-object-storage)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
