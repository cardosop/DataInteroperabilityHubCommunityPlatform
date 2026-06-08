# SecurityAuditLog

Serializer for SecurityAuditLog model.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**event_type** | **string** | Type of security event (e.g., EXTERNAL_REF_FETCH, RATE_LIMIT_EXCEEDED, CACHE_HIT, CACHE_MISS, CACHE_EVICTION, SECURITY_VIOLATION) | [optional] [readonly] [default to undefined]
**timestamp** | **string** | When the event occurred (UTC) | [optional] [readonly] [default to undefined]
**severity** | **string** | Severity level (for security violations)  * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical | [optional] [readonly] [default to undefined]
**ref_type** | **string** | Reference type (internal, local, external) | [optional] [readonly] [default to undefined]
**ref_path** | **string** | The $ref path/URL | [optional] [readonly] [default to undefined]
**resolved_path** | **string** | Resolved path/URL | [optional] [readonly] [default to undefined]
**rate_limit_level** | **string** | Rate limit level (global, tenant, user) | [optional] [readonly] [default to undefined]
**cache_operation** | **string** | Cache operation type (hit, miss, eviction) | [optional] [readonly] [default to undefined]
**cache_key** | **string** | Cache key (for cache operations) | [optional] [readonly] [default to undefined]
**eviction_reason** | **string** | Eviction reason (for cache evictions) | [optional] [readonly] [default to undefined]
**violation_type** | **string** | Human-readable violation type | [optional] [readonly] [default to undefined]
**attempted_path** | **string** | Attempted path (for path traversal) | [optional] [readonly] [default to undefined]
**attempted_url** | **string** | Attempted URL (for URL violations) | [optional] [readonly] [default to undefined]
**description** | **string** | Detailed description of the event | [optional] [readonly] [default to undefined]
**metadata_json** | **any** | Additional metadata as JSON | [optional] [readonly] [default to undefined]
**request_id** | **string** | Request ID for tracing | [optional] [readonly] [default to undefined]
**ip_address** | **string** | IP address of the request | [optional] [readonly] [default to undefined]
**user_agent** | **string** | User agent string | [optional] [readonly] [default to undefined]
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**user_id** | **string** |  | [optional] [readonly] [default to undefined]
**user_email** | **string** |  | [optional] [readonly] [default to undefined]
**contract_id** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { SecurityAuditLog } from './api';

const instance: SecurityAuditLog = {
    id,
    event_type,
    timestamp,
    severity,
    ref_type,
    ref_path,
    resolved_path,
    rate_limit_level,
    cache_operation,
    cache_key,
    eviction_reason,
    violation_type,
    attempted_path,
    attempted_url,
    description,
    metadata_json,
    request_id,
    ip_address,
    user_agent,
    tenant_id,
    tenant_name,
    user_id,
    user_email,
    contract_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
