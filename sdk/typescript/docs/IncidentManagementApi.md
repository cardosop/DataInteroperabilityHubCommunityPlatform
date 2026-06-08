# IncidentManagementApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilityIncidentsCreate**](#metricsobservabilityincidentscreate) | **POST** /metrics/observability/incidents/ | Get data incidents dashboard|
|[**metricsObservabilityIncidentsRetrieve**](#metricsobservabilityincidentsretrieve) | **GET** /metrics/observability/incidents/ | Get data incidents dashboard|
|[**metricsObservabilityIncidentsUpdatePartialUpdate**](#metricsobservabilityincidentsupdatepartialupdate) | **PATCH** /metrics/observability/incidents/update/ | Update data incident|
|[**observabilityIncidentsCreate**](#observabilityincidentscreate) | **POST** /api/v1/observability/incidents/ | Get data incidents dashboard|
|[**observabilityIncidentsRetrieve**](#observabilityincidentsretrieve) | **GET** /api/v1/observability/incidents/ | Get data incidents dashboard|
|[**observabilityIncidentsUpdatePartialUpdate**](#observabilityincidentsupdatepartialupdate) | **PATCH** /api/v1/observability/incidents/update/ | Update data incident|

# **metricsObservabilityIncidentsCreate**
> metricsObservabilityIncidentsCreate()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let assignedToId: string; //Assigned user UUID filter (optional) (default to undefined)
let incidentType: string; //Incident type filter (optional) (default to undefined)
let limit: number; //Maximum number of incidents (default: 100) (optional) (default to undefined)
let resourceId: string; //Resource UUID filter (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let severity: string; //Severity filter (optional) (default to undefined)
let status: string; //Status filter (optional) (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityIncidentsCreate(
    assignedToId,
    incidentType,
    limit,
    resourceId,
    resourceType,
    severity,
    status,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assignedToId** | [**string**] | Assigned user UUID filter | (optional) defaults to undefined|
| **incidentType** | [**string**] | Incident type filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of incidents (default: 100) | (optional) defaults to undefined|
| **resourceId** | [**string**] | Resource UUID filter | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **severity** | [**string**] | Severity filter | (optional) defaults to undefined|
| **status** | [**string**] | Status filter | (optional) defaults to undefined|
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
|**200** | Data incidents dashboard data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityIncidentsRetrieve**
> metricsObservabilityIncidentsRetrieve()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let assignedToId: string; //Assigned user UUID filter (optional) (default to undefined)
let incidentType: string; //Incident type filter (optional) (default to undefined)
let limit: number; //Maximum number of incidents (default: 100) (optional) (default to undefined)
let resourceId: string; //Resource UUID filter (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let severity: string; //Severity filter (optional) (default to undefined)
let status: string; //Status filter (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityIncidentsRetrieve(
    assignedToId,
    incidentType,
    limit,
    resourceId,
    resourceType,
    severity,
    status
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assignedToId** | [**string**] | Assigned user UUID filter | (optional) defaults to undefined|
| **incidentType** | [**string**] | Incident type filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of incidents (default: 100) | (optional) defaults to undefined|
| **resourceId** | [**string**] | Resource UUID filter | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **severity** | [**string**] | Severity filter | (optional) defaults to undefined|
| **status** | [**string**] | Status filter | (optional) defaults to undefined|


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
|**200** | Data incidents dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityIncidentsUpdatePartialUpdate**
> metricsObservabilityIncidentsUpdatePartialUpdate()

         Update a data incident (status, assignment, resolution).          **Body Parameters:**         - `status`: New status (TRIAGED, IN_PROGRESS, RESOLVED)         - `assigned_to_id`: User UUID to assign to (optional)         - `root_cause`: Root cause analysis (optional)         - `resolution_notes`: Resolution notes (optional)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let incidentId: string; //Incident UUID (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityIncidentsUpdatePartialUpdate(
    incidentId,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **incidentId** | [**string**] | Incident UUID | defaults to undefined|
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
|**200** | Incident updated |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityIncidentsCreate**
> observabilityIncidentsCreate()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let assignedToId: string; //Assigned user UUID filter (optional) (default to undefined)
let incidentType: string; //Incident type filter (optional) (default to undefined)
let limit: number; //Maximum number of incidents (default: 100) (optional) (default to undefined)
let resourceId: string; //Resource UUID filter (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let severity: string; //Severity filter (optional) (default to undefined)
let status: string; //Status filter (optional) (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityIncidentsCreate(
    assignedToId,
    incidentType,
    limit,
    resourceId,
    resourceType,
    severity,
    status,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assignedToId** | [**string**] | Assigned user UUID filter | (optional) defaults to undefined|
| **incidentType** | [**string**] | Incident type filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of incidents (default: 100) | (optional) defaults to undefined|
| **resourceId** | [**string**] | Resource UUID filter | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **severity** | [**string**] | Severity filter | (optional) defaults to undefined|
| **status** | [**string**] | Status filter | (optional) defaults to undefined|
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
|**200** | Data incidents dashboard data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityIncidentsRetrieve**
> observabilityIncidentsRetrieve()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let assignedToId: string; //Assigned user UUID filter (optional) (default to undefined)
let incidentType: string; //Incident type filter (optional) (default to undefined)
let limit: number; //Maximum number of incidents (default: 100) (optional) (default to undefined)
let resourceId: string; //Resource UUID filter (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let severity: string; //Severity filter (optional) (default to undefined)
let status: string; //Status filter (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityIncidentsRetrieve(
    assignedToId,
    incidentType,
    limit,
    resourceId,
    resourceType,
    severity,
    status
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assignedToId** | [**string**] | Assigned user UUID filter | (optional) defaults to undefined|
| **incidentType** | [**string**] | Incident type filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of incidents (default: 100) | (optional) defaults to undefined|
| **resourceId** | [**string**] | Resource UUID filter | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **severity** | [**string**] | Severity filter | (optional) defaults to undefined|
| **status** | [**string**] | Status filter | (optional) defaults to undefined|


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
|**200** | Data incidents dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityIncidentsUpdatePartialUpdate**
> observabilityIncidentsUpdatePartialUpdate()

         Update a data incident (status, assignment, resolution).          **Body Parameters:**         - `status`: New status (TRIAGED, IN_PROGRESS, RESOLVED)         - `assigned_to_id`: User UUID to assign to (optional)         - `root_cause`: Root cause analysis (optional)         - `resolution_notes`: Resolution notes (optional)         

### Example

```typescript
import {
    IncidentManagementApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IncidentManagementApi(configuration);

let incidentId: string; //Incident UUID (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityIncidentsUpdatePartialUpdate(
    incidentId,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **incidentId** | [**string**] | Incident UUID | defaults to undefined|
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
|**200** | Incident updated |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

