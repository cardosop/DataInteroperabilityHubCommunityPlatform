# DqApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**dqAlertingRulesCreate**](#dqalertingrulescreate) | **POST** /api/v1/dq/alerting-rules/ | |
|[**dqAlertingRulesDestroy**](#dqalertingrulesdestroy) | **DELETE** /api/v1/dq/alerting-rules/{id}/ | |
|[**dqAlertingRulesList**](#dqalertingruleslist) | **GET** /api/v1/dq/alerting-rules/ | |
|[**dqAlertingRulesPartialUpdate**](#dqalertingrulespartialupdate) | **PATCH** /api/v1/dq/alerting-rules/{id}/ | |
|[**dqAlertingRulesRetrieve**](#dqalertingrulesretrieve) | **GET** /api/v1/dq/alerting-rules/{id}/ | |
|[**dqAlertingRulesUpdate**](#dqalertingrulesupdate) | **PUT** /api/v1/dq/alerting-rules/{id}/ | |
|[**dqRunsCreate**](#dqrunscreate) | **POST** /api/v1/dq/runs/ | |
|[**dqRunsDestroy**](#dqrunsdestroy) | **DELETE** /api/v1/dq/runs/{id}/ | |
|[**dqRunsList**](#dqrunslist) | **GET** /api/v1/dq/runs/ | |
|[**dqRunsPartialUpdate**](#dqrunspartialupdate) | **PATCH** /api/v1/dq/runs/{id}/ | |
|[**dqRunsRetrieve**](#dqrunsretrieve) | **GET** /api/v1/dq/runs/{id}/ | |
|[**dqRunsUpdate**](#dqrunsupdate) | **PUT** /api/v1/dq/runs/{id}/ | |

# **dqAlertingRulesCreate**
> DQAlertingRule dqAlertingRulesCreate(dQAlertingRule)

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration,
    DQAlertingRule
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let dQAlertingRule: DQAlertingRule; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.dqAlertingRulesCreate(
    dQAlertingRule,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dQAlertingRule** | **DQAlertingRule**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQAlertingRule**

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

# **dqAlertingRulesDestroy**
> dqAlertingRulesDestroy()

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq alerting rule. (default to undefined)

const { status, data } = await apiInstance.dqAlertingRulesDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq alerting rule. | defaults to undefined|


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

# **dqAlertingRulesList**
> PaginatedDQAlertingRuleList dqAlertingRulesList()

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.dqAlertingRulesList(
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

**PaginatedDQAlertingRuleList**

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

# **dqAlertingRulesPartialUpdate**
> DQAlertingRule dqAlertingRulesPartialUpdate()

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration,
    PatchedDQAlertingRule
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq alerting rule. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedDQAlertingRule: PatchedDQAlertingRule; // (optional)

const { status, data } = await apiInstance.dqAlertingRulesPartialUpdate(
    id,
    idempotencyKey,
    patchedDQAlertingRule
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedDQAlertingRule** | **PatchedDQAlertingRule**|  | |
| **id** | [**string**] | A UUID string identifying this dq alerting rule. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQAlertingRule**

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

# **dqAlertingRulesRetrieve**
> DQAlertingRule dqAlertingRulesRetrieve()

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq alerting rule. (default to undefined)

const { status, data } = await apiInstance.dqAlertingRulesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq alerting rule. | defaults to undefined|


### Return type

**DQAlertingRule**

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

# **dqAlertingRulesUpdate**
> DQAlertingRule dqAlertingRulesUpdate(dQAlertingRule)

ViewSet for DQ alerting rule management.  Tenant-scoped: users can only see/manage alerting rules in their tenant.  Phase 240.4.B.2 — gated on ``Tenant.data_quality_enabled`` via ``DQFeatureFlagMixin`` (scope=basic).

### Example

```typescript
import {
    DqApi,
    Configuration,
    DQAlertingRule
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq alerting rule. (default to undefined)
let dQAlertingRule: DQAlertingRule; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.dqAlertingRulesUpdate(
    id,
    dQAlertingRule,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dQAlertingRule** | **DQAlertingRule**|  | |
| **id** | [**string**] | A UUID string identifying this dq alerting rule. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQAlertingRule**

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

# **dqRunsCreate**
> DQRun dqRunsCreate(dQRun)

Create a new DQ run.  POST /api/v1/dq/runs/ Body: {     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional, scan-only),     \"profile_key\": \"intake_basic_gx\" (optional) }

### Example

```typescript
import {
    DqApi,
    Configuration,
    DQRun
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let dQRun: DQRun; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.dqRunsCreate(
    dQRun,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dQRun** | **DQRun**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQRun**

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

# **dqRunsDestroy**
> dqRunsDestroy()

Delete DQ run

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)

const { status, data } = await apiInstance.dqRunsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|


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

# **dqRunsList**
> PaginatedDQRunList dqRunsList()

List DQ runs (tenant-scoped)

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.dqRunsList(
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

**PaginatedDQRunList**

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

# **dqRunsPartialUpdate**
> DQRun dqRunsPartialUpdate()

Update DQ run (partial update)

### Example

```typescript
import {
    DqApi,
    Configuration,
    PatchedDQRun
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedDQRun: PatchedDQRun; // (optional)

const { status, data } = await apiInstance.dqRunsPartialUpdate(
    id,
    idempotencyKey,
    patchedDQRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedDQRun** | **PatchedDQRun**|  | |
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQRun**

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

# **dqRunsRetrieve**
> DQRun dqRunsRetrieve()

Retrieve DQ run by ID

### Example

```typescript
import {
    DqApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)

const { status, data } = await apiInstance.dqRunsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|


### Return type

**DQRun**

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

# **dqRunsUpdate**
> DQRun dqRunsUpdate(dQRun)

Update DQ run (full update)

### Example

```typescript
import {
    DqApi,
    Configuration,
    DQRun
} from './api';

const configuration = new Configuration();
const apiInstance = new DqApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)
let dQRun: DQRun; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.dqRunsUpdate(
    id,
    dQRun,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dQRun** | **DQRun**|  | |
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DQRun**

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

