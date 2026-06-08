# EventsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**eventsDlqList**](#eventsdlqlist) | **GET** /api/v1/events/dlq/ | List dead letter queue entries|
|[**eventsDlqResolveCreate**](#eventsdlqresolvecreate) | **POST** /api/v1/events/dlq/{dlq_id}/resolve/ | Resolve dead letter queue entry|
|[**eventsDlqRetryCreate**](#eventsdlqretrycreate) | **POST** /api/v1/events/dlq/{dlq_id}/retry/ | Retry dead letter queue entry|
|[**eventsReplayCreate**](#eventsreplaycreate) | **POST** /api/v1/events/replay/ | Replay events|

# **eventsDlqList**
> PaginatedDLQEntryList eventsDlqList()

List dead letter queue entries with optional filtering. Requires PLATFORM_ADMIN or TENANT_ADMIN role.

### Example

```typescript
import {
    EventsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new EventsApi(configuration);

let eventType: string; //Filter by event type (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let resolved: boolean; //Filter by resolved status (true/false) (optional) (default to undefined)
let subscriber: string; //Filter by subscriber name (optional) (default to undefined)

const { status, data } = await apiInstance.eventsDlqList(
    eventType,
    page,
    pageSize,
    resolved,
    subscriber
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **eventType** | [**string**] | Filter by event type | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **resolved** | [**boolean**] | Filter by resolved status (true/false) | (optional) defaults to undefined|
| **subscriber** | [**string**] | Filter by subscriber name | (optional) defaults to undefined|


### Return type

**PaginatedDLQEntryList**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**401** |  |  -  |
|**403** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **eventsDlqResolveCreate**
> DLQResolveResponse eventsDlqResolveCreate()

Mark a dead letter queue entry as resolved without retrying. Requires PLATFORM_ADMIN or TENANT_ADMIN role.

### Example

```typescript
import {
    EventsApi,
    Configuration,
    DLQResolveRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new EventsApi(configuration);

let dlqId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let dLQResolveRequest: DLQResolveRequest; // (optional)

const { status, data } = await apiInstance.eventsDlqResolveCreate(
    dlqId,
    idempotencyKey,
    dLQResolveRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dLQResolveRequest** | **DLQResolveRequest**|  | |
| **dlqId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DLQResolveResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** |  |  -  |
|**403** |  |  -  |
|**404** |  |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **eventsDlqRetryCreate**
> DLQRetryResponse eventsDlqRetryCreate()

Retry processing a dead letter queue entry by republishing the event. Requires PLATFORM_ADMIN or TENANT_ADMIN role.

### Example

```typescript
import {
    EventsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new EventsApi(configuration);

let dlqId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.eventsDlqRetryCreate(
    dlqId,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dlqId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DLQRetryResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** |  |  -  |
|**403** |  |  -  |
|**404** |  |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **eventsReplayCreate**
> EventReplayResponse eventsReplayCreate()

Replay events from the event store. Supports filtering by event_type, tenant_id, and time range. Rate limited to 10 replays per hour per tenant. Events are idempotent (duplicate events are skipped).

### Example

```typescript
import {
    EventsApi,
    Configuration,
    EventReplayRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new EventsApi(configuration);

let endTime: string; //End time for replay (ISO 8601 format) (optional) (default to undefined)
let eventType: string; //Filter by event type (e.g., \"odps.created\") (optional) (default to undefined)
let limit: number; //Maximum number of events to replay (default: 100, max: 1000) (optional) (default to undefined)
let startTime: string; //Start time for replay (ISO 8601 format) (optional) (default to undefined)
let tenantId: string; //Filter by tenant ID (optional) (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let eventReplayRequest: EventReplayRequest; // (optional)

const { status, data } = await apiInstance.eventsReplayCreate(
    endTime,
    eventType,
    limit,
    startTime,
    tenantId,
    idempotencyKey,
    eventReplayRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **eventReplayRequest** | **EventReplayRequest**|  | |
| **endTime** | [**string**] | End time for replay (ISO 8601 format) | (optional) defaults to undefined|
| **eventType** | [**string**] | Filter by event type (e.g., \&quot;odps.created\&quot;) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of events to replay (default: 100, max: 1000) | (optional) defaults to undefined|
| **startTime** | [**string**] | Start time for replay (ISO 8601 format) | (optional) defaults to undefined|
| **tenantId** | [**string**] | Filter by tenant ID | (optional) defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**EventReplayResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** |  |  -  |
|**403** |  |  -  |
|**429** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

