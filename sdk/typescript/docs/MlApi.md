# MlApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**mlInferenceAbTestsCreate**](#mlinferenceabtestscreate) | **POST** /api/v1/ml/inference/ab-tests/ | |
|[**mlInferenceAbTestsDestroy**](#mlinferenceabtestsdestroy) | **DELETE** /api/v1/ml/inference/ab-tests/{id}/ | |
|[**mlInferenceAbTestsList**](#mlinferenceabtestslist) | **GET** /api/v1/ml/inference/ab-tests/ | |
|[**mlInferenceAbTestsPartialUpdate**](#mlinferenceabtestspartialupdate) | **PATCH** /api/v1/ml/inference/ab-tests/{id}/ | |
|[**mlInferenceAbTestsRetrieve**](#mlinferenceabtestsretrieve) | **GET** /api/v1/ml/inference/ab-tests/{id}/ | |
|[**mlInferenceAbTestsUpdate**](#mlinferenceabtestsupdate) | **PUT** /api/v1/ml/inference/ab-tests/{id}/ | |
|[**mlInferenceDeploymentsCreate**](#mlinferencedeploymentscreate) | **POST** /api/v1/ml/inference/deployments/ | |
|[**mlInferenceDeploymentsDestroy**](#mlinferencedeploymentsdestroy) | **DELETE** /api/v1/ml/inference/deployments/{id}/ | |
|[**mlInferenceDeploymentsMetricsRetrieve**](#mlinferencedeploymentsmetricsretrieve) | **GET** /api/v1/ml/inference/deployments/{id}/metrics/ | |
|[**mlInferenceDeploymentsPredictCreate**](#mlinferencedeploymentspredictcreate) | **POST** /api/v1/ml/inference/deployments/predict/ | |
|[**mlInferenceDeploymentsRetrieve**](#mlinferencedeploymentsretrieve) | **GET** /api/v1/ml/inference/deployments/ | |
|[**mlInferenceDeploymentsRetrieve2**](#mlinferencedeploymentsretrieve2) | **GET** /api/v1/ml/inference/deployments/{id}/ | |
|[**mlModelsCreate**](#mlmodelscreate) | **POST** /api/v1/ml/models/ | |
|[**mlModelsDatasetsRetrieve**](#mlmodelsdatasetsretrieve) | **GET** /api/v1/ml/models/{id}/datasets/ | |
|[**mlModelsDestroy**](#mlmodelsdestroy) | **DELETE** /api/v1/ml/models/{id}/ | |
|[**mlModelsLinkDatasetCreate**](#mlmodelslinkdatasetcreate) | **POST** /api/v1/ml/models/{id}/link-dataset/ | |
|[**mlModelsList**](#mlmodelslist) | **GET** /api/v1/ml/models/ | |
|[**mlModelsPartialUpdate**](#mlmodelspartialupdate) | **PATCH** /api/v1/ml/models/{id}/ | |
|[**mlModelsRetrieve**](#mlmodelsretrieve) | **GET** /api/v1/ml/models/{id}/ | |
|[**mlModelsSyncFromOdhCreate**](#mlmodelssyncfromodhcreate) | **POST** /api/v1/ml/models/{id}/sync-from-odh/ | |
|[**mlModelsUpdate**](#mlmodelsupdate) | **PUT** /api/v1/ml/models/{id}/ | |
|[**mlTrainingJobsCancelCreate**](#mltrainingjobscancelcreate) | **POST** /api/v1/ml/training/jobs/{id}/cancel/ | |
|[**mlTrainingJobsCreate**](#mltrainingjobscreate) | **POST** /api/v1/ml/training/jobs/ | |
|[**mlTrainingJobsLogsRetrieve**](#mltrainingjobslogsretrieve) | **GET** /api/v1/ml/training/jobs/{id}/logs/ | |
|[**mlTrainingJobsRetrieve**](#mltrainingjobsretrieve) | **GET** /api/v1/ml/training/jobs/ | |
|[**mlTrainingJobsRetrieve2**](#mltrainingjobsretrieve2) | **GET** /api/v1/ml/training/jobs/{id}/ | |

# **mlInferenceAbTestsCreate**
> ABTest mlInferenceAbTestsCreate(aBTest)

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration,
    ABTest
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let aBTest: ABTest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlInferenceAbTestsCreate(
    aBTest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **aBTest** | **ABTest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ABTest**

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

# **mlInferenceAbTestsDestroy**
> mlInferenceAbTestsDestroy()

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ab test. (default to undefined)

const { status, data } = await apiInstance.mlInferenceAbTestsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this ab test. | defaults to undefined|


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

# **mlInferenceAbTestsList**
> PaginatedABTestList mlInferenceAbTestsList()

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.mlInferenceAbTestsList(
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

**PaginatedABTestList**

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

# **mlInferenceAbTestsPartialUpdate**
> ABTest mlInferenceAbTestsPartialUpdate()

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration,
    PatchedABTest
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ab test. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedABTest: PatchedABTest; // (optional)

const { status, data } = await apiInstance.mlInferenceAbTestsPartialUpdate(
    id,
    idempotencyKey,
    patchedABTest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedABTest** | **PatchedABTest**|  | |
| **id** | [**string**] | A UUID string identifying this ab test. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ABTest**

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

# **mlInferenceAbTestsRetrieve**
> ABTest mlInferenceAbTestsRetrieve()

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ab test. (default to undefined)

const { status, data } = await apiInstance.mlInferenceAbTestsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this ab test. | defaults to undefined|


### Return type

**ABTest**

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

# **mlInferenceAbTestsUpdate**
> ABTest mlInferenceAbTestsUpdate(aBTest)

ViewSet for A/B test management.  Routes inference traffic between a base model and a variant model according to a configurable traffic split.  Endpoints: - POST   /api/v1/ml/inference/ab-tests/        — create A/B test - GET    /api/v1/ml/inference/ab-tests/        — list A/B tests - GET    /api/v1/ml/inference/ab-tests/{id}/   — get A/B test details - DELETE /api/v1/ml/inference/ab-tests/{id}/   — cancel A/B test

### Example

```typescript
import {
    MlApi,
    Configuration,
    ABTest
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ab test. (default to undefined)
let aBTest: ABTest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlInferenceAbTestsUpdate(
    id,
    aBTest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **aBTest** | **ABTest**|  | |
| **id** | [**string**] | A UUID string identifying this ab test. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ABTest**

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

# **mlInferenceDeploymentsCreate**
> mlInferenceDeploymentsCreate()

Deploy a model for inference.  POST /api/v1/ml/inference/deployments/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlInferenceDeploymentsCreate(
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
|**201** | No response body |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **mlInferenceDeploymentsDestroy**
> mlInferenceDeploymentsDestroy()

Undeploy a model.  DELETE /api/v1/ml/inference/deployments/{id}/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.mlInferenceDeploymentsDestroy(
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

# **mlInferenceDeploymentsMetricsRetrieve**
> mlInferenceDeploymentsMetricsRetrieve()

Get inference metrics for a deployment.  GET /api/v1/ml/inference/deployments/{id}/metrics/ Query parameters: - start_time: Start time for metrics (ISO 8601 format) - end_time: End time for metrics (ISO 8601 format)

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.mlInferenceDeploymentsMetricsRetrieve(
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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **mlInferenceDeploymentsPredictCreate**
> mlInferenceDeploymentsPredictCreate()

Run inference prediction.  POST /api/v1/ml/inference/deployments/predict/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlInferenceDeploymentsPredictCreate(
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

# **mlInferenceDeploymentsRetrieve**
> mlInferenceDeploymentsRetrieve()

List inference deployments with optional filters.  GET /api/v1/ml/inference/deployments/ Query parameters: - model_id: Filter by model ID - status: Filter by deployment status - limit: Pagination limit - offset: Pagination offset

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

const { status, data } = await apiInstance.mlInferenceDeploymentsRetrieve();
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

# **mlInferenceDeploymentsRetrieve2**
> mlInferenceDeploymentsRetrieve2()

Get deployment details.  GET /api/v1/ml/inference/deployments/{id}/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.mlInferenceDeploymentsRetrieve2(
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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **mlModelsCreate**
> MLModel mlModelsCreate(mLModel)

Create a new ML model link.  POST /api/v1/ml/models/

### Example

```typescript
import {
    MlApi,
    Configuration,
    MLModel
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let mLModel: MLModel; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlModelsCreate(
    mLModel,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **mLModel** | **MLModel**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsDatasetsRetrieve**
> MLModel mlModelsDatasetsRetrieve()

Get datasets linked to model.  GET /api/v1/ml/models/{id}/datasets/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)

const { status, data } = await apiInstance.mlModelsDatasetsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsDestroy**
> mlModelsDestroy()

ViewSet for ML model management.  Tenant-scoped: users can only see/manage models in their tenant.

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)

const { status, data } = await apiInstance.mlModelsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|


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

# **mlModelsLinkDatasetCreate**
> MLModel mlModelsLinkDatasetCreate(mLModel)

Link dataset to model.  POST /api/v1/ml/models/{id}/link-dataset/

### Example

```typescript
import {
    MlApi,
    Configuration,
    MLModel
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)
let mLModel: MLModel; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlModelsLinkDatasetCreate(
    id,
    mLModel,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **mLModel** | **MLModel**|  | |
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsList**
> PaginatedMLModelList mlModelsList()

ViewSet for ML model management.  Tenant-scoped: users can only see/manage models in their tenant.

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let ordering: string; //Which field to use when ordering the results. (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let search: string; //A search term. (optional) (default to undefined)

const { status, data } = await apiInstance.mlModelsList(
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

**PaginatedMLModelList**

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

# **mlModelsPartialUpdate**
> MLModel mlModelsPartialUpdate()

ViewSet for ML model management.  Tenant-scoped: users can only see/manage models in their tenant.

### Example

```typescript
import {
    MlApi,
    Configuration,
    PatchedMLModel
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedMLModel: PatchedMLModel; // (optional)

const { status, data } = await apiInstance.mlModelsPartialUpdate(
    id,
    idempotencyKey,
    patchedMLModel
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedMLModel** | **PatchedMLModel**|  | |
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsRetrieve**
> MLModel mlModelsRetrieve()

ViewSet for ML model management.  Tenant-scoped: users can only see/manage models in their tenant.

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)

const { status, data } = await apiInstance.mlModelsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsSyncFromOdhCreate**
> MLModel mlModelsSyncFromOdhCreate(mLModel)

Sync model metadata from ODH.  POST /api/v1/ml/models/{id}/sync-from-odh/

### Example

```typescript
import {
    MlApi,
    Configuration,
    MLModel
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)
let mLModel: MLModel; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlModelsSyncFromOdhCreate(
    id,
    mLModel,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **mLModel** | **MLModel**|  | |
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MLModel**

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

# **mlModelsUpdate**
> MLModel mlModelsUpdate(mLModel)

Update ML model.  PUT/PATCH /api/v1/ml/models/{id}/

### Example

```typescript
import {
    MlApi,
    Configuration,
    MLModel
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; //A UUID string identifying this ml model. (default to undefined)
let mLModel: MLModel; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlModelsUpdate(
    id,
    mLModel,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **mLModel** | **MLModel**|  | |
| **id** | [**string**] | A UUID string identifying this ml model. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MLModel**

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

# **mlTrainingJobsCancelCreate**
> mlTrainingJobsCancelCreate()

Cancel a training job.  POST /api/v1/ml/training/jobs/{id}/cancel/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlTrainingJobsCancelCreate(
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

# **mlTrainingJobsCreate**
> mlTrainingJobsCreate()

Submit a training job.  POST /api/v1/ml/training/jobs/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.mlTrainingJobsCreate(
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
|**201** | No response body |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **mlTrainingJobsLogsRetrieve**
> mlTrainingJobsLogsRetrieve()

Get training job logs.  GET /api/v1/ml/training/jobs/{id}/logs/ Query parameters: - lines: Number of log lines to retrieve (optional)

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.mlTrainingJobsLogsRetrieve(
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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **mlTrainingJobsRetrieve**
> mlTrainingJobsRetrieve()

List training jobs with optional filters.  GET /api/v1/ml/training/jobs/ Query parameters: - model_id: Filter by model ID - status: Filter by status - limit: Pagination limit - offset: Pagination offset

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

const { status, data } = await apiInstance.mlTrainingJobsRetrieve();
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

# **mlTrainingJobsRetrieve2**
> mlTrainingJobsRetrieve2()

Get training job details.  GET /api/v1/ml/training/jobs/{id}/

### Example

```typescript
import {
    MlApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MlApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.mlTrainingJobsRetrieve2(
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
|**200** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

