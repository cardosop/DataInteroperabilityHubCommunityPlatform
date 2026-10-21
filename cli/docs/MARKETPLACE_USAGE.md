# Marketplace Integration CLI Command Reference

> **Canonical guide:** [../../sdk/python/docs/MARKETPLACE_USAGE.md](../../sdk/python/docs/MARKETPLACE_USAGE.md)
> (concepts, SDK code, and setup — this file keeps ONLY the CLI command
> examples; W6.4 dedupe of the diverging `cli/docs` vs `sdk/python/docs`
> copies).

### List Available Connectors
```bash
# List all connectors (table format)
datahub marketplace connectors list

# List all connectors (JSON format)
datahub marketplace connectors list --format json
```

### Get Connector Information
```bash
# Get connector info (table format)
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE

# Get connector info (JSON format)
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE --format json
```

### Create Connection
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

### List Connections
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

### Get Connection Details
```bash
# Get connection details (table format)
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000

# Get connection details (JSON format)
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000 --format json
```

### Test Connection
```bash
# Test connection
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000

# Test connection with custom config
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000 \
  --config test-config.json

# JSON format
datahub marketplace connections test 550e8400-e29b-41d4-a716-446655440000 --format json
```

### Update Connection
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
```bash
# Delete connection
datahub marketplace connections delete 550e8400-e29b-41d4-a716-446655440000
```

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

### List Sync Jobs
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

### Get Sync Job Details
```bash
# Get sync job details
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000

# Watch sync job (real-time updates)
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000 --watch

# JSON format
datahub marketplace sync get 770e8400-e29b-41d4-a716-446655440000 --format json
```

### Cancel Sync Job
```bash
# Cancel sync job
datahub marketplace sync cancel 770e8400-e29b-41d4-a716-446655440000
```

### List Mappings
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

### Get Mapping Details
```bash
# Get mapping details
datahub marketplace mappings get 990e8400-e29b-41d4-a716-446655440000

# JSON format
datahub marketplace mappings get 990e8400-e29b-41d4-a716-446655440000 --format json
```

### Delete Mapping
```bash
# Delete mapping
datahub marketplace mappings delete 990e8400-e29b-41d4-a716-446655440000
```

### Workflow 1: Discover and Connect to Marketplace
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

#### Invalid Marketplace Type
```bash
# List available connector types
datahub marketplace connectors list

# Use a valid marketplace type
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  ...
```

#### Invalid Connection ID Format
```bash
# List connections to get valid IDs
datahub marketplace connections list

# Use a valid UUID
datahub marketplace connections get 550e8400-e29b-41d4-a716-446655440000
```

#### Invalid Configuration Format
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
```
Error: Connector type not found: INVALID_CONNECTOR
  Connector Type: INVALID_CONNECTOR

💡 Suggestion: Use 'datahub marketplace connectors list' to see available connector types
```

```bash
# List available connectors
datahub marketplace connectors list

# Use a valid connector type
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE
```

### Connection Issues
```bash
# 1. Check connector requirements
datahub marketplace connectors info <connector-type>

# 2. Verify connection config
datahub marketplace connections get <connection-id>

# 3. Test with verbose output
datahub marketplace connections test <connection-id> --format json
```

### Sync Job Issues
```bash
# 1. Get detailed job information
datahub marketplace sync get <sync-job-id> --format json

# 2. Check for errors
datahub marketplace sync get <sync-job-id> | grep -i error

# 3. List recent sync jobs
datahub marketplace sync list --status FAILED
```

### Mapping Issues
```bash
# 1. Check sync job status
datahub marketplace sync get <sync-job-id>

# 2. List mappings for connection
datahub marketplace mappings list --connection-id <connection-id>

# 3. Check sync job errors
datahub marketplace sync get <sync-job-id> --format json | jq '.errors'
```

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
