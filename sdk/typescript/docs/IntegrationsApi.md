# IntegrationsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**integrationsMarketplaceConnectionsCreate**](#integrationsmarketplaceconnectionscreate) | **POST** /api/v1/integrations/marketplace/connections/ | Create marketplace connection|
|[**integrationsMarketplaceConnectionsDestroy**](#integrationsmarketplaceconnectionsdestroy) | **DELETE** /api/v1/integrations/marketplace/connections/{id}/ | Delete marketplace connection|
|[**integrationsMarketplaceConnectionsList**](#integrationsmarketplaceconnectionslist) | **GET** /api/v1/integrations/marketplace/connections/ | List marketplace connections|
|[**integrationsMarketplaceConnectionsPartialUpdate**](#integrationsmarketplaceconnectionspartialupdate) | **PATCH** /api/v1/integrations/marketplace/connections/{id}/ | Partially update marketplace connection|
|[**integrationsMarketplaceConnectionsRetrieve**](#integrationsmarketplaceconnectionsretrieve) | **GET** /api/v1/integrations/marketplace/connections/{id}/ | Get marketplace connection details|
|[**integrationsMarketplaceConnectionsTestCreate**](#integrationsmarketplaceconnectionstestcreate) | **POST** /api/v1/integrations/marketplace/connections/{id}/test/ | Test marketplace connection|
|[**integrationsMarketplaceConnectionsUpdate**](#integrationsmarketplaceconnectionsupdate) | **PUT** /api/v1/integrations/marketplace/connections/{id}/ | Update marketplace connection|
|[**integrationsMarketplaceConnectorsRetrieve**](#integrationsmarketplaceconnectorsretrieve) | **GET** /api/v1/integrations/marketplace/connectors/ | List marketplace connectors|
|[**integrationsMarketplaceConnectorsRetrieve2**](#integrationsmarketplaceconnectorsretrieve2) | **GET** /api/v1/integrations/marketplace/connectors/{connector_type}/ | Get marketplace connector information|
|[**integrationsMarketplaceMappingsDestroy**](#integrationsmarketplacemappingsdestroy) | **DELETE** /api/v1/integrations/marketplace/mappings/{id}/ | Delete marketplace mapping|
|[**integrationsMarketplaceMappingsList**](#integrationsmarketplacemappingslist) | **GET** /api/v1/integrations/marketplace/mappings/ | List marketplace mappings|
|[**integrationsMarketplaceMappingsRetrieve**](#integrationsmarketplacemappingsretrieve) | **GET** /api/v1/integrations/marketplace/mappings/{id}/ | Get marketplace mapping details|
|[**integrationsMarketplaceSyncCancelCreate**](#integrationsmarketplacesynccancelcreate) | **POST** /api/v1/integrations/marketplace/sync/{id}/cancel/ | Cancel marketplace sync job|
|[**integrationsMarketplaceSyncCreate**](#integrationsmarketplacesynccreate) | **POST** /api/v1/integrations/marketplace/sync/ | Create marketplace sync job|
|[**integrationsMarketplaceSyncDestroy**](#integrationsmarketplacesyncdestroy) | **DELETE** /api/v1/integrations/marketplace/sync/{id}/ | |
|[**integrationsMarketplaceSyncList**](#integrationsmarketplacesynclist) | **GET** /api/v1/integrations/marketplace/sync/ | List marketplace sync jobs|
|[**integrationsMarketplaceSyncPartialUpdate**](#integrationsmarketplacesyncpartialupdate) | **PATCH** /api/v1/integrations/marketplace/sync/{id}/ | |
|[**integrationsMarketplaceSyncRetrieve**](#integrationsmarketplacesyncretrieve) | **GET** /api/v1/integrations/marketplace/sync/{id}/ | Get marketplace sync job details|
|[**integrationsMarketplaceSyncUpdate**](#integrationsmarketplacesyncupdate) | **PUT** /api/v1/integrations/marketplace/sync/{id}/ | |

# **integrationsMarketplaceConnectionsCreate**
> MarketplaceConnectionCreate integrationsMarketplaceConnectionsCreate(marketplaceConnectionCreate)

Create a new marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    MarketplaceConnectionCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let marketplaceConnectionCreate: MarketplaceConnectionCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsCreate(
    marketplaceConnectionCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **marketplaceConnectionCreate** | **MarketplaceConnectionCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceConnectionCreate**

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

# **integrationsMarketplaceConnectionsDestroy**
> integrationsMarketplaceConnectionsDestroy()

Delete a marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsDestroy(
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

# **integrationsMarketplaceConnectionsList**
> PaginatedMarketplaceConnectionList integrationsMarketplaceConnectionsList()

List all marketplace connections for the authenticated user\'s tenant with filtering, pagination, and search.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let isActive: boolean; //Filter by active status (true/false) (optional) (default to undefined)
let marketplaceType: string; //Filter by marketplace type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE) (optional) (default to undefined)
let ordering: string; //Order by field (e.g., name, -created_at). Prefix with - for descending. (optional) (default to undefined)
let page: number; //Page number (default: 1) (optional) (default to undefined)
let pageSize: number; //Items per page (default: 50, max: 100) (optional) (default to undefined)
let search: string; //Search in connection name (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsList(
    isActive,
    marketplaceType,
    ordering,
    page,
    pageSize,
    search
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **isActive** | [**boolean**] | Filter by active status (true/false) | (optional) defaults to undefined|
| **marketplaceType** | [**string**] | Filter by marketplace type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE) | (optional) defaults to undefined|
| **ordering** | [**string**] | Order by field (e.g., name, -created_at). Prefix with - for descending. | (optional) defaults to undefined|
| **page** | [**number**] | Page number (default: 1) | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page (default: 50, max: 100) | (optional) defaults to undefined|
| **search** | [**string**] | Search in connection name | (optional) defaults to undefined|


### Return type

**PaginatedMarketplaceConnectionList**

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

# **integrationsMarketplaceConnectionsPartialUpdate**
> MarketplaceConnectionUpdate integrationsMarketplaceConnectionsPartialUpdate()

Partially update an existing marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    PatchedMarketplaceConnectionUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedMarketplaceConnectionUpdate: PatchedMarketplaceConnectionUpdate; // (optional)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsPartialUpdate(
    id,
    idempotencyKey,
    patchedMarketplaceConnectionUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedMarketplaceConnectionUpdate** | **PatchedMarketplaceConnectionUpdate**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceConnectionUpdate**

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

# **integrationsMarketplaceConnectionsRetrieve**
> MarketplaceConnection integrationsMarketplaceConnectionsRetrieve()

Get detailed information about a specific marketplace connection.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**MarketplaceConnection**

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

# **integrationsMarketplaceConnectionsTestCreate**
> MarketplaceConnectionTestResponse integrationsMarketplaceConnectionsTestCreate()

Test a marketplace connection by verifying credentials and connectivity. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsTestCreate(
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

**MarketplaceConnectionTestResponse**

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
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **integrationsMarketplaceConnectionsUpdate**
> MarketplaceConnectionUpdate integrationsMarketplaceConnectionsUpdate()

Update an existing marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    MarketplaceConnectionUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let marketplaceConnectionUpdate: MarketplaceConnectionUpdate; // (optional)

const { status, data } = await apiInstance.integrationsMarketplaceConnectionsUpdate(
    id,
    idempotencyKey,
    marketplaceConnectionUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **marketplaceConnectionUpdate** | **MarketplaceConnectionUpdate**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceConnectionUpdate**

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

# **integrationsMarketplaceConnectorsRetrieve**
> any integrationsMarketplaceConnectorsRetrieve()

List all available marketplace connector types with their supported sync directions and status.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

const { status, data } = await apiInstance.integrationsMarketplaceConnectorsRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**any**

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

# **integrationsMarketplaceConnectorsRetrieve2**
> any integrationsMarketplaceConnectorsRetrieve2()

Get detailed information about a specific marketplace connector type including capabilities and configuration requirements.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let connectorType: string; // (default to undefined)
let type: string; //Marketplace connector type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceConnectorsRetrieve2(
    connectorType,
    type
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **connectorType** | [**string**] |  | defaults to undefined|
| **type** | [**string**] | Marketplace connector type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE) | defaults to undefined|


### Return type

**any**

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

# **integrationsMarketplaceMappingsDestroy**
> integrationsMarketplaceMappingsDestroy()

Delete a marketplace mapping. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceMappingsDestroy(
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

# **integrationsMarketplaceMappingsList**
> PaginatedMarketplaceMappingList integrationsMarketplaceMappingsList()

List all marketplace mappings for the authenticated user\'s tenant with filtering, pagination, and search.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let connectionId: string; //Filter by connection ID (optional) (default to undefined)
let externalListingId: string; //Filter by external listing ID (optional) (default to undefined)
let hubAssetId: string; //Filter by hub asset ID (optional) (default to undefined)
let ordering: string; //Order by field (e.g., created_at, -created_at, external_listing_id). Prefix with - for descending. (optional) (default to undefined)
let page: number; //Page number (default: 1) (optional) (default to undefined)
let pageSize: number; //Items per page (default: 50, max: 100) (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceMappingsList(
    connectionId,
    externalListingId,
    hubAssetId,
    ordering,
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **connectionId** | [**string**] | Filter by connection ID | (optional) defaults to undefined|
| **externalListingId** | [**string**] | Filter by external listing ID | (optional) defaults to undefined|
| **hubAssetId** | [**string**] | Filter by hub asset ID | (optional) defaults to undefined|
| **ordering** | [**string**] | Order by field (e.g., created_at, -created_at, external_listing_id). Prefix with - for descending. | (optional) defaults to undefined|
| **page** | [**number**] | Page number (default: 1) | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page (default: 50, max: 100) | (optional) defaults to undefined|


### Return type

**PaginatedMarketplaceMappingList**

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

# **integrationsMarketplaceMappingsRetrieve**
> MarketplaceMapping integrationsMarketplaceMappingsRetrieve()

Get detailed information about a specific marketplace mapping.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceMappingsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**MarketplaceMapping**

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

# **integrationsMarketplaceSyncCancelCreate**
> MarketplaceSyncJob integrationsMarketplaceSyncCancelCreate()

Cancel a running marketplace sync job. Only jobs in PENDING or RUNNING status can be cancelled. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    MarketplaceSyncJobCancel
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let marketplaceSyncJobCancel: MarketplaceSyncJobCancel; // (optional)

const { status, data } = await apiInstance.integrationsMarketplaceSyncCancelCreate(
    id,
    idempotencyKey,
    marketplaceSyncJobCancel
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **marketplaceSyncJobCancel** | **MarketplaceSyncJobCancel**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceSyncJob**

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
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **integrationsMarketplaceSyncCreate**
> MarketplaceSyncRequest integrationsMarketplaceSyncCreate(marketplaceSyncRequest)

Create a new marketplace sync job. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    MarketplaceSyncRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let marketplaceSyncRequest: MarketplaceSyncRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceSyncCreate(
    marketplaceSyncRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **marketplaceSyncRequest** | **MarketplaceSyncRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceSyncRequest**

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

# **integrationsMarketplaceSyncDestroy**
> integrationsMarketplaceSyncDestroy()

ViewSet for marketplace sync job management.  Tenant-scoped: users can only see/manage sync jobs in their tenant. Supports RBAC (role-based) and ABAC (attribute-based) authorization. Includes rate limiting, comprehensive filtering, pagination, and audit logging.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceSyncDestroy(
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

# **integrationsMarketplaceSyncList**
> PaginatedMarketplaceSyncJobList integrationsMarketplaceSyncList()

List all marketplace sync jobs for the authenticated user\'s tenant with filtering, pagination, and search.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let connectionId: string; //Filter by connection ID (optional) (default to undefined)
let direction: string; //Filter by sync direction (PUSH, PULL, BIDIRECTIONAL) (optional) (default to undefined)
let ordering: string; //Order by field (e.g., created_at, -created_at). Prefix with - for descending. (optional) (default to undefined)
let page: number; //Page number (default: 1) (optional) (default to undefined)
let pageSize: number; //Items per page (default: 50, max: 100) (optional) (default to undefined)
let status: string; //Filter by sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL) (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceSyncList(
    connectionId,
    direction,
    ordering,
    page,
    pageSize,
    status
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **connectionId** | [**string**] | Filter by connection ID | (optional) defaults to undefined|
| **direction** | [**string**] | Filter by sync direction (PUSH, PULL, BIDIRECTIONAL) | (optional) defaults to undefined|
| **ordering** | [**string**] | Order by field (e.g., created_at, -created_at). Prefix with - for descending. | (optional) defaults to undefined|
| **page** | [**number**] | Page number (default: 1) | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page (default: 50, max: 100) | (optional) defaults to undefined|
| **status** | [**string**] | Filter by sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL) | (optional) defaults to undefined|


### Return type

**PaginatedMarketplaceSyncJobList**

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

# **integrationsMarketplaceSyncPartialUpdate**
> MarketplaceSyncJob integrationsMarketplaceSyncPartialUpdate()

ViewSet for marketplace sync job management.  Tenant-scoped: users can only see/manage sync jobs in their tenant. Supports RBAC (role-based) and ABAC (attribute-based) authorization. Includes rate limiting, comprehensive filtering, pagination, and audit logging.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    PatchedMarketplaceSyncJob
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedMarketplaceSyncJob: PatchedMarketplaceSyncJob; // (optional)

const { status, data } = await apiInstance.integrationsMarketplaceSyncPartialUpdate(
    id,
    idempotencyKey,
    patchedMarketplaceSyncJob
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedMarketplaceSyncJob** | **PatchedMarketplaceSyncJob**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceSyncJob**

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

# **integrationsMarketplaceSyncRetrieve**
> MarketplaceSyncJob integrationsMarketplaceSyncRetrieve()

Get detailed information about a specific marketplace sync job.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceSyncRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**MarketplaceSyncJob**

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

# **integrationsMarketplaceSyncUpdate**
> MarketplaceSyncJob integrationsMarketplaceSyncUpdate(marketplaceSyncJob)

ViewSet for marketplace sync job management.  Tenant-scoped: users can only see/manage sync jobs in their tenant. Supports RBAC (role-based) and ABAC (attribute-based) authorization. Includes rate limiting, comprehensive filtering, pagination, and audit logging.

### Example

```typescript
import {
    IntegrationsApi,
    Configuration,
    MarketplaceSyncJob
} from './api';

const configuration = new Configuration();
const apiInstance = new IntegrationsApi(configuration);

let id: string; // (default to undefined)
let marketplaceSyncJob: MarketplaceSyncJob; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.integrationsMarketplaceSyncUpdate(
    id,
    marketplaceSyncJob,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **marketplaceSyncJob** | **MarketplaceSyncJob**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**MarketplaceSyncJob**

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

