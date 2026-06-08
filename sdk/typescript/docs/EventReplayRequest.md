# EventReplayRequest

Serializer for event replay request.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**event_type** | **string** | Filter by event type (e.g., \&#39;odps.created\&#39;) | [optional] [default to undefined]
**tenant_id** | **string** | Filter by tenant ID | [optional] [default to undefined]
**start_time** | **string** | Start time for replay (ISO 8601 format) | [optional] [default to undefined]
**end_time** | **string** | End time for replay (ISO 8601 format) | [optional] [default to undefined]
**limit** | **number** | Maximum number of events to replay (default: 100, max: 1000) | [optional] [default to 100]

## Example

```typescript
import { EventReplayRequest } from './api';

const instance: EventReplayRequest = {
    event_type,
    tenant_id,
    start_time,
    end_time,
    limit,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
