# BillingApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**billingAdminPlansCreate**](#billingadminplanscreate) | **POST** /api/v1/billing/admin/plans/ | |
|[**billingAdminPlansDestroy**](#billingadminplansdestroy) | **DELETE** /api/v1/billing/admin/plans/{id}/ | |
|[**billingAdminPlansList**](#billingadminplanslist) | **GET** /api/v1/billing/admin/plans/ | |
|[**billingAdminPlansPartialUpdate**](#billingadminplanspartialupdate) | **PATCH** /api/v1/billing/admin/plans/{id}/ | |
|[**billingAdminPlansRetrieve**](#billingadminplansretrieve) | **GET** /api/v1/billing/admin/plans/{id}/ | |
|[**billingAdminPlansUpdate**](#billingadminplansupdate) | **PUT** /api/v1/billing/admin/plans/{id}/ | |
|[**billingInvoicesList**](#billinginvoiceslist) | **GET** /api/v1/billing/invoices/ | |
|[**billingInvoicesRetrieve**](#billinginvoicesretrieve) | **GET** /api/v1/billing/invoices/{id}/ | |
|[**billingPlansList**](#billingplanslist) | **GET** /api/v1/billing/plans/ | |
|[**billingPlansRetrieve**](#billingplansretrieve) | **GET** /api/v1/billing/plans/{id}/ | |
|[**billingSubscriptionCurrentRetrieve**](#billingsubscriptioncurrentretrieve) | **GET** /api/v1/billing/subscription/current/ | |
|[**billingSubscriptionList**](#billingsubscriptionlist) | **GET** /api/v1/billing/subscription/ | |
|[**billingSubscriptionMlCurrentRetrieve**](#billingsubscriptionmlcurrentretrieve) | **GET** /api/v1/billing/subscription/ml/current/ | |
|[**billingSubscriptionRetrieve**](#billingsubscriptionretrieve) | **GET** /api/v1/billing/subscription/{id}/ | |
|[**changeMlSubscriptionPlan**](#changemlsubscriptionplan) | **POST** /api/v1/billing/subscription/ml/current/change-plan/ | Change ML subscription plan|
|[**changeSubscriptionPlan**](#changesubscriptionplan) | **POST** /api/v1/billing/subscription/current/change-plan/ | Change subscription plan|
|[**createRefund**](#createrefund) | **POST** /api/v1/billing/refunds/ | Issue a Stripe refund (admin only)|
|[**downloadInvoice**](#downloadinvoice) | **GET** /api/v1/billing/invoices/{id}/download/ | Download invoice|

# **billingAdminPlansCreate**
> TenantPlanAdmin billingAdminPlansCreate(tenantPlanAdmin)

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration,
    TenantPlanAdmin
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let tenantPlanAdmin: TenantPlanAdmin; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.billingAdminPlansCreate(
    tenantPlanAdmin,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantPlanAdmin** | **TenantPlanAdmin**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantPlanAdmin**

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
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **billingAdminPlansDestroy**
> billingAdminPlansDestroy()

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this tenant plan. (default to undefined)

const { status, data } = await apiInstance.billingAdminPlansDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this tenant plan. | defaults to undefined|


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
|**204** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **billingAdminPlansList**
> PaginatedTenantPlanAdminList billingAdminPlansList()

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.billingAdminPlansList(
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

**PaginatedTenantPlanAdminList**

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

# **billingAdminPlansPartialUpdate**
> TenantPlanAdmin billingAdminPlansPartialUpdate()

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration,
    PatchedTenantPlanAdmin
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this tenant plan. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantPlanAdmin: PatchedTenantPlanAdmin; // (optional)

const { status, data } = await apiInstance.billingAdminPlansPartialUpdate(
    id,
    idempotencyKey,
    patchedTenantPlanAdmin
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantPlanAdmin** | **PatchedTenantPlanAdmin**|  | |
| **id** | [**string**] | A UUID string identifying this tenant plan. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantPlanAdmin**

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
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **billingAdminPlansRetrieve**
> TenantPlanAdmin billingAdminPlansRetrieve()

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this tenant plan. (default to undefined)

const { status, data } = await apiInstance.billingAdminPlansRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this tenant plan. | defaults to undefined|


### Return type

**TenantPlanAdmin**

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

# **billingAdminPlansUpdate**
> TenantPlanAdmin billingAdminPlansUpdate(tenantPlanAdmin)

Admin ViewSet for full CRUD on TenantPlan.  Restricted to platform admins. Validates limits_json against KNOWN_LIMIT_KEYS.  Endpoints: - GET    /api/v1/billing/admin/plans/         — list all plans - POST   /api/v1/billing/admin/plans/         — create plan - GET    /api/v1/billing/admin/plans/{id}/     — retrieve plan - PUT    /api/v1/billing/admin/plans/{id}/     — full update - PATCH  /api/v1/billing/admin/plans/{id}/     — partial update - DELETE /api/v1/billing/admin/plans/{id}/     — delete plan

### Example

```typescript
import {
    BillingApi,
    Configuration,
    TenantPlanAdmin
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this tenant plan. (default to undefined)
let tenantPlanAdmin: TenantPlanAdmin; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.billingAdminPlansUpdate(
    id,
    tenantPlanAdmin,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantPlanAdmin** | **TenantPlanAdmin**|  | |
| **id** | [**string**] | A UUID string identifying this tenant plan. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantPlanAdmin**

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
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **billingInvoicesList**
> PaginatedInvoiceList billingInvoicesList()

ViewSet for invoice management.  Tenant-scoped: users can only see invoices for their tenant.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.billingInvoicesList(
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

**PaginatedInvoiceList**

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

# **billingInvoicesRetrieve**
> Invoice billingInvoicesRetrieve()

Get invoice detail

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this invoice. (default to undefined)

const { status, data } = await apiInstance.billingInvoicesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this invoice. | defaults to undefined|


### Return type

**Invoice**

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

# **billingPlansList**
> PaginatedTenantPlanList billingPlansList()

ViewSet for listing available tenant plans.  Used by tenant admins to see plans when changing subscription.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.billingPlansList(
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

**PaginatedTenantPlanList**

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

# **billingPlansRetrieve**
> TenantPlan billingPlansRetrieve()

ViewSet for listing available tenant plans.  Used by tenant admins to see plans when changing subscription.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this tenant plan. (default to undefined)

const { status, data } = await apiInstance.billingPlansRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this tenant plan. | defaults to undefined|


### Return type

**TenantPlan**

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

# **billingSubscriptionCurrentRetrieve**
> Subscription billingSubscriptionCurrentRetrieve()

Get current subscription for tenant

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

const { status, data } = await apiInstance.billingSubscriptionCurrentRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Subscription**

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

# **billingSubscriptionList**
> PaginatedSubscriptionList billingSubscriptionList()

ViewSet for subscription management.  Tenant-scoped: users can only see subscriptions for their tenant.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.billingSubscriptionList(
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

**PaginatedSubscriptionList**

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

# **billingSubscriptionMlCurrentRetrieve**
> Subscription billingSubscriptionMlCurrentRetrieve()

Get current ML subscription for tenant.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

const { status, data } = await apiInstance.billingSubscriptionMlCurrentRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Subscription**

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

# **billingSubscriptionRetrieve**
> Subscription billingSubscriptionRetrieve()

Retrieve subscription by id; uses get_queryset (platform admin can access any).

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this subscription. (default to undefined)

const { status, data } = await apiInstance.billingSubscriptionRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this subscription. | defaults to undefined|


### Return type

**Subscription**

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

# **changeMlSubscriptionPlan**
> Subscription changeMlSubscriptionPlan(changePlan)

Change ML subscription plan.

### Example

```typescript
import {
    BillingApi,
    Configuration,
    ChangePlan
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let changePlan: ChangePlan; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.changeMlSubscriptionPlan(
    changePlan,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **changePlan** | **ChangePlan**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Subscription**

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
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **changeSubscriptionPlan**
> Subscription changeSubscriptionPlan(changePlan)

Change the current tenant\'s subscription plan. Requires TENANT_ADMIN or PLATFORM_ADMIN.

### Example

```typescript
import {
    BillingApi,
    Configuration,
    ChangePlan
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let changePlan: ChangePlan; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.changeSubscriptionPlan(
    changePlan,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **changePlan** | **ChangePlan**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Subscription**

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
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **createRefund**
> createRefund()

POST /api/v1/billing/refunds/  Body: {   \"payment_intent_id\": \"pi_...\",   \"amount_cents\": 1000,   \"reason\": \"requested_by_customer\" }

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.createRefund(
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


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
|**201** | Refund created |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **downloadInvoice**
> downloadInvoice()

Redirect to invoice PDF or hosted invoice URL. Returns 302 redirect when URL available, 404 when not.

### Example

```typescript
import {
    BillingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new BillingApi(configuration);

let id: string; //A UUID string identifying this invoice. (default to undefined)

const { status, data } = await apiInstance.downloadInvoice(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this invoice. | defaults to undefined|


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
|**302** | Redirect to invoice PDF or hosted page |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

