# Esri Marketplace Integration Guide

## Overview

This guide covers integration with Esri Marketplace (ArcGIS Marketplace), a platform for discovering and accessing geospatial data products and services.

## Marketplace Type

- **Type**: `ESRI_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Esri OAuth 2.0 / API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "portal_url": "https://your-organization.maps.arcgis.com",
  "client_id": "your-esri-client-id",
  "client_secret": "your-esri-client-secret"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `portal_url` | string | Yes | Esri Portal URL (e.g., `https://your-org.maps.arcgis.com`) |
| `client_id` | string | Yes | Esri OAuth client ID |
| `client_secret` | string | Yes | Esri OAuth client secret |

### Optional Configuration

```json
{
  "portal_url": "https://your-organization.maps.arcgis.com",
  "client_id": "your-esri-client-id",
  "client_secret": "your-esri-client-secret",
  "organization_id": "your-organization-id",
  "api_key": "optional-api-key"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organization_id` | string | No | Esri organization ID |
| `api_key` | string | No | Esri API key (for some operations) |

## Creating an Esri Marketplace Connection

### Step 1: Prepare Esri Account

1. Ensure you have an Esri account with Marketplace access
2. Register application in Esri Developer Portal:
   - Go to https://developers.arcgis.com
   - Create new application
   - Configure OAuth redirect URLs
   - Note down client ID and client secret
3. Note your organization ID (if applicable)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "ESRI_MARKETPLACE",
  "name": "My Esri Marketplace",
  "config": {
    "portal_url": "https://your-organization.maps.arcgis.com",
    "client_id": "your-esri-client-id",
    "client_secret": "your-esri-client-secret",
    "organization_id": "your-organization-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Esri Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Esri:

1. **Item Creation**: Assets are published as Esri items (layers, services, etc.)
2. **Geospatial Metadata**: Asset metadata is published with geospatial information
3. **ODPS Integration**: Uses ODPS contracts for item descriptions
4. **ArcGIS Integration**: Integrates with ArcGIS Online/Enterprise

### Product Discovery (PULL)

When syncing from Esri:

1. **Item Discovery**: Lists available items in the marketplace
2. **Subscription**: Subscribes to selected items
3. **Geospatial Access**: Accesses geospatial data and services
4. **ODPS Generation**: Generates ODPS contracts from item metadata

## Esri Marketplace-Specific Limitations

1. **Account Requirements**: Requires Esri account with Marketplace access
2. **Geospatial Formats**: Requires understanding of geospatial data formats (GeoJSON, Shapefile, etc.)
3. **Portal Requirements**: Requires ArcGIS Online or Enterprise portal
4. **Coordinate Systems**: Must handle various coordinate reference systems
5. **Subscription Model**: PULL operations require item subscription
6. **Service Types**: Supports various service types (Feature Services, Map Services, etc.)

## Best Practices

1. **Geospatial Standards**: Understand geospatial data standards (OGC, ISO)
2. **Coordinate Systems**: Handle coordinate reference system transformations
3. **Service Types**: Understand different ArcGIS service types
4. **Metadata Quality**: Ensure complete geospatial metadata
5. **Portal Configuration**: Configure portal settings appropriately

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify client ID and client secret are correct

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct or remove from config

**Issue**: Geospatial data format errors
- **Solution**: Verify geospatial data formats are compatible with Esri

**Issue**: Service creation fails
- **Solution**: Check service type requirements and portal permissions

## Additional Resources

- [Esri ArcGIS Marketplace Documentation](https://doc.arcgis.com/en/marketplace/)
- [Esri REST API Documentation](https://developers.arcgis.com/rest/)
- [Esri OAuth Documentation](https://developers.arcgis.com/documentation/mapping-apis-and-services/security/oauth-2.0/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
