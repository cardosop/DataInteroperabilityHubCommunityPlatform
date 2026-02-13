# Marketplace Integration User Guide

## Overview

The Data Interoperability Hub provides comprehensive marketplace integration capabilities that allow you to:

- **Publish assets** from the Hub to external data marketplaces (PUSH sync)
- **Discover and import assets** from external marketplaces into the Hub (PULL sync)
- **Manage bidirectional synchronization** between the Hub and marketplace platforms
- **Track sync jobs** and view detailed progress and error information
- **View asset mappings** between Hub assets and marketplace listings

This guide covers the complete workflow for marketplace integration, from creating connections to managing sync operations.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Creating Marketplace Connections](#creating-marketplace-connections)
3. [Testing Connections](#testing-connections)
4. [Syncing Assets to Marketplaces (PUSH)](#syncing-assets-to-marketplaces-push)
5. [Syncing Assets from Marketplaces (PULL)](#syncing-assets-from-marketplaces-pull)
6. [Managing Sync Jobs](#managing-sync-jobs)
7. [Viewing Mappings](#viewing-mappings)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you can use marketplace integration, ensure:

1. **Tenant KYC Verification**: Your tenant must have `VERIFIED` KYC status to publish assets to marketplaces
2. **User Permissions**: You need one of the following roles:
   - `DATA_PROVIDER` - Can create connections and manage sync operations
   - `TENANT_ADMIN` - Full access to all marketplace integration features
3. **API Scopes**: You must have the `integrations:write` scope for write operations
4. **Active Assets**: Assets must be in `ACTIVE` status to be synced to marketplaces
5. **Valid Contracts**: Assets must have `ACTIVE` contracts with `VALID` or `WARNING_ONLY` validation status

## Creating Marketplace Connections

A marketplace connection stores the configuration and credentials needed to connect to an external marketplace platform.

### Step 1: Prepare Connection Configuration

Each marketplace type requires specific configuration parameters. Refer to the marketplace-specific guides for detailed configuration requirements:

- [CKAN Guide](MARKETPLACE_CKAN_GUIDE.md)
- [Snowflake Guide](MARKETPLACE_SNOWFLAKE_GUIDE.md)
- [AWS Data Exchange Guide](MARKETPLACE_AWS_GUIDE.md)
- [Azure Marketplace Guide](MARKETPLACE_AZURE_GUIDE.md)
- [GCP Marketplace Guide](MARKETPLACE_GCP_GUIDE.md)
- [Databricks Guide](MARKETPLACE_DATABRICKS_GUIDE.md)
- [SAP Guide](MARKETPLACE_SAP_GUIDE.md)
- [IBM Guide](MARKETPLACE_IBM_GUIDE.md)
- [Oracle Guide](MARKETPLACE_ORACLE_GUIDE.md)
- [Salesforce Guide](MARKETPLACE_SALESFORCE_GUIDE.md)
- [DataRade Guide](MARKETPLACE_DATARADE_GUIDE.md)
- [Dawex Guide](MARKETPLACE_DAWEX_GUIDE.md)
- [NASDAQ Guide](MARKETPLACE_NASDAQ_GUIDE.md)
- [Esri Guide](MARKETPLACE_ESRI_GUIDE.md)
- [Collibra Guide](MARKETPLACE_COLLIBRA_GUIDE.md)

### Step 2: Create Connection via API

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request Body**:
```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Connection",
  "config": {
    "account_identifier": "your-account",
    "username": "your-username",
    "password": "your-password",
    "warehouse": "COMPUTE_WH",
    "database": "MARKETPLACE_DB"
  },
  "is_active": true
}
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Connection",
  "is_active": true,
  "created_at": "2025-01-10T10:00:00Z",
  "updated_at": "2025-01-10T10:00:00Z"
}
```

**Important Notes**:
- Connection names must be unique within your tenant
- Configuration is automatically encrypted at rest for security
- The `config` field is never returned in API responses for security reasons
- Connections are tenant-scoped (you can only see connections in your tenant)

### Step 3: Verify Connection Creation

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/{connection_id}/`

This retrieves the connection details (without sensitive config data).

## Testing Connections

Before using a connection for sync operations, always test it to ensure credentials are valid.

### Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

**Response**:
```json
{
  "success": true,
  "message": "Connection test successful",
  "tested_at": "2025-01-10T10:05:00Z",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "response_time_ms": 245
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "message": "Connection test failed: Invalid credentials",
  "tested_at": "2025-01-10T10:05:00Z",
  "error": "Authentication failed"
}
```

**Best Practice**: Always test connections after creation and before running sync jobs.

## Syncing Assets to Marketplaces (PUSH)

PUSH sync publishes your Hub assets to external marketplaces, making them discoverable and available for purchase or access.

### Prerequisites for PUSH Sync

1. **Asset Requirements**:
   - Asset status: `ACTIVE`
   - Contract status: `ACTIVE` with `VALID` or `WARNING_ONLY` validation
   - DQ status: `PASS` or `WARN` (if dataset exists)
   - Compliance status: `PASS` or `WARN` (if dataset exists)

2. **Tenant Requirements**:
   - KYC status: `VERIFIED`

### Step 1: Create Sync Job

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/`

**Request Body**:
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "asset_ids": [
    "660e8400-e29b-41d4-a716-446655440001",
    "660e8400-e29b-41d4-a716-446655440002"
  ],
  "options": {
    "skip_resource_downloads": false,
    "skip_semantic_mapping": false
  }
}
```

**Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "created_at": "2025-01-10T10:10:00Z"
}
```

### Step 2: Monitor Sync Job Progress

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

**Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "RUNNING",
  "progress_percentage": 60,
  "current_step": "publish_to_marketplace",
  "items_synced": 1,
  "items_failed": 0,
  "metadata": {
    "progress_percentage": 60,
    "current_step": "publish_to_marketplace"
  },
  "started_at": "2025-01-10T10:10:05Z",
  "updated_at": "2025-01-10T10:10:30Z"
}
```

### PUSH Sync Workflow Steps

The PUSH sync workflow executes the following steps:

1. **Validate Connection**: Verifies connection is active and tested
2. **Validate Assets**: Checks asset eligibility (status, contracts, DQ, compliance)
3. **Map Assets to Marketplace**: Converts Hub asset format to marketplace listing format
4. **Publish to Marketplace**: Creates/updates listings in the external marketplace
5. **Create Mappings**: Records the mapping between Hub assets and marketplace listings
6. **Update Semantic Layer**: Updates semantic layer with federated asset properties
7. **Complete**: Marks sync job as completed

### Step 3: View Sync Results

Once the sync job completes, check the results:

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

**Completed Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "COMPLETED",
  "progress_percentage": 100,
  "current_step": "complete",
  "items_synced": 2,
  "items_failed": 0,
  "completed_at": "2025-01-10T10:12:00Z",
  "errors": []
}
```

**Failed Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "FAILED",
  "progress_percentage": 40,
  "current_step": "publish_to_marketplace",
  "items_synced": 0,
  "items_failed": 2,
  "errors": [
    {
      "step": "publish_to_marketplace",
      "asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "error": "Marketplace API rate limit exceeded"
    }
  ]
}
```

## Syncing Assets from Marketplaces (PULL)

PULL sync discovers and imports assets from external marketplaces into the Hub as federated assets.

### Step 1: Create PULL Sync Job

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/`

**Request Body**:
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "options": {
    "filters": {
      "domain": "finance",
      "category": "market-data"
    },
    "limit": 100,
    "data_strategy": "METADATA_ONLY",
    "skip_semantic_mapping": false
  }
}
```

**Data Strategy Options**:
- `METADATA_ONLY`: Import only metadata, no resource downloads (fastest)
- `DOWNLOAD_ALL`: Download all resources for all assets
- `DOWNLOAD_SELECTIVE`: Download resources for specific assets (use `download_resources` list)
- `download_resources_for_last_n`: Download resources only for the last N discovered assets

**Response**:
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440004",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "created_at": "2025-01-10T10:15:00Z"
}
```

### Step 2: Monitor PULL Sync Progress

Monitor progress the same way as PUSH sync:

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

### PULL Sync Workflow Steps

The PULL sync workflow executes the following steps:

1. **Validate Connection**: Verifies connection is active and tested
2. **Discover Listings**: Fetches listings from the marketplace (with optional filters)
3. **Map Listings to Assets**: Converts marketplace listing format to Hub asset format
4. **Create Federated Assets**: Creates assets with dual contracts (ODPS + ODCS)
5. **Download Resources**: Downloads resources from marketplace (if data_strategy allows)
6. **Create Mappings**: Records the mapping between marketplace listings and Hub assets
7. **Update Semantic Layer**: Updates semantic layer with federated asset properties
8. **Complete**: Marks sync job as completed

### Step 3: View Created Federated Assets

After PULL sync completes, federated assets are created in your tenant:

**Endpoint**: `GET /api/v1/assets/?source_type=FEDERATED`

Federated assets have:
- `source_type`: `FEDERATED`
- Dual contracts: ODPS (from marketplace) and ODCS (Hub-generated)
- `source_metadata`: Contains marketplace-specific metadata
- Resources: Downloaded from marketplace (if data_strategy allowed)

## Managing Sync Jobs

### List Sync Jobs

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/`

**Query Parameters**:
- `connection_id`: Filter by connection
- `direction`: Filter by direction (PUSH, PULL)
- `status`: Filter by status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL)
- `ordering`: Sort by field (default: `-created_at`)
- `page`: Page number for pagination
- `page_size`: Items per page

**Response**:
```json
{
  "count": 10,
  "next": "http://api.example.com/api/v1/integrations/marketplace/sync-jobs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440003",
      "connection_id": "550e8400-e29b-41d4-a716-446655440000",
      "direction": "PUSH",
      "status": "COMPLETED",
      "items_synced": 2,
      "items_failed": 0,
      "created_at": "2025-01-10T10:10:00Z",
      "completed_at": "2025-01-10T10:12:00Z"
    }
  ]
}
```

### Cancel Sync Job

If a sync job is running and you need to stop it:

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/cancel/`

**Request Body**:
```json
{
  "reason": "User requested cancellation"
}
```

**Response**:
```json
{
  "cancelled": true,
  "cancelled_at": "2025-01-10T10:20:00Z",
  "reason": "User requested cancellation"
}
```

**Note**: Cancellation may take a few moments to process. The job status will update to `FAILED` with cancellation details in the errors field.

### View Sync Job Details

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

Returns full details including:
- Progress information
- Current step
- Items synced/failed
- Error details
- Metadata

## Viewing Mappings

Mappings track the relationship between Hub assets and marketplace listings.

### List Mappings

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/`

**Query Parameters**:
- `connection_id`: Filter by connection
- `hub_asset_id`: Filter by Hub asset ID
- `external_listing_id`: Filter by marketplace listing ID
- `ordering`: Sort by field (default: `-last_synced_at`)
- `page`: Page number
- `page_size`: Items per page

**Response**:
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440005",
      "connection_id": "550e8400-e29b-41d4-a716-446655440000",
      "hub_asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "external_listing_id": "marketplace-listing-12345",
      "sync_metadata": {
        "sync_direction": "PUSH",
        "synced_at": "2025-01-10T10:12:00Z"
      },
      "last_synced_at": "2025-01-10T10:12:00Z"
    }
  ]
}
```

### Get Mapping Details

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/{mapping_id}/`

Returns detailed mapping information including:
- Hub asset details
- Marketplace listing ID
- Sync metadata
- Last sync timestamp

## Troubleshooting

### Connection Test Failures

**Problem**: Connection test fails with authentication error

**Solutions**:
1. Verify credentials are correct in the connection config
2. Check if credentials have expired
3. Ensure API keys have necessary permissions
4. Verify network connectivity to marketplace
5. Check marketplace-specific requirements (IP whitelisting, etc.)

### PUSH Sync Failures

**Problem**: Assets fail to sync to marketplace

**Common Causes**:
1. **Asset not eligible**: Check asset status, contract status, DQ/compliance status
2. **KYC not verified**: Tenant must have VERIFIED KYC status
3. **Marketplace API errors**: Check error details in sync job response
4. **Rate limiting**: Marketplace may have rate limits - wait and retry
5. **Invalid asset format**: Asset may not be compatible with marketplace requirements

**Solutions**:
- Review sync job error details
- Fix asset eligibility issues
- Retry sync job after resolving issues
- Check marketplace-specific limitations

### PULL Sync Failures

**Problem**: Assets fail to import from marketplace

**Common Causes**:
1. **Connection issues**: Marketplace API may be unavailable
2. **Invalid listing format**: Marketplace listing may not be compatible
3. **Resource download failures**: Resources may be inaccessible
4. **Contract creation failures**: ODPS/ODCS contract generation may fail

**Solutions**:
- Check connection test status
- Review sync job error details
- Verify marketplace listings are accessible
- Try with `METADATA_ONLY` data strategy first

### Sync Job Stuck in RUNNING Status

**Problem**: Sync job appears stuck and doesn't progress

**Solutions**:
1. Check workflow instance status in system logs
2. Verify marketplace API is responding
3. Cancel and retry the sync job
4. Contact support if issue persists

### Mapping Not Created

**Problem**: Sync job completes but no mapping is created

**Solutions**:
1. Verify sync job completed successfully (status: COMPLETED)
2. Check if assets/listings were actually synced (items_synced > 0)
3. Review sync job metadata for mapping creation details
4. Check if mapping already exists (may have been created in previous sync)

## Best Practices

1. **Always test connections** before creating sync jobs
2. **Start with small batches** when syncing many assets
3. **Use METADATA_ONLY for initial PULL syncs** to validate connectivity
4. **Monitor sync job progress** regularly for long-running operations
5. **Review error details** carefully to understand failure causes
6. **Keep connection credentials secure** - they are encrypted but should still be protected
7. **Use appropriate data strategies** based on your needs (METADATA_ONLY vs DOWNLOAD_ALL)
8. **Schedule regular syncs** for keeping marketplace listings up-to-date
9. **Review mappings periodically** to ensure sync accuracy
10. **Document connection configurations** for team knowledge sharing

## API Reference

For complete API documentation, see:
- [Marketplace Connections API](../../docs/api/marketplace-connections.md)
- [Marketplace Sync Jobs API](../../docs/api/marketplace-sync-jobs.md)
- [Marketplace Mappings API](../../docs/api/marketplace-mappings.md)

## Additional Resources

- [Marketplace-Specific Guides](./) - Detailed configuration for each marketplace
- [Workflow Documentation](../../docs/workflows/marketplace-sync.md)
- [Security Best Practices](../../docs/security/marketplace-integration.md)
- **CLI Usage**: [Marketplace CLI Usage Guide](../cli/docs/MARKETPLACE_USAGE.md) - Complete CLI commands for marketplace integration
- **SDK Usage**: [Marketplace Python SDK Usage Guide](../sdk/python/docs/MARKETPLACE_USAGE.md) - Complete SDK APIs for marketplace integration
