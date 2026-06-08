# DataMeshApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**meshDomainsAnalyticsRetrieve**](#meshdomainsanalyticsretrieve) | **GET** /api/v1/mesh/domains/{id}/analytics/ | Get domain analytics|
|[**meshDomainsAssetsCreate**](#meshdomainsassetscreate) | **POST** /api/v1/mesh/domains/{id}/assets/ | Add asset to domain|
|[**meshDomainsBoundariesPartialUpdate**](#meshdomainsboundariespartialupdate) | **PATCH** /api/v1/mesh/domains/{id}/boundaries/ | Update domain boundaries|
|[**meshDomainsComplianceCheckCreate**](#meshdomainscompliancecheckcreate) | **POST** /api/v1/mesh/domains/{id}/compliance/check/ | Check domain compliance|
|[**meshDomainsComplianceReportsList**](#meshdomainscompliancereportslist) | **GET** /api/v1/mesh/domains/{id}/compliance/reports/ | List compliance reports|
|[**meshDomainsComplianceReportsRetrieve**](#meshdomainscompliancereportsretrieve) | **GET** /api/v1/mesh/domains/{id}/compliance/reports/{report_id}/ | Get compliance report|
|[**meshDomainsCreate**](#meshdomainscreate) | **POST** /api/v1/mesh/domains/ | Create data mesh domain|
|[**meshDomainsDestroy**](#meshdomainsdestroy) | **DELETE** /api/v1/mesh/domains/{id}/ | Delete data mesh domain|
|[**meshDomainsHealthRetrieve**](#meshdomainshealthretrieve) | **GET** /api/v1/mesh/domains/{id}/health/ | Get domain health|
|[**meshDomainsInfrastructureCreate**](#meshdomainsinfrastructurecreate) | **POST** /api/v1/mesh/domains/{id}/infrastructure/ | Get domain infrastructure|
|[**meshDomainsInfrastructureRetrieve**](#meshdomainsinfrastructureretrieve) | **GET** /api/v1/mesh/domains/{id}/infrastructure/ | Get domain infrastructure|
|[**meshDomainsList**](#meshdomainslist) | **GET** /api/v1/mesh/domains/ | List data mesh domains|
|[**meshDomainsOwnershipPartialUpdate**](#meshdomainsownershippartialupdate) | **PATCH** /api/v1/mesh/domains/{id}/ownership/ | Assign domain ownership|
|[**meshDomainsPoliciesApplyCreate**](#meshdomainspoliciesapplycreate) | **POST** /api/v1/mesh/domains/{id}/policies/apply/ | Apply policy to domain|
|[**meshDomainsPoliciesDestroy**](#meshdomainspoliciesdestroy) | **DELETE** /api/v1/mesh/domains/{id}/policies/{policy_id}/ | Remove policy from domain|
|[**meshDomainsPoliciesList**](#meshdomainspolicieslist) | **GET** /api/v1/mesh/domains/{id}/policies/ | List applied policies|
|[**meshDomainsRetrieve**](#meshdomainsretrieve) | **GET** /api/v1/mesh/domains/{id}/ | Get domain details|
|[**meshDomainsSelfServeCreate**](#meshdomainsselfservecreate) | **POST** /api/v1/mesh/domains/{id}/self-serve/ | Get domain self-serve configuration|
|[**meshDomainsSelfServeRetrieve**](#meshdomainsselfserveretrieve) | **GET** /api/v1/mesh/domains/{id}/self-serve/ | Get domain self-serve configuration|
|[**meshDomainsTransferOwnershipCreate**](#meshdomainstransferownershipcreate) | **POST** /api/v1/mesh/domains/{id}/transfer-ownership/ | Transfer domain ownership|
|[**meshDomainsUpdate**](#meshdomainsupdate) | **PUT** /api/v1/mesh/domains/{id}/ | Update data mesh domain|

# **meshDomainsAnalyticsRetrieve**
> DomainAnalytics meshDomainsAnalyticsRetrieve()

Get analytics and statistics for a data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsAnalyticsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


### Return type

**DomainAnalytics**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsAssetsCreate**
> meshDomainsAssetsCreate(domainAssetRequest)

Associate an asset with a domain (set asset.domain).

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    DomainAssetRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domainAssetRequest: DomainAssetRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsAssetsCreate(
    id,
    domainAssetRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **domainAssetRequest** | **DomainAssetRequest**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** | Asset associated |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsBoundariesPartialUpdate**
> Domain meshDomainsBoundariesPartialUpdate()

Update boundaries (data products, governance rules) for a domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    PatchedBoundariesRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedBoundariesRequest: PatchedBoundariesRequest; // (optional)

const { status, data } = await apiInstance.meshDomainsBoundariesPartialUpdate(
    id,
    idempotencyKey,
    patchedBoundariesRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedBoundariesRequest** | **PatchedBoundariesRequest**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Domain**

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
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsComplianceCheckCreate**
> ComplianceReport meshDomainsComplianceCheckCreate()

Check compliance status for a data mesh domain and generate a compliance report.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    CheckCompliance
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let checkCompliance: CheckCompliance; // (optional)

const { status, data } = await apiInstance.meshDomainsComplianceCheckCreate(
    id,
    idempotencyKey,
    checkCompliance
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **checkCompliance** | **CheckCompliance**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ComplianceReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsComplianceReportsList**
> PaginatedComplianceReportList meshDomainsComplianceReportsList()

List all compliance reports for a data mesh domain with filtering and pagination.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsComplianceReportsList(
    id,
    ordering,
    page,
    pageSize,
    search
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **ordering** | [**string**] | Which field to use when ordering the results. | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **search** | [**string**] | A search term. | (optional) defaults to undefined|


### Return type

**PaginatedComplianceReportList**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsComplianceReportsRetrieve**
> ComplianceReport meshDomainsComplianceReportsRetrieve()

Get detailed information about a specific compliance report for a data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let reportId: string; // (default to undefined)

const { status, data } = await apiInstance.meshDomainsComplianceReportsRetrieve(
    id,
    reportId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **reportId** | [**string**] |  | defaults to undefined|


### Return type

**ComplianceReport**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsCreate**
> Domain meshDomainsCreate(domain)

Create a new data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsCreate(
    domain,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **domain** | **Domain**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Domain**

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

# **meshDomainsDestroy**
> meshDomainsDestroy()

Delete a data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


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

# **meshDomainsHealthRetrieve**
> MeshHealth meshDomainsHealthRetrieve()

Get health metrics for a specific domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsHealthRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


### Return type

**MeshHealth**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsInfrastructureCreate**
> meshDomainsInfrastructureCreate(domain)

Get infrastructure/capabilities for a domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsInfrastructureCreate(
    id,
    domain,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **domain** | **Domain**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Domain infrastructure |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsInfrastructureRetrieve**
> meshDomainsInfrastructureRetrieve()

Get infrastructure/capabilities for a domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsInfrastructureRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


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
|**200** | Domain infrastructure |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsList**
> PaginatedDomainList meshDomainsList()

List all data mesh domains for the authenticated user\'s tenant with filtering and pagination.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsList(
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

**PaginatedDomainList**

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

# **meshDomainsOwnershipPartialUpdate**
> Domain meshDomainsOwnershipPartialUpdate()

Assign or update domain owner (PATCH alias for transfer-ownership).

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    PatchedOwnershipRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedOwnershipRequest: PatchedOwnershipRequest; // (optional)

const { status, data } = await apiInstance.meshDomainsOwnershipPartialUpdate(
    id,
    idempotencyKey,
    patchedOwnershipRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedOwnershipRequest** | **PatchedOwnershipRequest**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Domain**

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
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsPoliciesApplyCreate**
> PolicyApplication meshDomainsPoliciesApplyCreate(applyPolicy)

Apply an access policy to a data mesh domain with optional overrides.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    ApplyPolicy
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let applyPolicy: ApplyPolicy; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsPoliciesApplyCreate(
    id,
    applyPolicy,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **applyPolicy** | **ApplyPolicy**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**PolicyApplication**

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
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsPoliciesDestroy**
> PolicyApplication meshDomainsPoliciesDestroy()

Remove (revoke) a policy application from a data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let policyId: string; // (default to undefined)

const { status, data } = await apiInstance.meshDomainsPoliciesDestroy(
    id,
    policyId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **policyId** | [**string**] |  | defaults to undefined|


### Return type

**PolicyApplication**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsPoliciesList**
> PaginatedPolicyApplicationList meshDomainsPoliciesList()

List all policies applied to a data mesh domain with filtering and pagination.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsPoliciesList(
    id,
    ordering,
    page,
    pageSize,
    search
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **ordering** | [**string**] | Which field to use when ordering the results. | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **search** | [**string**] | A search term. | (optional) defaults to undefined|


### Return type

**PaginatedPolicyApplicationList**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsRetrieve**
> Domain meshDomainsRetrieve()

Get detailed information about a specific data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


### Return type

**Domain**

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

# **meshDomainsSelfServeCreate**
> meshDomainsSelfServeCreate(domain)

Get self-serve capabilities and configuration for a domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsSelfServeCreate(
    id,
    domain,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **domain** | **Domain**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Self-serve config |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsSelfServeRetrieve**
> meshDomainsSelfServeRetrieve()

Get self-serve capabilities and configuration for a domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsSelfServeRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|


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
|**200** | Self-serve config |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsTransferOwnershipCreate**
> Domain meshDomainsTransferOwnershipCreate()

Transfer ownership of a data mesh domain to another user.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    TransferOwnership
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let transferOwnership: TransferOwnership; // (optional)

const { status, data } = await apiInstance.meshDomainsTransferOwnershipCreate(
    id,
    idempotencyKey,
    transferOwnership
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **transferOwnership** | **TransferOwnership**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Domain**

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
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshDomainsUpdate**
> Domain meshDomainsUpdate(domain)

Update an existing data mesh domain.

### Example

```typescript
import {
    DataMeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsUpdate(
    id,
    domain,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **domain** | **Domain**|  | |
| **id** | [**string**] | A UUID string identifying this data mesh domain. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Domain**

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

