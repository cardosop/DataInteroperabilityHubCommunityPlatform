# DataMeshTopologyApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**meshTopologyHealthRetrieve**](#meshtopologyhealthretrieve) | **GET** /api/v1/mesh/topology/health/ | Get mesh health|
|[**meshTopologyList**](#meshtopologylist) | **GET** /api/v1/mesh/topology/ | Get mesh topology|
|[**meshTopologyRelationshipsRetrieve**](#meshtopologyrelationshipsretrieve) | **GET** /api/v1/mesh/topology/relationships/ | Get domain relationships|
|[**meshTopologyRetrieve**](#meshtopologyretrieve) | **GET** /api/v1/mesh/topology/{id}/ | Get domain topology|

# **meshTopologyHealthRetrieve**
> MeshHealth meshTopologyHealthRetrieve()

Get overall mesh health metrics and per-domain health status.

### Example

```typescript
import {
    DataMeshTopologyApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshTopologyApi(configuration);

const { status, data } = await apiInstance.meshTopologyHealthRetrieve();
```

### Parameters
This endpoint does not have any parameters.


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
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **meshTopologyList**
> Array<Topology> meshTopologyList()

Get complete data mesh topology including all domains, relationships, and health metrics.

### Example

```typescript
import {
    DataMeshTopologyApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshTopologyApi(configuration);

const { status, data } = await apiInstance.meshTopologyList();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Array<Topology>**

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

# **meshTopologyRelationshipsRetrieve**
> DomainRelationship meshTopologyRelationshipsRetrieve()

Get all domain relationships in the mesh.

### Example

```typescript
import {
    DataMeshTopologyApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshTopologyApi(configuration);

const { status, data } = await apiInstance.meshTopologyRelationshipsRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**DomainRelationship**

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

# **meshTopologyRetrieve**
> DomainTopology meshTopologyRetrieve()

Get topology view for a specific domain including its relationships and health metrics.

### Example

```typescript
import {
    DataMeshTopologyApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataMeshTopologyApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.meshTopologyRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**DomainTopology**

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

