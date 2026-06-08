# BaasApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**baasBillingReportsList**](#baasbillingreportslist) | **GET** /api/v1/baas/billing-reports/ | |
|[**baasBillingReportsRetrieve**](#baasbillingreportsretrieve) | **GET** /api/v1/baas/billing-reports/{id}/ | |
|[**baasUsageList**](#baasusagelist) | **GET** /api/v1/baas/usage/ | |
|[**baasUsageRetrieve**](#baasusageretrieve) | **GET** /api/v1/baas/usage/{id}/ | |

# **baasBillingReportsList**
> PaginatedCustomerBillingReportList baasBillingReportsList()

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    BaasApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BaasApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.baasBillingReportsList(
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedCustomerBillingReportList**

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

# **baasBillingReportsRetrieve**
> CustomerBillingReport baasBillingReportsRetrieve()

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    BaasApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BaasApi(configuration);

let id: string; //A UUID string identifying this customer billing report. (default to undefined)

const { status, data } = await apiInstance.baasBillingReportsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this customer billing report. | defaults to undefined|


### Return type

**CustomerBillingReport**

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

# **baasUsageList**
> PaginatedAPIUsageList baasUsageList()

API endpoints for viewing API usage records.  Provides: - List usage records with filtering - Get usage statistics - Get usage breakdown by endpoint

### Example

```typescript
import {
    BaasApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BaasApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.baasUsageList(
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedAPIUsageList**

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

# **baasUsageRetrieve**
> APIUsage baasUsageRetrieve()

API endpoints for viewing API usage records.  Provides: - List usage records with filtering - Get usage statistics - Get usage breakdown by endpoint

### Example

```typescript
import {
    BaasApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BaasApi(configuration);

let id: string; //A UUID string identifying this API Usage. (default to undefined)

const { status, data } = await apiInstance.baasUsageRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this API Usage. | defaults to undefined|


### Return type

**APIUsage**

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

