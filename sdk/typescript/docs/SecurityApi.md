# SecurityApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**securityAuditLogsList**](#securityauditlogslist) | **GET** /api/v1/security/audit-logs/ | List security audit logs|
|[**securityAuditLogsRetrieve**](#securityauditlogsretrieve) | **GET** /api/v1/security/audit-logs/{id}/ | |
|[**securityIncidentsList**](#securityincidentslist) | **GET** /api/v1/security/incidents/ | |
|[**securityIncidentsResolveCreate**](#securityincidentsresolvecreate) | **POST** /api/v1/security/incidents/{id}/resolve/ | Resolve security incident|
|[**securityIncidentsRetrieve**](#securityincidentsretrieve) | **GET** /api/v1/security/incidents/{id}/ | |

# **securityAuditLogsList**
> PaginatedSecurityAuditLogList securityAuditLogsList()

         List security audit logs with filtering and pagination.          **Filtering:**         - `event_type`: Filter by event type (e.g., EXTERNAL_REF_FETCH,           RATE_LIMIT_EXCEEDED, CACHE_HIT, CACHE_MISS, CACHE_EVICTION,           SECURITY_VIOLATION)         - `tenant_id`: Filter by tenant ID         - `user_id`: Filter by user ID         - `ref_type`: Filter by ref type (internal, local, external)         - `cache_operation`: Filter by cache operation (hit, miss, eviction)         - `start_date`: Filter by start date (ISO 8601 format)         - `end_date`: Filter by end date (ISO 8601 format)          **Sorting:**         - `ordering`: Comma-separated list of fields to sort by           (e.g., -timestamp,event_type)         - Default: `-timestamp` (newest first)          **Access:**         - Admin only (platform admins)         

### Example

```typescript
import {
    SecurityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SecurityApi(configuration);

let cacheOperation: string; //Filter by cache operation (hit, miss, eviction) (optional) (default to undefined)
let endDate: string; //Filter by end date (ISO 8601 format) (optional) (default to undefined)
let eventType: string; //Filter by event type (optional) (default to undefined)
let ordering: string; //Comma-separated list of fields to sort by (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let refType: string; //Filter by ref type (internal, local, external) (optional) (default to undefined)
let startDate: string; //Filter by start date (ISO 8601 format) (optional) (default to undefined)
let tenantId: string; //Filter by tenant ID (optional) (default to undefined)
let userId: string; //Filter by user ID (optional) (default to undefined)

const { status, data } = await apiInstance.securityAuditLogsList(
    cacheOperation,
    endDate,
    eventType,
    ordering,
    page,
    pageSize,
    refType,
    startDate,
    tenantId,
    userId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **cacheOperation** | [**string**] | Filter by cache operation (hit, miss, eviction) | (optional) defaults to undefined|
| **endDate** | [**string**] | Filter by end date (ISO 8601 format) | (optional) defaults to undefined|
| **eventType** | [**string**] | Filter by event type | (optional) defaults to undefined|
| **ordering** | [**string**] | Comma-separated list of fields to sort by | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **refType** | [**string**] | Filter by ref type (internal, local, external) | (optional) defaults to undefined|
| **startDate** | [**string**] | Filter by start date (ISO 8601 format) | (optional) defaults to undefined|
| **tenantId** | [**string**] | Filter by tenant ID | (optional) defaults to undefined|
| **userId** | [**string**] | Filter by user ID | (optional) defaults to undefined|


### Return type

**PaginatedSecurityAuditLogList**

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

# **securityAuditLogsRetrieve**
> SecurityAuditLog securityAuditLogsRetrieve()

ViewSet for security audit logs (read-only).  Provides queryable access to security audit logs with filtering and pagination. Admin only access.

### Example

```typescript
import {
    SecurityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SecurityApi(configuration);

let id: string; //A UUID string identifying this security audit log. (default to undefined)

const { status, data } = await apiInstance.securityAuditLogsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this security audit log. | defaults to undefined|


### Return type

**SecurityAuditLog**

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

# **securityIncidentsList**
> PaginatedSecurityIncidentList securityIncidentsList()

ViewSet for security incident management.  Provides read-only access to security incidents with filtering by severity, status, and time range. Admin-only access for security incident resolution.

### Example

```typescript
import {
    SecurityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SecurityApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.securityIncidentsList(
    ordering,
    page,
    pageSize,
    search
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **ordering** | [**string**] | Which field to use when ordering the results. | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **search** | [**string**] | A search term. | (optional) defaults to undefined|


### Return type

**PaginatedSecurityIncidentList**

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

# **securityIncidentsResolveCreate**
> SecurityIncident securityIncidentsResolveCreate()

Mark a security incident as resolved. Admin only.

### Example

```typescript
import {
    SecurityApi,
    Configuration,
    SecurityIncidentResolve
} from './api';

const configuration = new Configuration();
const apiInstance = new SecurityApi(configuration);

let id: string; //A UUID string identifying this security incident. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let securityIncidentResolve: SecurityIncidentResolve; // (optional)

const { status, data } = await apiInstance.securityIncidentsResolveCreate(
    id,
    idempotencyKey,
    securityIncidentResolve
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **securityIncidentResolve** | **SecurityIncidentResolve**|  | |
| **id** | [**string**] | A UUID string identifying this security incident. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**SecurityIncident**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **securityIncidentsRetrieve**
> SecurityIncident securityIncidentsRetrieve()

ViewSet for security incident management.  Provides read-only access to security incidents with filtering by severity, status, and time range. Admin-only access for security incident resolution.

### Example

```typescript
import {
    SecurityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SecurityApi(configuration);

let id: string; //A UUID string identifying this security incident. (default to undefined)

const { status, data } = await apiInstance.securityIncidentsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this security incident. | defaults to undefined|


### Return type

**SecurityIncident**

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

