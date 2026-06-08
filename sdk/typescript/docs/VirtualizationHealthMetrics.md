# VirtualizationHealthMetrics

Serializer for virtual dataset health metrics

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**health_score** | **number** | Health score (0-100) | [default to undefined]
**total_executions** | **number** | Total number of query executions | [default to undefined]
**completed_executions** | **number** | Number of completed executions | [default to undefined]
**failed_executions** | **number** | Number of failed executions | [default to undefined]
**running_executions** | **number** | Number of currently running executions | [default to undefined]
**success_rate** | **number** | Success rate percentage (0-100) | [default to undefined]
**recent_success_rate** | **number** | Recent success rate (last 24 hours) percentage (0-100) | [default to undefined]
**recent_failed_count** | **number** | Number of failed executions in last 24 hours | [default to undefined]
**average_duration_ms** | **number** | Average execution duration in milliseconds | [default to undefined]
**is_active** | **boolean** | Whether dataset is active | [default to undefined]

## Example

```typescript
import { VirtualizationHealthMetrics } from './api';

const instance: VirtualizationHealthMetrics = {
    health_score,
    total_executions,
    completed_executions,
    failed_executions,
    running_executions,
    success_rate,
    recent_success_rate,
    recent_failed_count,
    average_duration_ms,
    is_active,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
