# TenantUsage

Serializer for tenant usage summary

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**period_start** | **string** |  | [optional] [readonly] [default to undefined]
**period_end** | **string** |  | [optional] [readonly] [default to undefined]
**asset_count** | **number** |  | [optional] [readonly] [default to undefined]
**dataset_count** | **number** |  | [optional] [readonly] [default to undefined]
**scheduled_ingestion_count** | **number** |  | [optional] [readonly] [default to undefined]
**scheduled_export_count** | **number** |  | [optional] [readonly] [default to undefined]
**storage_bytes** | **number** |  | [optional] [readonly] [default to undefined]
**storage_gb** | **number** |  | [optional] [readonly] [default to undefined]
**api_calls_this_month** | **number** |  | [optional] [readonly] [default to undefined]
**plan_limits** | **{ [key: string]: any; }** |  | [optional] [readonly] [default to undefined]
**usage_percentages** | **{ [key: string]: any; }** |  | [optional] [readonly] [default to undefined]
**plan_slug** | **string** |  | [optional] [readonly] [default to undefined]
**plan_tier** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { TenantUsage } from './api';

const instance: TenantUsage = {
    tenant_id,
    period_start,
    period_end,
    asset_count,
    dataset_count,
    scheduled_ingestion_count,
    scheduled_export_count,
    storage_bytes,
    storage_gb,
    api_calls_this_month,
    plan_limits,
    usage_percentages,
    plan_slug,
    plan_tier,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
