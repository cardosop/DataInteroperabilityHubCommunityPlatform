# AccessAnalyticsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**governanceAccessAnalyticsAnomaliesRetrieve**](#governanceaccessanalyticsanomaliesretrieve) | **GET** /api/v1/governance/access/analytics/anomalies/ | Get anomalies|
|[**governanceAccessAnalyticsDashboardRetrieve**](#governanceaccessanalyticsdashboardretrieve) | **GET** /api/v1/governance/access/analytics/dashboard/ | Get access analytics dashboard|
|[**governanceAccessAnalyticsPatternsRetrieve**](#governanceaccessanalyticspatternsretrieve) | **GET** /api/v1/governance/access/analytics/patterns/ | Get access patterns|
|[**governanceAccessAnalyticsSecurityEventsRetrieve**](#governanceaccessanalyticssecurityeventsretrieve) | **GET** /api/v1/governance/access/analytics/security-events/ | Get security events|
|[**governanceAnalyticsAnomaliesRetrieve**](#governanceanalyticsanomaliesretrieve) | **GET** /api/v1/governance/analytics/anomalies/ | Get anomalies|
|[**governanceAnalyticsDashboardRetrieve**](#governanceanalyticsdashboardretrieve) | **GET** /api/v1/governance/analytics/dashboard/ | Get access analytics dashboard|
|[**governanceAnalyticsPatternsRetrieve**](#governanceanalyticspatternsretrieve) | **GET** /api/v1/governance/analytics/patterns/ | Get access patterns|
|[**governanceAnalyticsSecurityEventsRetrieve**](#governanceanalyticssecurityeventsretrieve) | **GET** /api/v1/governance/analytics/security-events/ | Get security events|

# **governanceAccessAnalyticsAnomaliesRetrieve**
> governanceAccessAnalyticsAnomaliesRetrieve()

Get detected access anomalies

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let limit: number; //Maximum number of results (default: 100) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAnalyticsAnomaliesRetrieve(
    endDate,
    limit,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of results (default: 100) | (optional) defaults to undefined|
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
|**200** | List of anomalies |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessAnalyticsDashboardRetrieve**
> governanceAccessAnalyticsDashboardRetrieve()

Get complete access analytics dashboard with patterns, anomalies, and security events

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAnalyticsDashboardRetrieve(
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
|**200** | Access analytics dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessAnalyticsPatternsRetrieve**
> governanceAccessAnalyticsPatternsRetrieve()

Get access patterns for analysis

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)
let userId: string; //User UUID filter (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAnalyticsPatternsRetrieve(
    endDate,
    resourceType,
    startDate,
    userId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|
| **userId** | [**string**] | User UUID filter | (optional) defaults to undefined|


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
|**200** | List of access patterns |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessAnalyticsSecurityEventsRetrieve**
> governanceAccessAnalyticsSecurityEventsRetrieve()

Get security events (denied access, anomalies)

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let limit: number; //Maximum number of results (default: 100) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAnalyticsSecurityEventsRetrieve(
    endDate,
    limit,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of results (default: 100) | (optional) defaults to undefined|
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
|**200** | List of security events |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAnalyticsAnomaliesRetrieve**
> governanceAnalyticsAnomaliesRetrieve()

Get detected access anomalies

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let limit: number; //Maximum number of results (default: 100) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAnalyticsAnomaliesRetrieve(
    endDate,
    limit,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of results (default: 100) | (optional) defaults to undefined|
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
|**200** | List of anomalies |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAnalyticsDashboardRetrieve**
> governanceAnalyticsDashboardRetrieve()

Get complete access analytics dashboard with patterns, anomalies, and security events

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAnalyticsDashboardRetrieve(
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
|**200** | Access analytics dashboard data |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAnalyticsPatternsRetrieve**
> governanceAnalyticsPatternsRetrieve()

Get access patterns for analysis

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let resourceType: string; //Resource type filter (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)
let userId: string; //User UUID filter (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAnalyticsPatternsRetrieve(
    endDate,
    resourceType,
    startDate,
    userId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **resourceType** | [**string**] | Resource type filter | (optional) defaults to undefined|
| **startDate** | [**string**] | Start date (ISO format) | (optional) defaults to undefined|
| **userId** | [**string**] | User UUID filter | (optional) defaults to undefined|


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
|**200** | List of access patterns |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAnalyticsSecurityEventsRetrieve**
> governanceAnalyticsSecurityEventsRetrieve()

Get security events (denied access, anomalies)

### Example

```typescript
import {
    AccessAnalyticsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessAnalyticsApi(configuration);

let endDate: string; //End date (ISO format) (optional) (default to undefined)
let limit: number; //Maximum number of results (default: 100) (optional) (default to undefined)
let startDate: string; //Start date (ISO format) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAnalyticsSecurityEventsRetrieve(
    endDate,
    limit,
    startDate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **endDate** | [**string**] | End date (ISO format) | (optional) defaults to undefined|
| **limit** | [**number**] | Maximum number of results (default: 100) | (optional) defaults to undefined|
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
|**200** | List of security events |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

