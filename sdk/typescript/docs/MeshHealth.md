# MeshHealth

Serializer for mesh health response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**overall_health_score** | **number** | Overall mesh health score (0-100) | [default to undefined]
**total_domains** | **number** | Total number of domains | [default to undefined]
**active_domains** | **number** | Number of active domains | [default to undefined]
**compliant_domains** | **number** | Number of compliant domains | [default to undefined]
**non_compliant_domains** | **number** | Number of non-compliant domains | [default to undefined]
**domains_with_violations** | **number** | Number of domains with violations | [default to undefined]
**domain_health** | **Array&lt;{ [key: string]: any; }&gt;** | Health metrics per domain | [default to undefined]

## Example

```typescript
import { MeshHealth } from './api';

const instance: MeshHealth = {
    overall_health_score,
    total_domains,
    active_domains,
    compliant_domains,
    non_compliant_domains,
    domains_with_violations,
    domain_health,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
