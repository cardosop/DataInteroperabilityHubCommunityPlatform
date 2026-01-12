# Oracle Data Marketplace Integration Guide

## Overview

This guide covers integration with Oracle Data Marketplace, a platform for discovering and accessing data products within the Oracle Cloud ecosystem.

## Marketplace Type

- **Type**: `ORACLE_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Oracle Cloud Infrastructure (OCI) API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
  "user_ocid": "ocid1.user.oc1..your-user-ocid",
  "fingerprint": "your-api-key-fingerprint",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "region": "us-ashburn-1"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenancy_ocid` | string | Yes | OCI tenancy OCID |
| `user_ocid` | string | Yes | OCI user OCID |
| `fingerprint` | string | Yes | API key fingerprint |
| `private_key` | string | Yes | RSA private key (PEM format) |
| `region` | string | Yes | OCI region (e.g., `us-ashburn-1`) |

### Optional Configuration

```json
{
  "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
  "user_ocid": "ocid1.user.oc1..your-user-ocid",
  "fingerprint": "your-api-key-fingerprint",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "region": "us-ashburn-1",
  "compartment_id": "ocid1.compartment.oc1..your-compartment-ocid",
  "bucket_name": "marketplace-data-bucket"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `compartment_id` | string | No | OCI compartment OCID |
| `bucket_name` | string | No | Object Storage bucket name |

## Creating an Oracle Data Marketplace Connection

### Step 1: Prepare OCI Account

1. Ensure you have an OCI account with Data Marketplace access
2. Create API key:
   - Go to Identity → Users → Your User → API Keys
   - Add API key and download private key
   - Note down fingerprint
3. Create compartment for marketplace resources (optional)
4. Create Object Storage bucket (if needed)
5. Ensure user has necessary IAM policies:
   - `Allow group DataMarketplaceAdmins to manage data-marketplace-products`
   - `Allow group DataMarketplaceAdmins to manage object-family`

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "ORACLE_DATA_MARKETPLACE",
  "name": "My Oracle Data Marketplace",
  "config": {
    "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
    "user_ocid": "ocid1.user.oc1..your-user-ocid",
    "fingerprint": "aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
    "region": "us-ashburn-1",
    "compartment_id": "ocid1.compartment.oc1..your-compartment-ocid"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Oracle Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Oracle:

1. **Product Creation**: Assets are published as Oracle Data Marketplace products
2. **Object Storage**: Uploads asset resources to OCI Object Storage
3. **Metadata Publishing**: Asset metadata is published as product metadata
4. **ODPS Integration**: Uses ODPS contracts for product descriptions

### Product Discovery (PULL)

When syncing from Oracle:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Object Storage Access**: Accesses data from OCI Object Storage
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Oracle Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires OCI account with Data Marketplace access
2. **API Key Management**: RSA private keys must be managed securely
3. **Object Storage**: Data must be stored in OCI Object Storage
4. **Region Constraints**: Operations are region-specific
5. **Compartment Organization**: Resources must belong to a compartment
6. **Subscription Model**: PULL operations require product subscription
7. **IAM Policies**: Requires specific IAM policies for marketplace operations

## Best Practices

1. **Private Key Security**: Store RSA private keys securely (encrypted)
2. **Compartment Organization**: Use dedicated compartments for marketplace
3. **Object Storage Organization**: Use bucket prefixes for organization
4. **IAM Policies**: Use least-privilege IAM policies
5. **Cost Monitoring**: Monitor Object Storage and data transfer costs
6. **Metadata Quality**: Ensure complete metadata for discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify OCIDs, fingerprint, and private key are correct

**Issue**: PUSH sync fails with "Compartment not found"
- **Solution**: Ensure compartment exists and user has access

**Issue**: Object Storage upload fails
- **Solution**: Verify bucket exists and IAM policies allow object-family operations

**Issue**: Product creation fails
- **Solution**: Check IAM policies for data-marketplace-products permissions

## Additional Resources

- [Oracle Data Marketplace Documentation](https://docs.oracle.com/en/cloud/paas/data-marketplace/)
- [OCI Object Storage Documentation](https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm)
- [OCI IAM Documentation](https://docs.oracle.com/en-us/iaas/Content/Identity/Concepts/overview.htm)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
