# InternalWorkerApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**scheduledExportsInternalConfigRetrieve**](#scheduledexportsinternalconfigretrieve) | **GET** /api/v1/scheduled-exports/internal/config/{scheduled_export_id}/ | Get scheduled export configuration|
|[**scheduledExportsInternalProcessExportCreate**](#scheduledexportsinternalprocessexportcreate) | **POST** /api/v1/scheduled-exports/internal/process-export/ | Process export item for scheduled export run|
|[**scheduledExportsInternalRunsCreate**](#scheduledexportsinternalrunscreate) | **POST** /api/v1/scheduled-exports/internal/runs/ | Create scheduled export run|
|[**scheduledExportsInternalRunsPartialUpdate**](#scheduledexportsinternalrunspartialupdate) | **PATCH** /api/v1/scheduled-exports/internal/runs/{id}/ | Update scheduled export run|
|[**scheduledIngestionsInternalConfigRetrieve**](#scheduledingestionsinternalconfigretrieve) | **GET** /api/v1/scheduled-ingestions/internal/config/{scheduled_ingestion_id}/ | Get scheduled ingestion configuration|
|[**scheduledIngestionsInternalJobsCreate**](#scheduledingestionsinternaljobscreate) | **POST** /api/v1/scheduled-ingestions/internal/jobs/ | |
|[**scheduledIngestionsInternalProcessFileCreate**](#scheduledingestionsinternalprocessfilecreate) | **POST** /api/v1/scheduled-ingestions/internal/process-file/ | Process file for scheduled ingestion run|
|[**scheduledIngestionsInternalRunsCreate**](#scheduledingestionsinternalrunscreate) | **POST** /api/v1/scheduled-ingestions/internal/runs/ | Create scheduled ingestion run|
|[**scheduledIngestionsInternalRunsPartialUpdate**](#scheduledingestionsinternalrunspartialupdate) | **PATCH** /api/v1/scheduled-ingestions/internal/runs/{id}/ | Update scheduled ingestion run|

# **scheduledExportsInternalConfigRetrieve**
> scheduledExportsInternalConfigRetrieve()

Get configuration for a scheduled export (destination_type, destination_config with masked credentials, source_scope, schedule_config, etc.). Credentials in destination_config are masked for security. Requires worker authentication and X-Tenant-ID header. Rate limiting: No rate limit (internal worker endpoints).

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let scheduledExportId: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledExportsInternalConfigRetrieve(
    scheduledExportId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledExportId** | [**string**] |  | defaults to undefined|


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
|**200** | Configuration retrieved successfully (credentials masked) |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledExportsInternalProcessExportCreate**
> scheduledExportsInternalProcessExportCreate(internalProcessExport)

Process a single export item (dataset or file) for a scheduled export run. Validates run and tenant, applies business rules (scope, access), prepares payload or signed URL. Returns success with upload instructions or structured error. Requires worker authentication and X-Tenant-ID header. Rate limiting: No rate limit (internal worker endpoints).

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    InternalProcessExport
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let internalProcessExport: InternalProcessExport; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledExportsInternalProcessExportCreate(
    internalProcessExport,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **internalProcessExport** | **InternalProcessExport**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Export item processed successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledExportsInternalRunsCreate**
> scheduledExportsInternalRunsCreate(internalCreateRun)

Create a new scheduled export run with status RUNNING. Idempotent by idempotency_key or prefect_flow_run_id. Requires worker authentication and X-Tenant-ID header.

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    InternalCreateRun
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let internalCreateRun: InternalCreateRun; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledExportsInternalRunsCreate(
    internalCreateRun,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **internalCreateRun** | **InternalCreateRun**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** | Run created successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**200** | Run already exists (idempotent replay) |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledExportsInternalRunsPartialUpdate**
> scheduledExportsInternalRunsPartialUpdate()

Update a scheduled export run (status, item counts, result_json, completed_at, etc.). When status changes to COMPLETED or FAILED, side effects are triggered (next_run_at calculation, cost tracking, domain events). Requires worker authentication and X-Tenant-ID header.

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    PatchedInternalUpdateRun
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedInternalUpdateRun: PatchedInternalUpdateRun; // (optional)

const { status, data } = await apiInstance.scheduledExportsInternalRunsPartialUpdate(
    id,
    idempotencyKey,
    patchedInternalUpdateRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedInternalUpdateRun** | **PatchedInternalUpdateRun**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Run updated successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledIngestionsInternalConfigRetrieve**
> scheduledIngestionsInternalConfigRetrieve()

Get configuration for a scheduled ingestion (source_type, source_config with masked credentials, file_pattern, schedule_config, ingestion_state, etc.). Credentials in source_config are masked for security. Requires worker authentication and X-Tenant-ID header. Rate limiting: No rate limit (internal worker endpoints).

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let scheduledIngestionId: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsInternalConfigRetrieve(
    scheduledIngestionId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestionId** | [**string**] |  | defaults to undefined|


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
|**200** | Configuration retrieved successfully (credentials masked) |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledIngestionsInternalJobsCreate**
> scheduledIngestionsInternalJobsCreate()

POST .../internal/jobs/ — create Job (type SCHEDULED_INGESTION) for Prefect execution.  Job is created with executed_by_prefect=True and is NOT enqueued to RQ. RQ worker will no-op when it sees this job. UI can show \"Execution: Prefect\" and link to prefect_flow_run_id.

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsInternalJobsCreate(
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

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | No response body |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledIngestionsInternalProcessFileCreate**
> scheduledIngestionsInternalProcessFileCreate(internalProcessFile)

Process a single file for a scheduled ingestion run. Performs validation, optional DQ checks, creates File and Dataset, indexes in search, and updates incremental state. On permanent failure, creates DLQ record and emits audit/domain events. Requires worker authentication and X-Tenant-ID header. Rate limiting: No rate limit (internal worker endpoints).

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    InternalProcessFile
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let internalProcessFile: InternalProcessFile; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsInternalProcessFileCreate(
    internalProcessFile,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **internalProcessFile** | **InternalProcessFile**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** | File processed successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledIngestionsInternalRunsCreate**
> scheduledIngestionsInternalRunsCreate(internalCreateRun)

Create a new scheduled ingestion run with status RUNNING. Idempotent by idempotency_key or prefect_flow_run_id. Requires worker authentication and X-Tenant-ID header.

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    InternalCreateRun
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let internalCreateRun: InternalCreateRun; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsInternalRunsCreate(
    internalCreateRun,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **internalCreateRun** | **InternalCreateRun**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** | Run created successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**200** | Run already exists (idempotent replay) |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledIngestionsInternalRunsPartialUpdate**
> scheduledIngestionsInternalRunsPartialUpdate()

Update a scheduled ingestion run (status, file counts, result_json, completed_at, etc.). When status changes to COMPLETED or FAILED, side effects are triggered (next_run_at calculation, cost tracking, DLQ sync, notifications, domain events). Requires worker authentication and X-Tenant-ID header.

### Example

```typescript
import {
    InternalWorkerApi,
    Configuration,
    PatchedInternalUpdateRun
} from './api';

const configuration = new Configuration();
const apiInstance = new InternalWorkerApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedInternalUpdateRun: PatchedInternalUpdateRun; // (optional)

const { status, data } = await apiInstance.scheduledIngestionsInternalRunsPartialUpdate(
    id,
    idempotencyKey,
    patchedInternalUpdateRun
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedInternalUpdateRun** | **PatchedInternalUpdateRun**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Run updated successfully |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

