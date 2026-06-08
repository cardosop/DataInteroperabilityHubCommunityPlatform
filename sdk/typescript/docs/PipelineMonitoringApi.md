# PipelineMonitoringApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilityPipelinesRetrieve**](#metricsobservabilitypipelinesretrieve) | **GET** /metrics/observability/pipelines/ | Get pipeline monitoring dashboard|
|[**observabilityPipelinesRetrieve**](#observabilitypipelinesretrieve) | **GET** /api/v1/observability/pipelines/ | Get pipeline monitoring dashboard|

# **metricsObservabilityPipelinesRetrieve**
> metricsObservabilityPipelinesRetrieve()

         Get pipeline monitoring dashboard with execution metrics, success rates, error rates, latency, and throughput.          **Query Parameters:**         - `pipeline_type`: Optional pipeline type filter (SCHEDULED_INGESTION, DQ_RUN, etc.)         - `pipeline_id`: Optional pipeline UUID filter         - `limit`: Maximum number of executions (default: 100)         

### Example

```typescript
import {
    PipelineMonitoringApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new PipelineMonitoringApi(configuration);

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

# **observabilityPipelinesRetrieve**
> observabilityPipelinesRetrieve()

         Get pipeline monitoring dashboard with execution metrics, success rates, error rates, latency, and throughput.          **Query Parameters:**         - `pipeline_type`: Optional pipeline type filter (SCHEDULED_INGESTION, DQ_RUN, etc.)         - `pipeline_id`: Optional pipeline UUID filter         - `limit`: Maximum number of executions (default: 100)         

### Example

```typescript
import {
    PipelineMonitoringApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new PipelineMonitoringApi(configuration);

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

