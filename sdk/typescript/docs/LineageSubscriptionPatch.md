# LineageSubscriptionPatch

REQ-LIN-F3-003 PATCH — only the channel + threshold are mutable.  The source FK is immutable post-create (a user who wants to re-target deletes + re-creates).  This keeps the dispatcher\'s debounce key stable across edits.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**severity_threshold** | **string** | * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical | [optional] [default to undefined]
**in_app** | **boolean** |  | [optional] [default to undefined]
**email** | **boolean** |  | [optional] [default to undefined]
**slack** | **boolean** |  | [optional] [default to undefined]

## Example

```typescript
import { LineageSubscriptionPatch } from './api';

const instance: LineageSubscriptionPatch = {
    severity_threshold,
    in_app,
    email,
    slack,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
