# FailedJobDLQ

Serializer for FailedJobDLQ (Phase 91.9).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**job_id** | **string** | Original Job UUID that failed | [optional] [readonly] [default to undefined]
**queue** | **string** | RQ queue name the job was on | [optional] [readonly] [default to undefined]
**func_name** | **string** | Fully-qualified function name | [optional] [readonly] [default to undefined]
**args_json** | **any** | Serialised positional and keyword arguments | [optional] [readonly] [default to undefined]
**error_message** | **string** | Final error message | [optional] [readonly] [default to undefined]
**traceback** | **string** | Full traceback at time of final failure | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant the job belonged to | [optional] [readonly] [default to undefined]
**retry_count** | **number** | Number of times retried | [optional] [readonly] [default to undefined]
**resolved_at** | **string** | When resolved | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { FailedJobDLQ } from './api';

const instance: FailedJobDLQ = {
    id,
    job_id,
    queue,
    func_name,
    args_json,
    error_message,
    traceback,
    tenant,
    retry_count,
    resolved_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
