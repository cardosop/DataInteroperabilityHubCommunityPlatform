# ImpactAnalysisApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**contractsImpactAnalysisRetrieve**](#contractsimpactanalysisretrieve) | **GET** /api/v1/contracts/{id}/impact-analysis/ | Get impact analysis|

# **contractsImpactAnalysisRetrieve**
> contractsImpactAnalysisRetrieve()

         Analyze impact of changes to a contract, model, or field.          Performs reverse lineage traversal to find all resources that depend on         the specified contract/model/field.          **Query Parameters:**         - `depth`: Maximum traversal depth (default: 10)         - `model_name`: Optional model name for model-level impact         - `field_name`: Optional field name for field-level impact         - `include_fields`: Include field-level dependencies (default: true)         - `format`: Response format (json, csv, dot, mermaid, paths) (default: json)         

### Example

```typescript
import {
    ImpactAnalysisApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ImpactAnalysisApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let depth: number; //Maximum traversal depth (default: 10) (optional) (default to undefined)
let fieldName: string; //Field name for field-level impact (optional) (default to undefined)
let format: string; //Response format: json, csv, dot, mermaid, paths (default: json) (optional) (default to undefined)
let includeFields: boolean; //Include field-level dependencies (default: true) (optional) (default to undefined)
let modelName: string; //Model name for model-level impact (optional) (default to undefined)

const { status, data } = await apiInstance.contractsImpactAnalysisRetrieve(
    id,
    depth,
    fieldName,
    format,
    includeFields,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **depth** | [**number**] | Maximum traversal depth (default: 10) | (optional) defaults to undefined|
| **fieldName** | [**string**] | Field name for field-level impact | (optional) defaults to undefined|
| **format** | [**string**] | Response format: json, csv, dot, mermaid, paths (default: json) | (optional) defaults to undefined|
| **includeFields** | [**boolean**] | Include field-level dependencies (default: true) | (optional) defaults to undefined|
| **modelName** | [**string**] | Model name for model-level impact | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Impact analysis result |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

