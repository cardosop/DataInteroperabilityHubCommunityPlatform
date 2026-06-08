# SemanticApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**semanticContextJsonldRetrieve**](#semanticcontextjsonldretrieve) | **GET** /api/v1/semantic/context.jsonld | |
|[**semanticContextRetrieve**](#semanticcontextretrieve) | **GET** /api/v1/semantic/context | |
|[**semanticExportCreate**](#semanticexportcreate) | **POST** /api/v1/semantic/export | Bulk RDF export|
|[**semanticGraphqlCreate**](#semanticgraphqlcreate) | **POST** /api/v1/semantic/graphql | |
|[**semanticIdFieldRetrieve**](#semanticidfieldretrieve) | **GET** /api/v1/semantic/id/field/{asset_uuid}/{field_name} | |
|[**semanticIdRetrieve**](#semanticidretrieve) | **GET** /api/v1/semantic/id/{resource_type}/{resource_id} | |
|[**semanticLdnInboxCreate**](#semanticldninboxcreate) | **POST** /api/v1/semantic/ldn/inbox/{tenant_id} | |
|[**semanticLdnInboxRetrieve**](#semanticldninboxretrieve) | **GET** /api/v1/semantic/ldn/inbox/{tenant_id}/ | |
|[**semanticLdnInboxRetrieve2**](#semanticldninboxretrieve2) | **GET** /api/v1/semantic/ldn/inbox/{tenant_id}/{inbox_id} | |
|[**semanticLdnSubscriptionsCreate**](#semanticldnsubscriptionscreate) | **POST** /api/v1/semantic/ldn/subscriptions/ | |
|[**semanticLdnSubscriptionsDestroy**](#semanticldnsubscriptionsdestroy) | **DELETE** /api/v1/semantic/ldn/subscriptions/{id}/ | |
|[**semanticLdnSubscriptionsList**](#semanticldnsubscriptionslist) | **GET** /api/v1/semantic/ldn/subscriptions/ | |
|[**semanticLdnSubscriptionsPartialUpdate**](#semanticldnsubscriptionspartialupdate) | **PATCH** /api/v1/semantic/ldn/subscriptions/{id}/ | |
|[**semanticLdnSubscriptionsRetrieve**](#semanticldnsubscriptionsretrieve) | **GET** /api/v1/semantic/ldn/subscriptions/{id}/ | |
|[**semanticLdnSubscriptionsUpdate**](#semanticldnsubscriptionsupdate) | **PUT** /api/v1/semantic/ldn/subscriptions/{id}/ | |
|[**semanticOntologiesCreate**](#semanticontologiescreate) | **POST** /api/v1/semantic/ontologies/ | |
|[**semanticOntologiesDestroy**](#semanticontologiesdestroy) | **DELETE** /api/v1/semantic/ontologies/{id}/ | |
|[**semanticOntologiesList**](#semanticontologieslist) | **GET** /api/v1/semantic/ontologies/ | |
|[**semanticOntologiesPartialUpdate**](#semanticontologiespartialupdate) | **PATCH** /api/v1/semantic/ontologies/{id}/ | |
|[**semanticOntologiesRetrieve**](#semanticontologiesretrieve) | **GET** /api/v1/semantic/ontologies/{id}/ | |
|[**semanticOntologiesUpdate**](#semanticontologiesupdate) | **PUT** /api/v1/semantic/ontologies/{id}/ | |
|[**semanticOntologyRetrieve**](#semanticontologyretrieve) | **GET** /api/v1/semantic/ontology | |
|[**semanticRdfIngestCreate**](#semanticrdfingestcreate) | **POST** /api/v1/semantic/rdf/ingest | Ingest RDF into tenant graph|
|[**semanticRelationshipsRetrieve**](#semanticrelationshipsretrieve) | **GET** /api/v1/semantic/relationships/{contract_id} | |
|[**semanticResourceRetrieve**](#semanticresourceretrieve) | **GET** /api/v1/semantic/resource/{resource_type}/{resource_id}/ | |
|[**semanticResourceTimemapRetrieve**](#semanticresourcetimemapretrieve) | **GET** /api/v1/semantic/resource/{resource_type}/{resource_id}/timemap | TimeMap (RFC 7089)|
|[**semanticResourceVersionRetrieve**](#semanticresourceversionretrieve) | **GET** /api/v1/semantic/resource/{resource_type}/{resource_id}/version/{snapshot_at} | Versioned dereference (Memento)|
|[**semanticSemanticResourcesList**](#semanticsemanticresourceslist) | **GET** /api/v1/semantic/semantic-resources/ | |
|[**semanticSemanticResourcesRetrieve**](#semanticsemanticresourcesretrieve) | **GET** /api/v1/semantic/semantic-resources/{id}/ | |
|[**semanticSparqlCreate**](#semanticsparqlcreate) | **POST** /api/v1/semantic/sparql | |
|[**semanticSparqlDescriptionRetrieve**](#semanticsparqldescriptionretrieve) | **GET** /api/v1/semantic/sparql/description | |
|[**semanticSparqlRetrieve**](#semanticsparqlretrieve) | **GET** /api/v1/semantic/sparql | |

# **semanticContextJsonldRetrieve**
> object semanticContextJsonldRetrieve()

Get JSON-LD context for hub ontology.  Requires authentication (Phase 219.2).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

const { status, data } = await apiInstance.semanticContextJsonldRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**object**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticContextRetrieve**
> object semanticContextRetrieve()

Get JSON-LD context for hub ontology.  Requires authentication (Phase 219.2).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

const { status, data } = await apiInstance.semanticContextRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**object**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticExportCreate**
> semanticExportCreate()

Phase 230.2 (REQ-SEM-EXPORT-001) — exports the authenticated user\'s tenant graph in the requested RDF serialization. Throttle: 5 requests / 5 minutes / user. Hard cap 100M triples (413 above). Streams via the FastAPI semantic-service `/export` endpoint; the body is forwarded verbatim to the HTTP client.

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    SemanticExportRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let semanticExportRequest: SemanticExportRequest; // (optional)

const { status, data } = await apiInstance.semanticExportCreate(
    idempotencyKey,
    semanticExportRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **semanticExportRequest** | **SemanticExportRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | RDF body in the requested serialization. |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**413** | Result exceeds 100M-triple cap. |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**503** | Semantic service unavailable. |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticGraphqlCreate**
> semanticGraphqlCreate()

``POST /api/v1/semantic/graphql`` — Linked-Data GraphQL endpoint.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticGraphqlCreate(
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

# **semanticIdFieldRetrieve**
> SemanticIdRetrieve200Response semanticIdFieldRetrieve()

Resolve a field URI to JSON-LD representation.  URL pattern: /id/field/{asset_uuid}/{field_name}

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let assetUuid: string; // (default to undefined)
let fieldName: string; // (default to undefined)

const { status, data } = await apiInstance.semanticIdFieldRetrieve(
    assetUuid,
    fieldName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetUuid** | [**string**] |  | defaults to undefined|
| **fieldName** | [**string**] |  | defaults to undefined|


### Return type

**SemanticIdRetrieve200Response**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** |  |  -  |
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticIdRetrieve**
> SemanticIdRetrieve200Response semanticIdRetrieve()

Resolve a stable URI to JSON-LD representation.  Supports: asset, contract, dataset  For field resources, use: /id/field/{asset_uuid}/{field_name}

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let resourceId: string; // (default to undefined)
let resourceType: string; // (default to undefined)

const { status, data } = await apiInstance.semanticIdRetrieve(
    resourceId,
    resourceType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **resourceId** | [**string**] |  | defaults to undefined|
| **resourceType** | [**string**] |  | defaults to undefined|


### Return type

**SemanticIdRetrieve200Response**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**404** |  |  -  |
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticLdnInboxCreate**
> semanticLdnInboxCreate()

Phase 230.12.3 — accept a signed RDF notification.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let tenantId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticLdnInboxCreate(
    tenantId,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[BearerAuth](../README.md#BearerAuth)

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

# **semanticLdnInboxRetrieve**
> semanticLdnInboxRetrieve()

List inbox entries for a tenant (admins / auditors only).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.semanticLdnInboxRetrieve(
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantId** | [**string**] |  | defaults to undefined|


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

# **semanticLdnInboxRetrieve2**
> semanticLdnInboxRetrieve2()

Retrieve a single inbox entry (admins / auditors only).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let inboxId: string; // (default to undefined)
let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.semanticLdnInboxRetrieve2(
    inboxId,
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **inboxId** | [**string**] |  | defaults to undefined|
| **tenantId** | [**string**] |  | defaults to undefined|


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

# **semanticLdnSubscriptionsCreate**
> LdnSubscription semanticLdnSubscriptionsCreate(ldnSubscription)

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    LdnSubscription
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let ldnSubscription: LdnSubscription; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticLdnSubscriptionsCreate(
    ldnSubscription,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **ldnSubscription** | **LdnSubscription**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**LdnSubscription**

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

# **semanticLdnSubscriptionsDestroy**
> semanticLdnSubscriptionsDestroy()

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.semanticLdnSubscriptionsDestroy(
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

# **semanticLdnSubscriptionsList**
> PaginatedLdnSubscriptionList semanticLdnSubscriptionsList()

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticLdnSubscriptionsList(
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

**PaginatedLdnSubscriptionList**

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

# **semanticLdnSubscriptionsPartialUpdate**
> LdnSubscription semanticLdnSubscriptionsPartialUpdate()

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    PatchedLdnSubscription
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedLdnSubscription: PatchedLdnSubscription; // (optional)

const { status, data } = await apiInstance.semanticLdnSubscriptionsPartialUpdate(
    id,
    idempotencyKey,
    patchedLdnSubscription
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedLdnSubscription** | **PatchedLdnSubscription**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**LdnSubscription**

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

# **semanticLdnSubscriptionsRetrieve**
> LdnSubscription semanticLdnSubscriptionsRetrieve()

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.semanticLdnSubscriptionsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**LdnSubscription**

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

# **semanticLdnSubscriptionsUpdate**
> LdnSubscription semanticLdnSubscriptionsUpdate(ldnSubscription)

Phase 230.12 (REQ-SEM-LDN-003) — outbound subscription CRUD.  Tenant scoping: list/retrieve filter by request tenant; create binds the row to the request tenant (the body\'s tenant_id, if any, is ignored — security boundary).

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    LdnSubscription
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)
let ldnSubscription: LdnSubscription; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticLdnSubscriptionsUpdate(
    id,
    ldnSubscription,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **ldnSubscription** | **LdnSubscription**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**LdnSubscription**

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

# **semanticOntologiesCreate**
> TenantOntology semanticOntologiesCreate(tenantOntology)

List / upload / activate / deactivate / delete custom ontologies. Tenant-capability gate (REQ-SEM-ONTO-002) returns 403 when ``Tenant.semantic_custom_ontology_enabled=False`` regardless of role.

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    TenantOntology
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let tenantOntology: TenantOntology; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticOntologiesCreate(
    tenantOntology,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantOntology** | **TenantOntology**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantOntology**

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

# **semanticOntologiesDestroy**
> semanticOntologiesDestroy()

List / upload / activate / deactivate / delete custom ontologies. Tenant-capability gate (REQ-SEM-ONTO-002) returns 403 when ``Tenant.semantic_custom_ontology_enabled=False`` regardless of role.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.semanticOntologiesDestroy(
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

# **semanticOntologiesList**
> PaginatedTenantOntologyList semanticOntologiesList()

List / upload / activate / deactivate / delete custom ontologies. Tenant-capability gate (REQ-SEM-ONTO-002) returns 403 when ``Tenant.semantic_custom_ontology_enabled=False`` regardless of role.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticOntologiesList(
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

**PaginatedTenantOntologyList**

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

# **semanticOntologiesPartialUpdate**
> TenantOntology semanticOntologiesPartialUpdate()

PATCH — primarily used to flip ``is_active`` to True/False. On True → load into Fuseki, emit SEMANTIC_ONTOLOGY_ACTIVATE. On False → drop the named graph.

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    PatchedTenantOntology
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantOntology: PatchedTenantOntology; // (optional)

const { status, data } = await apiInstance.semanticOntologiesPartialUpdate(
    id,
    idempotencyKey,
    patchedTenantOntology
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantOntology** | **PatchedTenantOntology**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantOntology**

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

# **semanticOntologiesRetrieve**
> TenantOntology semanticOntologiesRetrieve()

List / upload / activate / deactivate / delete custom ontologies. Tenant-capability gate (REQ-SEM-ONTO-002) returns 403 when ``Tenant.semantic_custom_ontology_enabled=False`` regardless of role.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.semanticOntologiesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**TenantOntology**

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

# **semanticOntologiesUpdate**
> TenantOntology semanticOntologiesUpdate(tenantOntology)

List / upload / activate / deactivate / delete custom ontologies. Tenant-capability gate (REQ-SEM-ONTO-002) returns 403 when ``Tenant.semantic_custom_ontology_enabled=False`` regardless of role.

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    TenantOntology
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; // (default to undefined)
let tenantOntology: TenantOntology; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticOntologiesUpdate(
    id,
    tenantOntology,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantOntology** | **TenantOntology**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantOntology**

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

# **semanticOntologyRetrieve**
> any semanticOntologyRetrieve()

Get ontology definition in Turtle format.  Requires authentication (Phase 219.2).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

const { status, data } = await apiInstance.semanticOntologyRetrieve();
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
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticRdfIngestCreate**
> semanticRdfIngestCreate(rdfIngestRequest)

Phase 23.6 ingest endpoint. Tenant scope is derived from the authenticated request context. Transitional compatibility for one release cycle: a body `tenant_id` matching the request tenant is accepted but deprecated; mismatches are rejected with 403.

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    RdfIngestRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let rdfIngestRequest: RdfIngestRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticRdfIngestCreate(
    rdfIngestRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **rdfIngestRequest** | **RdfIngestRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | RDF ingest completed. |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticRelationshipsRetrieve**
> any semanticRelationshipsRetrieve()

Phase 230.5.1 — return RDF relationship triples for a contract.  REQ-SEM-RELATIONSHIPS-001 mandates content negotiation: the response body is the actual RDF data in the format the client requested via ``Accept`` (Turtle, N-Triples, or JSON-LD), NOT a JSON envelope around an opaque triples string.  Phase 230.5 MetaDoD audit fix M1 — the prior implementation always returned a ``{triples, status}`` JSON wrapper which violated the spec scenario \"response body contains at least one prov:wasDerivedFrom predicate\" (the predicate was buried inside a string field, not parseable as JSON-LD).  Tenant-scoped: a cross-tenant ``contract_id`` returns 404 to avoid fingerprinting another tenant\'s contracts.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let contractId: string; // (default to undefined)
let format: 'html' | 'json' | 'ld_json' | 'n_triples' | 'rdf_xml' | 'turtle'; // (optional) (default to undefined)

const { status, data } = await apiInstance.semanticRelationshipsRetrieve(
    contractId,
    format
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractId** | [**string**] |  | defaults to undefined|
| **format** | [**&#39;html&#39; | &#39;json&#39; | &#39;ld_json&#39; | &#39;n_triples&#39; | &#39;rdf_xml&#39; | &#39;turtle&#39;**]**Array<&#39;html&#39; &#124; &#39;json&#39; &#124; &#39;ld_json&#39; &#124; &#39;n_triples&#39; &#124; &#39;rdf_xml&#39; &#124; &#39;turtle&#39;>** |  | (optional) defaults to undefined|


### Return type

**any**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, text/turtle, application/rdf+xml, application/ld+json, application/n-triples, text/html


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**401** |  |  -  |
|**404** |  |  -  |
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticResourceRetrieve**
> any semanticResourceRetrieve()

Dereference a resource IRI (Phase 22.3).  RDF clients (``Accept: text/turtle`` etc.) receive a ``303 See Other`` redirect to the canonical ``{SEMANTIC_BASE_IRI}/id/{type}/{id}`` IRI. JSON/browser clients receive the JSON-LD representation directly.  Phase 230.3.9 (REQ-SEM-TOMBSTONE-001) — TOMBSTONED resources short-circuit BOTH the RDF-redirect path AND the JSON-LD path with HTTP 410 Gone.  The body shape is fixed across all 5 RDF content types (the response body is JSON; the RDF renderers serialise it unchanged because the body is structural data, not a triple-graph) and includes ``Cache-Control: max-age=86400`` so caches honour the terminal state for ~1 day before retrying.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let resourceId: string; // (default to undefined)
let resourceType: string; // (default to undefined)
let format: 'html' | 'json' | 'ld_json' | 'n_triples' | 'rdf_xml' | 'turtle'; // (optional) (default to undefined)

const { status, data } = await apiInstance.semanticResourceRetrieve(
    resourceId,
    resourceType,
    format
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **resourceId** | [**string**] |  | defaults to undefined|
| **resourceType** | [**string**] |  | defaults to undefined|
| **format** | [**&#39;html&#39; | &#39;json&#39; | &#39;ld_json&#39; | &#39;n_triples&#39; | &#39;rdf_xml&#39; | &#39;turtle&#39;**]**Array<&#39;html&#39; &#124; &#39;json&#39; &#124; &#39;ld_json&#39; &#124; &#39;n_triples&#39; &#124; &#39;rdf_xml&#39; &#124; &#39;turtle&#39;>** |  | (optional) defaults to undefined|


### Return type

**any**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json, text/turtle, application/rdf+xml, application/ld+json, application/n-triples, text/html


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**303** |  |  -  |
|**400** |  |  -  |
|**404** |  |  -  |
|**503** |  |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticResourceTimemapRetrieve**
> semanticResourceTimemapRetrieve()

Phase 230.4 (REQ-SEM-MEMENTO-001) — list all snapshots for a resource as ``application/link-format``. One ``rel=\"memento\"`` entry per snapshot in chronological order, plus ``rel=\"timegate\"`` + ``rel=\"original\"`` entries pointing at the live IRI.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let resourceId: string; // (default to undefined)
let resourceType: string; // (default to undefined)

const { status, data } = await apiInstance.semanticResourceTimemapRetrieve(
    resourceId,
    resourceType
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **resourceId** | [**string**] |  | defaults to undefined|
| **resourceType** | [**string**] |  | defaults to undefined|


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
|**200** | Link-format TimeMap. |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticResourceVersionRetrieve**
> semanticResourceVersionRetrieve()

Phase 230.4 (REQ-SEM-MEMENTO-001) — return the RDF body that was captured at ``snapshot_at`` for the resource. The Memento-Datetime response header carries the snapshot\'s actual timestamp.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let resourceId: string; // (default to undefined)
let resourceType: string; // (default to undefined)
let snapshotAt: string; // (default to undefined)

const { status, data } = await apiInstance.semanticResourceVersionRetrieve(
    resourceId,
    resourceType,
    snapshotAt
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **resourceId** | [**string**] |  | defaults to undefined|
| **resourceType** | [**string**] |  | defaults to undefined|
| **snapshotAt** | [**string**] |  | defaults to undefined|


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
|**200** | RDF body of the captured version. |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticSemanticResourcesList**
> PaginatedSemanticResourceList semanticSemanticResourcesList()

Read-only API endpoints for Semantic Resources.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticSemanticResourcesList(
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

**PaginatedSemanticResourceList**

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

# **semanticSemanticResourcesRetrieve**
> SemanticResource semanticSemanticResourcesRetrieve()

Read-only API endpoints for Semantic Resources.

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let id: string; //A UUID string identifying this semantic resource. (default to undefined)

const { status, data } = await apiInstance.semanticSemanticResourcesRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this semantic resource. | defaults to undefined|


### Return type

**SemanticResource**

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

# **semanticSparqlCreate**
> SPARQLQueryResponse semanticSparqlCreate(sPARQLQueryRequest)

SPARQL query endpoint.  POST /sparql Body: {     \"query\": \"SELECT ?s ?p ?o WHERE { ?s ?p ?o }\",     \"format\": \"json\",     \"timeout\": 30 }  GET /sparql?query=SELECT...

### Example

```typescript
import {
    SemanticApi,
    Configuration,
    SPARQLQueryRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

let sPARQLQueryRequest: SPARQLQueryRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.semanticSparqlCreate(
    sPARQLQueryRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **sPARQLQueryRequest** | **SPARQLQueryRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**SPARQLQueryResponse**

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

# **semanticSparqlDescriptionRetrieve**
> any semanticSparqlDescriptionRetrieve()

SPARQL 1.1 Service Description endpoint (Phase 22.5).  Returns a Turtle document describing the SPARQL endpoint capabilities. Requires authentication (Phase 219.2).

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

const { status, data } = await apiInstance.semanticSparqlDescriptionRetrieve();
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
|**503** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **semanticSparqlRetrieve**
> SPARQLQueryResponse semanticSparqlRetrieve()

SPARQL query endpoint.  POST /sparql Body: {     \"query\": \"SELECT ?s ?p ?o WHERE { ?s ?p ?o }\",     \"format\": \"json\",     \"timeout\": 30 }  GET /sparql?query=SELECT...

### Example

```typescript
import {
    SemanticApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SemanticApi(configuration);

const { status, data } = await apiInstance.semanticSparqlRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**SPARQLQueryResponse**

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

