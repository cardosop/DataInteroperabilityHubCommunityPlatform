# APIAnalyticsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**analyticsApiDashboardRetrieve**](#analyticsapidashboardretrieve) | **GET** /api/v1/analytics/api/dashboard/ | Get API analytics dashboard|
|[**analyticsApiPerformanceRetrieve**](#analyticsapiperformanceretrieve) | **GET** /api/v1/analytics/api/performance/ | Get performance metrics|
|[**analyticsApiPopularEndpointsRetrieve**](#analyticsapipopularendpointsretrieve) | **GET** /api/v1/analytics/api/popular-endpoints/ | Get popular endpoints|
|[**analyticsApiUsageTrendsRetrieve**](#analyticsapiusagetrendsretrieve) | **GET** /api/v1/analytics/api/usage-trends/ | Get usage trends|

# **analyticsApiDashboardRetrieve**
> analyticsApiDashboardRetrieve()

Get complete API analytics dashboard with popular endpoints, usage trends, and performance metrics

### Example

```typescript
import {
    APIAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsApiDashboardRetrieve(
    endDate,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|


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
|**200** | Analytics dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsApiPerformanceRetrieve**
> analyticsApiPerformanceRetrieve()

Get API performance metrics summary

### Example

```typescript
import {
    APIAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsApiPerformanceRetrieve(
    endDate,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|


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
|**200** | Performance metrics data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsApiPopularEndpointsRetrieve**
> analyticsApiPopularEndpointsRetrieve()

Get most popular API endpoints by request count

### Example

```typescript
import {
    APIAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let limit: number; //Maximum number of results (default: 20) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsApiPopularEndpointsRetrieve(
    endDate,
    limit,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of results (default: 20) | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|


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
|**200** | List of popular endpoints |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsApiUsageTrendsRetrieve**
> analyticsApiUsageTrendsRetrieve()

Get API usage trends over time

### Example

```typescript
import {
    APIAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new APIAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let granularity: string; //Time granularity: hour, day, or week (default: day) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsApiUsageTrendsRetrieve(
    endDate,
    granularity,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **granularity** | [**string**] | Time granularity: hour, day, or week (default: day) | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|


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
|**200** | Usage trends data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

