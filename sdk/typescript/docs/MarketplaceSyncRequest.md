# MarketplaceSyncRequest

Serializer for creating a marketplace sync job request.  Supports both PUSH (sync assets to marketplace) and PULL (sync from marketplace) operations.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**connection_id** | **string** | ID of the marketplace connection to use for sync | [default to undefined]
**direction** | **string** | Sync direction: PUSH (Hub → Marketplace) or PULL (Marketplace → Hub)  * &#x60;PUSH&#x60; - Push * &#x60;PULL&#x60; - Pull * &#x60;BIDIRECTIONAL&#x60; - Bidirectional | [default to undefined]
**asset_ids** | **Array&lt;string&gt;** | List of Hub asset IDs to synchronize (required for PUSH direction) | [optional] [default to undefined]
**listing_ids** | **Array&lt;string&gt;** | List of marketplace listing IDs to sync (optional for PULL direction) | [optional] [default to undefined]
**filters** | **any** | Optional dictionary of filters to apply (for PULL direction) | [optional] [default to undefined]
**_options** | **any** | Optional dictionary of sync options (e.g., dry_run, force_update, create_assets) | [optional] [default to undefined]

## Example

```typescript
import { MarketplaceSyncRequest } from './api';

const instance: MarketplaceSyncRequest = {
    connection_id,
    direction,
    asset_ids,
    listing_ids,
    filters,
    _options,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
