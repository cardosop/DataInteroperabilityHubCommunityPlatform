# OpenapiJsonApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**openapiJsonRetrieve**](#openapijsonretrieve) | **GET** /api/v1/openapi.json | |

# **openapiJsonRetrieve**
> openapiJsonRetrieve()

Return JSON format schema with validation and enhancement

### Example

```typescript
import {
    OpenapiJsonApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new OpenapiJsonApi(configuration);

const { status, data } = await apiInstance.openapiJsonRetrieve();
```

### Parameters
This endpoint does not have any parameters.


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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

