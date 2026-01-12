# Collibra Data Marketplace Integration Guide

## Overview

This guide covers integration with Collibra Data Marketplace, a platform for discovering and accessing data products within the Collibra Data Intelligence Cloud ecosystem.

## Marketplace Type

- **Type**: `COLLIBRA_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Collibra API Token / OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://your-instance.collibra.com",
  "username": "your-collibra-username",
  "password": "your-collibra-password"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | Collibra API endpoint (e.g., `https://your-instance.collibra.com`) |
| `username` | string | Yes | Collibra username |
| `password` | string | Yes | Collibra password |

### Optional Configuration

```json
{
  "api_endpoint": "https://your-instance.collibra.com",
  "username": "your-collibra-username",
  "password": "your-collibra-password",
  "api_token": "optional-api-token",
  "community_id": "your-community-id"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_token` | string | No | Collibra API token (alternative to username/password) |
| `community_id` | string | No | Collibra community ID |

## Creating a Collibra Data Marketplace Connection

### Step 1: Prepare Collibra Account

1. Ensure you have a Collibra Data Intelligence Cloud account
2. Generate API token (optional):
   - Go to User Settings → API Tokens
   - Generate new token
   - Note down the token
3. Note your community ID (if applicable)
4. Ensure user has necessary permissions:
   - Data Marketplace Admin
   - API access enabled

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "COLLIBRA_DATA_MARKETPLACE",
  "name": "My Collibra Data Marketplace",
  "config": {
    "api_endpoint": "https://your-instance.collibra.com",
    "username": "your-collibra-username",
    "password": "your-collibra-password",
    "community_id": "your-community-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Collibra Data Marketplace-Specific Features

### Asset Publishing (PUSH)

When syncing assets to Collibra:

1. **Asset Creation**: Assets are published as Collibra data assets
2. **Metadata Publishing**: Asset metadata is published with data governance information
3. **ODPS Integration**: Uses ODPS contracts for asset descriptions
4. **Data Governance**: Integrates with Collibra data governance framework

### Asset Discovery (PULL)

When syncing from Collibra:

1. **Asset Discovery**: Lists available data assets in the marketplace
2. **Subscription**: Subscribes to selected assets
3. **Data Access**: Accesses data assets via Collibra
4. **ODPS Generation**: Generates ODPS contracts from asset metadata

## Collibra Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires Collibra Data Intelligence Cloud account
2. **Data Governance**: Requires understanding of Collibra data governance model
3. **Community Scope**: Assets may be community-scoped
4. **API Token Management**: API tokens must be managed securely
5. **Subscription Model**: PULL operations require asset subscription
6. **Governance Integration**: Requires integration with Collibra governance framework

## Best Practices

1. **API Token Security**: Store API tokens securely
2. **Community Management**: Use community ID for proper scoping
3. **Data Governance**: Understand Collibra data governance model
4. **Metadata Quality**: Ensure complete metadata with governance information
5. **Governance Integration**: Integrate with Collibra governance workflows

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify username and password are correct, or use API token

**Issue**: PUSH sync fails with "Community not found"
- **Solution**: Ensure community ID is correct or remove from config

**Issue**: Asset creation fails
- **Solution**: Check asset requirements and data governance permissions

**Issue**: Governance integration errors
- **Solution**: Verify governance framework configuration

## Additional Resources

- [Collibra Data Marketplace Documentation](https://documentation.collibra.com/data-marketplace)
- [Collibra API Documentation](https://developer.collibra.com/)
- [Collibra Data Governance Documentation](https://documentation.collibra.com/data-governance)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
