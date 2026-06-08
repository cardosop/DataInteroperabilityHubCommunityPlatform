# VirtualizationApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**virtualizationDatasetsCreate**](#virtualizationdatasetscreate) | **POST** /api/v1/virtualization/datasets/ | Create virtual dataset|
|[**virtualizationDatasetsDestroy**](#virtualizationdatasetsdestroy) | **DELETE** /api/v1/virtualization/datasets/{id}/ | Delete virtual dataset|
|[**virtualizationDatasetsList**](#virtualizationdatasetslist) | **GET** /api/v1/virtualization/datasets/ | List virtual datasets|
|[**virtualizationDatasetsPartialUpdate**](#virtualizationdatasetspartialupdate) | **PATCH** /api/v1/virtualization/datasets/{id}/ | |
|[**virtualizationDatasetsQueriesCreate**](#virtualizationdatasetsqueriescreate) | **POST** /api/v1/virtualization/datasets/{id}/queries/ | Execute query on virtual dataset|
|[**virtualizationDatasetsRetrieve**](#virtualizationdatasetsretrieve) | **GET** /api/v1/virtualization/datasets/{id}/ | Get virtual dataset details|
|[**virtualizationDatasetsUpdate**](#virtualizationdatasetsupdate) | **PUT** /api/v1/virtualization/datasets/{id}/ | Update virtual dataset|
|[**virtualizationDatasetsValidateCreate**](#virtualizationdatasetsvalidatecreate) | **POST** /api/v1/virtualization/datasets/{id}/validate/ | Validate virtual dataset|
|[**virtualizationDatasetsVersionsRetrieve**](#virtualizationdatasetsversionsretrieve) | **GET** /api/v1/virtualization/datasets/{id}/versions/ | Get virtual dataset versions|
|[**virtualizationQueriesCancelCreate**](#virtualizationqueriescancelcreate) | **POST** /api/v1/virtualization/queries/{id}/cancel/ | Cancel query execution|
|[**virtualizationQueriesList**](#virtualizationquerieslist) | **GET** /api/v1/virtualization/queries/ | |
|[**virtualizationQueriesProgressRetrieve**](#virtualizationqueriesprogressretrieve) | **GET** /api/v1/virtualization/queries/{id}/progress/ | Get query execution progress|
|[**virtualizationQueriesResultRetrieve**](#virtualizationqueriesresultretrieve) | **GET** /api/v1/virtualization/queries/{id}/result/ | Get query execution result|
|[**virtualizationQueriesRetrieve**](#virtualizationqueriesretrieve) | **GET** /api/v1/virtualization/queries/{id}/ | Get query execution details|
|[**virtualizationQueriesStreamRetrieve**](#virtualizationqueriesstreamretrieve) | **GET** /api/v1/virtualization/queries/{id}/stream/ | Stream query execution result|
|[**virtualizationTopologyList**](#virtualizationtopologylist) | **GET** /api/v1/virtualization/topology/ | Get virtualization topology|
|[**virtualizationTopologyRetrieve**](#virtualizationtopologyretrieve) | **GET** /api/v1/virtualization/topology/{id}/ | Get dataset topology|

# **virtualizationDatasetsCreate**
> VirtualDatasetCreate virtualizationDatasetsCreate(virtualDatasetCreate)

Create a new virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration,
    VirtualDatasetCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let virtualDatasetCreate: VirtualDatasetCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsCreate(
    virtualDatasetCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **virtualDatasetCreate** | **VirtualDatasetCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**VirtualDatasetCreate**

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

# **virtualizationDatasetsDestroy**
> virtualizationDatasetsDestroy()

Delete a virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


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

# **virtualizationDatasetsList**
> PaginatedVirtualDatasetList virtualizationDatasetsList()

List all virtual datasets for the authenticated user\'s tenant with filtering, pagination, and search.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let createdBy: string; //Filter by created_by user ID (alias for owner) (optional) (default to undefined)
let ordering: string; //Order by field (e.g., name, -created_at). Prefix with - for descending. (optional) (default to undefined)
let owner: string; //Filter by owner/created_by user ID (optional) (default to undefined)
let page: number; //Page number (default: 1) (optional) (default to undefined)
let pageSize: number; //Items per page (default: 50, max: 100) (optional) (default to undefined)
let queryType: string; //Filter by query type (SQL, SPARQL, FEDERATED, GRAPHQL, REST) (optional) (default to undefined)
let search: string; //Search in name, description, and query fields (optional) (default to undefined)
let status: string; //Filter by status (DRAFT, ACTIVE, INACTIVE, ARCHIVED) (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsList(
    createdBy,
    ordering,
    owner,
    page,
    pageSize,
    queryType,
    search,
    status
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **createdBy** | [**string**] | Filter by created_by user ID (alias for owner) | (optional) defaults to undefined|
| **ordering** | [**string**] | Order by field (e.g., name, -created_at). Prefix with - for descending. | (optional) defaults to undefined|
| **owner** | [**string**] | Filter by owner/created_by user ID | (optional) defaults to undefined|
| **page** | [**number**] | Page number (default: 1) | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page (default: 50, max: 100) | (optional) defaults to undefined|
| **queryType** | [**string**] | Filter by query type (SQL, SPARQL, FEDERATED, GRAPHQL, REST) | (optional) defaults to undefined|
| **search** | [**string**] | Search in name, description, and query fields | (optional) defaults to undefined|
| **status** | [**string**] | Filter by status (DRAFT, ACTIVE, INACTIVE, ARCHIVED) | (optional) defaults to undefined|


### Return type

**PaginatedVirtualDatasetList**

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

# **virtualizationDatasetsPartialUpdate**
> VirtualDatasetUpdate virtualizationDatasetsPartialUpdate()

Partially update virtual dataset.  PATCH /api/v1/virtualization/datasets/{id}/

### Example

```typescript
import {
    VirtualizationApi,
    Configuration,
    PatchedVirtualDatasetUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedVirtualDatasetUpdate: PatchedVirtualDatasetUpdate; // (optional)

const { status, data } = await apiInstance.virtualizationDatasetsPartialUpdate(
    id,
    idempotencyKey,
    patchedVirtualDatasetUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedVirtualDatasetUpdate** | **PatchedVirtualDatasetUpdate**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**VirtualDatasetUpdate**

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

# **virtualizationDatasetsQueriesCreate**
> QueryExecution virtualizationDatasetsQueriesCreate()

Execute a query on a virtual dataset. Supports synchronous and asynchronous execution modes.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration,
    QueryExecutionCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let queryExecutionCreate: QueryExecutionCreate; // (optional)

const { status, data } = await apiInstance.virtualizationDatasetsQueriesCreate(
    id,
    idempotencyKey,
    queryExecutionCreate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **queryExecutionCreate** | **QueryExecutionCreate**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**QueryExecution**

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

# **virtualizationDatasetsRetrieve**
> VirtualDataset virtualizationDatasetsRetrieve()

Get detailed information about a specific virtual dataset.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**VirtualDataset**

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

# **virtualizationDatasetsUpdate**
> VirtualDatasetUpdate virtualizationDatasetsUpdate()

Update an existing virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration,
    VirtualDatasetUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let virtualDatasetUpdate: VirtualDatasetUpdate; // (optional)

const { status, data } = await apiInstance.virtualizationDatasetsUpdate(
    id,
    idempotencyKey,
    virtualDatasetUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **virtualDatasetUpdate** | **VirtualDatasetUpdate**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**VirtualDatasetUpdate**

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

# **virtualizationDatasetsValidateCreate**
> VirtualDatasetValidationResponse virtualizationDatasetsValidateCreate()

Validate a virtual dataset structure, query syntax, schema alignment, and source compatibility.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsValidateCreate(
    id,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**VirtualDatasetValidationResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
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

# **virtualizationDatasetsVersionsRetrieve**
> VirtualDatasetVersionsResponse virtualizationDatasetsVersionsRetrieve()

Get all versions of a virtual dataset (by name) for the current tenant.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationDatasetsVersionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**VirtualDatasetVersionsResponse**

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

# **virtualizationQueriesCancelCreate**
> QueryExecutionCancelResponse virtualizationQueriesCancelCreate()

Cancel a running or pending query execution.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesCancelCreate(
    id,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**QueryExecutionCancelResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
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

# **virtualizationQueriesList**
> PaginatedQueryExecutionList virtualizationQueriesList()

ViewSet for query execution management.  Tenant-scoped: users can only see query executions for virtual datasets in their tenant. Supports RBAC (role-based) and ABAC (attribute-based) authorization. Includes rate limiting, comprehensive audit logging, and result retrieval in multiple formats.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesList(
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

**PaginatedQueryExecutionList**

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

# **virtualizationQueriesProgressRetrieve**
> QueryExecutionProgress virtualizationQueriesProgressRetrieve()

Get real-time progress information for a query execution.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesProgressRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**QueryExecutionProgress**

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

# **virtualizationQueriesResultRetrieve**
> QueryExecutionResult virtualizationQueriesResultRetrieve()

Get the result of a completed query execution, with support for pagination and multiple formats.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesResultRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**QueryExecutionResult**

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
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **virtualizationQueriesRetrieve**
> QueryExecution virtualizationQueriesRetrieve()

Get detailed information about a specific query execution.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**QueryExecution**

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

# **virtualizationQueriesStreamRetrieve**
> virtualizationQueriesStreamRetrieve()

Stream query execution result using Server-Sent Events (SSE) for large datasets.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationQueriesStreamRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


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
|**200** | SSE stream |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **virtualizationTopologyList**
> Array<VirtualizationTopology> virtualizationTopologyList()

Get complete virtualization topology including all virtual datasets, relationships, and health metrics.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let includeHealthMetrics: boolean; //Include health metrics in response (default: true) (optional) (default to undefined)

const { status, data } = await apiInstance.virtualizationTopologyList(
    includeHealthMetrics
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **includeHealthMetrics** | [**boolean**] | Include health metrics in response (default: true) | (optional) defaults to undefined|


### Return type

**Array<VirtualizationTopology>**

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

# **virtualizationTopologyRetrieve**
> DatasetTopology virtualizationTopologyRetrieve()

Get topology view for a specific virtual dataset including its relationships and health metrics.

### Example

```typescript
import {
    VirtualizationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VirtualizationApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.virtualizationTopologyRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**DatasetTopology**

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

