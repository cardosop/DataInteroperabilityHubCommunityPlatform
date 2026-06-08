# FreshnessApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilityFreshnessRetrieve**](#metricsobservabilityfreshnessretrieve) | **GET** /metrics/observability/freshness/ | Get freshness dashboard|
|[**metricsObservabilityFreshnessStaleRetrieve**](#metricsobservabilityfreshnessstaleretrieve) | **GET** /metrics/observability/freshness/stale/ | Get stale data|
|[**observabilityFreshnessRetrieve**](#observabilityfreshnessretrieve) | **GET** /api/v1/observability/freshness/ | Get freshness dashboard|
|[**observabilityFreshnessStaleRetrieve**](#observabilityfreshnessstaleretrieve) | **GET** /api/v1/observability/freshness/stale/ | Get stale data|

# **metricsObservabilityFreshnessRetrieve**
> metricsObservabilityFreshnessRetrieve()

         Get data freshness dashboard with metrics and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    FreshnessApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new FreshnessApi(configuration);

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
    FreshnessApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new FreshnessApi(configuration);

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

# **observabilityFreshnessRetrieve**
> observabilityFreshnessRetrieve()

         Get data freshness dashboard with metrics and statistics.          **Query Parameters:**         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `limit`: Maximum number of records (default: 100)         

### Example

```typescript
import {
    FreshnessApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new FreshnessApi(configuration);

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
    FreshnessApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new FreshnessApi(configuration);

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

