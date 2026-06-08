# VersioningApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**versioningCompareRetrieve**](#versioningcompareretrieve) | **GET** /api/v1/versioning/compare/ | Compare two versions|
|[**versioningVersionsCompareRetrieve**](#versioningversionscompareretrieve) | **GET** /api/v1/versioning/versions/compare/ | Compare two versions|
|[**versioningVersionsList**](#versioningversionslist) | **GET** /api/v1/versioning/versions/ | List versions|
|[**versioningVersionsRetrieve**](#versioningversionsretrieve) | **GET** /api/v1/versioning/versions/{id}/ | Get version by id|

# **versioningCompareRetrieve**
> VersionCompare versioningCompareRetrieve()

Compare two versions (same resource type). Tenant-scoped.

### Example

```typescript
import {
    VersioningApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VersioningApi(configuration);

let idA: string; // (default to undefined)
let idB: string; // (default to undefined)
let resourceType: 'contract' | 'dataset'; // (default to undefined)

const { status, data } = await apiInstance.versioningCompareRetrieve(
    idA,
    idB,
    resourceType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idA** | [**string**] |  | defaults to undefined|
| **idB** | [**string**] |  | defaults to undefined|
| **resourceType** | [**&#39;contract&#39; | &#39;dataset&#39;**]**Array<&#39;contract&#39; &#124; &#39;dataset&#39;>** |  | defaults to undefined|


### Return type

**VersionCompare**

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

# **versioningVersionsCompareRetrieve**
> VersionCompare versioningVersionsCompareRetrieve()

Compare two versions (same resource type). Tenant-scoped.

### Example

```typescript
import {
    VersioningApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VersioningApi(configuration);

let idA: string; // (default to undefined)
let idB: string; // (default to undefined)
let resourceType: 'contract' | 'dataset'; // (default to undefined)

const { status, data } = await apiInstance.versioningVersionsCompareRetrieve(
    idA,
    idB,
    resourceType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idA** | [**string**] |  | defaults to undefined|
| **idB** | [**string**] |  | defaults to undefined|
| **resourceType** | [**&#39;contract&#39; | &#39;dataset&#39;**]**Array<&#39;contract&#39; &#124; &#39;dataset&#39;>** |  | defaults to undefined|


### Return type

**VersionCompare**

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

# **versioningVersionsList**
> Array<VersionListEntry> versioningVersionsList()

List versions by asset id. Tenant-scoped.

### Example

```typescript
import {
    VersioningApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VersioningApi(configuration);

let resourceId: string; // (default to undefined)
let resourceType: 'contract' | 'dataset'; // (default to undefined)

const { status, data } = await apiInstance.versioningVersionsList(
    resourceId,
    resourceType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **resourceId** | [**string**] |  | defaults to undefined|
| **resourceType** | [**&#39;contract&#39; | &#39;dataset&#39;**]**Array<&#39;contract&#39; &#124; &#39;dataset&#39;>** |  | defaults to undefined|


### Return type

**Array<VersionListEntry>**

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

# **versioningVersionsRetrieve**
> VersionDetail versioningVersionsRetrieve()

Retrieve one version by id. Tenant-scoped.

### Example

```typescript
import {
    VersioningApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new VersioningApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.versioningVersionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**VersionDetail**

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

