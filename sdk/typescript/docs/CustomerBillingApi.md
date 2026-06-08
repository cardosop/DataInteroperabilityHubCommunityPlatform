# CustomerBillingApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**baasBillingReportsFinalizeCreate**](#baasbillingreportsfinalizecreate) | **POST** /api/v1/baas/billing-reports/{id}/finalize/ | Finalize billing report|
|[**baasBillingReportsGenerateCreate**](#baasbillingreportsgeneratecreate) | **POST** /api/v1/baas/billing-reports/generate/ | Generate billing report|
|[**baasBillingReportsSendCreate**](#baasbillingreportssendcreate) | **POST** /api/v1/baas/billing-reports/{id}/send/ | Send billing report to customer|
|[**baasBillingReportsVoidCreate**](#baasbillingreportsvoidcreate) | **POST** /api/v1/baas/billing-reports/{id}/void/ | Void a billing report|

# **baasBillingReportsFinalizeCreate**
> CustomerBillingReport baasBillingReportsFinalizeCreate()

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    CustomerBillingApi,
    Configuration,
    CustomerBillingReport
} from './api';

const configuration = new Configuration();
const apiInstance = new CustomerBillingApi(configuration);

let id: string; //A UUID string identifying this customer billing report. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let customerBillingReport: CustomerBillingReport; // (optional)

const { status, data } = await apiInstance.baasBillingReportsFinalizeCreate(
    id,
    idempotencyKey,
    customerBillingReport
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **customerBillingReport** | **CustomerBillingReport**|  | |
| **id** | [**string**] | A UUID string identifying this customer billing report. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**CustomerBillingReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasBillingReportsGenerateCreate**
> CustomerBillingReport baasBillingReportsGenerateCreate(customerBillingReportCreate)

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    CustomerBillingApi,
    Configuration,
    CustomerBillingReportCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new CustomerBillingApi(configuration);

let customerBillingReportCreate: CustomerBillingReportCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.baasBillingReportsGenerateCreate(
    customerBillingReportCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **customerBillingReportCreate** | **CustomerBillingReportCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**CustomerBillingReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasBillingReportsSendCreate**
> CustomerBillingReport baasBillingReportsSendCreate()

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    CustomerBillingApi,
    Configuration,
    CustomerBillingReport
} from './api';

const configuration = new Configuration();
const apiInstance = new CustomerBillingApi(configuration);

let id: string; //A UUID string identifying this customer billing report. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let customerBillingReport: CustomerBillingReport; // (optional)

const { status, data } = await apiInstance.baasBillingReportsSendCreate(
    id,
    idempotencyKey,
    customerBillingReport
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **customerBillingReport** | **CustomerBillingReport**|  | |
| **id** | [**string**] | A UUID string identifying this customer billing report. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**CustomerBillingReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasBillingReportsVoidCreate**
> CustomerBillingReport baasBillingReportsVoidCreate()

ViewSet for customer billing reports.  Endpoints: - GET  /api/v1/baas/billing-reports/ - GET  /api/v1/baas/billing-reports/{id}/ - POST /api/v1/baas/billing-reports/generate/ - POST /api/v1/baas/billing-reports/{id}/finalize/ - POST /api/v1/baas/billing-reports/{id}/send/ - POST /api/v1/baas/billing-reports/{id}/void/

### Example

```typescript
import {
    CustomerBillingApi,
    Configuration,
    CustomerBillingReport
} from './api';

const configuration = new Configuration();
const apiInstance = new CustomerBillingApi(configuration);

let id: string; //A UUID string identifying this customer billing report. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let customerBillingReport: CustomerBillingReport; // (optional)

const { status, data } = await apiInstance.baasBillingReportsVoidCreate(
    id,
    idempotencyKey,
    customerBillingReport
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **customerBillingReport** | **CustomerBillingReport**|  | |
| **id** | [**string**] | A UUID string identifying this customer billing report. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**CustomerBillingReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

