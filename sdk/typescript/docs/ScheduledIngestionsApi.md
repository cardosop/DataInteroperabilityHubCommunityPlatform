# ScheduledIngestionsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**scheduledIngestionRuns**](#scheduledingestionruns) | **GET** /api/v1/scheduled-ingestions/{id}/runs/ | |
|[**scheduledIngestionTrigger**](#scheduledingestiontrigger) | **POST** /api/v1/scheduled-ingestions/{id}/trigger/ | |
|[**scheduledIngestionsCostsRetrieve**](#scheduledingestionscostsretrieve) | **GET** /api/v1/scheduled-ingestions/costs/ | |
|[**scheduledIngestionsCreate**](#scheduledingestionscreate) | **POST** /api/v1/scheduled-ingestions/ | |
|[**scheduledIngestionsDashboardRetrieve**](#scheduledingestionsdashboardretrieve) | **GET** /api/v1/scheduled-ingestions/dashboard/ | |
|[**scheduledIngestionsDeadLetterQueueRetrieve**](#scheduledingestionsdeadletterqueueretrieve) | **GET** /api/v1/scheduled-ingestions/dead-letter-queue/ | |
|[**scheduledIngestionsDestroy**](#scheduledingestionsdestroy) | **DELETE** /api/v1/scheduled-ingestions/{id}/ | |
|[**scheduledIngestionsDlqResolveCreate**](#scheduledingestionsdlqresolvecreate) | **POST** /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/ | |
|[**scheduledIngestionsDlqRetryCreate**](#scheduledingestionsdlqretrycreate) | **POST** /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/ | |
|[**scheduledIngestionsList**](#scheduledingestionslist) | **GET** /api/v1/scheduled-ingestions/ | |
|[**scheduledIngestionsPartialUpdate**](#scheduledingestionspartialupdate) | **PATCH** /api/v1/scheduled-ingestions/{id}/ | |
|[**scheduledIngestionsRetrieve**](#scheduledingestionsretrieve) | **GET** /api/v1/scheduled-ingestions/{id}/ | |
|[**scheduledIngestionsRunsList**](#scheduledingestionsrunslist) | **GET** /api/v1/scheduled-ingestions/runs/ | |
|[**scheduledIngestionsRunsRetrieve**](#scheduledingestionsrunsretrieve) | **GET** /api/v1/scheduled-ingestions/runs/{id}/ | |
|[**scheduledIngestionsUpdate**](#scheduledingestionsupdate) | **PUT** /api/v1/scheduled-ingestions/{id}/ | |

# **scheduledIngestionRuns**
> PaginatedScheduledIngestionRunList scheduledIngestionRuns()

List runs for a scheduled ingestion.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionRuns(
    id,
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedScheduledIngestionRunList**

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

# **scheduledIngestionTrigger**
> ScheduledIngestionTriggerResponse scheduledIngestionTrigger()

Manually trigger a scheduled ingestion.  Creates a Prefect flow run for the scheduled ingestion.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    ScheduledIngestionTrigger
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let scheduledIngestionTrigger: ScheduledIngestionTrigger; // (optional)

const { status, data } = await apiInstance.scheduledIngestionTrigger(
    id,
    idempotencyKey,
    scheduledIngestionTrigger
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestionTrigger** | **ScheduledIngestionTrigger**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestionTriggerResponse**

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

# **scheduledIngestionsCostsRetrieve**
> ScheduledIngestion scheduledIngestionsCostsRetrieve()

Get ingestion cost report.  GET /api/v1/scheduled-ingestions/costs/

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

const { status, data } = await apiInstance.scheduledIngestionsCostsRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsCreate**
> ScheduledIngestionCreate scheduledIngestionsCreate(scheduledIngestionCreate)

Create scheduled ingestion via service (validates via ScheduledIngestionBusinessRules).

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    ScheduledIngestionCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let scheduledIngestionCreate: ScheduledIngestionCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsCreate(
    scheduledIngestionCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestionCreate** | **ScheduledIngestionCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestionCreate**

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

# **scheduledIngestionsDashboardRetrieve**
> ScheduledIngestion scheduledIngestionsDashboardRetrieve()

Get ingestion monitoring dashboard.  GET /api/v1/scheduled-ingestions/dashboard/

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

const { status, data } = await apiInstance.scheduledIngestionsDashboardRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsDeadLetterQueueRetrieve**
> ScheduledIngestion scheduledIngestionsDeadLetterQueueRetrieve()

Get Dead Letter Queue dashboard.  GET /api/v1/scheduled-ingestions/dead-letter-queue/

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

const { status, data } = await apiInstance.scheduledIngestionsDeadLetterQueueRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsDestroy**
> scheduledIngestionsDestroy()

Phase 25.9.1 — Ordered delete: remove Prefect deployment *before* DB record.  1. If the instance has a prefect_deployment_id, call the integration    service to delete the deployment first. 2. If that call fails, mark the record status=DELETED (soft-delete) so    the hourly purge CronJob can retry, and return HTTP 409 Conflict. 3. Only hard-delete the DB record after a successful deployment delete.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


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

# **scheduledIngestionsDlqResolveCreate**
> ScheduledIngestion scheduledIngestionsDlqResolveCreate(scheduledIngestion)

Resolve a Dead Letter Queue item.  POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    ScheduledIngestion
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let dlqItemId: string; // (default to undefined)
let id: string; // (default to undefined)
let scheduledIngestion: ScheduledIngestion; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsDlqResolveCreate(
    dlqItemId,
    id,
    scheduledIngestion,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestion** | **ScheduledIngestion**|  | |
| **dlqItemId** | [**string**] |  | defaults to undefined|
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsDlqRetryCreate**
> ScheduledIngestion scheduledIngestionsDlqRetryCreate(scheduledIngestion)

Retry a failed file from Dead Letter Queue.  POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    ScheduledIngestion
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let dlqItemId: string; // (default to undefined)
let id: string; // (default to undefined)
let scheduledIngestion: ScheduledIngestion; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsDlqRetryCreate(
    dlqItemId,
    id,
    scheduledIngestion,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestion** | **ScheduledIngestion**|  | |
| **dlqItemId** | [**string**] |  | defaults to undefined|
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsList**
> PaginatedScheduledIngestionList scheduledIngestionsList()

ViewSet for scheduled ingestion management.  Provides CRUD operations and additional actions for scheduled ingestions.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsList(
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

**PaginatedScheduledIngestionList**

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

# **scheduledIngestionsPartialUpdate**
> ScheduledIngestion scheduledIngestionsPartialUpdate()

ViewSet for scheduled ingestion management.  Provides CRUD operations and additional actions for scheduled ingestions.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    PatchedScheduledIngestion
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedScheduledIngestion: PatchedScheduledIngestion; // (optional)

const { status, data } = await apiInstance.scheduledIngestionsPartialUpdate(
    id,
    idempotencyKey,
    patchedScheduledIngestion
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedScheduledIngestion** | **PatchedScheduledIngestion**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsRetrieve**
> ScheduledIngestion scheduledIngestionsRetrieve()

ViewSet for scheduled ingestion management.  Provides CRUD operations and additional actions for scheduled ingestions.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**ScheduledIngestion**

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

# **scheduledIngestionsRunsList**
> PaginatedScheduledIngestionRunList scheduledIngestionsRunsList()

Read-only ViewSet for scheduled ingestion runs.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsRunsList(
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

**PaginatedScheduledIngestionRunList**

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

# **scheduledIngestionsRunsRetrieve**
> ScheduledIngestionRun scheduledIngestionsRunsRetrieve()

Read-only ViewSet for scheduled ingestion runs.

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsRunsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**ScheduledIngestionRun**

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

# **scheduledIngestionsUpdate**
> ScheduledIngestion scheduledIngestionsUpdate(scheduledIngestion)

Override to return 207 when sync fails (Phase 25.5.1).

### Example

```typescript
import {
    ScheduledIngestionsApi,
    Configuration,
    ScheduledIngestion
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledIngestionsApi(configuration);

let id: string; // (default to undefined)
let scheduledIngestion: ScheduledIngestion; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledIngestionsUpdate(
    id,
    scheduledIngestion,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **scheduledIngestion** | **ScheduledIngestion**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ScheduledIngestion**

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

