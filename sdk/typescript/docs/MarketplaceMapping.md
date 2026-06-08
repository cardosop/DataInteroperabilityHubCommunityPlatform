# MarketplaceMapping

Serializer for MarketplaceMapping model (read operations).  Provides read-only access to marketplace mappings with related entity information.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the mapping | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant ID | [optional] [readonly] [default to undefined]
**tenant_name** | **string** | Tenant name | [optional] [readonly] [default to undefined]
**connection_id** | **string** | Connection ID | [optional] [readonly] [default to undefined]
**connection_name** | **string** | Connection name | [optional] [readonly] [default to undefined]
**hub_asset_id** | **string** | Hub asset ID | [optional] [readonly] [default to undefined]
**hub_asset_name** | **string** | Hub asset name | [optional] [readonly] [default to undefined]
**hub_asset_key** | **string** | Hub asset key | [optional] [readonly] [default to undefined]
**external_listing_id** | **string** | External marketplace listing identifier | [optional] [readonly] [default to undefined]
**external_resource_ids** | **any** | List of external resource identifiers (e.g., dataset IDs, file IDs) | [optional] [readonly] [default to undefined]
**sync_metadata** | **any** | Metadata about the synchronization (last sync status, errors, etc.) | [optional] [readonly] [default to undefined]
**last_synced_at** | **string** | Timestamp of last successful synchronization | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { MarketplaceMapping } from './api';

const instance: MarketplaceMapping = {
    id,
    tenant,
    tenant_name,
    connection_id,
    connection_name,
    hub_asset_id,
    hub_asset_name,
    hub_asset_key,
    external_listing_id,
    external_resource_ids,
    sync_metadata,
    last_synced_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
