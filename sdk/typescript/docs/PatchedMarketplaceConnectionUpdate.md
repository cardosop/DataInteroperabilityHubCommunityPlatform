# PatchedMarketplaceConnectionUpdate

Serializer for updating a marketplace connection.  All fields are optional - only provided fields will be updated.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Human-readable name for this connection | [optional] [default to undefined]
**config** | **any** | Connection configuration dictionary. Will be encrypted at rest. | [optional] [default to undefined]
**is_active** | **boolean** | Whether this connection is active and can be used | [optional] [default to undefined]

## Example

```typescript
import { PatchedMarketplaceConnectionUpdate } from './api';

const instance: PatchedMarketplaceConnectionUpdate = {
    name,
    config,
    is_active,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
