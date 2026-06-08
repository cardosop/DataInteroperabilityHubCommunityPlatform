# DatasetsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**datasetsCreate**](#datasetscreate) | **POST** /api/v1/datasets/ | |
|[**datasetsDestroy**](#datasetsdestroy) | **DELETE** /api/v1/datasets/{id}/ | |
|[**datasetsList**](#datasetslist) | **GET** /api/v1/datasets/ | |
|[**datasetsPartialUpdate**](#datasetspartialupdate) | **PATCH** /api/v1/datasets/{id}/ | |
|[**datasetsRetrieve**](#datasetsretrieve) | **GET** /api/v1/datasets/{id}/ | |
|[**datasetsSampleRetrieve**](#datasetssampleretrieve) | **GET** /api/v1/datasets/{id}/sample/ | |
|[**datasetsSchemaEvolutionRetrieve**](#datasetsschemaevolutionretrieve) | **GET** /api/v1/datasets/{id}/schema-evolution/ | |
|[**datasetsUpdate**](#datasetsupdate) | **PUT** /api/v1/datasets/{id}/ | |
|[**datasetsVersionsCompareRetrieve**](#datasetsversionscompareretrieve) | **GET** /api/v1/datasets/{id}/versions/compare/ | |
|[**datasetsVersionsCreate**](#datasetsversionscreate) | **POST** /api/v1/datasets/{id}/versions/ | |
|[**datasetsVersionsRetrieve**](#datasetsversionsretrieve) | **GET** /api/v1/datasets/{id}/versions/ | |

# **datasetsCreate**
> Dataset datasetsCreate(dataset)

Create a dataset from a file with schema inference.  POST /datasets Body: {     \"file_id\": \"uuid\",     \"asset_id\": \"uuid\" (optional) }

### Example

```typescript
import {
    DatasetsApi,
    Configuration,
    Dataset
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let dataset: Dataset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.datasetsCreate(
    dataset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dataset** | **Dataset**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Dataset**

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

# **datasetsDestroy**
> datasetsDestroy()

Delete a dataset. Delegates to DatasetService; business rules (validate_version_deletion) run before delete. DELETE /api/v1/datasets/{id}/

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


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

# **datasetsList**
> PaginatedDatasetList datasetsList()

List datasets (tenant-scoped) with caching.  GET /api/v1/datasets/ Query params: page, page_size, ordering, search, asset_id, dataset_format, etc.

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.datasetsList(
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

**PaginatedDatasetList**

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

# **datasetsPartialUpdate**
> Dataset datasetsPartialUpdate()

Update dataset (partial update). Delegates to DatasetService; business rules run before update. PATCH /api/v1/datasets/{id}/

### Example

```typescript
import {
    DatasetsApi,
    Configuration,
    PatchedDataset
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedDataset: PatchedDataset; // (optional)

const { status, data } = await apiInstance.datasetsPartialUpdate(
    id,
    idempotencyKey,
    patchedDataset
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedDataset** | **PatchedDataset**|  | |
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Dataset**

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

# **datasetsRetrieve**
> Dataset datasetsRetrieve()

Retrieve dataset by ID with caching.  GET /api/v1/datasets/{id}/  117B.5: Cross-tenant access allowed when consumer holds an ACTIVE entitlement for the dataset\'s asset.

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


### Return type

**Dataset**

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

# **datasetsSampleRetrieve**
> Dataset datasetsSampleRetrieve()

Return pre-computed sample data rows from the dataset.  GET /api/v1/datasets/{id}/sample/?limit=50  Sample data is extracted during dataset creation and cached on the model (sample_data_json). No S3 access needed at read time.

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsSampleRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


### Return type

**Dataset**

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

# **datasetsSchemaEvolutionRetrieve**
> Dataset datasetsSchemaEvolutionRetrieve()

Get schema evolution between dataset versions.  GET /api/v1/datasets/{id}/schema-evolution/?from_version_id={uuid}&to_version_id={uuid} If from_version_id/to_version_id not provided, compares parent version with current version.

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsSchemaEvolutionRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


### Return type

**Dataset**

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

# **datasetsUpdate**
> Dataset datasetsUpdate(dataset)

Update dataset (full or partial). Delegates to DatasetService; business rules run before update. PUT /api/v1/datasets/{id}/ accepts partial data; only provided fields are updated.

### Example

```typescript
import {
    DatasetsApi,
    Configuration,
    Dataset
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)
let dataset: Dataset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.datasetsUpdate(
    id,
    dataset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dataset** | **Dataset**|  | |
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Dataset**

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

# **datasetsVersionsCompareRetrieve**
> Dataset datasetsVersionsCompareRetrieve()

Compare two dataset versions.  GET /api/v1/datasets/{id}/versions/compare/?version1={uuid}&version2={uuid} If version1/version2 not provided, compares parent version with current version.

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsVersionsCompareRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


### Return type

**Dataset**

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

# **datasetsVersionsCreate**
> Dataset datasetsVersionsCreate(dataset)

List or create dataset versions.  GET /api/v1/datasets/{id}/versions/ - List all versions POST /api/v1/datasets/{id}/versions/ - Create a new version

### Example

```typescript
import {
    DatasetsApi,
    Configuration,
    Dataset
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)
let dataset: Dataset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.datasetsVersionsCreate(
    id,
    dataset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **dataset** | **Dataset**|  | |
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Dataset**

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

# **datasetsVersionsRetrieve**
> Dataset datasetsVersionsRetrieve()

List or create dataset versions.  GET /api/v1/datasets/{id}/versions/ - List all versions POST /api/v1/datasets/{id}/versions/ - Create a new version

### Example

```typescript
import {
    DatasetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DatasetsApi(configuration);

let id: string; //A UUID string identifying this dataset. (default to undefined)

const { status, data } = await apiInstance.datasetsVersionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dataset. | defaults to undefined|


### Return type

**Dataset**

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

