# EventReplayResponse

Serializer for event replay response.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**success** | **boolean** | Whether replay was successful | [default to undefined]
**events_replayed** | **number** | Number of events replayed | [default to undefined]
**events_skipped** | **number** | Number of events skipped (duplicates) | [default to undefined]
**total_events_found** | **number** | Total number of events found matching filters | [default to undefined]
**event_ids** | **Array&lt;string&gt;** | List of event IDs that were replayed | [default to undefined]
**skipped_event_ids** | **Array&lt;string&gt;** | List of event IDs that were skipped (duplicates) | [default to undefined]

## Example

```typescript
import { EventReplayResponse } from './api';

const instance: EventReplayResponse = {
    success,
    events_replayed,
    events_skipped,
    total_events_found,
    event_ids,
    skipped_event_ids,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
