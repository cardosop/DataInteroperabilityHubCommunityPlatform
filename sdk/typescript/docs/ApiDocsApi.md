# ApiDocsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**apiDocsOpenapiJsonRetrieve**](#apidocsopenapijsonretrieve) | **GET** /api-docs/openapi.json | |
|[**apiDocsRedocRetrieve**](#apidocsredocretrieve) | **GET** /api-docs/redoc/ | |
|[**apiDocsRetrieve**](#apidocsretrieve) | **GET** /api-docs/ | |

# **apiDocsOpenapiJsonRetrieve**
> apiDocsOpenapiJsonRetrieve()

Return JSON format schema with validation and enhancement

### Example

```typescript
import {
    ApiDocsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ApiDocsApi(configuration);

const { status, data } = await apiInstance.apiDocsOpenapiJsonRetrieve();
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

# **apiDocsRedocRetrieve**
> apiDocsRedocRetrieve()

Return ReDoc documentation.  ReDoc automatically loads the OpenAPI schema and provides a clean, readable documentation interface.

### Example

```typescript
import {
    ApiDocsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ApiDocsApi(configuration);

const { status, data } = await apiInstance.apiDocsRedocRetrieve();
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

# **apiDocsRetrieve**
> apiDocsRetrieve()

Return Swagger UI with enhanced configuration.  The Swagger UI automatically loads the OpenAPI schema from the openapi-schema endpoint and provides interactive API exploration.

### Example

```typescript
import {
    ApiDocsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ApiDocsApi(configuration);

const { status, data } = await apiInstance.apiDocsRetrieve();
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

