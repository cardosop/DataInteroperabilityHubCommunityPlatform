# CapabilitiesResponse


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**capabilities** | **{ [key: string]: boolean; }** | Flat map of capability flag name → enabled. Phase 228 ships five lineage flags; future phases extend this map. | [default to undefined]

## Example

```typescript
import { CapabilitiesResponse } from './api';

const instance: CapabilitiesResponse = {
    capabilities,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
