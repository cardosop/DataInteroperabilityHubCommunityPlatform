# LineageApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**contractsFieldsLineageRetrieve**](#contractsfieldslineageretrieve) | **GET** /api/v1/contracts/{id}/fields/{field_name}/lineage/ | Get field-level lineage|
|[**contractsLineageContractsRetrieve**](#contractslineagecontractsretrieve) | **GET** /api/v1/contracts/{id}/lineage/contracts/ | Get contract-level lineage|
|[**contractsLineageDiffRetrieve**](#contractslineagediffretrieve) | **GET** /api/v1/contracts/{id}/lineage/diff/ | Diff lineage between two points in time|
|[**contractsLineageFullRetrieve**](#contractslineagefullretrieve) | **GET** /api/v1/contracts/{id}/lineage/full/ | Get hierarchical lineage|
|[**contractsLineageVisualizationRetrieve**](#contractslineagevisualizationretrieve) | **GET** /api/v1/contracts/{id}/lineage/visualization/ | Get lineage visualization|
|[**contractsModelsLineageRetrieve**](#contractsmodelslineageretrieve) | **GET** /api/v1/contracts/{id}/models/{model_name}/lineage/ | Get model-level lineage|
|[**lineageSubscriptionsCreate**](#lineagesubscriptionscreate) | **POST** /api/v1/lineage/subscriptions/ | |
|[**lineageSubscriptionsDestroy**](#lineagesubscriptionsdestroy) | **DELETE** /api/v1/lineage/subscriptions/{id}/ | |
|[**lineageSubscriptionsList**](#lineagesubscriptionslist) | **GET** /api/v1/lineage/subscriptions/ | |
|[**lineageSubscriptionsPartialUpdate**](#lineagesubscriptionspartialupdate) | **PATCH** /api/v1/lineage/subscriptions/{id}/ | |
|[**lineageSubscriptionsRetrieve**](#lineagesubscriptionsretrieve) | **GET** /api/v1/lineage/subscriptions/{id}/ | |
|[**metricsObservabilityLineageRetrieve**](#metricsobservabilitylineageretrieve) | **GET** /metrics/observability/lineage/ | Get lineage|
|[**observabilityLineageRetrieve**](#observabilitylineageretrieve) | **GET** /api/v1/observability/lineage/ | Get lineage|

# **contractsFieldsLineageRetrieve**
> FieldLineageResponse contractsFieldsLineageRetrieve()

         Get lineage for a specific field in a contract.          Returns lineage information including field references and entries.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let fieldName: string; // (default to undefined)
let id: string; //A UUID string identifying this contract. (default to undefined)
let modelName: string; //Model name (optional) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsFieldsLineageRetrieve(
    fieldName,
    id,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **fieldName** | [**string**] |  | defaults to undefined|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **modelName** | [**string**] | Model name (optional) | (optional) defaults to undefined|


### Return type

**FieldLineageResponse**

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

# **contractsLineageContractsRetrieve**
> ContractLineageResponse contractsLineageContractsRetrieve()

         Get contract-level lineage including contract references.          Returns contract references and lineage entries.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsLineageContractsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


### Return type

**ContractLineageResponse**

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

# **contractsLineageDiffRetrieve**
> contractsLineageDiffRetrieve()

Compute the set-arithmetic delta between the contract\'s lineage edge state at two anchors. Anchors accept ISO-8601 (`from=2026-04-30T00:00:00Z`) or version-int (`from_version=3`); ``to`` defaults to NOW() when omitted. Returns ``{added, removed, changed, unchanged, summary}`` with deterministic ordering. Pure function behind the response — driven by [lineage_diff.py](../lineage_diff.py).

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let from: string; //ISO-8601 timestamp for the older anchor. (optional) (default to undefined)
let fromVersion: number; //Contract version int → resolves to its created_at. (optional) (default to undefined)
let to: string; //ISO-8601 timestamp for the newer anchor; defaults to NOW(). (optional) (default to undefined)
let toVersion: number; //Contract version int → resolves to its created_at. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageDiffRetrieve(
    id,
    from,
    fromVersion,
    to,
    toVersion
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **from** | [**string**] | ISO-8601 timestamp for the older anchor. | (optional) defaults to undefined|
| **fromVersion** | [**number**] | Contract version int → resolves to its created_at. | (optional) defaults to undefined|
| **to** | [**string**] | ISO-8601 timestamp for the newer anchor; defaults to NOW(). | (optional) defaults to undefined|
| **toVersion** | [**number**] | Contract version int → resolves to its created_at. | (optional) defaults to undefined|


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
|**200** | Lineage diff body. |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLineageFullRetrieve**
> HierarchicalLineageResponse contractsLineageFullRetrieve()

         Get complete hierarchical lineage (contract, model, and field levels).          Returns full lineage traversal with all levels.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let maxContractDepth: number; //Maximum contract depth for traversal (default: 10) (optional) (default to undefined)
let maxFieldDepth: number; //Maximum field depth for traversal (default: 10) (optional) (default to undefined)
let maxModelDepth: number; //Maximum model depth for traversal (default: 10) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageFullRetrieve(
    id,
    maxContractDepth,
    maxFieldDepth,
    maxModelDepth
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **maxContractDepth** | [**number**] | Maximum contract depth for traversal (default: 10) | (optional) defaults to undefined|
| **maxFieldDepth** | [**number**] | Maximum field depth for traversal (default: 10) | (optional) defaults to undefined|
| **maxModelDepth** | [**number**] | Maximum model depth for traversal (default: 10) | (optional) defaults to undefined|


### Return type

**HierarchicalLineageResponse**

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

# **contractsLineageVisualizationRetrieve**
> contractsLineageVisualizationRetrieve()

Get lineage graph in various visualization formats.  Supports JSON (D3.js), DOT (Graphviz), and Mermaid formats.  Phase 228 F5 (228.F5.2 / REQ-LIN-F5-001) — point-in-time knobs `?as_of=<ISO8601>` (direct historical cutoff) and `?version=<int>` (resolves to the contract\'s `created_at` for that version). Both knobs echo back in the response as `as_of` + `as_of_source ∈ {as_of, version}` so the UI can render the resolved cutoff without re-parsing query params. When both are supplied, `as_of` wins.

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let asOf: string; //ISO-8601 timestamp; renders the lineage at that historical cutoff. Mutually-permissive with `?version=`; when both provided, `as_of` wins. (optional) (default to undefined)
let format: string; //Visualization format: json, dot, or mermaid (default: json) (optional) (default to undefined)
let includeFields: boolean; //Phase 228.F2 (228.F2.3) — augment JSON visualization with field-level nodes derived from open LineageEdge rows. (optional) (default to undefined)
let maxDepth: number; //Maximum traversal depth (default: 10) (optional) (default to undefined)
let version: number; //Contract version int; resolves to that contract\'s `created_at` and uses it as the `as_of` cutoff. 404 when the version doesn\'t exist for the tenant. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageVisualizationRetrieve(
    id,
    asOf,
    format,
    includeFields,
    maxDepth,
    version
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **asOf** | [**string**] | ISO-8601 timestamp; renders the lineage at that historical cutoff. Mutually-permissive with &#x60;?version&#x3D;&#x60;; when both provided, &#x60;as_of&#x60; wins. | (optional) defaults to undefined|
| **format** | [**string**] | Visualization format: json, dot, or mermaid (default: json) | (optional) defaults to undefined|
| **includeFields** | [**boolean**] | Phase 228.F2 (228.F2.3) — augment JSON visualization with field-level nodes derived from open LineageEdge rows. | (optional) defaults to undefined|
| **maxDepth** | [**number**] | Maximum traversal depth (default: 10) | (optional) defaults to undefined|
| **version** | [**number**] | Contract version int; resolves to that contract\&#39;s &#x60;created_at&#x60; and uses it as the &#x60;as_of&#x60; cutoff. 404 when the version doesn\&#39;t exist for the tenant. | (optional) defaults to undefined|


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
|**200** | Lineage graph in requested format |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsModelsLineageRetrieve**
> ModelLineageResponse contractsModelsLineageRetrieve()

         Get lineage for a specific model in a contract.          Returns lineage information including model references and entries.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let modelName: string; //Model name (default to undefined)

const { status, data } = await apiInstance.contractsModelsLineageRetrieve(
    id,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **modelName** | [**string**] | Model name | defaults to undefined|


### Return type

**ModelLineageResponse**

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

# **lineageSubscriptionsCreate**
> LineageSubscription lineageSubscriptionsCreate()

REQ-LIN-F3-003 ViewSet.

### Example

```typescript
import {
    LineageApi,
    Configuration,
    LineageSubscription
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let lineageSubscription: LineageSubscription; // (optional)

const { status, data } = await apiInstance.lineageSubscriptionsCreate(
    idempotencyKey,
    lineageSubscription
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **lineageSubscription** | **LineageSubscription**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**LineageSubscription**

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

# **lineageSubscriptionsDestroy**
> lineageSubscriptionsDestroy()

REQ-LIN-F3-003 ViewSet.

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.lineageSubscriptionsDestroy(
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

# **lineageSubscriptionsList**
> PaginatedLineageSubscriptionList lineageSubscriptionsList()

REQ-LIN-F3-003 ViewSet.

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let cursor: string; //The pagination cursor value. (optional) (default to undefined)
let limit: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.lineageSubscriptionsList(
    cursor,
    limit
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **cursor** | [**string**] | The pagination cursor value. | (optional) defaults to undefined|
| **limit** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedLineageSubscriptionList**

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

# **lineageSubscriptionsPartialUpdate**
> LineageSubscriptionPatch lineageSubscriptionsPartialUpdate()

REQ-LIN-F3-003 ViewSet.

### Example

```typescript
import {
    LineageApi,
    Configuration,
    PatchedLineageSubscriptionPatch
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedLineageSubscriptionPatch: PatchedLineageSubscriptionPatch; // (optional)

const { status, data } = await apiInstance.lineageSubscriptionsPartialUpdate(
    id,
    idempotencyKey,
    patchedLineageSubscriptionPatch
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedLineageSubscriptionPatch** | **PatchedLineageSubscriptionPatch**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**LineageSubscriptionPatch**

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

# **lineageSubscriptionsRetrieve**
> LineageSubscription lineageSubscriptionsRetrieve()

REQ-LIN-F3-003 ViewSet.

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.lineageSubscriptionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**LineageSubscription**

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

# **metricsObservabilityLineageRetrieve**
> metricsObservabilityLineageRetrieve()

         Get contract-level lineage (delegates to contract lineage service).          **Query Parameters:**         - `contract_id` (required): Contract UUID to retrieve lineage for.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let contractId: string; //Contract UUID to get lineage for (default to undefined)

const { status, data } = await apiInstance.metricsObservabilityLineageRetrieve(
    contractId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractId** | [**string**] | Contract UUID to get lineage for | defaults to undefined|


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
|**200** | Lineage data with contracts and entries |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **observabilityLineageRetrieve**
> observabilityLineageRetrieve()

         Get contract-level lineage (delegates to contract lineage service).          **Query Parameters:**         - `contract_id` (required): Contract UUID to retrieve lineage for.         

### Example

```typescript
import {
    LineageApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new LineageApi(configuration);

let contractId: string; //Contract UUID to get lineage for (default to undefined)

const { status, data } = await apiInstance.observabilityLineageRetrieve(
    contractId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractId** | [**string**] | Contract UUID to get lineage for | defaults to undefined|


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
|**200** | Lineage data with contracts and entries |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

