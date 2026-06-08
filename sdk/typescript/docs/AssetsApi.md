# AssetsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**assetsActivateCreate**](#assetsactivatecreate) | **POST** /api/v1/assets/{id}/activate/ | |
|[**assetsContractsCreate**](#assetscontractscreate) | **POST** /api/v1/assets/{id}/contracts/ | |
|[**assetsCreate**](#assetscreate) | **POST** /api/v1/assets/ | |
|[**assetsDataFirstCreate**](#assetsdatafirstcreate) | **POST** /api/v1/assets/data-first/ | |
|[**assetsDatasetsCreate**](#assetsdatasetscreate) | **POST** /api/v1/assets/{id}/datasets/ | |
|[**assetsDependenciesRetrieve**](#assetsdependenciesretrieve) | **GET** /api/v1/assets/{id}/dependencies/ | |
|[**assetsDestroy**](#assetsdestroy) | **DELETE** /api/v1/assets/{id}/ | |
|[**assetsEnsureE2eActivationPrerequisitesCreate**](#assetsensuree2eactivationprerequisitescreate) | **POST** /api/v1/assets/{id}/ensure-e2e-activation-prerequisites/ | |
|[**assetsExternalResourcesBatchDownloadCreate**](#assetsexternalresourcesbatchdownloadcreate) | **POST** /api/v1/assets/{id}/external-resources/batch-download/ | |
|[**assetsExternalResourcesDownloadCreate**](#assetsexternalresourcesdownloadcreate) | **POST** /api/v1/assets/{id}/external-resources/download/ | |
|[**assetsExternalResourcesRetrieve**](#assetsexternalresourcesretrieve) | **GET** /api/v1/assets/{id}/external-resources/ | |
|[**assetsHealthScoreRetrieve**](#assetshealthscoreretrieve) | **GET** /api/v1/assets/{id}/health-score/ | |
|[**assetsList**](#assetslist) | **GET** /api/v1/assets/ | |
|[**assetsPartialUpdate**](#assetspartialupdate) | **PATCH** /api/v1/assets/{id}/ | |
|[**assetsRecommendationsRetrieve**](#assetsrecommendationsretrieve) | **GET** /api/v1/assets/recommendations/ | |
|[**assetsRetireCreate**](#assetsretirecreate) | **POST** /api/v1/assets/{id}/retire/ | |
|[**assetsRetrieve**](#assetsretrieve) | **GET** /api/v1/assets/{id}/ | |
|[**assetsTrackDownloadCreate**](#assetstrackdownloadcreate) | **POST** /api/v1/assets/{id}/track-download/ | |
|[**assetsTrackViewCreate**](#assetstrackviewcreate) | **POST** /api/v1/assets/{id}/track-view/ | |
|[**assetsUpdate**](#assetsupdate) | **PUT** /api/v1/assets/{id}/ | |
|[**assetsWorkflowsStatusRetrieve**](#assetsworkflowsstatusretrieve) | **GET** /api/v1/assets/workflows/{workflow_instance_id}/status/ | |

# **assetsActivateCreate**
> Asset assetsActivateCreate(asset)

Activate an asset.  POST /assets/{id}/activate Body: {     \"version\": 1  // Required for optimistic locking }  Checks all activation requirements: - Contract: ACTIVE status, VALID/WARNING_ONLY validation, NORMALIZED_OK/WITH_WARNINGS - DQ: PASS or WARN (if dataset exists) - Compliance: PASS or WARN (if dataset exists) - Contract-only assets (no dataset) are allowed

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsActivateCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsContractsCreate**
> Asset assetsContractsCreate(asset)

Attach a contract to an asset.  POST /assets/{id}/contracts Body: {     \"contract_id\": \"uuid\" }

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsContractsCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsCreate**
> Asset assetsCreate(asset)

Create a new asset.  POST /assets Body: {     \"key\": \"my-asset\",     \"name\": \"My Asset\",     \"description\": \"Asset description\",     \"domain\": \"marketing\",     \"visibility\": \"INTERNAL\" } Requires DATA_PROVIDER or TENANT_ADMIN role. Views call AssetService only; business rules run in service.  Phase 226 G10b — HTTP ``Idempotency-Key`` is handled at the project level by ``hub.apps.api.middleware.idempotency.IdempotencyMiddleware`` for every POST/PUT/PATCH on ``/api/v1/_*``; no per-view wiring needed.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsCreate(
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsDataFirstCreate**
> Asset assetsDataFirstCreate(asset)

Create asset, dataset, and contract from uploaded file (data-first flow).  Not wrapped in ``transaction.atomic``: ``AssetCreationWorkflow.execute`` runs for a long time (storage, DQ, compliance HTTP) and manages its own atomic sections. A view-wide transaction would hold DB locks until ``statement_timeout``, breaking parallel tests and analytics/counters on the same connection.  Phase 250.1.A — fail-closed-at-intake gates (compliance + DQ) run BEFORE the Asset row is persisted; a FAIL on either gate returns 422 with audit event ``ASSET_FAIL_CLOSED_REJECTED``. A degraded compliance-service (circuit OPEN) returns 503 + ``Retry-After`` per D250.9 unless the tenant has opted into ``allow_intake_on_compliance_degraded``.  POST /api/v1/assets/data-first/ Body: {     \"file_id\": \"uuid\",     \"key\": \"my-asset\",     \"name\": \"My Asset\",     \"description\": \"Optional\",     \"domain\": \"Optional\" } Returns: { \"asset_id\": \"uuid\", \"dataset_id\": \"uuid\", \"contract_id\": \"uuid\" }

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsDataFirstCreate(
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsDatasetsCreate**
> Asset assetsDatasetsCreate(asset)

Attach a dataset to an asset.  POST /assets/{id}/datasets Body: {     \"dataset_id\": \"uuid\" }

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsDatasetsCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsDependenciesRetrieve**
> Asset assetsDependenciesRetrieve()

Get asset dependency graph.  GET /api/v1/assets/{id}/dependencies/  Query Parameters: - direction: \"upstream\", \"downstream\", or \"both\" (default: \"both\") - max_depth: Maximum traversal depth (default: 10) - format: \"json\", \"d3\", \"dot\", or \"mermaid\" (default: \"json\")

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)

const { status, data } = await apiInstance.assetsDependenciesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|


### Return type

**Asset**

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

# **assetsDestroy**
> assetsDestroy()

Delete an asset (soft delete: set status to RETIRED).  DELETE /assets/{id} Views call AssetService only; business rules (e.g. retirement requirements) run in service.

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)

const { status, data } = await apiInstance.assetsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|


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

# **assetsEnsureE2eActivationPrerequisitesCreate**
> Asset assetsEnsureE2eActivationPrerequisitesCreate(asset)

E2E-only: Create and attach an ACTIVE contract with valid validation/normalization.  POST /assets/{id}/ensure-e2e-activation-prerequisites/ Only available when RATE_LIMIT_E2E_RELAX or ENVIRONMENT=test, for E2E users. Creates a minimal ODCS contract, sets validation/normalization, attaches to asset. No mocks; real DB writes for test setup.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsEnsureE2eActivationPrerequisitesCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsExternalResourcesBatchDownloadCreate**
> Asset assetsExternalResourcesBatchDownloadCreate(asset)

Download multiple external resources in batch.  POST /api/v1/assets/{id}/external-resources/batch-download Body: {     \"resource_ids\": [\"res-1\", \"res-2\", ...] }  Downloads multiple resources in parallel and returns batch status.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsExternalResourcesBatchDownloadCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsExternalResourcesDownloadCreate**
> Asset assetsExternalResourcesDownloadCreate(asset)

Download an external resource on-demand.  Not wrapped in ``transaction.atomic``: connector download and S3 upload are slow I/O. A single long transaction caused ``statement_timeout`` and contention under parallel tests. Individual ORM steps use autocommit; ``_create_dataset_impl`` may use nested atomic blocks.  POST /api/v1/assets/{id}/external-resources/{resource_id}/download  Downloads the resource, creates File/Dataset records, and updates asset data_strategy.  POST /api/v1/assets/{id}/external-resources/download Body: {     \"resource_id\": \"res-123\" }

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsExternalResourcesDownloadCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsExternalResourcesRetrieve**
> Asset assetsExternalResourcesRetrieve()

List all external resources for an asset.  GET /api/v1/assets/{id}/external-resources/  Returns list of external resources with download status.

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)

const { status, data } = await apiInstance.assetsExternalResourcesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|


### Return type

**Asset**

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

# **assetsHealthScoreRetrieve**
> Asset assetsHealthScoreRetrieve()

Get asset health score.  GET /api/v1/assets/{id}/health-score/  Query Parameters: - recalculate: Recalculate health score (default: false) - breakdown: Include component breakdown (default: false)

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)

const { status, data } = await apiInstance.assetsHealthScoreRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|


### Return type

**Asset**

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

# **assetsList**
> PaginatedAssetList assetsList()

List assets (tenant-scoped) with caching.  GET /api/v1/assets/ Query params: domain, status, ordering, search, etc.

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsList(
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

**PaginatedAssetList**

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

# **assetsPartialUpdate**
> Asset assetsPartialUpdate()

ViewSet for asset management.  Tenant-scoped: users can only see/manage assets in their tenant.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    PatchedAsset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedAsset: PatchedAsset; // (optional)

const { status, data } = await apiInstance.assetsPartialUpdate(
    id,
    idempotencyKey,
    patchedAsset
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedAsset** | **PatchedAsset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsRecommendationsRetrieve**
> Asset assetsRecommendationsRetrieve()

Get asset recommendations.  GET /api/v1/assets/recommendations/  Query Parameters: - user_id: Optional user UUID for personalized recommendations - asset_id: Optional asset UUID for \"similar to\" recommendations - limit: Maximum number of recommendations (default: 10) - include_usage_patterns: Include usage-based recommendations (default: true) - include_lineage: Include lineage-based recommendations (default: true) - include_user_behavior: Include user behavior-based recommendations (default: true)

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

const { status, data } = await apiInstance.assetsRecommendationsRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Asset**

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

# **assetsRetireCreate**
> Asset assetsRetireCreate(asset)

Retire an active asset (soft delete).  POST /assets/{id}/retire  Only ACTIVE assets can be retired.  Attempting to retire a DRAFT or already-RETIRED asset returns 400.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsRetireCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsRetrieve**
> Asset assetsRetrieve()

Retrieve asset by ID with caching.  GET /api/v1/assets/{id}/

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)

const { status, data } = await apiInstance.assetsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|


### Return type

**Asset**

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

# **assetsTrackDownloadCreate**
> Asset assetsTrackDownloadCreate(asset)

Track an asset download.  POST /api/v1/assets/{id}/track-download/

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsTrackDownloadCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsTrackViewCreate**
> Asset assetsTrackViewCreate(asset)

Track an asset view.  POST /api/v1/assets/{id}/track-view/

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsTrackViewCreate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsUpdate**
> Asset assetsUpdate(asset)

Update an asset with optimistic locking.  PATCH /assets/{id} Header: If-Match: <asset.version> Body: {\"name\": \"Updated Name\", ...}  Rollout gate: * ``OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True``  -> missing header   is rejected (428 PRECONDITION_REQUIRED). * ``False`` (default soak window) -> missing header is accepted   for backward compatibility and emits a deprecation warning.  Views call AssetService only; business rules run in service.

### Example

```typescript
import {
    AssetsApi,
    Configuration,
    Asset
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let id: string; //A UUID string identifying this asset. (default to undefined)
let asset: Asset; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.assetsUpdate(
    id,
    asset,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **asset** | **Asset**|  | |
| **id** | [**string**] | A UUID string identifying this asset. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Asset**

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

# **assetsWorkflowsStatusRetrieve**
> Asset assetsWorkflowsStatusRetrieve()

Phase 250.6.C — asset-creation workflow status polling endpoint.  ``GET /api/v1/assets/workflows/{workflow_instance_id}/status/``  Returns the current state of an asset-creation workflow so the frontend\'s ``WorkflowProgressWidget`` can render step + progress + ETA without scraping intermediate audit events. Mirrors the existing contracts-side endpoint at ``hub/apps/contracts/views_product.py::get_product_workflow_status`` but returns asset-domain shape (``asset_id`` instead of ``odps_contract`` / ``odcs_contract``).  Tenant-scoped: the workflow MUST belong to the request\'s tenant OR the request returns 404 (existence-leak protection — same contract as the IDOR gate from Phase 250.5.C).  Response shape (matching the FE ``AssetWorkflowStatus`` type):  * ``workflow_instance_id``: str * ``status``: ``\"PENDING\"`` / ``\"RUNNING\"`` / ``\"COMPLETED\"``   / ``\"FAILED\"`` * ``progress_percentage``: 0-100 (from ``state_data``) * ``current_step_name``: str | null (from ``state_data``) * ``asset_id``: str | null (set on COMPLETED) * ``message``: str (human-readable status detail) * ``started_at``: ISO-8601 string | null (so the FE can   compute \"running for X seconds\" + apply the F2-4 polling   backoff after 30s)

### Example

```typescript
import {
    AssetsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AssetsApi(configuration);

let workflowInstanceId: string; // (default to undefined)

const { status, data } = await apiInstance.assetsWorkflowsStatusRetrieve(
    workflowInstanceId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **workflowInstanceId** | [**string**] |  | defaults to undefined|


### Return type

**Asset**

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

