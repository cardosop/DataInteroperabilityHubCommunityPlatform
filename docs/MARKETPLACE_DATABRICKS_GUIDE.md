# Databricks Marketplace Integration Guide

## Overview

This guide covers integration with Databricks Marketplace, a platform for discovering and sharing data products within the Databricks ecosystem.

## Marketplace Type

- **Type**: `DATABRICKS_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Databricks Personal Access Token

## Connection Configuration

### Required Configuration Parameters

```json
{
  "workspace_url": "https://your-workspace.cloud.databricks.com",
  "personal_access_token": "your-databricks-token"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workspace_url` | string | Yes | Databricks workspace URL (e.g., `https://your-workspace.cloud.databricks.com`) |
| `personal_access_token` | string | Yes | Databricks personal access token |

### Optional Configuration

```json
{
  "workspace_url": "https://your-workspace.cloud.databricks.com",
  "personal_access_token": "your-databricks-token",
  "catalog": "marketplace_catalog",
  "schema": "marketplace_schema",
  "cluster_id": "optional-cluster-id"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `catalog` | string | No | Unity Catalog catalog name for marketplace data |
| `schema` | string | No | Unity Catalog schema name (default: `default`) |
| `cluster_id` | string | No | Databricks cluster ID for operations (optional) |

## Creating a Databricks Marketplace Connection

### Step 1: Prepare Databricks Workspace

1. Ensure you have a Databricks workspace with Marketplace access
2. Create personal access token:
   - Go to User Settings → Access Tokens
   - Generate new token with appropriate permissions
   - Note down the token (it won't be shown again)
3. Ensure workspace has Unity Catalog enabled (recommended)
4. Create catalog and schema for marketplace data (optional)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DATABRICKS_MARKETPLACE",
  "name": "My Databricks Marketplace",
  "config": {
    "workspace_url": "https://your-workspace.cloud.databricks.com",
    "personal_access_token": "dapi1234567890abcdef",
    "catalog": "marketplace_catalog",
    "schema": "marketplace_schema"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Databricks Marketplace-Specific Features

### Listing Publishing (PUSH)

When syncing assets to Databricks:

1. **Delta Table Creation**: Assets are published as Delta tables
2. **Unity Catalog Integration**: Tables are registered in Unity Catalog
3. **Metadata Publishing**: Asset metadata is published as listing metadata
4. **ODPS Integration**: Uses ODPS contracts for listing descriptions
5. **Sharing**: Shares Delta tables via Databricks sharing

### Listing Discovery (PULL)

When syncing from Databricks:

1. **Listing Discovery**: Lists available listings in the marketplace
2. **Delta Table Access**: Accesses shared Delta tables
3. **Schema Extraction**: Extracts table schemas from Delta tables
4. **ODPS Generation**: Generates ODPS contracts from listing metadata

## Databricks Marketplace-Specific Limitations

1. **Workspace Requirements**: Requires Databricks workspace with Marketplace access
2. **Unity Catalog**: Unity Catalog is recommended for table management
3. **Delta Format**: Only Delta format is supported for tabular data
4. **Cluster Requirements**: Some operations may require running cluster
5. **Sharing Permissions**: PUSH operations require sharing permissions
6. **Region Constraints**: Workspace region affects data locality
7. **Compute Costs**: Querying Delta tables incurs compute costs

## Best Practices

1. **Unity Catalog**: Use Unity Catalog for better table organization
2. **Token Security**: Store personal access tokens securely
3. **Delta Optimization**: Use Delta table optimization for better performance
4. **Schema Organization**: Organize tables in dedicated catalogs/schemas
5. **Cost Monitoring**: Monitor compute costs when querying marketplace data
6. **Metadata Quality**: Ensure complete metadata for discoverability
7. **Sharing Configuration**: Configure sharing settings appropriately

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid token"
- **Solution**: Verify personal access token is correct and not expired

**Issue**: PUSH sync fails with "Catalog not found"
- **Solution**: Ensure catalog exists in Unity Catalog or remove catalog from config

**Issue**: Delta table creation fails
- **Solution**: Verify workspace has Unity Catalog enabled and necessary permissions

**Issue**: Sharing fails
- **Solution**: Ensure workspace has sharing enabled and you have sharing permissions

**Issue**: PULL sync fails with "Table not accessible"
- **Solution**: Verify you have access to the shared Delta table

## Additional Resources

- [Databricks Marketplace Documentation](https://docs.databricks.com/marketplace/)
- [Databricks Unity Catalog Documentation](https://docs.databricks.com/data-governance/unity-catalog/)
- [Databricks Delta Tables Documentation](https://docs.databricks.com/delta/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
