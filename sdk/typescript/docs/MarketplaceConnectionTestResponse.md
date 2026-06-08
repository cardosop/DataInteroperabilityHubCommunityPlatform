# MarketplaceConnectionTestResponse

Serializer for connection test response.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**success** | **boolean** | Whether the connection test was successful | [default to undefined]
**message** | **string** | Test result message | [default to undefined]
**error** | **string** | Error message if test failed | [optional] [default to undefined]
**tested_at** | **string** | Timestamp when the test was performed (ISO format) | [default to undefined]
**connection_id** | **string** | ID of the tested connection | [default to undefined]

## Example

```typescript
import { MarketplaceConnectionTestResponse } from './api';

const instance: MarketplaceConnectionTestResponse = {
    success,
    message,
    error,
    tested_at,
    connection_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
