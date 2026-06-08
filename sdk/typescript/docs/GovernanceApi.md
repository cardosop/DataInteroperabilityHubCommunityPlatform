# GovernanceApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**governanceAccessAccessRequestsApproveCreate**](#governanceaccessaccessrequestsapprovecreate) | **POST** /api/v1/governance/access/access-requests/{id}/approve/ | |
|[**governanceAccessAccessRequestsBulkApproveCreate**](#governanceaccessaccessrequestsbulkapprovecreate) | **POST** /api/v1/governance/access/access-requests/bulk-approve/ | |
|[**governanceAccessAccessRequestsBulkRejectCreate**](#governanceaccessaccessrequestsbulkrejectcreate) | **POST** /api/v1/governance/access/access-requests/bulk-reject/ | |
|[**governanceAccessAccessRequestsCreate**](#governanceaccessaccessrequestscreate) | **POST** /api/v1/governance/access/access-requests/ | |
|[**governanceAccessAccessRequestsDestroy**](#governanceaccessaccessrequestsdestroy) | **DELETE** /api/v1/governance/access/access-requests/{id}/ | |
|[**governanceAccessAccessRequestsList**](#governanceaccessaccessrequestslist) | **GET** /api/v1/governance/access/access-requests/ | |
|[**governanceAccessAccessRequestsPartialUpdate**](#governanceaccessaccessrequestspartialupdate) | **PATCH** /api/v1/governance/access/access-requests/{id}/ | |
|[**governanceAccessAccessRequestsPendingCountRetrieve**](#governanceaccessaccessrequestspendingcountretrieve) | **GET** /api/v1/governance/access/access-requests/pending-count/ | |
|[**governanceAccessAccessRequestsRejectCreate**](#governanceaccessaccessrequestsrejectcreate) | **POST** /api/v1/governance/access/access-requests/{id}/reject/ | |
|[**governanceAccessAccessRequestsRetrieve**](#governanceaccessaccessrequestsretrieve) | **GET** /api/v1/governance/access/access-requests/{id}/ | |
|[**governanceAccessAccessRequestsRevokeCreate**](#governanceaccessaccessrequestsrevokecreate) | **POST** /api/v1/governance/access/access-requests/{id}/revoke/ | |
|[**governanceAccessAccessRequestsUpdate**](#governanceaccessaccessrequestsupdate) | **PUT** /api/v1/governance/access/access-requests/{id}/ | |
|[**governanceAccessCertificationsCreate**](#governanceaccesscertificationscreate) | **POST** /api/v1/governance/access/certifications/ | |
|[**governanceAccessCertificationsDestroy**](#governanceaccesscertificationsdestroy) | **DELETE** /api/v1/governance/access/certifications/{id}/ | |
|[**governanceAccessCertificationsList**](#governanceaccesscertificationslist) | **GET** /api/v1/governance/access/certifications/ | |
|[**governanceAccessCertificationsPartialUpdate**](#governanceaccesscertificationspartialupdate) | **PATCH** /api/v1/governance/access/certifications/{id}/ | |
|[**governanceAccessCertificationsRetrieve**](#governanceaccesscertificationsretrieve) | **GET** /api/v1/governance/access/certifications/{id}/ | |
|[**governanceAccessCertificationsUpdate**](#governanceaccesscertificationsupdate) | **PUT** /api/v1/governance/access/certifications/{id}/ | |
|[**governanceAccessRequestsApproveCreate**](#governanceaccessrequestsapprovecreate) | **POST** /api/v1/governance/access-requests/{id}/approve/ | |
|[**governanceAccessRequestsBulkApproveCreate**](#governanceaccessrequestsbulkapprovecreate) | **POST** /api/v1/governance/access-requests/bulk-approve/ | |
|[**governanceAccessRequestsBulkRejectCreate**](#governanceaccessrequestsbulkrejectcreate) | **POST** /api/v1/governance/access-requests/bulk-reject/ | |
|[**governanceAccessRequestsCreate**](#governanceaccessrequestscreate) | **POST** /api/v1/governance/access-requests/ | |
|[**governanceAccessRequestsDestroy**](#governanceaccessrequestsdestroy) | **DELETE** /api/v1/governance/access-requests/{id}/ | |
|[**governanceAccessRequestsList**](#governanceaccessrequestslist) | **GET** /api/v1/governance/access-requests/ | |
|[**governanceAccessRequestsPartialUpdate**](#governanceaccessrequestspartialupdate) | **PATCH** /api/v1/governance/access-requests/{id}/ | |
|[**governanceAccessRequestsPendingCountRetrieve**](#governanceaccessrequestspendingcountretrieve) | **GET** /api/v1/governance/access-requests/pending-count/ | |
|[**governanceAccessRequestsRejectCreate**](#governanceaccessrequestsrejectcreate) | **POST** /api/v1/governance/access-requests/{id}/reject/ | |
|[**governanceAccessRequestsRetrieve**](#governanceaccessrequestsretrieve) | **GET** /api/v1/governance/access-requests/{id}/ | |
|[**governanceAccessRequestsRevokeCreate**](#governanceaccessrequestsrevokecreate) | **POST** /api/v1/governance/access-requests/{id}/revoke/ | |
|[**governanceAccessRequestsUpdate**](#governanceaccessrequestsupdate) | **PUT** /api/v1/governance/access-requests/{id}/ | |
|[**governanceAccessRetentionPoliciesCreate**](#governanceaccessretentionpoliciescreate) | **POST** /api/v1/governance/access/retention-policies/ | |
|[**governanceAccessRetentionPoliciesDestroy**](#governanceaccessretentionpoliciesdestroy) | **DELETE** /api/v1/governance/access/retention-policies/{id}/ | |
|[**governanceAccessRetentionPoliciesList**](#governanceaccessretentionpolicieslist) | **GET** /api/v1/governance/access/retention-policies/ | |
|[**governanceAccessRetentionPoliciesPartialUpdate**](#governanceaccessretentionpoliciespartialupdate) | **PATCH** /api/v1/governance/access/retention-policies/{id}/ | |
|[**governanceAccessRetentionPoliciesRetrieve**](#governanceaccessretentionpoliciesretrieve) | **GET** /api/v1/governance/access/retention-policies/{id}/ | |
|[**governanceAccessRetentionPoliciesUpdate**](#governanceaccessretentionpoliciesupdate) | **PUT** /api/v1/governance/access/retention-policies/{id}/ | |
|[**governanceCertificationsCreate**](#governancecertificationscreate) | **POST** /api/v1/governance/certifications/ | |
|[**governanceCertificationsDestroy**](#governancecertificationsdestroy) | **DELETE** /api/v1/governance/certifications/{id}/ | |
|[**governanceCertificationsList**](#governancecertificationslist) | **GET** /api/v1/governance/certifications/ | |
|[**governanceCertificationsPartialUpdate**](#governancecertificationspartialupdate) | **PATCH** /api/v1/governance/certifications/{id}/ | |
|[**governanceCertificationsRetrieve**](#governancecertificationsretrieve) | **GET** /api/v1/governance/certifications/{id}/ | |
|[**governanceCertificationsUpdate**](#governancecertificationsupdate) | **PUT** /api/v1/governance/certifications/{id}/ | |
|[**governanceRetentionPoliciesCreate**](#governanceretentionpoliciescreate) | **POST** /api/v1/governance/retention-policies/ | |
|[**governanceRetentionPoliciesDestroy**](#governanceretentionpoliciesdestroy) | **DELETE** /api/v1/governance/retention-policies/{id}/ | |
|[**governanceRetentionPoliciesList**](#governanceretentionpolicieslist) | **GET** /api/v1/governance/retention-policies/ | |
|[**governanceRetentionPoliciesPartialUpdate**](#governanceretentionpoliciespartialupdate) | **PATCH** /api/v1/governance/retention-policies/{id}/ | |
|[**governanceRetentionPoliciesRetrieve**](#governanceretentionpoliciesretrieve) | **GET** /api/v1/governance/retention-policies/{id}/ | |
|[**governanceRetentionPoliciesUpdate**](#governanceretentionpoliciesupdate) | **PUT** /api/v1/governance/retention-policies/{id}/ | |

# **governanceAccessAccessRequestsApproveCreate**
> AccessRequest governanceAccessAccessRequestsApproveCreate(accessRequest)

Approve an access request.  POST /api/v1/governance/access-requests/{id}/approve/

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsApproveCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsBulkApproveCreate**
> AccessRequest governanceAccessAccessRequestsBulkApproveCreate(accessRequest)

Bulk-approve pending access requests (Phase 223.3.3).  POST /api/v1/governance/access-requests/bulk-approve/ Body: { \"ids\": [\"uuid\", ...], \"comments\": \"optional\" }  Each id is processed in its **own** ``transaction.atomic`` so a single failure does not roll back the successful approvals. The response surfaces both outcomes:     { \"succeeded\": [\"uuid\", ...], \"failed\": [{\"id\": \"uuid\", \"error\": \"...\"}] }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsBulkApproveCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsBulkRejectCreate**
> AccessRequest governanceAccessAccessRequestsBulkRejectCreate(accessRequest)

Bulk-reject pending access requests (Phase 223.3.3).  POST /api/v1/governance/access-requests/bulk-reject/ Body: { \"ids\": [\"uuid\", ...], \"reason\": \"required string\" }  Semantics match ``bulk_approve``: per-id atomicity, partial success reported in ``failed``.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsBulkRejectCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsCreate**
> AccessRequest governanceAccessAccessRequestsCreate(accessRequest)

Create an access request.  POST /api/v1/governance/access-requests/ Body: {     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional),     \"reason\": \"string\",     \"requested_access_type\": \"READ\" (optional, default: \"READ\"),     \"expires_at\": \"ISO datetime\" (optional) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsDestroy**
> governanceAccessAccessRequestsDestroy()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|


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

# **governanceAccessAccessRequestsList**
> PaginatedAccessRequestList governanceAccessAccessRequestsList()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsList(
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

**PaginatedAccessRequestList**

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

# **governanceAccessAccessRequestsPartialUpdate**
> AccessRequest governanceAccessAccessRequestsPartialUpdate()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedAccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedAccessRequest: PatchedAccessRequest; // (optional)

const { status, data } = await apiInstance.governanceAccessAccessRequestsPartialUpdate(
    id,
    idempotencyKey,
    patchedAccessRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedAccessRequest** | **PatchedAccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsPendingCountRetrieve**
> AccessRequest governanceAccessAccessRequestsPendingCountRetrieve()

Return the number of PENDING access requests visible to an admin.  GET /api/v1/governance/access-requests/pending-count/  - Platform admins: count across all tenants. - TENANT_ADMIN role: count within the caller\'s tenant. - All other users: 403.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

const { status, data } = await apiInstance.governanceAccessAccessRequestsPendingCountRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsRejectCreate**
> AccessRequest governanceAccessAccessRequestsRejectCreate(accessRequest)

Reject an access request.  POST /api/v1/governance/access-requests/{id}/reject/ Body: {     \"reason\": \"string\" (required) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsRejectCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsRetrieve**
> AccessRequest governanceAccessAccessRequestsRetrieve()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsRevokeCreate**
> AccessRequest governanceAccessAccessRequestsRevokeCreate(accessRequest)

Revoke an approved access request.  POST /api/v1/governance/access-requests/{id}/revoke/

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsRevokeCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessAccessRequestsUpdate**
> AccessRequest governanceAccessAccessRequestsUpdate(accessRequest)

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessAccessRequestsUpdate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessCertificationsCreate**
> AccessCertification governanceAccessCertificationsCreate(accessCertification)

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessCertification: AccessCertification; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsCreate(
    accessCertification,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessCertification** | **AccessCertification**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceAccessCertificationsDestroy**
> governanceAccessCertificationsDestroy()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|


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

# **governanceAccessCertificationsList**
> PaginatedAccessCertificationList governanceAccessCertificationsList()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsList(
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

**PaginatedAccessCertificationList**

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

# **governanceAccessCertificationsPartialUpdate**
> AccessCertification governanceAccessCertificationsPartialUpdate()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedAccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedAccessCertification: PatchedAccessCertification; // (optional)

const { status, data } = await apiInstance.governanceAccessCertificationsPartialUpdate(
    id,
    idempotencyKey,
    patchedAccessCertification
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedAccessCertification** | **PatchedAccessCertification**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceAccessCertificationsRetrieve**
> AccessCertification governanceAccessCertificationsRetrieve()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceAccessCertificationsUpdate**
> AccessCertification governanceAccessCertificationsUpdate(accessCertification)

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let accessCertification: AccessCertification; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsUpdate(
    id,
    accessCertification,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessCertification** | **AccessCertification**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceAccessRequestsApproveCreate**
> AccessRequest governanceAccessRequestsApproveCreate(accessRequest)

Approve an access request.  POST /api/v1/governance/access-requests/{id}/approve/

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsApproveCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsBulkApproveCreate**
> AccessRequest governanceAccessRequestsBulkApproveCreate(accessRequest)

Bulk-approve pending access requests (Phase 223.3.3).  POST /api/v1/governance/access-requests/bulk-approve/ Body: { \"ids\": [\"uuid\", ...], \"comments\": \"optional\" }  Each id is processed in its **own** ``transaction.atomic`` so a single failure does not roll back the successful approvals. The response surfaces both outcomes:     { \"succeeded\": [\"uuid\", ...], \"failed\": [{\"id\": \"uuid\", \"error\": \"...\"}] }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsBulkApproveCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsBulkRejectCreate**
> AccessRequest governanceAccessRequestsBulkRejectCreate(accessRequest)

Bulk-reject pending access requests (Phase 223.3.3).  POST /api/v1/governance/access-requests/bulk-reject/ Body: { \"ids\": [\"uuid\", ...], \"reason\": \"required string\" }  Semantics match ``bulk_approve``: per-id atomicity, partial success reported in ``failed``.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsBulkRejectCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsCreate**
> AccessRequest governanceAccessRequestsCreate(accessRequest)

Create an access request.  POST /api/v1/governance/access-requests/ Body: {     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional),     \"reason\": \"string\",     \"requested_access_type\": \"READ\" (optional, default: \"READ\"),     \"expires_at\": \"ISO datetime\" (optional) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsCreate(
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsDestroy**
> governanceAccessRequestsDestroy()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|


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

# **governanceAccessRequestsList**
> PaginatedAccessRequestList governanceAccessRequestsList()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsList(
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

**PaginatedAccessRequestList**

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

# **governanceAccessRequestsPartialUpdate**
> AccessRequest governanceAccessRequestsPartialUpdate()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedAccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedAccessRequest: PatchedAccessRequest; // (optional)

const { status, data } = await apiInstance.governanceAccessRequestsPartialUpdate(
    id,
    idempotencyKey,
    patchedAccessRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedAccessRequest** | **PatchedAccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsPendingCountRetrieve**
> AccessRequest governanceAccessRequestsPendingCountRetrieve()

Return the number of PENDING access requests visible to an admin.  GET /api/v1/governance/access-requests/pending-count/  - Platform admins: count across all tenants. - TENANT_ADMIN role: count within the caller\'s tenant. - All other users: 403.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

const { status, data } = await apiInstance.governanceAccessRequestsPendingCountRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**AccessRequest**

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

# **governanceAccessRequestsRejectCreate**
> AccessRequest governanceAccessRequestsRejectCreate(accessRequest)

Reject an access request.  POST /api/v1/governance/access-requests/{id}/reject/ Body: {     \"reason\": \"string\" (required) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsRejectCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsRetrieve**
> AccessRequest governanceAccessRequestsRetrieve()

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsRevokeCreate**
> AccessRequest governanceAccessRequestsRevokeCreate(accessRequest)

Revoke an approved access request.  POST /api/v1/governance/access-requests/{id}/revoke/

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsRevokeCreate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRequestsUpdate**
> AccessRequest governanceAccessRequestsUpdate(accessRequest)

ViewSet for access request management.  Tenant-scoped: users can only see/manage access requests in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access request. (default to undefined)
let accessRequest: AccessRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRequestsUpdate(
    id,
    accessRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessRequest** | **AccessRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access request. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessRequest**

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

# **governanceAccessRetentionPoliciesCreate**
> RetentionPolicy governanceAccessRetentionPoliciesCreate(retentionPolicy)

Create a retention policy via service layer (Phase 12.1.2).  POST /api/v1/governance/retention-policies/ Body: {     \"name\": \"string\" (required),     \"description\": \"string\" (optional),     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional),     \"policy_type\": \"TIME_BASED\" | \"EVENT_BASED\" (required),     \"retention_period_days\": int (required for TIME_BASED),     \"event_trigger\": \"string\" (required for EVENT_BASED),     \"action\": \"SOFT_DELETE\" | \"HARD_DELETE\" | \"ARCHIVE\" (optional, default: SOFT_DELETE),     \"grace_period_days\": int (optional, default: 30),     \"legal_hold\": bool (optional, default: false),     \"legal_hold_reason\": \"string\" (optional),     \"legal_hold_expires_at\": \"ISO datetime\" (optional),     \"enabled\": bool (optional, default: true) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    RetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let retentionPolicy: RetentionPolicy; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesCreate(
    retentionPolicy,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **retentionPolicy** | **RetentionPolicy**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceAccessRetentionPoliciesDestroy**
> governanceAccessRetentionPoliciesDestroy()

Delete retention policy

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|


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

# **governanceAccessRetentionPoliciesList**
> PaginatedRetentionPolicyList governanceAccessRetentionPoliciesList()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesList(
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

**PaginatedRetentionPolicyList**

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

# **governanceAccessRetentionPoliciesPartialUpdate**
> RetentionPolicy governanceAccessRetentionPoliciesPartialUpdate()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedRetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedRetentionPolicy: PatchedRetentionPolicy; // (optional)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesPartialUpdate(
    id,
    idempotencyKey,
    patchedRetentionPolicy
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedRetentionPolicy** | **PatchedRetentionPolicy**|  | |
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceAccessRetentionPoliciesRetrieve**
> RetentionPolicy governanceAccessRetentionPoliciesRetrieve()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceAccessRetentionPoliciesUpdate**
> RetentionPolicy governanceAccessRetentionPoliciesUpdate(retentionPolicy)

Update retention policy via service layer (Phase 12.1.2).  Service handles validation, persistence, and audit event emission.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    RetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)
let retentionPolicy: RetentionPolicy; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessRetentionPoliciesUpdate(
    id,
    retentionPolicy,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **retentionPolicy** | **RetentionPolicy**|  | |
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceCertificationsCreate**
> AccessCertification governanceCertificationsCreate(accessCertification)

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let accessCertification: AccessCertification; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsCreate(
    accessCertification,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessCertification** | **AccessCertification**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceCertificationsDestroy**
> governanceCertificationsDestroy()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|


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

# **governanceCertificationsList**
> PaginatedAccessCertificationList governanceCertificationsList()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsList(
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

**PaginatedAccessCertificationList**

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

# **governanceCertificationsPartialUpdate**
> AccessCertification governanceCertificationsPartialUpdate()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedAccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedAccessCertification: PatchedAccessCertification; // (optional)

const { status, data } = await apiInstance.governanceCertificationsPartialUpdate(
    id,
    idempotencyKey,
    patchedAccessCertification
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedAccessCertification** | **PatchedAccessCertification**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceCertificationsRetrieve**
> AccessCertification governanceCertificationsRetrieve()

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceCertificationsUpdate**
> AccessCertification governanceCertificationsUpdate(accessCertification)

ViewSet for access certification management.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    AccessCertification
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let accessCertification: AccessCertification; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsUpdate(
    id,
    accessCertification,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **accessCertification** | **AccessCertification**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**AccessCertification**

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

# **governanceRetentionPoliciesCreate**
> RetentionPolicy governanceRetentionPoliciesCreate(retentionPolicy)

Create a retention policy via service layer (Phase 12.1.2).  POST /api/v1/governance/retention-policies/ Body: {     \"name\": \"string\" (required),     \"description\": \"string\" (optional),     \"asset_id\": \"uuid\" (optional),     \"dataset_id\": \"uuid\" (optional),     \"file_id\": \"uuid\" (optional),     \"policy_type\": \"TIME_BASED\" | \"EVENT_BASED\" (required),     \"retention_period_days\": int (required for TIME_BASED),     \"event_trigger\": \"string\" (required for EVENT_BASED),     \"action\": \"SOFT_DELETE\" | \"HARD_DELETE\" | \"ARCHIVE\" (optional, default: SOFT_DELETE),     \"grace_period_days\": int (optional, default: 30),     \"legal_hold\": bool (optional, default: false),     \"legal_hold_reason\": \"string\" (optional),     \"legal_hold_expires_at\": \"ISO datetime\" (optional),     \"enabled\": bool (optional, default: true) }

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    RetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let retentionPolicy: RetentionPolicy; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceRetentionPoliciesCreate(
    retentionPolicy,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **retentionPolicy** | **RetentionPolicy**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceRetentionPoliciesDestroy**
> governanceRetentionPoliciesDestroy()

Delete retention policy

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)

const { status, data } = await apiInstance.governanceRetentionPoliciesDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|


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

# **governanceRetentionPoliciesList**
> PaginatedRetentionPolicyList governanceRetentionPoliciesList()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceRetentionPoliciesList(
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

**PaginatedRetentionPolicyList**

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

# **governanceRetentionPoliciesPartialUpdate**
> RetentionPolicy governanceRetentionPoliciesPartialUpdate()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    PatchedRetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedRetentionPolicy: PatchedRetentionPolicy; // (optional)

const { status, data } = await apiInstance.governanceRetentionPoliciesPartialUpdate(
    id,
    idempotencyKey,
    patchedRetentionPolicy
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedRetentionPolicy** | **PatchedRetentionPolicy**|  | |
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceRetentionPoliciesRetrieve**
> RetentionPolicy governanceRetentionPoliciesRetrieve()

ViewSet for retention policy management.  Tenant-scoped: users can only see/manage retention policies in their tenant.

### Example

```typescript
import {
    GovernanceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)

const { status, data } = await apiInstance.governanceRetentionPoliciesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|


### Return type

**RetentionPolicy**

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

# **governanceRetentionPoliciesUpdate**
> RetentionPolicy governanceRetentionPoliciesUpdate(retentionPolicy)

Update retention policy via service layer (Phase 12.1.2).  Service handles validation, persistence, and audit event emission.

### Example

```typescript
import {
    GovernanceApi,
    Configuration,
    RetentionPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new GovernanceApi(configuration);

let id: string; //A UUID string identifying this retention policy. (default to undefined)
let retentionPolicy: RetentionPolicy; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.governanceRetentionPoliciesUpdate(
    id,
    retentionPolicy,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **retentionPolicy** | **RetentionPolicy**|  | |
| **id** | [**string**] | A UUID string identifying this retention policy. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**RetentionPolicy**

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

