# SchemaDriftApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilitySchemaDriftDetectCreate**](#metricsobservabilityschemadriftdetectcreate) | **POST** /metrics/observability/schema-drift/detect/ | Detect schema drift|
|[**metricsObservabilitySchemaDriftRetrieve**](#metricsobservabilityschemadriftretrieve) | **GET** /metrics/observability/schema-drift/ | Get schema drift dashboard|
|[**observabilitySchemaDriftDetectCreate**](#observabilityschemadriftdetectcreate) | **POST** /api/v1/observability/schema-drift/detect/ | Detect schema drift|
|[**observabilitySchemaDriftRetrieve**](#observabilityschemadriftretrieve) | **GET** /api/v1/observability/schema-drift/ | Get schema drift dashboard|

# **metricsObservabilitySchemaDriftDetectCreate**
> metricsObservabilitySchemaDriftDetectCreate()

         Manually trigger schema drift detection for a dataset or asset.          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `tolerance_config`: Tolerance configuration (optional)         

### Example

```typescript
import {
    SchemaDriftApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SchemaDriftApi(configuration);

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
    SchemaDriftApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SchemaDriftApi(configuration);

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

# **observabilitySchemaDriftDetectCreate**
> observabilitySchemaDriftDetectCreate()

         Manually trigger schema drift detection for a dataset or asset.          **Body Parameters:**         - `dataset_id`: Dataset UUID (optional)         - `asset_id`: Asset UUID (optional)         - `tolerance_config`: Tolerance configuration (optional)         

### Example

```typescript
import {
    SchemaDriftApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SchemaDriftApi(configuration);

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
    SchemaDriftApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SchemaDriftApi(configuration);

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

