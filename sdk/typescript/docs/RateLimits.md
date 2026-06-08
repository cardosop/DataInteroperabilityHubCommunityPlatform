# RateLimits

Serializer for rate limits structure

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**burst_per_10s** | **number** |  | [optional] [default to undefined]
**sustained_per_min** | **number** |  | [optional] [default to undefined]
**daily_cap** | **number** |  | [optional] [default to undefined]

## Example

```typescript
import { RateLimits } from './api';

const instance: RateLimits = {
    burst_per_10s,
    sustained_per_min,
    daily_cap,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
