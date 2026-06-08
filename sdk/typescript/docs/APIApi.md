# APIApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**capabilitiesRetrieve**](#capabilitiesretrieve) | **GET** /api/v1/capabilities/ | |
|[**rootRetrieve**](#rootretrieve) | **GET** /api/v1/ | |

# **capabilitiesRetrieve**
> CapabilitiesResponse capabilitiesRetrieve()

Backend-driven feature-discovery surface. Frontends call this to branch UI on what the deployed backend supports. The flat shape lets the frontend\'s ``useCapability(\'lineage.<flag>\')`` hook read by name without traversing nested objects.

### Example

```typescript
import {
    APIApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIApi(configuration);

const { status, data } = await apiInstance.capabilitiesRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**CapabilitiesResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rootRetrieve**
> APIInfo rootRetrieve()

API information endpoint.  GET /api/v1/ Returns basic API information and available endpoints.

### Example

```typescript
import {
    APIApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIApi(configuration);

const { status, data } = await apiInstance.rootRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**APIInfo**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

