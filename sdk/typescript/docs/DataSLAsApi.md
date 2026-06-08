# DataSLAsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**metricsObservabilitySlasRetrieve**](#metricsobservabilityslasretrieve) | **GET** /metrics/observability/slas/ | Get data SLAs dashboard|
|[**observabilitySlasRetrieve**](#observabilityslasretrieve) | **GET** /api/v1/observability/slas/ | Get data SLAs dashboard|

# **metricsObservabilitySlasRetrieve**
> metricsObservabilitySlasRetrieve()

         Get data SLAs dashboard with compliance monitoring.          **Query Parameters:**         - `sla_type`: Optional SLA type filter (AVAILABILITY, FRESHNESS, QUALITY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `is_active`: Optional active filter (true/false)         - `is_violated`: Optional violation filter (true/false)         - `limit`: Maximum number of SLAs (default: 100)         

### Example

```typescript
import {
    DataSLAsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataSLAsApi(configuration);

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

# **observabilitySlasRetrieve**
> observabilitySlasRetrieve()

         Get data SLAs dashboard with compliance monitoring.          **Query Parameters:**         - `sla_type`: Optional SLA type filter (AVAILABILITY, FRESHNESS, QUALITY)         - `dataset_id`: Optional dataset UUID filter         - `asset_id`: Optional asset UUID filter         - `is_active`: Optional active filter (true/false)         - `is_violated`: Optional violation filter (true/false)         - `limit`: Maximum number of SLAs (default: 100)         

### Example

```typescript
import {
    DataSLAsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataSLAsApi(configuration);

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

