# BaaS (Backend as a Service) CLI Command Reference

> **Canonical guide:** [../../sdk/python/docs/BAAS_USAGE.md](../../sdk/python/docs/BAAS_USAGE.md)
> (concepts, SDK code, and setup — this file keeps ONLY the CLI command
> examples; W6.4 dedupe of the diverging `cli/docs` vs `sdk/python/docs`
> copies).

### Create API Key
```bash
# Create API key with default FREE tier
datahub baas api-keys create --name "My API Key"

# Create API key with PRO tier
datahub baas api-keys create \
  --name "Production Key" \
  --tier PRO

# Create API key with expiration date
datahub baas api-keys create \
  --name "Temporary Key" \
  --tier FREE \
  --expires-at "2025-12-31T23:59:59Z"

# Create API key with JSON output
datahub baas api-keys create \
  --name "My API Key" \
  --format json
```

```
API key created successfully!

⚠️  IMPORTANT: Save this API key securely. It will not be shown again.

ID: 123e4567-e89b-12d3-a456-426614174000
Name: My API Key
API Key: dh_live_abc123xyz789...
Tier: FREE
Created At: 2025-01-12T10:30:00Z

💡 Use this API key with: datahub config set api_key <key>
```

### List API Keys
```bash
# List all API keys (table format)
datahub baas api-keys list

# List API keys with tier filter
datahub baas api-keys list --tier PRO

# List API keys with pagination
datahub baas api-keys list --limit 10 --offset 20

# List API keys in JSON format
datahub baas api-keys list --format json
```

### Get API Key Details
```bash
# Get API key details (table format)
datahub baas api-keys get <api-key-id>

# Get API key details in JSON format
datahub baas api-keys get <api-key-id> --format json
```

### Update API Key
```bash
# Update API key name
datahub baas api-keys update <api-key-id> --name "Updated Name"

# Update API key tier
datahub baas api-keys update <api-key-id> --tier PRO

# Update expiration date
datahub baas api-keys update <api-key-id> \
  --expires-at "2026-12-31T23:59:59Z"

# Update multiple fields
datahub baas api-keys update <api-key-id> \
  --name "Updated Name" \
  --tier PRO \
  --expires-at "2026-12-31T23:59:59Z"
```

### Revoke API Key
```bash
# Revoke API key
datahub baas api-keys revoke <api-key-id>

# Revoke API key with JSON output
datahub baas api-keys revoke <api-key-id> --format json
```

### Get Usage Statistics
```bash
# Get usage statistics (table format)
datahub baas usage stats

# Get usage statistics for specific API key
datahub baas usage stats --api-key-id <api-key-id>

# Get usage statistics for date range
datahub baas usage stats \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage statistics in JSON format
datahub baas usage stats --format json
```

### Get Usage by Endpoint
```bash
# Get usage by endpoint (table format)
datahub baas usage by-endpoint

# Get usage by endpoint for specific API key
datahub baas usage by-endpoint --api-key-id <api-key-id>

# Get usage by endpoint for date range
datahub baas usage by-endpoint \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage by endpoint in JSON format
datahub baas usage by-endpoint --format json
```

### Get Usage by Tenant
```bash
# Get usage by tenant (table format)
datahub baas usage by-tenant

# Get usage by tenant for date range
datahub baas usage by-tenant \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# Get usage by tenant in JSON format
datahub baas usage by-tenant --format json
```

### Show API Documentation
```bash
# Show API documentation (default: HTML format)
datahub baas docs show

# Show API documentation in JSON format
datahub baas docs show --format json

# Show API documentation in HTML format
datahub baas docs show --format html

# Show API documentation in Markdown format
datahub baas docs show --format markdown
```

### Get OpenAPI Schema
```bash
# Get OpenAPI schema (default: JSON format)
datahub baas docs openapi

# Get OpenAPI schema in JSON format
datahub baas docs openapi --format json

# Get OpenAPI schema in YAML format
datahub baas docs openapi --format yaml
```

### Get SDK Download Links
```bash
# List SDK download links (default: table format)
datahub baas docs sdks

# List SDK download links in JSON format
datahub baas docs sdks --format json
```

### Workflow 1: Create API Key and Configure CLI
```bash
# 1. Create API key
datahub baas api-keys create --name "CLI Key" --tier FREE

# Output shows the API key value - save it!
# API Key: dh_live_abc123xyz789...

# 2. Configure CLI to use the API key
datahub config set api_key dh_live_abc123xyz789...

# 3. Verify configuration
datahub config get

# 4. Test API access
datahub assets list
```

### Workflow 2: Monitor API Usage
```bash
# 1. Get overall usage statistics
datahub baas usage stats

# 2. Get usage breakdown by endpoint
datahub baas usage by-endpoint

# 3. Get usage for specific date range
datahub baas usage stats \
  --start-date "2025-01-01T00:00:00Z" \
  --end-date "2025-01-31T23:59:59Z"

# 4. Get usage for specific API key
datahub baas usage stats --api-key-id <api-key-id>
```

### Workflow 3: Manage API Keys Lifecycle
```bash
# 1. Create API key for development
DEV_KEY_ID=$(datahub baas api-keys create \
  --name "Development Key" \
  --tier FREE \
  --format json | jq -r '.id')

# 2. Create API key for production with expiration
PROD_KEY_ID=$(datahub baas api-keys create \
  --name "Production Key" \
  --tier PRO \
  --expires-at "2025-12-31T23:59:59Z" \
  --format json | jq -r '.id')

# 3. List all API keys
datahub baas api-keys list

# 4. Update production key tier if needed
datahub baas api-keys update $PROD_KEY_ID --tier ENTERPRISE

# 5. Revoke development key when no longer needed
datahub baas api-keys revoke $DEV_KEY_ID
```

### Workflow 4: Access Developer Resources
```bash
# 1. Get API documentation overview
datahub baas docs show --format json > api-docs.json

# 2. Download OpenAPI schema
datahub baas docs openapi --format json > openapi.json

# 3. Get SDK download links
datahub baas docs sdks --format json > sdks.json

# 4. Use OpenAPI schema with code generators
# (e.g., openapi-generator, swagger-codegen)
```

#### Invalid API Key ID
```bash
$ datahub baas api-keys get invalid-id
Error: API key not found: invalid-id
Error Code: API_KEY_NOT_FOUND
Suggestion: Check that the API key ID is correct
```

#### Empty API Key Name
```bash
$ datahub baas api-keys create --name ""
Error: API key name cannot be empty
Error Code: INVALID_NAME
Suggestion: Provide a non-empty name for the API key
```

#### Invalid Expiration Date
```bash
$ datahub baas api-keys create --name "Key" --expires-at "2020-01-01"
Error: Expiration date must be in the future
Error Code: INVALID_EXPIRATION_DATE
Suggestion: Provide a future date in ISO format (e.g., 2025-12-31T23:59:59Z)
```

#### Missing Update Fields
```bash
$ datahub baas api-keys update <api-key-id>
Error: At least one field (--name, --tier, or --expires-at) must be provided
Error Code: MISSING_UPDATE_FIELDS
Suggestion: Provide at least one field to update
```

#### YAML Format Unavailable
```bash
$ datahub baas docs openapi --format yaml
Error: YAML format requires PyYAML. Please install it with: pip install pyyaml
Error Code: YAML_FORMAT_UNAVAILABLE
Suggestion: Install PyYAML or use JSON format
```

### API Key Not Working
   ```bash
   datahub baas api-keys get <api-key-id>
   ```

   ```bash
   datahub baas api-keys list
   ```

   ```bash
   datahub config get
   ```

   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### Rate Limit Exceeded
   ```bash
   datahub baas docs show --format json | jq '.rate_limiting.tiers'
   ```

   ```bash
   datahub baas usage stats
   ```

   ```bash
   datahub baas api-keys update <api-key-id> --tier PRO
   ```

### API Key Expired
   ```bash
   datahub baas api-keys get <api-key-id>
   ```

   ```bash
   datahub baas api-keys update <api-key-id> \
     --expires-at "2026-12-31T23:59:59Z"
   ```

   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### OpenAPI Schema Not Loading
   ```bash
   datahub config get
   ```

   ```bash
   datahub baas docs openapi --format json
   ```

## Troubleshooting

### API Key Not Working

**Symptoms**: API requests fail with authentication errors.

**Solutions**:
1. Verify API key is active:
   ```bash
   datahub baas api-keys get <api-key-id>
   ```
2. Check if API key is revoked:
   ```bash
   datahub baas api-keys list
   ```
3. Verify API key is configured:
   ```bash
   datahub config get
   ```
4. Re-create API key if needed:
   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### Rate Limit Exceeded

**Symptoms**: API requests fail with 429 (Too Many Requests) errors.

**Solutions**:
1. Check current tier limits:
   ```bash
   datahub baas docs show --format json | jq '.rate_limiting.tiers'
   ```
2. Check usage statistics:
   ```bash
   datahub baas usage stats
   ```
3. Upgrade tier if needed:
   ```bash
   datahub baas api-keys update <api-key-id> --tier PRO
   ```

### API Key Expired

**Symptoms**: API requests fail with authentication errors after expiration date.

**Solutions**:
1. Check expiration date:
   ```bash
   datahub baas api-keys get <api-key-id>
   ```
2. Update expiration date:
   ```bash
   datahub baas api-keys update <api-key-id> \
     --expires-at "2026-12-31T23:59:59Z"
   ```
3. Create new API key if update not possible:
   ```bash
   datahub baas api-keys create --name "New Key" --tier FREE
   ```

### OpenAPI Schema Not Loading

**Symptoms**: `datahub baas docs openapi` fails or returns empty.

**Solutions**:
1. Check API connectivity:
   ```bash
   curl http://localhost:8000/api/v1/baas/docs/openapi.json/
   ```
2. Verify authentication:
   ```bash
   datahub config get
   ```
3. Try JSON format:
   ```bash
   datahub baas docs openapi --format json
   ```
