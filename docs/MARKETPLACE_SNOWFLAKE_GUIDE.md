# Snowflake Data Marketplace Integration Guide

## Overview

This guide covers integration with Snowflake Data Marketplace, a platform for discovering and accessing third-party data products within the Snowflake ecosystem.

## Marketplace Type

- **Type**: `SNOWFLAKE_DATA_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Snowflake Account Credentials

## Connection Configuration

### Required Configuration Parameters

```json
{
  "account_identifier": "your-account-identifier",
  "username": "your-username",
  "password": "your-password",
  "warehouse": "COMPUTE_WH",
  "database": "MARKETPLACE_DB"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_identifier` | string | Yes | Snowflake account identifier (e.g., `xy12345.us-east-1`) |
| `username` | string | Yes | Snowflake username |
| `password` | string | Yes | Snowflake password |
| `warehouse` | string | Yes | Snowflake warehouse name (e.g., `COMPUTE_WH`) |
| `database` | string | Yes | Database name for marketplace operations |

### Optional Configuration

```json
{
  "account_identifier": "your-account-identifier",
  "username": "your-username",
  "password": "your-password",
  "warehouse": "COMPUTE_WH",
  "database": "MARKETPLACE_DB",
  "role": "ACCOUNTADMIN",
  "schema": "PUBLIC",
  "region": "us-east-1"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `role` | string | No | Snowflake role to use (default: account default role) |
| `schema` | string | No | Schema name (default: `PUBLIC`) |
| `region` | string | No | Snowflake region (auto-detected from account_identifier if not specified) |

## Creating a Snowflake Connection

### Step 1: Prepare Snowflake Account

1. Ensure you have a Snowflake account with Data Marketplace access
2. Create a dedicated warehouse for marketplace operations (recommended)
3. Create a database for storing marketplace listings
4. Ensure your user has necessary permissions:
   - `CREATE DATABASE` (if creating new database)
   - `CREATE SCHEMA`
   - `CREATE TABLE`
   - `CREATE SHARE` (for PUSH operations)
   - `IMPORT SHARE` (for PULL operations)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Marketplace",
  "config": {
    "account_identifier": "xy12345.us-east-1",
    "username": "marketplace_user",
    "password": "secure-password",
    "warehouse": "MARKETPLACE_WH",
    "database": "MARKETPLACE_DB",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Snowflake-Specific Features

### Listing Publishing (PUSH)

When syncing assets to Snowflake:

1. **Share Creation**: Assets are published as Snowflake shares
2. **Table Mapping**: Hub asset datasets are mapped to Snowflake tables
3. **Metadata Publishing**: Asset metadata is published as listing metadata
4. **ODPS Integration**: ODPS contracts are used to generate Snowflake listing descriptions

### Listing Discovery (PULL)

When syncing from Snowflake:

1. **Share Discovery**: Lists available shares in the marketplace
2. **Table Schema Extraction**: Extracts table schemas from Snowflake shares
3. **Data Access**: Creates federated assets with access to Snowflake tables
4. **ODPS Generation**: Generates ODPS contracts from Snowflake listing metadata

## Snowflake-Specific Limitations

1. **Account Requirements**: Requires a Snowflake account with Data Marketplace enabled
2. **Share Permissions**: PUSH operations require share creation permissions
3. **Table Format**: Only tabular data can be published (CSV, Parquet, etc.)
4. **Region Constraints**: Shares must be in the same region as the consumer account
5. **Compute Costs**: Querying Snowflake tables incurs compute costs
6. **Data Types**: Some Hub data types may not map directly to Snowflake types

## Best Practices

1. **Dedicated Warehouse**: Use a dedicated warehouse for marketplace operations
2. **Role-Based Access**: Use specific roles with minimal required permissions
3. **Schema Organization**: Organize listings in dedicated schemas
4. **Cost Monitoring**: Monitor compute costs when querying marketplace data
5. **Data Type Mapping**: Verify data type compatibility before syncing
6. **Share Naming**: Use descriptive share names that match asset names
7. **Metadata Quality**: Ensure asset metadata is complete for better discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid account identifier"
- **Solution**: Verify account identifier format (e.g., `xy12345.us-east-1`)

**Issue**: PUSH sync fails with "Insufficient privileges"
- **Solution**: Ensure user has `CREATE SHARE` and `CREATE DATABASE` permissions

**Issue**: PULL sync fails with "Share not found"
- **Solution**: Verify share exists and is accessible from your account

**Issue**: Table schema extraction fails
- **Solution**: Ensure you have `SELECT` permissions on the share tables

**Issue**: Data type conversion errors
- **Solution**: Review data type mappings and convert incompatible types before syncing

## Additional Resources

- [Snowflake Data Marketplace Documentation](https://docs.snowflake.com/en/user-guide/data-marketplace-intro.html)
- [Snowflake Shares Documentation](https://docs.snowflake.com/en/user-guide/data-sharing-intro.html)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
