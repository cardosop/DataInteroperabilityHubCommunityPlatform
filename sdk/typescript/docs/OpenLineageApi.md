# OpenLineageApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**lineageOpenlineageEventsCreate**](#lineageopenlineageeventscreate) | **POST** /api/v1/lineage/openlineage/events/ | |
|[**lineageOpenlineageKeysCreate**](#lineageopenlineagekeyscreate) | **POST** /api/v1/lineage/openlineage/keys/ | |
|[**lineageOpenlineageKeysDestroy**](#lineageopenlineagekeysdestroy) | **DELETE** /api/v1/lineage/openlineage/keys/{id}/ | |
|[**lineageOpenlineageKeysRetrieve**](#lineageopenlineagekeysretrieve) | **GET** /api/v1/lineage/openlineage/keys/ | |

# **lineageOpenlineageEventsCreate**
> lineageOpenlineageEventsCreate()

Inbound OpenLineage RunEvent endpoint. Auth: ``X-Meshant-OpenLineage-Key: msh_ol_<plaintext>`` + ``X-Meshant-Signature: sha256=<hmac>``. Returns 202 on accept (with ``edges_created``), 400 on schema validation, 401 on auth, 413 if body > 1 MB or > 100 datasets, 404 when the ``lineage.openlineage_export`` capability is OFF. Idempotent on ``run.runId``: a duplicate POST returns the original 202 payload unchanged.

### Example

```typescript
import {
    OpenLineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new OpenLineageApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.lineageOpenlineageEventsCreate(
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


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
|**202** | Event accepted (or duplicate). |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**413** | Payload too large. |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **lineageOpenlineageKeysCreate**
> lineageOpenlineageKeysCreate()

List / create OpenLineage ingest API keys for the caller\'s tenant. TENANT_ADMIN-only. The ``key_hash`` and plaintext are NEVER returned in list responses. The plaintext is returned ONCE in the create response.

### Example

```typescript
import {
    OpenLineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new OpenLineageApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.lineageOpenlineageKeysCreate(
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


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
|**200** | No response body |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **lineageOpenlineageKeysDestroy**
> lineageOpenlineageKeysDestroy()

Revoke an OpenLineage ingest API key. TENANT_ADMIN-only. Sets ``revoked_at`` so the next inbound request fails auth immediately. The row is retained for audit; use the rotate command (228.F4.11) for the 7-day grace flow.

### Example

```typescript
import {
    OpenLineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new OpenLineageApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.lineageOpenlineageKeysDestroy(
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

# **lineageOpenlineageKeysRetrieve**
> lineageOpenlineageKeysRetrieve()

List / create OpenLineage ingest API keys for the caller\'s tenant. TENANT_ADMIN-only. The ``key_hash`` and plaintext are NEVER returned in list responses. The plaintext is returned ONCE in the create response.

### Example

```typescript
import {
    OpenLineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new OpenLineageApi(configuration);

const { status, data } = await apiInstance.lineageOpenlineageKeysRetrieve();
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

