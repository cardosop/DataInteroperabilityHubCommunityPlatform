# Azure Marketplace Integration Guide

## Overview

This guide covers integration with Azure Marketplace, Microsoft's cloud marketplace for data products and services.

## Marketplace Type

- **Type**: `AZURE_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Azure Service Principal

## Connection Configuration

### Required Configuration Parameters

```json
{
  "tenant_id": "your-azure-tenant-id",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "subscription_id": "your-subscription-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenant_id` | string | Yes | Azure Active Directory tenant ID |
| `client_id` | string | Yes | Azure service principal client ID |
| `client_secret` | string | Yes | Azure service principal client secret |
| `subscription_id` | string | Yes | Azure subscription ID |

### Optional Configuration

```json
{
  "tenant_id": "your-azure-tenant-id",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "subscription_id": "your-subscription-id",
  "resource_group": "marketplace-rg",
  "storage_account": "marketplacestorage",
  "location": "eastus"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `resource_group` | string | No | Azure resource group for marketplace resources |
| `storage_account` | string | No | Azure Storage account for data files |
| `location` | string | No | Azure region (default: `eastus`) |

## Creating an Azure Marketplace Connection

### Step 1: Prepare Azure Service Principal

1. Create Azure Service Principal in Azure Active Directory
2. Assign necessary roles:
   - `Marketplace Publisher` (for PUSH)
   - `Storage Blob Data Contributor` (for data access)
   - `Reader` (for PULL operations)
3. Grant API permissions for Azure Marketplace API
4. Note down tenant ID, client ID, and client secret

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "AZURE_MARKETPLACE",
  "name": "My Azure Marketplace",
  "config": {
    "tenant_id": "12345678-1234-1234-1234-123456789012",
    "client_id": "87654321-4321-4321-4321-210987654321",
    "client_secret": "your-client-secret",
    "subscription_id": "11111111-2222-3333-4444-555555555555",
    "resource_group": "marketplace-rg",
    "storage_account": "marketplacestorage"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Azure Marketplace-Specific Features

### Offer Publishing (PUSH)

When syncing assets to Azure Marketplace:

1. **Offer Creation**: Assets are published as Azure Marketplace offers
2. **Plan Configuration**: Creates plans for different pricing models
3. **Blob Storage**: Uploads asset resources to Azure Blob Storage
4. **Metadata Publishing**: Publishes asset metadata as offer metadata
5. **ODPS Integration**: Uses ODPS contracts for offer descriptions

### Offer Discovery (PULL)

When syncing from Azure Marketplace:

1. **Offer Discovery**: Lists available offers in the marketplace
2. **Subscription**: Subscribes to selected offers
3. **Blob Access**: Accesses data from Azure Blob Storage
4. **ODPS Generation**: Generates ODPS contracts from offer metadata

## Azure Marketplace-Specific Limitations

1. **Service Principal Requirements**: Requires Azure AD service principal
2. **Publisher Account**: PUSH operations require publisher account setup
3. **Certification Process**: Offers may require certification before publishing
4. **Blob Storage**: All data must be stored in Azure Blob Storage
5. **Region Constraints**: Operations are region-specific
6. **Subscription Model**: PULL operations require offer subscription
7. **Pricing Configuration**: Offers require pricing plan configuration

## Best Practices

1. **Service Principal Security**: Use managed identities when possible
2. **Resource Group Organization**: Use dedicated resource groups for marketplace
3. **Blob Storage Organization**: Use container prefixes for organization
4. **Role-Based Access**: Use least-privilege role assignments
5. **Cost Monitoring**: Monitor Azure storage and data transfer costs
6. **Offer Certification**: Understand certification requirements before publishing
7. **Metadata Quality**: Ensure complete metadata for offer discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify service principal credentials and permissions

**Issue**: PUSH sync fails with "Publisher account not found"
- **Solution**: Ensure publisher account is set up in Azure Marketplace

**Issue**: Blob upload fails
- **Solution**: Verify storage account exists and service principal has blob contributor role

**Issue**: Offer creation fails
- **Solution**: Check certification requirements and publisher account status

**Issue**: Subscription fails
- **Solution**: Verify subscription has necessary permissions and quotas

## Additional Resources

- [Azure Marketplace Documentation](https://docs.microsoft.com/azure/marketplace/)
- [Azure Marketplace Publisher Guide](https://docs.microsoft.com/azure/marketplace/marketplace-publishers-guide)
- [Azure Storage Documentation](https://docs.microsoft.com/azure/storage/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
