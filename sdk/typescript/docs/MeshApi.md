# MeshApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**meshDomainsDeployCreate**](#meshdomainsdeploycreate) | **POST** /api/v1/mesh/domains/{id}/deploy/ | |
|[**meshDomainsGovernanceCreate**](#meshdomainsgovernancecreate) | **POST** /api/v1/mesh/domains/{id}/governance/ | |
|[**meshDomainsGovernanceRetrieve**](#meshdomainsgovernanceretrieve) | **GET** /api/v1/mesh/domains/{id}/governance/ | |
|[**meshDomainsMonitoringRetrieve**](#meshdomainsmonitoringretrieve) | **GET** /api/v1/mesh/domains/{id}/monitoring/ | |
|[**meshDomainsPartialUpdate**](#meshdomainspartialupdate) | **PATCH** /api/v1/mesh/domains/{id}/ | |
|[**meshDomainsQuotasCreate**](#meshdomainsquotascreate) | **POST** /api/v1/mesh/domains/{id}/quotas/ | |
|[**meshDomainsQuotasRetrieve**](#meshdomainsquotasretrieve) | **GET** /api/v1/mesh/domains/{id}/quotas/ | |
|[**meshGovernanceComplianceRetrieve**](#meshgovernancecomplianceretrieve) | **GET** /api/v1/mesh/governance/compliance/ | |
|[**meshGovernancePoliciesRetrieve**](#meshgovernancepoliciesretrieve) | **GET** /api/v1/mesh/governance/policies/ | |
|[**meshGovernanceReportsRetrieve**](#meshgovernancereportsretrieve) | **GET** /api/v1/mesh/governance/reports/ | |
|[**meshGovernanceRetrieve**](#meshgovernanceretrieve) | **GET** /api/v1/mesh/governance/ | |

# **meshDomainsDeployCreate**
> Domain meshDomainsDeployCreate(domain)

Deploy domain (placeholder).

### Example

```typescript
import {
    MeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsDeployCreate(
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

# **meshDomainsGovernanceCreate**
> Domain meshDomainsGovernanceCreate(domain)

Get or configure domain governance.

### Example

```typescript
import {
    MeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsGovernanceCreate(
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

# **meshDomainsGovernanceRetrieve**
> Domain meshDomainsGovernanceRetrieve()

Get or configure domain governance.

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsGovernanceRetrieve(
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

# **meshDomainsMonitoringRetrieve**
> Domain meshDomainsMonitoringRetrieve()

Get domain monitoring metrics.

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsMonitoringRetrieve(
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

# **meshDomainsPartialUpdate**
> Domain meshDomainsPartialUpdate()

ViewSet for data mesh domain management.  Tenant-scoped: users can only see/manage domains in their tenant. Requires TENANT_ADMIN role for write operations. Requires mesh:write scope for write operations.

### Example

```typescript
import {
    MeshApi,
    Configuration,
    PatchedDomain
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedDomain: PatchedDomain; // (optional)

const { status, data } = await apiInstance.meshDomainsPartialUpdate(
    id,
    idempotencyKey,
    patchedDomain
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedDomain** | **PatchedDomain**|  | |
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

# **meshDomainsQuotasCreate**
> Domain meshDomainsQuotasCreate(domain)

Get or configure domain resource quotas.

### Example

```typescript
import {
    MeshApi,
    Configuration,
    Domain
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)
let domain: Domain; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.meshDomainsQuotasCreate(
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

# **meshDomainsQuotasRetrieve**
> Domain meshDomainsQuotasRetrieve()

Get or configure domain resource quotas.

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

let id: string; //A UUID string identifying this data mesh domain. (default to undefined)

const { status, data } = await apiInstance.meshDomainsQuotasRetrieve(
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

# **meshGovernanceComplianceRetrieve**
> meshGovernanceComplianceRetrieve()

List mesh governance compliance status.  GET /api/v1/mesh/governance/compliance/

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

const { status, data } = await apiInstance.meshGovernanceComplianceRetrieve();
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

# **meshGovernancePoliciesRetrieve**
> meshGovernancePoliciesRetrieve()

List governance policies applied to mesh domains.  GET /api/v1/mesh/governance/policies/

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

const { status, data } = await apiInstance.meshGovernancePoliciesRetrieve();
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

# **meshGovernanceReportsRetrieve**
> meshGovernanceReportsRetrieve()

List mesh governance reports.  GET /api/v1/mesh/governance/reports/

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

const { status, data } = await apiInstance.meshGovernanceReportsRetrieve();
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

# **meshGovernanceRetrieve**
> meshGovernanceRetrieve()

Get mesh governance summary.  GET /api/v1/mesh/governance/

### Example

```typescript
import {
    MeshApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MeshApi(configuration);

const { status, data } = await apiInstance.meshGovernanceRetrieve();
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

