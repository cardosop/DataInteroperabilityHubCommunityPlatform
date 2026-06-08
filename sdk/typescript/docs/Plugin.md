# Plugin

Serializer for Plugin model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Plugin name (unique) | [default to undefined]
**description** | **string** | Plugin description | [default to undefined]
**version** | **string** | Plugin version (semantic versioning) | [default to undefined]
**author** | **string** | Plugin author/organization | [default to undefined]
**category** | **string** | Plugin category  * &#x60;CONNECTOR&#x60; - Connector * &#x60;TRANSFORMER&#x60; - Transformer * &#x60;VALIDATOR&#x60; - Validator * &#x60;ANALYZER&#x60; - Analyzer * &#x60;INTEGRATION&#x60; - Integration * &#x60;OTHER&#x60; - Other | [optional] [default to undefined]
**status** | **string** | Plugin status: AVAILABLE, DEPRECATED, BETA, ALPHA  * &#x60;AVAILABLE&#x60; - Available * &#x60;DEPRECATED&#x60; - Deprecated * &#x60;BETA&#x60; - Beta * &#x60;ALPHA&#x60; - Alpha | [optional] [default to undefined]
**download_count** | **number** | Number of times plugin has been downloaded | [optional] [readonly] [default to undefined]
**rating** | **number** | Average rating (0-5) | [optional] [default to undefined]
**metadata_json** | **any** | Additional plugin metadata (tags, dependencies, etc.) | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Plugin } from './api';

const instance: Plugin = {
    id,
    name,
    description,
    version,
    author,
    category,
    status,
    download_count,
    rating,
    metadata_json,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
