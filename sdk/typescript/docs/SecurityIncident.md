# SecurityIncident

Serializer for SecurityIncident model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**title** | **string** | Incident title | [default to undefined]
**description** | **string** | Incident description | [default to undefined]
**severity** | **string** | Incident severity level  * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical | [default to undefined]
**status** | **string** | Incident status  * &#x60;OPEN&#x60; - Open * &#x60;INVESTIGATING&#x60; - Investigating * &#x60;RESOLVED&#x60; - Resolved | [optional] [default to undefined]
**event_type** | **string** | Type of security event that triggered the incident | [default to undefined]
**violation_count** | **number** | Number of violations that contributed to this incident | [optional] [default to undefined]
**first_detected_at** | **string** | When the incident was first detected | [optional] [readonly] [default to undefined]
**last_updated_at** | **string** | When the incident was last updated | [optional] [readonly] [default to undefined]
**resolved_at** | **string** | When the incident was resolved | [optional] [default to undefined]
**resolution_notes** | **string** | Notes about how the incident was resolved | [optional] [default to undefined]
**tenant** | **string** | Tenant this incident belongs to (null for platform-level incidents) | [optional] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**user** | **string** | User associated with the incident (if applicable) | [optional] [default to undefined]
**user_email** | **string** |  | [optional] [readonly] [default to undefined]
**contract** | **string** | Contract associated with the incident (if applicable) | [optional] [default to undefined]
**resolved_by** | **string** | User who resolved the incident | [optional] [default to undefined]
**resolved_by_email** | **string** |  | [optional] [readonly] [default to undefined]
**metadata_json** | **any** | Additional metadata as JSON | [optional] [default to undefined]

## Example

```typescript
import { SecurityIncident } from './api';

const instance: SecurityIncident = {
    id,
    title,
    description,
    severity,
    status,
    event_type,
    violation_count,
    first_detected_at,
    last_updated_at,
    resolved_at,
    resolution_notes,
    tenant,
    tenant_name,
    user,
    user_email,
    contract,
    resolved_by,
    resolved_by_email,
    metadata_json,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
