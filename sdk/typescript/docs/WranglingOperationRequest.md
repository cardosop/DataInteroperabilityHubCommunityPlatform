# WranglingOperationRequest

Serializer for wrangling operation request

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**asset_id** | **string** | Source asset ID | [default to undefined]
**operation** | **{ [key: string]: any; }** | Operation definition with \&#39;type\&#39; and \&#39;parameters\&#39; | [default to undefined]
**session_id** | **string** | Optional wrangling session ID (creates new if not provided) | [optional] [default to undefined]

## Example

```typescript
import { WranglingOperationRequest } from './api';

const instance: WranglingOperationRequest = {
    asset_id,
    operation,
    session_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
