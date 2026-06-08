# ComplianceApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**complianceRunsCancelCreate**](#compliancerunscancelcreate) | **POST** /api/v1/compliance/runs/{id}/cancel/ | |
|[**complianceRunsCreate**](#compliancerunscreate) | **POST** /api/v1/compliance/runs/ | |
|[**complianceRunsDestroy**](#compliancerunsdestroy) | **DELETE** /api/v1/compliance/runs/{id}/ | |
|[**complianceRunsList**](#compliancerunslist) | **GET** /api/v1/compliance/runs/ | |
|[**complianceRunsPartialUpdate**](#compliancerunspartialupdate) | **PATCH** /api/v1/compliance/runs/{id}/ | |
|[**complianceRunsRetrieve**](#compliancerunsretrieve) | **GET** /api/v1/compliance/runs/{id}/ | |
|[**complianceRunsUpdate**](#compliancerunsupdate) | **PUT** /api/v1/compliance/runs/{id}/ | |
|[**complianceWebhooksCompletedReportRetrieve**](#compliancewebhookscompletedreportretrieve) | **GET** /api/v1/compliance/webhooks/completed/report/ | |
|[**exportComplianceRunCsv**](#exportcomplianceruncsv) | **GET** /api/v1/compliance/runs/{id}/export.csv/ | |
|[**exportComplianceRunJson**](#exportcompliancerunjson) | **GET** /api/v1/compliance/runs/{id}/export.json/ | |
|[**getComplianceRunResults**](#getcompliancerunresults) | **GET** /api/v1/compliance/runs/{id}/results/ | |

# **complianceRunsCancelCreate**
> ComplianceRun complianceRunsCancelCreate()

Cancel a compliance run by cancelling its underlying job.  POST /compliance/runs/{id}/cancel/  Only PENDING or RUNNING runs can be cancelled.

### Example

```typescript
import {
    ComplianceApi,
    Configuration,
    ComplianceRun
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let complianceRun: ComplianceRun; // (optional)

const { status, data } = await apiInstance.complianceRunsCancelCreate(
    id,
    idempotencyKey,
    complianceRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **complianceRun** | **ComplianceRun**|  | |
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ComplianceRun**

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

# **complianceRunsCreate**
> ComplianceRun complianceRunsCreate()

Create a new compliance run.  POST /runs Body: {     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional, scan-only),     \"scan_mode\": \"internal\" | \"external\",     \"applicable_regulations\": [\"GDPR\", \"HIPAA\"] (optional) }

### Example

```typescript
import {
    ComplianceApi,
    Configuration,
    ComplianceRun
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let complianceRun: ComplianceRun; // (optional)

const { status, data } = await apiInstance.complianceRunsCreate(
    idempotencyKey,
    complianceRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **complianceRun** | **ComplianceRun**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ComplianceRun**

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

# **complianceRunsDestroy**
> complianceRunsDestroy()

Delete compliance run

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)

const { status, data } = await apiInstance.complianceRunsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|


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

# **complianceRunsList**
> PaginatedComplianceRunList complianceRunsList()

List compliance runs (tenant-scoped)

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.complianceRunsList(
    ordering,
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **ordering** | [**string**] | Which field to use when ordering the results. | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedComplianceRunList**

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

# **complianceRunsPartialUpdate**
> ComplianceRun complianceRunsPartialUpdate()

Update compliance run (partial update)

### Example

```typescript
import {
    ComplianceApi,
    Configuration,
    PatchedComplianceRun
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedComplianceRun: PatchedComplianceRun; // (optional)

const { status, data } = await apiInstance.complianceRunsPartialUpdate(
    id,
    idempotencyKey,
    patchedComplianceRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedComplianceRun** | **PatchedComplianceRun**|  | |
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ComplianceRun**

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

# **complianceRunsRetrieve**
> ComplianceRun complianceRunsRetrieve()

Retrieve compliance run by ID

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)

const { status, data } = await apiInstance.complianceRunsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|


### Return type

**ComplianceRun**

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

# **complianceRunsUpdate**
> ComplianceRun complianceRunsUpdate()

Update compliance run (full update)

### Example

```typescript
import {
    ComplianceApi,
    Configuration,
    ComplianceRun
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let complianceRun: ComplianceRun; // (optional)

const { status, data } = await apiInstance.complianceRunsUpdate(
    id,
    idempotencyKey,
    complianceRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **complianceRun** | **ComplianceRun**|  | |
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ComplianceRun**

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

# **complianceWebhooksCompletedReportRetrieve**
> complianceWebhooksCompletedReportRetrieve()

Redeem ``?token=`` from ``report_presigned_url`` (TTL 7 days).  Response mirrors the webhook ``data`` envelope (whitelist fields only).

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

const { status, data } = await apiInstance.complianceWebhooksCompletedReportRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

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

# **exportComplianceRunCsv**
> exportComplianceRunCsv()

GET /api/v1/compliance/runs/{id}/export.csv/ — stream violations as CSV.

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)

const { status, data } = await apiInstance.exportComplianceRunCsv(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|


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
|**200** | Violation table as UTF-8 text/csv. |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **exportComplianceRunJson**
> exportComplianceRunJson()

GET /api/v1/compliance/runs/{id}/export.json/ — full run + results JSON.

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)

const { status, data } = await apiInstance.exportComplianceRunJson(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|


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
|**200** | Run + results JSON export. |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **getComplianceRunResults**
> ComplianceRunResultsResponse getComplianceRunResults()

Get enhanced compliance run results with detailed violation information.  GET /api/v1/compliance/runs/{id}/results/  Returns detailed compliance results including: - Violation details with remediation suggestions - Compliance score breakdown - Risk assessment - Timeline of violations

### Example

```typescript
import {
    ComplianceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ComplianceApi(configuration);

let id: string; //A UUID string identifying this compliance run. (default to undefined)

const { status, data } = await apiInstance.getComplianceRunResults(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this compliance run. | defaults to undefined|


### Return type

**ComplianceRunResultsResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

