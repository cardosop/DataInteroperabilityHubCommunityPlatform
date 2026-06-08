# TrustSignalConfig

Serializer for TrustSignalConfig (tenant-scoped trust signal definitions).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Unique name within tenant (e.g. quality_verified, sla_99) | [default to undefined]
**kind** | **string** | Type: badge or quality_sla  * &#x60;badge&#x60; - Badge * &#x60;quality_sla&#x60; - Quality SLA | [default to undefined]
**config** | **any** | Definition payload (e.g. description for badge; availability, freshness_hours for SLA) | [optional] [default to undefined]
**is_active** | **boolean** |  | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { TrustSignalConfig } from './api';

const instance: TrustSignalConfig = {
    id,
    tenant_id,
    name,
    kind,
    config,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
