# AuditApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**auditAuditEventsExportRetrieve**](#auditauditeventsexportretrieve) | **GET** /api/v1/audit/audit-events/export/ | |
|[**auditAuditEventsList**](#auditauditeventslist) | **GET** /api/v1/audit/audit-events/ | |
|[**auditAuditEventsResourceActivityRetrieve**](#auditauditeventsresourceactivityretrieve) | **GET** /api/v1/audit/audit-events/resource-activity/ | |
|[**auditAuditEventsRetrieve**](#auditauditeventsretrieve) | **GET** /api/v1/audit/audit-events/{id}/ | |
|[**auditResourceActivityRetrieve**](#auditresourceactivityretrieve) | **GET** /api/v1/audit/resource-activity/ | |

# **auditAuditEventsExportRetrieve**
> AuditEvent auditAuditEventsExportRetrieve()

Export audit events to CSV or JSON.  Query params: - format: \'csv\' or \'json\' (default: \'json\') - All other filters from list endpoint apply  Note: DRF may interpret ?format=csv as a format suffix, causing routing issues. This method prioritizes query parameter over format suffix to avoid conflicts.

### Example

```typescript
import {
    AuditApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AuditApi(configuration);

let format: 'csv' | 'json'; // (optional) (default to undefined)

const { status, data } = await apiInstance.auditAuditEventsExportRetrieve(
    format
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **format** | [**&#39;csv&#39; | &#39;json&#39;**]**Array<&#39;csv&#39; &#124; &#39;json&#39;>** |  | (optional) defaults to undefined|


### Return type

**AuditEvent**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: text/csv, application/json


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

# **auditAuditEventsList**
> PaginatedAuditEventList auditAuditEventsList()

List audit events with filtering

### Example

```typescript
import {
    AuditApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AuditApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.auditAuditEventsList(
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

**PaginatedAuditEventList**

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

# **auditAuditEventsResourceActivityRetrieve**
> AuditEvent auditAuditEventsResourceActivityRetrieve()

Backwards-compat shim — delegates to :class:`ResourceActivityViewSet`.  Kept so existing frontend callers at ``/api/v1/audit/audit-events/resource-activity/`` keep working while clients migrate to the new top-level ``/api/v1/audit/resource-activity/`` route.  All scoping / sanitization rules are identical because both paths share the same helper.

### Example

```typescript
import {
    AuditApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AuditApi(configuration);

const { status, data } = await apiInstance.auditAuditEventsResourceActivityRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**AuditEvent**

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

# **auditAuditEventsRetrieve**
> AuditEvent auditAuditEventsRetrieve()

Retrieve audit event by ID

### Example

```typescript
import {
    AuditApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AuditApi(configuration);

let id: string; //A UUID string identifying this audit event. (default to undefined)

const { status, data } = await apiInstance.auditAuditEventsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this audit event. | defaults to undefined|


### Return type

**AuditEvent**

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

# **auditResourceActivityRetrieve**
> auditResourceActivityRetrieve()

Per-resource sanitized audit feed.  Mounted at ``/api/v1/audit/resource-activity/``.  List-only (no retrieve / create / update / destroy).  Authentication required; authorization is handled per-request via the involvement predicate so role-based gating cannot be used to starve legitimate owners.

### Example

```typescript
import {
    AuditApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AuditApi(configuration);

const { status, data } = await apiInstance.auditResourceActivityRetrieve();
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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

