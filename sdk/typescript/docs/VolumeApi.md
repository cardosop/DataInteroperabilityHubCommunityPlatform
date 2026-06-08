# VolumeApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilityVolumeAggregateCreate**](#metricsobservabilityvolumeaggregatecreate) | **POST** /metrics/observability/volume/aggregate/ | Aggregate volume trends|
|[**metricsObservabilityVolumeRetrieve**](#metricsobservabilityvolumeretrieve) | **GET** /metrics/observability/volume/ | Get volume dashboard|
|[**observabilityVolumeAggregateCreate**](#observabilityvolumeaggregatecreate) | **POST** /api/v1/observability/volume/aggregate/ | Aggregate volume trends|
|[**observabilityVolumeRetrieve**](#observabilityvolumeretrieve) | **GET** /api/v1/observability/volume/ | Get volume dashboard|

# **metricsObservabilityVolumeAggregateCreate**
> metricsObservabilityVolumeAggregateCreate()

         Aggregate volume trends for hourly or daily periods.          **Query Parameters:**         - `period_type`: Period type (HOURLY or DAILY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `hours`: Number of hours to aggregate (for HOURLY, default: 24)         - `days`: Number of days to aggregate (for DAILY, default: 30)         

### Example

```typescript
import {
    VolumeApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VolumeApi(configuration);

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
    VolumeApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VolumeApi(configuration);

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

# **observabilityVolumeAggregateCreate**
> observabilityVolumeAggregateCreate()

         Aggregate volume trends for hourly or daily periods.          **Query Parameters:**         - `period_type`: Period type (HOURLY or DAILY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `hours`: Number of hours to aggregate (for HOURLY, default: 24)         - `days`: Number of days to aggregate (for DAILY, default: 30)         

### Example

```typescript
import {
    VolumeApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VolumeApi(configuration);

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
    VolumeApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VolumeApi(configuration);

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

