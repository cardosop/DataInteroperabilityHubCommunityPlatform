# CostTrackingApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**analyticsCostsBreakdownRetrieve**](#analyticscostsbreakdownretrieve) | **GET** /api/v1/analytics/costs/breakdown/ | Get cost breakdown|
|[**analyticsCostsByAssetRetrieve**](#analyticscostsbyassetretrieve) | **GET** /api/v1/analytics/costs/by-asset/ | Get cost by asset|
|[**analyticsCostsList**](#analyticscostslist) | **GET** /api/v1/analytics/costs/ | Get cost summary|
|[**analyticsCostsRecommendationsRetrieve**](#analyticscostsrecommendationsretrieve) | **GET** /api/v1/analytics/costs/recommendations/ | Get cost recommendations|
|[**analyticsCostsTrendsRetrieve**](#analyticscoststrendsretrieve) | **GET** /api/v1/analytics/costs/trends/ | Get cost trends|

# **analyticsCostsBreakdownRetrieve**
> analyticsCostsBreakdownRetrieve()

Get cost breakdown by category (storage, API, ingestion, export).

### Example

```typescript
import {
    CostTrackingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new CostTrackingApi(configuration);

let endDate: string; // (optional) (default to undefined)
let period: string; //period (month) (optional) (default to undefined)
let startDate: string; // (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsCostsBreakdownRetrieve(
    endDate,
    period,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] |  | (optional) defaults to undefined|
| **period** | [**string**] | period (month) | (optional) defaults to undefined|
| **startDate** | [**string**] |  | (optional) defaults to undefined|


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
|**200** | Cost breakdown |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsCostsByAssetRetrieve**
> analyticsCostsByAssetRetrieve()

Get cost breakdown by asset (storage per asset).

### Example

```typescript
import {
    CostTrackingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new CostTrackingApi(configuration);

let endDate: string; // (optional) (default to undefined)
let startDate: string; // (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsCostsByAssetRetrieve(
    endDate,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] |  | (optional) defaults to undefined|
| **startDate** | [**string**] |  | (optional) defaults to undefined|


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
|**200** | Cost by asset |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsCostsList**
> analyticsCostsList()

Get cost tracking summary for tenant (usage → cost).

### Example

```typescript
import {
    CostTrackingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new CostTrackingApi(configuration);

const { status, data } = await apiInstance.analyticsCostsList();
```

### Parameters
This endpoint does not have any parameters.


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
|**200** | Cost summary |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsCostsRecommendationsRetrieve**
> analyticsCostsRecommendationsRetrieve()

Get cost optimization recommendations.

### Example

```typescript
import {
    CostTrackingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new CostTrackingApi(configuration);

const { status, data } = await apiInstance.analyticsCostsRecommendationsRetrieve();
```

### Parameters
This endpoint does not have any parameters.


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
|**200** | Recommendations |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **analyticsCostsTrendsRetrieve**
> analyticsCostsTrendsRetrieve()

Get cost trends over time.

### Example

```typescript
import {
    CostTrackingApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new CostTrackingApi(configuration);

let months: number; //Number of months (default 6) (optional) (default to undefined)
let period: string; // (optional) (default to undefined)

const { status, data } = await apiInstance.analyticsCostsTrendsRetrieve(
    months,
    period
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **months** | [**number**] | Number of months (default 6) | (optional) defaults to undefined|
| **period** | [**string**] |  | (optional) defaults to undefined|


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
|**200** | Cost trends |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

