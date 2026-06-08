# SDKDocumentation

Serializer for SDK Documentation model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**language** | **string** | SDK language  * &#x60;python&#x60; - Python * &#x60;javascript&#x60; - JavaScript * &#x60;typescript&#x60; - TypeScript * &#x60;r&#x60; - R * &#x60;go&#x60; - Go | [default to undefined]
**version** | **string** | SDK version (semantic versioning) | [default to undefined]
**documentation** | **string** | SDK documentation (markdown format) | [default to undefined]
**installation** | **string** | Installation instructions (e.g., \&#39;pip install datahub-sdk\&#39;) | [default to undefined]
**quick_start** | **string** | Quick start code snippet | [default to undefined]
**examples_json** | **any** | Code examples as JSON array | [optional] [default to undefined]
**api_reference_json** | **any** | API reference documentation | [optional] [default to undefined]
**documentation_url** | **string** | External documentation URL | [optional] [default to undefined]
**is_active** | **boolean** | Whether this SDK version is active | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { SDKDocumentation } from './api';

const instance: SDKDocumentation = {
    id,
    language,
    version,
    documentation,
    installation,
    quick_start,
    examples_json,
    api_reference_json,
    documentation_url,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
