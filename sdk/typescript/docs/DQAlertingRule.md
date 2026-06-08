# DQAlertingRule

Serializer for DQAlertingRule model (read)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this rule belongs to | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Rule name | [default to undefined]
**description** | **string** | Rule description | [optional] [default to undefined]
**metric_type** | **string** | Type of metric (e.g., quality_score, completeness, accuracy) | [default to undefined]
**threshold** | **number** | Threshold value (e.g., quality_score &lt; 0.9) | [default to undefined]
**comparison_operator** | **string** | Comparison operator  * &#x60;&lt;&#x60; - Less than * &#x60;&lt;&#x3D;&#x60; - Less than or equal * &#x60;&gt;&#x60; - Greater than * &#x60;&gt;&#x3D;&#x60; - Greater than or equal * &#x60;&#x3D;&#x3D;&#x60; - Equal to * &#x60;!&#x3D;&#x60; - Not equal to | [optional] [default to undefined]
**severity** | **string** | Alert severity: CRITICAL, HIGH, MEDIUM, LOW  * &#x60;CRITICAL&#x60; - Critical * &#x60;HIGH&#x60; - High * &#x60;MEDIUM&#x60; - Medium * &#x60;LOW&#x60; - Low | [optional] [default to undefined]
**alert_channels** | **any** | List of alert channels (EMAIL, SLACK, WEBHOOK, PAGERDUTY) | [optional] [default to undefined]
**enabled** | **boolean** | Whether the rule is enabled | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { DQAlertingRule } from './api';

const instance: DQAlertingRule = {
    id,
    tenant,
    asset_id,
    name,
    description,
    metric_type,
    threshold,
    comparison_operator,
    severity,
    alert_channels,
    enabled,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
