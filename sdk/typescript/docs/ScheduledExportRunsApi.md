# ScheduledExportRunsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**scheduledExportsRunsList**](#scheduledexportsrunslist) | **GET** /api/v1/scheduled-exports/runs/ | List scheduled export runs|
|[**scheduledExportsRunsRetrieve**](#scheduledexportsrunsretrieve) | **GET** /api/v1/scheduled-exports/runs/{id}/ | Get scheduled export run details|

# **scheduledExportsRunsList**
> PaginatedScheduledExportRunList scheduledExportsRunsList()

List all scheduled export runs for the authenticated user\'s tenant with filtering and pagination.

### Example

```typescript
import {
    ScheduledExportRunsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledExportRunsApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.scheduledExportsRunsList(
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedScheduledExportRunList**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **scheduledExportsRunsRetrieve**
> ScheduledExportRun scheduledExportsRunsRetrieve()

Get detailed information about a specific scheduled export run.

### Example

```typescript
import {
    ScheduledExportRunsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ScheduledExportRunsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.scheduledExportsRunsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**ScheduledExportRun**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

