# UsersApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**usersCreate**](#userscreate) | **POST** /api/v1/users/ | |
|[**usersDestroy**](#usersdestroy) | **DELETE** /api/v1/users/{id}/ | |
|[**usersInviteCreate**](#usersinvitecreate) | **POST** /api/v1/users/invite/ | |
|[**usersList**](#userslist) | **GET** /api/v1/users/ | |
|[**usersMeErasureRequestsList**](#usersmeerasurerequestslist) | **GET** /api/v1/users/me/erasure-requests/ | |
|[**usersMeErasureRequestsRequestErasureCreate**](#usersmeerasurerequestsrequesterasurecreate) | **POST** /api/v1/users/me/erasure-requests/request-erasure/ | |
|[**usersMeErasureRequestsRetrieve**](#usersmeerasurerequestsretrieve) | **GET** /api/v1/users/me/erasure-requests/{id}/ | |
|[**usersMeExportJobsExportDataCreate**](#usersmeexportjobsexportdatacreate) | **POST** /api/v1/users/me/export-jobs/export-data/ | |
|[**usersMeExportJobsList**](#usersmeexportjobslist) | **GET** /api/v1/users/me/export-jobs/ | |
|[**usersMeExportJobsRetrieve**](#usersmeexportjobsretrieve) | **GET** /api/v1/users/me/export-jobs/{id}/ | |
|[**usersPartialUpdate**](#userspartialupdate) | **PATCH** /api/v1/users/{id}/ | |
|[**usersRetrieve**](#usersretrieve) | **GET** /api/v1/users/{id}/ | |
|[**usersRolesCreate**](#usersrolescreate) | **POST** /api/v1/users/{id}/roles/ | |
|[**usersRolesList**](#usersroleslist) | **GET** /api/v1/users/roles/ | |
|[**usersRolesRetrieve**](#usersrolesretrieve) | **GET** /api/v1/users/roles/{id}/ | |
|[**usersUpdate**](#usersupdate) | **PUT** /api/v1/users/{id}/ | |

# **usersCreate**
> UserCreate usersCreate(userCreate)

Create a new user via service layer.  Creates user with optional role assignment and invitation.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    UserCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let userCreate: UserCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.usersCreate(
    userCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **userCreate** | **UserCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**UserCreate**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersDestroy**
> usersDestroy()

Delete user via service layer. Requires TENANT_ADMIN or PLATFORM_ADMIN.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this user. (default to undefined)

const { status, data } = await apiInstance.usersDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this user. | defaults to undefined|


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
|**204** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersInviteCreate**
> User usersInviteCreate(user)

Invite a user to join the tenant via service layer.  Creates user with INVITED status and sends invitation email.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    User
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let user: User; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.usersInviteCreate(
    user,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **user** | **User**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**User**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersList**
> PaginatedUserList usersList()

List users (tenant-scoped)

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.usersList(
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

**PaginatedUserList**

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

# **usersMeErasureRequestsList**
> PaginatedErasureRequestList usersMeErasureRequestsList()

ViewSet for erasure requests.  Users can only see their own erasure requests.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.usersMeErasureRequestsList(
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

**PaginatedErasureRequestList**

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

# **usersMeErasureRequestsRequestErasureCreate**
> ErasureRequest usersMeErasureRequestsRequestErasureCreate()

Request data erasure (GDPR Article 17 - Right to be Forgotten).  POST /api/v1/users/me/request-erasure/  Creates an erasure request.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    ErasureRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let erasureRequest: ErasureRequest; // (optional)

const { status, data } = await apiInstance.usersMeErasureRequestsRequestErasureCreate(
    idempotencyKey,
    erasureRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **erasureRequest** | **ErasureRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ErasureRequest**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersMeErasureRequestsRetrieve**
> ErasureRequest usersMeErasureRequestsRetrieve()

ViewSet for erasure requests.  Users can only see their own erasure requests.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.usersMeErasureRequestsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**ErasureRequest**

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

# **usersMeExportJobsExportDataCreate**
> DataExportJob usersMeExportJobsExportDataCreate()

Request a GDPR Article 20 data export.  Returns a job descriptor whose `download_url` resolves to a ZIP archive once `status == COMPLETED`. The archive layout is the public contract for downstream consumers:  **Archive contents** - `user_data.json` — JSON envelope (UTF-8). Top-level keys: `format_version` (semver), `exported_at` (ISO-8601), `user_profile`, `audit_events`, `assets`, `datasets`, `contracts`. Additive changes (new keys, new resource types) are non-breaking; renamed/removed keys or changed semantics bump the **major** component of `format_version` (currently `1.0.0`). - `README.txt` — human-readable cover sheet.  Consumers should branch on the major version of `format_version` and tolerate unknown keys. Encryption-at-rest of the archive is out of scope for v1 — delivery is over HTTPS via short-lived presigned URL.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    DataExportJob
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let dataExportJob: DataExportJob; // (optional)

const { status, data } = await apiInstance.usersMeExportJobsExportDataCreate(
    idempotencyKey,
    dataExportJob
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dataExportJob** | **DataExportJob**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**DataExportJob**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersMeExportJobsList**
> PaginatedDataExportJobList usersMeExportJobsList()

ViewSet for data export jobs.  Users can only see their own export jobs.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.usersMeExportJobsList(
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

**PaginatedDataExportJobList**

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

# **usersMeExportJobsRetrieve**
> DataExportJob usersMeExportJobsRetrieve()

ViewSet for data export jobs.  Users can only see their own export jobs.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.usersMeExportJobsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**DataExportJob**

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

# **usersPartialUpdate**
> UserUpdate usersPartialUpdate()

Update user via service layer (partial update). Requires TENANT_ADMIN or PLATFORM_ADMIN.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    PatchedUserUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this user. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedUserUpdate: PatchedUserUpdate; // (optional)

const { status, data } = await apiInstance.usersPartialUpdate(
    id,
    idempotencyKey,
    patchedUserUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedUserUpdate** | **PatchedUserUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this user. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**UserUpdate**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersRetrieve**
> User usersRetrieve()

Retrieve user by ID

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this user. (default to undefined)

const { status, data } = await apiInstance.usersRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this user. | defaults to undefined|


### Return type

**User**

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

# **usersRolesCreate**
> User usersRolesCreate(user)

Assign or remove a role from a user.  Requires TENANT_ADMIN or platform admin. Increments token_version to invalidate existing sessions.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    User
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this user. (default to undefined)
let user: User; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.usersRolesCreate(
    id,
    user,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **user** | **User**|  | |
| **id** | [**string**] | A UUID string identifying this user. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**User**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **usersRolesList**
> PaginatedRoleList usersRolesList()

ViewSet for role management (read-only for MVP).  Roles are created automatically when tenants are created.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.usersRolesList(
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

**PaginatedRoleList**

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

# **usersRolesRetrieve**
> Role usersRolesRetrieve()

ViewSet for role management (read-only for MVP).  Roles are created automatically when tenants are created.

### Example

```typescript
import {
    UsersApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this role. (default to undefined)

const { status, data } = await apiInstance.usersRolesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this role. | defaults to undefined|


### Return type

**Role**

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

# **usersUpdate**
> UserUpdate usersUpdate()

Update user via service layer (full update). Requires TENANT_ADMIN or PLATFORM_ADMIN.

### Example

```typescript
import {
    UsersApi,
    Configuration,
    UserUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new UsersApi(configuration);

let id: string; //A UUID string identifying this user. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let userUpdate: UserUpdate; // (optional)

const { status, data } = await apiInstance.usersUpdate(
    id,
    idempotencyKey,
    userUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **userUpdate** | **UserUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this user. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**UserUpdate**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

