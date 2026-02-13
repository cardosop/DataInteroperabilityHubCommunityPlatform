# Marketplace Integration CLI Usage Guide

Complete guide for using marketplace integration commands in the DataHub CLI.

## Table of Contents

1. [Overview](#overview)
2. [Marketplace Concepts](#marketplace-concepts)
3. [Connectors](#connectors)
4. [Connections](#connections)
5. [Sync Jobs](#sync-jobs)
6. [Mappings](#mappings)
7. [Common Workflows](#common-workflows)
8. [Error Handling](#error-handling)
9. [Troubleshooting](#troubleshooting)

## Overview

The DataHub CLI provides comprehensive support for marketplace integration, enabling bidirectional synchronization between Hub assets and external data marketplaces. This includes managing connections, monitoring sync jobs, and viewing mappings between Hub assets and marketplace listings.

### Key Features

- **Connector Discovery**: List and inspect available marketplace connector types
- **Connection Management**: Create, test, update, and delete marketplace connections
- **Sync Job Management**: Start, monitor, and cancel synchronization jobs
- **Mapping Management**: View and manage mappings between Hub assets and marketplace listings
- **Multiple Marketplace Support**: Support for 15+ marketplace platforms (Snowflake, AWS, Databricks, CKAN, etc.)

### Supported Marketplace Types

- `SNOWFLAKE_DATA_MARKETPLACE` - Snowflake Data Marketplace
- `AWS_DATA_EXCHANGE` - AWS Data Exchange
- `DATABRICKS_MARKETPLACE` - Databricks Marketplace
- `GOOGLE_CLOUD_MARKETPLACE` - Google Cloud Marketplace
- `AZURE_MARKETPLACE` - Azure Marketplace
- `DATA_WORLD` - Data World
- `KAGGLE` - Kaggle
- `QUANDL` - Quandl
- `APIS_GURU` - APIs.guru
- `RAPIDAPI` - RapidAPI
- `PROGRAMMABLE_WEB` - Programmable Web
- `DATA_GOV` - Data.gov
- `EUROPEAN_DATA_PORTAL` - European Data Portal
- `CKAN_INSTANCE` - CKAN instances
- `CUSTOM` - Custom marketplace

## Marketplace Concepts

### Connectors

Connectors are implementations that enable communication with specific marketplace platforms. Each connector supports different sync directions (PUSH, PULL, or BIDIRECTIONAL) and has specific configuration requirements.

### Connections

Connections are configured instances of connectors, containing authentication credentials and marketplace-specific settings. Each connection is tenant-scoped and can be active or inactive.

### Sync Jobs

Sync jobs perform synchronization operations between the Hub and marketplaces:
- **PUSH**: Push Hub assets to marketplace (create/update listings)
- **PULL**: Pull marketplace listings into Hub (create federated assets)
- **BIDIRECTIONAL**: Both push and pull operations

### Mappings

Mappings represent the relationship between Hub assets and external marketplace listings, tracking synchronization status and metadata.

## Connectors

### List Available Connectors

List all available marketplace connector types with their supported sync directions and status.

```bash
# List all connectors (table format)
datahub marketplace connectors list

# List all connectors (JSON format)
datahub marketplace connectors list --format json
```

**Example Output (Table)**:
```
Type                                Display Name                         Sync Directions            Status
----------------------------------- ----------------------------------- ------------------------- --------------
SNOWFLAKE_DATA_MARKETPLACE          Snowflake Data Marketplace          PULL                       available
AWS_DATA_EXCHANGE                   Aws Data Exchange                    PULL, PUSH                 available
CKAN_INSTANCE                       Ckan Instance                        PULL                       available
```

**Example Output (JSON)**:
```json
[
  {
    "type": "SNOWFLAKE_DATA_MARKETPLACE",
    "display_name": "Snowflake Data Marketplace",
    "supported_sync_directions": ["PULL"],
    "status": "available",
    "description": "Connector for Snowflake Data Marketplace"
  },
  {
    "type": "AWS_DATA_EXCHANGE",
    "display_name": "Aws Data Exchange",
    "supported_sync_directions": ["PULL", "PUSH"],
    "status": "available",
    "description": "Connector for AWS Data Exchange"
  }
]
```

### Get Connector Information

Get detailed information about a specific connector type, including capabilities and configuration requirements.

```bash
# Get connector info (table format)
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE

# Get connector info (JSON format)
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE --format json
```

**Example Output (Table)**:
```
Type: SNOWFLAKE_DATA_MARKETPLACE
Display Name: Snowflake Data Marketplace
Status: available
Description: Connector for Snowflake Data Marketplace
Supported Sync Directions: PULL

Capabilities:
  ✓ Discovery
  ✓ Harvest
  ✗ Push
  ✓ Pull
  ✗ Bidirectional

Configuration Requirements:
  Required: account, user, token
  Optional: warehouse, role, database
```

**Example Output (JSON)**:
```json
{
  "type": "SNOWFLAKE_DATA_MARKETPLACE",
  "display_name": "Snowflake Data Marketplace",
  "supported_sync_directions": ["PULL"],
  "status": "available",
  "description": "Connector for Snowflake Data Marketplace",
  "capabilities": {
    "discovery": true,
    "harvest": true,
    "push": false,
    "pull": true,
    "bidirectional": false
  },
  "configuration_requirements": {
    "required": ["account", "user", "token"],
    "optional": ["warehouse", "role", "database"]
  }
}
```

## Connections

### Create Connection

Create a new marketplace connection. Configuration can be provided as a JSON string or file path.

```bash
# Create connection with JSON string
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  --name "Snowflake Production" \
  --config '{"account": "myaccount", "user": "myuser", "token": "mytoken"}'

# Create connection with config file
datahub marketplace connections create \
  --marketplace-type AWS_DATA_EXCHANGE \
  --name "AWS Production" \
  --config config.json

# Create inactive connection
datahub marketplace connections create \
  --marketplace-type CKAN_INSTANCE \
  --name "CKAN Test" \
  --config config.json \
  --no-is-active
```

**Example Config File** (`snowflake-config.json`):
```json
{
  "account": "myaccount",
  "user": "myuser",
  "token": "mytoken",
  "warehouse": "COMPUTE_WH",
  "role": "ACCOUNTADMIN",
  "database": "MARKETPLACE_DB"
}
```

**Example Config File** (`aws-config.json`):
```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "region_name": "us-east-1"
}
```

**Example Config File** (`ckan-config.json`):
```json
{
  "base_url": "https://data.gov",
  "api_key": "your-api-key-here"
}
```

### List Connections

List marketplace connections with optional filtering.

```bash
# List all connections
datahub marketplace connections list

# Filter by marketplace type
datahub marketplace connections list --marketplace-type SNOWFLAKE_DATA_MARKETPLACE

# Filter by active status
datahub marketplace connections list --is-active true

# Pagination
datahub marketplace connections list --limit 20 --offset 0

# JSON format
datahub marketplace connections list --format json
```

**Example Output (Table)**:
```
ID                                     Name                           Marketplace Type                 Active     Created
-------------------------------------- ------------------------------ ------------------------------ ---------- --------------------
550e8400-e29b-41d4-a716-446655440000  Snowflake Production          SNOWFLAKE_DATA_MARKETPLACE      Yes        2026-01-10T10:00:00Z
660e8400-e29b-41d4-a716-446655440001  AWS Production                 AWS_DATA_EXCHANGE                Yes        2026-01-10T11:00:00Z
```

### Get Connection Details

Get detailed information about a specific connection.

```bash
# Get connection details (table format)
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000

# Get connection details (JSON format)
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000 --format json
```

**Example Output (Table)**:
```
ID: 550e8400-e29b-41d4-a716-446655440000
Name: Snowflake Production
Marketplace Type: SNOWFLAKE_DATA_MARKETPLACE
Active: True
Created: 2026-01-10T10:00:00Z
Updated: 2026-01-10T10:00:00Z
Tenant: My Tenant
```

### Test Connection

Test a marketplace connection to verify authentication and connectivity.

```bash
# Test connection
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000

# Test connection with custom config
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000 \
  --config test-config.json

# JSON format
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000 --format json
```

**Example Output (Success)**:
```
✓ Connection test successful!
Message: Connection verified successfully
Tested at: 2026-01-10T12:00:00Z
Marketplace Type: SNOWFLAKE_DATA_MARKETPLACE
Response Time: 245 ms
```

**Example Output (Failure)**:
```
✗ Connection test failed!
Message: Authentication failed
Tested at: 2026-01-10T12:00:00Z
Error: Invalid credentials
```

### Update Connection

Update connection name, configuration, or active status.

```bash
# Update connection name
datahub marketplace connections update 550e8400-e29b-41d4-a716-446655440000 \
  --name "Snowflake Production Updated"

# Update connection config
datahub marketplace connections update 550e8400-e29b-41d4-a716-446655440000 \
  --config updated-config.json

# Deactivate connection
datahub marketplace connections update 550e8400-e29b-41d4-a716-446655440000 \
  --no-is-active

# Activate connection
datahub marketplace connections update 550e8400-e29b-41d4-a716-446655440000 \
  --is-active
```

### Delete Connection

Delete a marketplace connection. Note: Connections with active sync jobs cannot be deleted.

```bash
# Delete connection
datahub marketplace connections delete 550e8400-e29b-41d4-a716-446655440000
```

## Sync Jobs

### Start Sync Job

Start a synchronization job between the Hub and marketplace.

#### PULL Sync (Harvest from Marketplace)

```bash
# PULL all listings from marketplace
datahub marketplace sync start \
  --connection-id 550e8400-e29b-41d4-a716-446655440000 \
  --direction PULL

# PULL specific listings
datahub marketplace sync start \
  --connection-id 550e8400-e29b-41d4-a716-446655440000 \
  --direction PULL \
  --listing-ids listing-1,listing-2,listing-3
```

#### PUSH Sync (Publish to Marketplace)

```bash
# PUSH assets to marketplace
datahub marketplace sync start \
  --connection-id 550e8400-e29b-41d4-a716-446655440000 \
  --direction PUSH \
  --asset-ids asset-id-1,asset-id-2,asset-id-3
```

#### BIDIRECTIONAL Sync

```bash
# BIDIRECTIONAL sync
datahub marketplace sync start \
  --connection-id 550e8400-e29b-41d4-a716-446655440000 \
  --direction BIDIRECTIONAL \
  --asset-ids asset-id-1,asset-id-2
```

**Example Output**:
```
Sync job created successfully!
ID: 770e8400-e29b-41d4-a716-446655440000
Connection: Snowflake Production
Direction: Pull
Status: Pending
Created: 2026-01-10T12:00:00Z
```

### List Sync Jobs

List sync jobs with optional filtering.

```bash
# List all sync jobs
datahub marketplace sync list

# Filter by connection
datahub marketplace sync list --connection-id 550e8400-e29b-41d4-a716-446655440000

# Filter by status
datahub marketplace sync list --status COMPLETED

# Filter by direction
datahub marketplace sync list --direction PULL

# Pagination
datahub marketplace sync list --limit 20 --offset 0

# JSON format
datahub marketplace sync list --format json
```

**Example Output (Table)**:
```
ID                                     Connection                     Direction       Status          Progress        Created
-------------------------------------- ------------------------------ --------------- --------------- --------------- -------------------------
770e8400-e29b-41d4-a716-446655440000  Snowflake Production           Pull            Running         45.2%           2026-01-10T12:00:00Z
880e8400-e29b-41d4-a716-446655440001  AWS Production                 Push            Completed       100.0%          2026-01-10T11:00:00Z
```

### Get Sync Job Details

Get detailed information about a sync job, including progress and errors.

```bash
# Get sync job details
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000

# Watch sync job (real-time updates)
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000 --watch

# JSON format
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000 --format json
```

**Example Output (Table)**:
```
ID: 770e8400-e29b-41d4-a716-446655440000
Connection: Snowflake Production
Direction: Pull
Status: Running
Items Synced: 45
Items Failed: 2
Progress: 95.7%
Errors: 2
  1. Listing listing-123: Authentication failed
  2. Listing listing-456: Invalid format
Created: 2026-01-10T12:00:00Z
Updated: 2026-01-10T12:05:00Z
```

**Watch Mode** (`--watch`):
The watch mode continuously polls the sync job and updates the display every 2 seconds until the job reaches a terminal state (COMPLETED, FAILED, or CANCELLED). Press Ctrl+C to stop watching.

### Cancel Sync Job

Cancel a running or pending sync job.

```bash
# Cancel sync job
datahub marketplace sync cancel 770e8400-e29b-41d4-a716-446655440000
```

**Example Output**:
```
Sync job cancelled successfully!
ID: 770e8400-e29b-41d4-a716-446655440000
Status: Cancelled
Updated: 2026-01-10T12:10:00Z
```

## Mappings

### List Mappings

List mappings between Hub assets and marketplace listings.

```bash
# List all mappings
datahub marketplace mappings list

# Filter by connection
datahub marketplace mappings list --connection-id 550e8400-e29b-41d4-a716-446655440000

# Filter by asset
datahub marketplace mappings list --asset-id asset-id-1

# Pagination
datahub marketplace mappings list --limit 20 --offset 0

# JSON format
datahub marketplace mappings list --format json
```

**Example Output (Table)**:
```
ID                                     Connection                     Asset                           External Listing              Last Synced
-------------------------------------- ------------------------------ ------------------------------ ------------------------------ --------------------
990e8400-e29b-41d4-a716-446655440000  Snowflake Production          Customer Analytics             LISTING_123                   2026-01-10T12:00:00Z
aa0e8400-e29b-41d4-a716-446655440001  AWS Production                 Sales Data                      LISTING_456                   2026-01-10T11:00:00Z
```

### Get Mapping Details

Get detailed information about a specific mapping.

```bash
# Get mapping details
datahub marketplace mappings get 990e8400-e29b-41d4-a716-446655440000

# JSON format
datahub marketplace mappings get 990e8400-e29b-41d4-a716-446655440000 --format json
```

**Example Output (Table)**:
```
ID: 990e8400-e29b-41d4-a716-446655440000
Connection ID: 550e8400-e29b-41d4-a716-446655440000
Connection Name: Snowflake Production
Marketplace Type: SNOWFLAKE_DATA_MARKETPLACE
Hub Asset ID: asset-id-1
Hub Asset Name: Customer Analytics
Hub Asset Status: ACTIVE
External Listing ID: LISTING_123
External Resource IDs: resource-1, resource-2
Last Sync Status: SUCCESS
Last Synced: 2026-01-10T12:00:00Z
Created: 2026-01-10T10:00:00Z
Updated: 2026-01-10T12:00:00Z
```

### Delete Mapping

Delete a mapping between a Hub asset and marketplace listing.

```bash
# Delete mapping
datahub marketplace mappings delete 990e8400-e29b-41d4-a716-446655440000
```

## Common Workflows

### Workflow 1: Discover and Connect to Marketplace

This workflow demonstrates discovering available connectors and creating a connection.

```bash
# 1. List available connectors
datahub marketplace connectors list

# 2. Get connector information
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE

# 3. Create connection configuration file
cat > snowflake-config.json << EOF
{
  "account": "myaccount",
  "user": "myuser",
  "token": "mytoken",
  "warehouse": "COMPUTE_WH"
}
EOF

# 4. Create connection
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  --name "Snowflake Production" \
  --config snowflake-config.json

# 5. Test connection
datahub marketplace connections test <connection-id>
```

### Workflow 2: Harvest Data from Marketplace (PULL)

This workflow demonstrates harvesting listings from a marketplace and creating federated assets.

```bash
# 1. List connections
datahub marketplace connections list

# 2. Start PULL sync job
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PULL

# 3. Monitor sync job progress
datahub marketplace sync get <sync-job-id> --watch

# 4. List created mappings
datahub marketplace mappings list --connection-id <connection-id>

# 5. View mapping details
datahub marketplace mappings get <mapping-id>
```

### Workflow 3: Publish Assets to Marketplace (PUSH)

This workflow demonstrates publishing Hub assets to a marketplace.

```bash
# 1. List assets to publish
datahub assets list

# 2. Start PUSH sync job
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PUSH \
  --asset-ids <asset-id-1>,<asset-id-2>

# 3. Monitor sync job
datahub marketplace sync get <sync-job-id> --watch

# 4. Verify mappings
datahub marketplace mappings list --asset-id <asset-id-1>
```

### Workflow 4: Update Connection and Re-sync

This workflow demonstrates updating a connection configuration and re-syncing.

```bash
# 1. Get current connection details
datahub marketplace connections get <connection-id>

# 2. Update connection config
datahub marketplace connections update <connection-id> \
  --config updated-config.json

# 3. Test updated connection
datahub marketplace connections test <connection-id>

# 4. Start new sync job
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PULL
```

### Workflow 5: Monitor and Troubleshoot Sync Jobs

This workflow demonstrates monitoring sync jobs and handling errors.

```bash
# 1. List all sync jobs
datahub marketplace sync list

# 2. Get detailed job information
datahub marketplace sync get <sync-job-id>

# 3. Watch job progress in real-time
datahub marketplace sync get <sync-job-id> --watch

# 4. If job fails, check errors
datahub marketplace sync get <sync-job-id> --format json | jq '.errors'

# 5. Cancel stuck job if needed
datahub marketplace sync cancel <sync-job-id>

# 6. Check mappings for failed items
datahub marketplace mappings list --connection-id <connection-id>
```

## Error Handling

The CLI provides comprehensive error handling with user-friendly messages and actionable suggestions.

### Common Errors and Solutions

#### Invalid Marketplace Type

**Error**:
```
Error: Invalid marketplace type: INVALID_TYPE
  Marketplace Type: INVALID_TYPE

💡 Suggestion: Use one of: SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE, ...
```

**Solution**:
```bash
# List available connector types
datahub marketplace connectors list

# Use a valid marketplace type
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  ...
```

#### Invalid Connection ID Format

**Error**:
```
Error: Invalid connection ID format: invalid-id
  Connection ID: invalid-id

💡 Suggestion: Connection ID must be a valid UUID (e.g., 550e8400-e29b-41d4-a716-446655440000)
```

**Solution**:
```bash
# List connections to get valid IDs
datahub marketplace connections list

# Use a valid UUID
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000
```

#### Invalid Configuration Format

**Error**:
```
Error: Configuration must be valid JSON or a file path. Got: invalid-json
  Config: invalid-json

💡 Suggestion: Provide configuration as a JSON string or path to a JSON file
```

**Solution**:
```bash
# Use valid JSON string
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  --name "Test" \
  --config '{"account": "myaccount", "user": "myuser", "token": "mytoken"}'

# Or use a JSON file
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  --name "Test" \
  --config config.json
```

#### Connection Test Failed

**Error**:
```
✗ Connection test failed!
Message: Authentication failed
Tested at: 2026-01-10T12:00:00Z
Error: Invalid credentials
```

**Solution**:
```bash
# 1. Get connector info to check required config fields
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE

# 2. Verify configuration
datahub marketplace connections get <connection-id>

# 3. Update configuration with correct credentials
datahub marketplace connections update <connection-id> \
  --config corrected-config.json

# 4. Test again
datahub marketplace connections test <connection-id>
```

#### Sync Job Validation Errors

**Error**:
```
Error: --asset-ids is required for PUSH direction
```

**Solution**:
```bash
# For PUSH, provide asset IDs
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PUSH \
  --asset-ids <asset-id-1>,<asset-id-2>

# For PULL, asset IDs are not allowed
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PULL
```

#### Connector Not Found

**Error**:
```
Error: Connector type not found: INVALID_CONNECTOR
  Connector Type: INVALID_CONNECTOR

💡 Suggestion: Use 'datahub marketplace connectors list' to see available connector types
```

**Solution**:
```bash
# List available connectors
datahub marketplace connectors list

# Use a valid connector type
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE
```

### Error Handling Best Practices

1. **Always validate inputs**: Use `list` commands to verify IDs and types before operations
2. **Check connector capabilities**: Use `connectors info` to verify supported sync directions
3. **Test connections first**: Always test connections before starting sync jobs
4. **Monitor sync jobs**: Use `--watch` flag to monitor sync job progress
5. **Review error messages**: Error messages include suggestions for resolution
6. **Use JSON format for debugging**: Use `--format json` to get detailed error information

## Troubleshooting

### Connection Issues

**Problem**: Connection test fails with authentication error

**Diagnosis**:
```bash
# 1. Check connector requirements
datahub marketplace connectors info <connector-type>

# 2. Verify connection config
datahub marketplace connections get <connection-id>

# 3. Test with verbose output
datahub marketplace connections test <connection-id> --format json
```

**Solutions**:
- Verify all required configuration fields are provided
- Check credentials are valid and not expired
- Ensure network connectivity to marketplace
- Review connector-specific documentation for configuration requirements

### Sync Job Issues

**Problem**: Sync job fails or gets stuck

**Diagnosis**:
```bash
# 1. Get detailed job information
datahub marketplace sync get <sync-job-id> --format json

# 2. Check for errors
datahub marketplace sync get <sync-job-id> | grep -i error

# 3. List recent sync jobs
datahub marketplace sync list --status FAILED
```

**Solutions**:
- Review error messages in sync job details
- Check connection status: `datahub marketplace connections test <connection-id>`
- Verify marketplace service availability
- Check asset/mapping status for specific failures
- Cancel stuck jobs and retry: `datahub marketplace sync cancel <sync-job-id>`

### Mapping Issues

**Problem**: Mappings not created after sync

**Diagnosis**:
```bash
# 1. Check sync job status
datahub marketplace sync get <sync-job-id>

# 2. List mappings for connection
datahub marketplace mappings list --connection-id <connection-id>

# 3. Check sync job errors
datahub marketplace sync get <sync-job-id> --format json | jq '.errors'
```

**Solutions**:
- Verify sync job completed successfully
- Check for errors in sync job details
- Ensure assets exist and are in correct status
- Review marketplace-specific requirements

### Performance Issues

**Problem**: Sync jobs take too long

**Solutions**:
- Use `--listing-ids` for PULL to sync specific listings only
- Use `--asset-ids` for PUSH to sync specific assets only
- Monitor progress with `--watch` flag
- Check marketplace API rate limits
- Consider breaking large syncs into smaller batches

## Command Reference

### Connectors

| Command | Description | Options |
|---------|-------------|---------|
| `connectors list` | List available connector types | `--format json\|table` |
| `connectors info <type>` | Get connector information | `--format json\|table` |

### Connections

| Command | Description | Options |
|---------|-------------|---------|
| `connections create` | Create marketplace connection | `--marketplace-type`, `--name`, `--config`, `--is-active/--no-is-active`, `--format` |
| `connections list` | List connections | `--marketplace-type`, `--is-active`, `--limit`, `--offset`, `--format` |
| `connections get <id>` | Get connection details | `--format` |
| `connections update <id>` | Update connection | `--name`, `--config`, `--is-active/--no-is-active`, `--format` |
| `connections test <id>` | Test connection | `--config`, `--format` |
| `connections delete <id>` | Delete connection | `--format` |

### Sync Jobs

| Command | Description | Options |
|---------|-------------|---------|
| `sync start` | Start sync job | `--connection-id`, `--direction`, `--asset-ids`, `--listing-ids`, `--format` |
| `sync list` | List sync jobs | `--connection-id`, `--status`, `--direction`, `--limit`, `--offset`, `--format` |
| `sync get <id>` | Get sync job details | `--format`, `--watch` |
| `sync cancel <id>` | Cancel sync job | `--format` |

### Mappings

| Command | Description | Options |
|---------|-------------|---------|
| `mappings list` | List mappings | `--connection-id`, `--asset-id`, `--limit`, `--offset`, `--format` |
| `mappings get <id>` | Get mapping details | `--format` |
| `mappings delete <id>` | Delete mapping | `--format` |

## Additional Resources

- **[CLI README](../README.md)** - Complete CLI documentation
- **[ODPS Usage Guide](ODPS_USAGE.md)** - ODPS contract management
- **[BaaS Usage Guide](BAAS_USAGE.md)** - BaaS platform commands
- **[ODH Usage Guide](ODH_USAGE.md)** - ML/ODH commands
- **[Model Serving Usage Guide](MODEL_SERVING_USAGE.md)** - Model serving and A/B testing
- **[Marketplace Integration API Reference](../../docs/MARKETPLACE_API_REFERENCE.md)** - Complete marketplace API documentation
- **[Marketplace Integration User Guide](../../docs/MARKETPLACE_INTEGRATION_USER_GUIDE.md)** - User guide for marketplace integrations
- **[API Reference](../../docs/API_REFERENCE.md)** - Complete API documentation
