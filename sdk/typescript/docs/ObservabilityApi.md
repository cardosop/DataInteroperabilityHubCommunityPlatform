# ObservabilityApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilityFreshnessRetrieve**](#metricsobservabilityfreshnessretrieve) | **GET** /metrics/observability/freshness/ | Get freshness dashboard|
|[**metricsObservabilityFreshnessStaleRetrieve**](#metricsobservabilityfreshnessstaleretrieve) | **GET** /metrics/observability/freshness/stale/ | Get stale data|
|[**metricsObservabilityIncidentsCreate**](#metricsobservabilityincidentscreate) | **POST** /metrics/observability/incidents/ | Get data incidents dashboard|
|[**metricsObservabilityIncidentsRetrieve**](#metricsobservabilityincidentsretrieve) | **GET** /metrics/observability/incidents/ | Get data incidents dashboard|
|[**metricsObservabilityIncidentsUpdatePartialUpdate**](#metricsobservabilityincidentsupdatepartialupdate) | **PATCH** /metrics/observability/incidents/update/ | Update data incident|
|[**metricsObservabilityLineageRetrieve**](#metricsobservabilitylineageretrieve) | **GET** /metrics/observability/lineage/ | Get lineage|
|[**metricsObservabilityMetricsCreate**](#metricsobservabilitymetricscreate) | **POST** /metrics/observability/metrics/ | Record observability metric|
|[**metricsObservabilityPipelinesRetrieve**](#metricsobservabilitypipelinesretrieve) | **GET** /metrics/observability/pipelines/ | Get pipeline monitoring dashboard|
|[**metricsObservabilitySchemaDriftDetectCreate**](#metricsobservabilityschemadriftdetectcreate) | **POST** /metrics/observability/schema-drift/detect/ | Detect schema drift|
|[**metricsObservabilitySchemaDriftRetrieve**](#metricsobservabilityschemadriftretrieve) | **GET** /metrics/observability/schema-drift/ | Get schema drift dashboard|
|[**metricsObservabilitySlasRetrieve**](#metricsobservabilityslasretrieve) | **GET** /metrics/observability/slas/ | Get data SLAs dashboard|
|[**metricsObservabilityVolumeAggregateCreate**](#metricsobservabilityvolumeaggregatecreate) | **POST** /metrics/observability/volume/aggregate/ | Aggregate volume trends|
|[**metricsObservabilityVolumeRetrieve**](#metricsobservabilityvolumeretrieve) | **GET** /metrics/observability/volume/ | Get volume dashboard|
|[**observabilityFreshnessRetrieve**](#observabilityfreshnessretrieve) | **GET** /api/v1/observability/freshness/ | Get freshness dashboard|
|[**observabilityFreshnessStaleRetrieve**](#observabilityfreshnessstaleretrieve) | **GET** /api/v1/observability/freshness/stale/ | Get stale data|
|[**observabilityIncidentsCreate**](#observabilityincidentscreate) | **POST** /api/v1/observability/incidents/ | Get data incidents dashboard|
|[**observabilityIncidentsRetrieve**](#observabilityincidentsretrieve) | **GET** /api/v1/observability/incidents/ | Get data incidents dashboard|
|[**observabilityIncidentsUpdatePartialUpdate**](#observabilityincidentsupdatepartialupdate) | **PATCH** /api/v1/observability/incidents/update/ | Update data incident|
|[**observabilityLineageRetrieve**](#observabilitylineageretrieve) | **GET** /api/v1/observability/lineage/ | Get lineage|
|[**observabilityMetricsCreate**](#observabilitymetricscreate) | **POST** /api/v1/observability/metrics/ | Record observability metric|
|[**observabilityPipelinesRetrieve**](#observabilitypipelinesretrieve) | **GET** /api/v1/observability/pipelines/ | Get pipeline monitoring dashboard|
|[**observabilitySchemaDriftDetectCreate**](#observabilityschemadriftdetectcreate) | **POST** /api/v1/observability/schema-drift/detect/ | Detect schema drift|
|[**observabilitySchemaDriftRetrieve**](#observabilityschemadriftretrieve) | **GET** /api/v1/observability/schema-drift/ | Get schema drift dashboard|
|[**observabilitySlasRetrieve**](#observabilityslasretrieve) | **GET** /api/v1/observability/slas/ | Get data SLAs dashboard|
|[**observabilityVolumeAggregateCreate**](#observabilityvolumeaggregatecreate) | **POST** /api/v1/observability/volume/aggregate/ | Aggregate volume trends|
|[**observabilityVolumeRetrieve**](#observabilityvolumeretrieve) | **GET** /api/v1/observability/volume/ | Get volume dashboard|

# **metricsObservabilityFreshnessRetrieve**
> metricsObservabilityFreshnessRetrieve()

         Get data freshness dashboard with metrics and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of records (default: 100) (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityFreshnessRetrieve(
    assetId,
    datasetId,
    limit
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of records (default: 100) | (optional) defaults to undefined|


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
|**200** | Freshness dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityFreshnessStaleRetrieve**
> metricsObservabilityFreshnessStaleRetrieve()

         Get all stale data (exceeds SLA).          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityFreshnessStaleRetrieve(
    assetId,
    datasetId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|


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
|**200** | List of stale data records |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityIncidentsCreate**
> metricsObservabilityIncidentsCreate()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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

# **metricsObservabilityLineageRetrieve**
> metricsObservabilityLineageRetrieve()

         Get contract-level lineage (delegates to contract lineage service).          **Query Parameters:**         - `contract_id` (required): Contract UUID to retrieve lineage for.         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let contractId: string; //Contract UUID to get lineage for (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityLineageRetrieve(
    contractId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractId** | [**string**] | Contract UUID to get lineage for | defaults to undefined|


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
|**200** | Lineage data with contracts and entries |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityMetricsCreate**
> metricsObservabilityMetricsCreate()

         Record a data observability metric (freshness, volume, schema).          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `last_update_time`: Last update timestamp (ISO format, optional)         - `freshness_sla`: Freshness SLA level (optional)         - `row_count`: Number of rows (optional)         - `size_bytes`: Size in bytes (optional)         - `schema_json`: Schema JSON (optional)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityMetricsCreate(
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
|**201** | Metric recorded |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityPipelinesRetrieve**
> metricsObservabilityPipelinesRetrieve()

         Get pipeline monitoring dashboard with execution metrics, success rates, error rates, latency, and throughput.          **Query Parameters:**         - `pipeline_type`: Optional pipeline type filter (SCHEDULED_INGESTION, DQ_RUN, etc.)         - `pipeline_id`: Optional pipeline UUID filter         - `limit`: Maximum number of executions (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let limit: number; //Maximum number of executions (default: 100) (optional) (default to undefined)
let pipelineId: string; //Pipeline UUID filter (optional) (default to undefined)
let pipelineType: string; //Pipeline type filter (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityPipelinesRetrieve(
    limit,
    pipelineId,
    pipelineType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **limit** | [**number**] | Maximum number of executions (default: 100) | (optional) defaults to undefined|
| **pipelineId** | [**string**] | Pipeline UUID filter | (optional) defaults to undefined|
| **pipelineType** | [**string**] | Pipeline type filter | (optional) defaults to undefined|


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
|**200** | Pipeline monitoring dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilitySchemaDriftDetectCreate**
> metricsObservabilitySchemaDriftDetectCreate()

         Manually trigger schema drift detection for a dataset or asset.          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `tolerance_config`: Tolerance configuration (optional)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilitySchemaDriftDetectCreate(
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
|**200** | Drift detection result |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilitySchemaDriftRetrieve**
> metricsObservabilitySchemaDriftRetrieve()

         Get schema drift dashboard with detected drifts and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of records (default: 100) (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilitySchemaDriftRetrieve(
    assetId,
    datasetId,
    limit
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of records (default: 100) | (optional) defaults to undefined|


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
|**200** | Schema drift dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilitySlasRetrieve**
> metricsObservabilitySlasRetrieve()

         Get data SLAs dashboard with compliance monitoring.          **Query Parameters:**         - `sla_type`: Optional SLA type filter (AVAILABILITY, FRESHNESS, QUALITY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `is_active`: Optional active filter (true/false)         - `is_violated`: Optional violation filter (true/false)         - `limit`: Maximum number of SLAs (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let isActive: boolean; //Active filter (optional) (default to undefined)
let isViolated: boolean; //Violation filter (optional) (default to undefined)
let limit: number; //Maximum number of SLAs (default: 100) (optional) (default to undefined)
let slaType: string; //SLA type filter (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilitySlasRetrieve(
    assetId,
    datasetId,
    isActive,
    isViolated,
    limit,
    slaType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **isActive** | [**boolean**] | Active filter | (optional) defaults to undefined|
| **isViolated** | [**boolean**] | Violation filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of SLAs (default: 100) | (optional) defaults to undefined|
| **slaType** | [**string**] | SLA type filter | (optional) defaults to undefined|


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
|**200** | Data SLAs dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityVolumeAggregateCreate**
> metricsObservabilityVolumeAggregateCreate()

         Aggregate volume trends for hourly or daily periods.          **Query Parameters:**         - `period_type`: Period type (HOURLY or DAILY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `hours`: Number of hours to aggregate (for HOURLY, default: 24)         - `days`: Number of days to aggregate (for DAILY, default: 30)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let periodType: string; //Period type: HOURLY or DAILY (default to undefined)
let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let days: number; //Number of days to aggregate (for DAILY) (optional) (default to undefined)
let hours: number; //Number of hours to aggregate (for HOURLY) (optional) (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityVolumeAggregateCreate(
    periodType,
    assetId,
    datasetId,
    days,
    hours,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **periodType** | [**string**] | Period type: HOURLY or DAILY | defaults to undefined|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **days** | [**number**] | Number of days to aggregate (for DAILY) | (optional) defaults to undefined|
| **hours** | [**number**] | Number of hours to aggregate (for HOURLY) | (optional) defaults to undefined|
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
|**200** | Aggregated trends |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **metricsObservabilityVolumeRetrieve**
> metricsObservabilityVolumeRetrieve()

         Get data volume dashboard with trends and anomaly detection.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `period_type`: Period type (HOURLY or DAILY, default: DAILY)         - `limit`: Maximum number of trends (default: 30)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of trends (default: 30) (optional) (default to undefined)
let periodType: string; //Period type: HOURLY or DAILY (default: DAILY) (optional) (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityVolumeRetrieve(
    assetId,
    datasetId,
    limit,
    periodType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of trends (default: 30) | (optional) defaults to undefined|
| **periodType** | [**string**] | Period type: HOURLY or DAILY (default: DAILY) | (optional) defaults to undefined|


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
|**200** | Volume dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityFreshnessRetrieve**
> observabilityFreshnessRetrieve()

         Get data freshness dashboard with metrics and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of records (default: 100) (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityFreshnessRetrieve(
    assetId,
    datasetId,
    limit
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of records (default: 100) | (optional) defaults to undefined|


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
|**200** | Freshness dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityFreshnessStaleRetrieve**
> observabilityFreshnessStaleRetrieve()

         Get all stale data (exceeds SLA).          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityFreshnessStaleRetrieve(
    assetId,
    datasetId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|


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
|**200** | List of stale data records |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityIncidentsCreate**
> observabilityIncidentsCreate()

         Get data incidents dashboard with lifecycle tracking.          **Query Parameters:**         - `status`: Optional status filter (DETECTED, TRIAGED, IN_PROGRESS, RESOLVED)         - `incident_type`: Optional incident type filter         - `severity`: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)         - `assigned_to_id`: Optional assigned user UUID filter         - `resource_type`: Optional resource type filter         - `resource_id`: Optional resource UUID filter         - `limit`: Maximum number of incidents (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

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

# **observabilityLineageRetrieve**
> observabilityLineageRetrieve()

         Get contract-level lineage (delegates to contract lineage service).          **Query Parameters:**         - `contract_id` (required): Contract UUID to retrieve lineage for.         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let contractId: string; //Contract UUID to get lineage for (default to undefined)

const { status, data } = await apiInstance.observabilityLineageRetrieve(
    contractId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractId** | [**string**] | Contract UUID to get lineage for | defaults to undefined|


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
|**200** | Lineage data with contracts and entries |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityMetricsCreate**
> observabilityMetricsCreate()

         Record a data observability metric (freshness, volume, schema).          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `last_update_time`: Last update timestamp (ISO format, optional)         - `freshness_sla`: Freshness SLA level (optional)         - `row_count`: Number of rows (optional)         - `size_bytes`: Size in bytes (optional)         - `schema_json`: Schema JSON (optional)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityMetricsCreate(
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
|**201** | Metric recorded |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityPipelinesRetrieve**
> observabilityPipelinesRetrieve()

         Get pipeline monitoring dashboard with execution metrics, success rates, error rates, latency, and throughput.          **Query Parameters:**         - `pipeline_type`: Optional pipeline type filter (SCHEDULED_INGESTION, DQ_RUN, etc.)         - `pipeline_id`: Optional pipeline UUID filter         - `limit`: Maximum number of executions (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let limit: number; //Maximum number of executions (default: 100) (optional) (default to undefined)
let pipelineId: string; //Pipeline UUID filter (optional) (default to undefined)
let pipelineType: string; //Pipeline type filter (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityPipelinesRetrieve(
    limit,
    pipelineId,
    pipelineType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **limit** | [**number**] | Maximum number of executions (default: 100) | (optional) defaults to undefined|
| **pipelineId** | [**string**] | Pipeline UUID filter | (optional) defaults to undefined|
| **pipelineType** | [**string**] | Pipeline type filter | (optional) defaults to undefined|


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
|**200** | Pipeline monitoring dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilitySchemaDriftDetectCreate**
> observabilitySchemaDriftDetectCreate()

         Manually trigger schema drift detection for a dataset or asset.          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `tolerance_config`: Tolerance configuration (optional)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.observabilitySchemaDriftDetectCreate(
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
|**200** | Drift detection result |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilitySchemaDriftRetrieve**
> observabilitySchemaDriftRetrieve()

         Get schema drift dashboard with detected drifts and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of records (default: 100) (optional) (default to undefined)

const { status, data } = await apiInstance.observabilitySchemaDriftRetrieve(
    assetId,
    datasetId,
    limit
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of records (default: 100) | (optional) defaults to undefined|


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
|**200** | Schema drift dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilitySlasRetrieve**
> observabilitySlasRetrieve()

         Get data SLAs dashboard with compliance monitoring.          **Query Parameters:**         - `sla_type`: Optional SLA type filter (AVAILABILITY, FRESHNESS, QUALITY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `is_active`: Optional active filter (true/false)         - `is_violated`: Optional violation filter (true/false)         - `limit`: Maximum number of SLAs (default: 100)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let isActive: boolean; //Active filter (optional) (default to undefined)
let isViolated: boolean; //Violation filter (optional) (default to undefined)
let limit: number; //Maximum number of SLAs (default: 100) (optional) (default to undefined)
let slaType: string; //SLA type filter (optional) (default to undefined)

const { status, data } = await apiInstance.observabilitySlasRetrieve(
    assetId,
    datasetId,
    isActive,
    isViolated,
    limit,
    slaType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **isActive** | [**boolean**] | Active filter | (optional) defaults to undefined|
| **isViolated** | [**boolean**] | Violation filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of SLAs (default: 100) | (optional) defaults to undefined|
| **slaType** | [**string**] | SLA type filter | (optional) defaults to undefined|


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
|**200** | Data SLAs dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityVolumeAggregateCreate**
> observabilityVolumeAggregateCreate()

         Aggregate volume trends for hourly or daily periods.          **Query Parameters:**         - `period_type`: Period type (HOURLY or DAILY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `hours`: Number of hours to aggregate (for HOURLY, default: 24)         - `days`: Number of days to aggregate (for DAILY, default: 30)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let periodType: string; //Period type: HOURLY or DAILY (default to undefined)
let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let days: number; //Number of days to aggregate (for DAILY) (optional) (default to undefined)
let hours: number; //Number of hours to aggregate (for HOURLY) (optional) (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityVolumeAggregateCreate(
    periodType,
    assetId,
    datasetId,
    days,
    hours,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **periodType** | [**string**] | Period type: HOURLY or DAILY | defaults to undefined|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **days** | [**number**] | Number of days to aggregate (for DAILY) | (optional) defaults to undefined|
| **hours** | [**number**] | Number of hours to aggregate (for HOURLY) | (optional) defaults to undefined|
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
|**200** | Aggregated trends |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityVolumeRetrieve**
> observabilityVolumeRetrieve()

         Get data volume dashboard with trends and anomaly detection.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `period_type`: Period type (HOURLY or DAILY, default: DAILY)         - `limit`: Maximum number of trends (default: 30)         

### Example

```typescript
import {
    ObservabilityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ObservabilityApi(configuration);

let assetId: string; //Asset UUID filter (optional) (default to undefined)
let datasetId: string; //Dataset UUID filter (optional) (default to undefined)
let limit: number; //Maximum number of trends (default: 30) (optional) (default to undefined)
let periodType: string; //Period type: HOURLY or DAILY (default: DAILY) (optional) (default to undefined)

const { status, data } = await apiInstance.observabilityVolumeRetrieve(
    assetId,
    datasetId,
    limit,
    periodType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID filter | (optional) defaults to undefined|
| **datasetId** | [**string**] | Dataset UUID filter | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of trends (default: 30) | (optional) defaults to undefined|
| **periodType** | [**string**] | Period type: HOURLY or DAILY (default: DAILY) | (optional) defaults to undefined|


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
|**200** | Volume dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

