# DeveloperPortalApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**baasApiKeysCreate**](#baasapikeyscreate) | **POST** /api/v1/baas/api-keys/ | Create API key|
|[**baasApiKeysDestroy**](#baasapikeysdestroy) | **DELETE** /api/v1/baas/api-keys/{id}/ | Revoke API key|
|[**baasApiKeysList**](#baasapikeyslist) | **GET** /api/v1/baas/api-keys/ | List API keys|
|[**baasApiKeysPartialUpdate**](#baasapikeyspartialupdate) | **PATCH** /api/v1/baas/api-keys/{id}/ | Partially update API key|
|[**baasApiKeysQuotaRetrieve**](#baasapikeysquotaretrieve) | **GET** /api/v1/baas/api-keys/{id}/quota/ | Get quota information|
|[**baasApiKeysRetrieve**](#baasapikeysretrieve) | **GET** /api/v1/baas/api-keys/{id}/ | Get API key|
|[**baasApiKeysUpdate**](#baasapikeysupdate) | **PUT** /api/v1/baas/api-keys/{id}/ | Update API key|
|[**baasDocsList**](#baasdocslist) | **GET** /api/v1/baas/docs/ | Get API documentation|
|[**baasDocsOpenapiJsonRetrieve**](#baasdocsopenapijsonretrieve) | **GET** /api/v1/baas/docs/openapi.json/ | Get OpenAPI schema|
|[**baasDocsSdksRetrieve**](#baasdocssdksretrieve) | **GET** /api/v1/baas/docs/sdks/ | Get SDK download links|
|[**baasDocsSdksRetrieve2**](#baasdocssdksretrieve2) | **GET** /api/v1/baas/docs/sdks/{language}/ | Generate SDK|

# **baasApiKeysCreate**
> BaaSAPIKeyResponse baasApiKeysCreate(baaSAPIKeyCreate)

Create a new API key. Returns the plaintext key (shown only once).

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration,
    BaaSAPIKeyCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let baaSAPIKeyCreate: BaaSAPIKeyCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.baasApiKeysCreate(
    baaSAPIKeyCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **baaSAPIKeyCreate** | **BaaSAPIKeyCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**BaaSAPIKeyResponse**

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

# **baasApiKeysDestroy**
> baasApiKeysDestroy()

Revoke an API key (soft delete by setting revoked_at).

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let id: string; //A UUID string identifying this api key. (default to undefined)

const { status, data } = await apiInstance.baasApiKeysDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this api key. | defaults to undefined|


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
|**204** | API key revoked |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasApiKeysList**
> PaginatedBaaSAPIKeyList baasApiKeysList()

List all API keys for the authenticated user\'s tenant.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.baasApiKeysList(
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

**PaginatedBaaSAPIKeyList**

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

# **baasApiKeysPartialUpdate**
> BaaSAPIKey baasApiKeysPartialUpdate()

Partially update an API key (name, expires_at).

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration,
    PatchedBaaSAPIKey
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let id: string; //A UUID string identifying this api key. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedBaaSAPIKey: PatchedBaaSAPIKey; // (optional)

const { status, data } = await apiInstance.baasApiKeysPartialUpdate(
    id,
    idempotencyKey,
    patchedBaaSAPIKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedBaaSAPIKey** | **PatchedBaaSAPIKey**|  | |
| **id** | [**string**] | A UUID string identifying this api key. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**BaaSAPIKey**

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

# **baasApiKeysQuotaRetrieve**
> QuotaInfo baasApiKeysQuotaRetrieve()

Get quota information for an API key.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let id: string; //A UUID string identifying this api key. (default to undefined)

const { status, data } = await apiInstance.baasApiKeysQuotaRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this api key. | defaults to undefined|


### Return type

**QuotaInfo**

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

# **baasApiKeysRetrieve**
> BaaSAPIKey baasApiKeysRetrieve()

Get details of a specific API key.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let id: string; //A UUID string identifying this api key. (default to undefined)

const { status, data } = await apiInstance.baasApiKeysRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this api key. | defaults to undefined|


### Return type

**BaaSAPIKey**

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

# **baasApiKeysUpdate**
> BaaSAPIKey baasApiKeysUpdate(baaSAPIKey)

Update an API key (name, expires_at). Cannot change tier or key itself.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration,
    BaaSAPIKey
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let id: string; //A UUID string identifying this api key. (default to undefined)
let baaSAPIKey: BaaSAPIKey; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.baasApiKeysUpdate(
    id,
    baaSAPIKey,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **baaSAPIKey** | **BaaSAPIKey**|  | |
| **id** | [**string**] | A UUID string identifying this api key. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**BaaSAPIKey**

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

# **baasDocsList**
> baasDocsList()

Get API documentation overview with links to OpenAPI schema and SDKs.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

const { status, data } = await apiInstance.baasDocsList();
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
|**200** | API documentation |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasDocsOpenapiJsonRetrieve**
> baasDocsOpenapiJsonRetrieve()

Get OpenAPI 3.0 schema in JSON format.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

const { status, data } = await apiInstance.baasDocsOpenapiJsonRetrieve();
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
|**200** | OpenAPI schema |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasDocsSdksRetrieve**
> baasDocsSdksRetrieve()

Get download links for SDKs in various languages.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

const { status, data } = await apiInstance.baasDocsSdksRetrieve();
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
|**200** | SDK download links |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **baasDocsSdksRetrieve2**
> baasDocsSdksRetrieve2()

Generate SDK code for the specified language.

### Example

```typescript
import {
    DeveloperPortalApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DeveloperPortalApi(configuration);

let language: string; // (default to undefined)

const { status, data } = await apiInstance.baasDocsSdksRetrieve2(
    language
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **language** | [**string**] |  | defaults to undefined|


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
|**200** | Generated SDK code |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

