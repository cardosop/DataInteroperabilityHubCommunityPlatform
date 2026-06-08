# MarketplaceApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**downloadMarketplaceContract**](#downloadmarketplacecontract) | **GET** /api/v1/marketplace/listings/{id}/download/ | |
|[**listingLineage**](#listinglineage) | **GET** /api/v1/marketplace/listings/{id}/lineage/ | Lineage graph for a listing\&#39;s backing asset (Phase 228.F1)|
|[**marketplaceConfigTrustSignalsCreate**](#marketplaceconfigtrustsignalscreate) | **POST** /api/v1/marketplace/config/trust-signals/ | |
|[**marketplaceConfigTrustSignalsDestroy**](#marketplaceconfigtrustsignalsdestroy) | **DELETE** /api/v1/marketplace/config/trust-signals/{id}/ | |
|[**marketplaceConfigTrustSignalsList**](#marketplaceconfigtrustsignalslist) | **GET** /api/v1/marketplace/config/trust-signals/ | |
|[**marketplaceConfigTrustSignalsPartialUpdate**](#marketplaceconfigtrustsignalspartialupdate) | **PATCH** /api/v1/marketplace/config/trust-signals/{id}/ | |
|[**marketplaceConfigTrustSignalsRetrieve**](#marketplaceconfigtrustsignalsretrieve) | **GET** /api/v1/marketplace/config/trust-signals/{id}/ | |
|[**marketplaceConfigTrustSignalsUpdate**](#marketplaceconfigtrustsignalsupdate) | **PUT** /api/v1/marketplace/config/trust-signals/{id}/ | |
|[**marketplaceEntitlementsCheckAccessCreate**](#marketplaceentitlementscheckaccesscreate) | **POST** /api/v1/marketplace/entitlements/check-access/ | |
|[**marketplaceEntitlementsList**](#marketplaceentitlementslist) | **GET** /api/v1/marketplace/entitlements/ | |
|[**marketplaceEntitlementsRetrieve**](#marketplaceentitlementsretrieve) | **GET** /api/v1/marketplace/entitlements/{id}/ | |
|[**marketplaceEntitlementsRevokeCreate**](#marketplaceentitlementsrevokecreate) | **POST** /api/v1/marketplace/entitlements/{id}/revoke/ | |
|[**marketplaceListingsCreate**](#marketplacelistingscreate) | **POST** /api/v1/marketplace/listings/ | |
|[**marketplaceListingsDestroy**](#marketplacelistingsdestroy) | **DELETE** /api/v1/marketplace/listings/{id}/ | |
|[**marketplaceListingsList**](#marketplacelistingslist) | **GET** /api/v1/marketplace/listings/ | |
|[**marketplaceListingsPartialUpdate**](#marketplacelistingspartialupdate) | **PATCH** /api/v1/marketplace/listings/{id}/ | |
|[**marketplaceListingsRetrieve**](#marketplacelistingsretrieve) | **GET** /api/v1/marketplace/listings/{id}/ | |
|[**marketplaceListingsSearchRetrieve**](#marketplacelistingssearchretrieve) | **GET** /api/v1/marketplace/listings/search/ | |
|[**marketplaceListingsUpdate**](#marketplacelistingsupdate) | **PUT** /api/v1/marketplace/listings/{id}/ | |
|[**marketplaceOrdersApproveCreate**](#marketplaceordersapprovecreate) | **POST** /api/v1/marketplace/orders/{id}/approve/ | |
|[**marketplaceOrdersCancelCreate**](#marketplaceorderscancelcreate) | **POST** /api/v1/marketplace/orders/{id}/cancel/ | |
|[**marketplaceOrdersConfirmPaymentCreate**](#marketplaceordersconfirmpaymentcreate) | **POST** /api/v1/marketplace/orders/{id}/confirm-payment/ | Poll Stripe payment and complete order after 3DS|
|[**marketplaceOrdersCreate**](#marketplaceorderscreate) | **POST** /api/v1/marketplace/orders/ | |
|[**marketplaceOrdersDestroy**](#marketplaceordersdestroy) | **DELETE** /api/v1/marketplace/orders/{id}/ | |
|[**marketplaceOrdersList**](#marketplaceorderslist) | **GET** /api/v1/marketplace/orders/ | |
|[**marketplaceOrdersPartialUpdate**](#marketplaceorderspartialupdate) | **PATCH** /api/v1/marketplace/orders/{id}/ | |
|[**marketplaceOrdersPurchaseCreate**](#marketplaceorderspurchasecreate) | **POST** /api/v1/marketplace/orders/purchase/ | |
|[**marketplaceOrdersRefundCreate**](#marketplaceordersrefundcreate) | **POST** /api/v1/marketplace/orders/{id}/refund/ | Refund a succeeded marketplace payment|
|[**marketplaceOrdersRejectCreate**](#marketplaceordersrejectcreate) | **POST** /api/v1/marketplace/orders/{id}/reject/ | |
|[**marketplaceOrdersRetrieve**](#marketplaceordersretrieve) | **GET** /api/v1/marketplace/orders/{id}/ | |
|[**marketplaceOrdersUpdate**](#marketplaceordersupdate) | **PUT** /api/v1/marketplace/orders/{id}/ | |
|[**previewMarketplaceListing**](#previewmarketplacelisting) | **GET** /api/v1/marketplace/listings/{id}/preview/ | |

# **downloadMarketplaceContract**
> ContractDownloadResponse downloadMarketplaceContract()

Download contract from marketplace listing.  GET /api/v1/marketplace/listings/{id}/download/  Query Parameters: - format: odps|odcs|hubcontract|original (default: original) - output_format: json|yaml (default: json)  Returns the contract file for a marketplace listing in the requested format. Requires active entitlement for cross-tenant access.  Supported formats: - original: Original contract format (from original_raw) - hubcontract: HubContract normalized format - odcs: ODCS format (from original_raw or generated) - odps: ODPS 4.1 format (generated from HubContract)

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)

const { status, data } = await apiInstance.downloadMarketplaceContract(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|


### Return type

**ContractDownloadResponse**

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

# **listingLineage**
> listingLineage()

Cross-tenant marketplace lineage. Two detail tiers — `summary` (pre-purchase, IP-stripped) and `full` (post-purchase, transformation IP included; requires an ACTIVE entitlement). When the capability flag `lineage.cross_tenant_marketplace` is off the endpoint returns 404 (intentional information-leak hardening — NOT 403). Rate-limited per-user (60/min) and per-tenant (600/min). Cross-tenant accesses emit a `LINEAGE_VIEWED_CROSS_TENANT` audit event de-duplicated to 1 row per (consumer, listing) per hour.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)

const { status, data } = await apiInstance.listingLineage(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|


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
|**200** | Lineage graph |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **marketplaceConfigTrustSignalsCreate**
> TrustSignalConfig marketplaceConfigTrustSignalsCreate(trustSignalConfig)

Create trust signal config; 403 when trust_signals_enabled=False; 400 on duplicate.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    TrustSignalConfig
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let trustSignalConfig: TrustSignalConfig; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsCreate(
    trustSignalConfig,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **trustSignalConfig** | **TrustSignalConfig**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TrustSignalConfig**

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

# **marketplaceConfigTrustSignalsDestroy**
> marketplaceConfigTrustSignalsDestroy()

Delete trust signal config; 403 when trust_signals_enabled=False.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this trust signal config. (default to undefined)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this trust signal config. | defaults to undefined|


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

# **marketplaceConfigTrustSignalsList**
> PaginatedTrustSignalConfigList marketplaceConfigTrustSignalsList()

CRUD for tenant-scoped trust signal definitions (badges, quality SLAs).  Supports UC-MKT-ADV-003 (Manage Trust Signals) and UC-MKT-ADV-005 (Configure Data Quality SLAs). List/create at GET/POST /api/v1/marketplace/config/trust-signals/; retrieve/update/delete at GET/PUT/PATCH/DELETE /api/v1/marketplace/config/trust-signals/{id}/.  Respects tenant config trust_signals_enabled (Phase 11): when False, list returns empty and create/update/delete return 403.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsList(
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

**PaginatedTrustSignalConfigList**

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

# **marketplaceConfigTrustSignalsPartialUpdate**
> TrustSignalConfig marketplaceConfigTrustSignalsPartialUpdate()

CRUD for tenant-scoped trust signal definitions (badges, quality SLAs).  Supports UC-MKT-ADV-003 (Manage Trust Signals) and UC-MKT-ADV-005 (Configure Data Quality SLAs). List/create at GET/POST /api/v1/marketplace/config/trust-signals/; retrieve/update/delete at GET/PUT/PATCH/DELETE /api/v1/marketplace/config/trust-signals/{id}/.  Respects tenant config trust_signals_enabled (Phase 11): when False, list returns empty and create/update/delete return 403.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    PatchedTrustSignalConfig
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this trust signal config. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTrustSignalConfig: PatchedTrustSignalConfig; // (optional)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsPartialUpdate(
    id,
    idempotencyKey,
    patchedTrustSignalConfig
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTrustSignalConfig** | **PatchedTrustSignalConfig**|  | |
| **id** | [**string**] | A UUID string identifying this trust signal config. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TrustSignalConfig**

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

# **marketplaceConfigTrustSignalsRetrieve**
> TrustSignalConfig marketplaceConfigTrustSignalsRetrieve()

Retrieve trust signal config; 403 when trust_signals_enabled=False.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this trust signal config. (default to undefined)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this trust signal config. | defaults to undefined|


### Return type

**TrustSignalConfig**

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

# **marketplaceConfigTrustSignalsUpdate**
> TrustSignalConfig marketplaceConfigTrustSignalsUpdate(trustSignalConfig)

Update trust signal config; 403 when trust_signals_enabled=False; 400 if name duplicate.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    TrustSignalConfig
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this trust signal config. (default to undefined)
let trustSignalConfig: TrustSignalConfig; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceConfigTrustSignalsUpdate(
    id,
    trustSignalConfig,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **trustSignalConfig** | **TrustSignalConfig**|  | |
| **id** | [**string**] | A UUID string identifying this trust signal config. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TrustSignalConfig**

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

# **marketplaceEntitlementsCheckAccessCreate**
> Entitlement marketplaceEntitlementsCheckAccessCreate(entitlement)

Check if tenant has access to an asset via entitlement. POST /entitlements/check-access Body: {     \"asset_id\": \"uuid\" }

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Entitlement
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let entitlement: Entitlement; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceEntitlementsCheckAccessCreate(
    entitlement,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **entitlement** | **Entitlement**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Entitlement**

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

# **marketplaceEntitlementsList**
> PaginatedEntitlementList marketplaceEntitlementsList()

API endpoints for managing Marketplace Entitlements.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceEntitlementsList(
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

**PaginatedEntitlementList**

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

# **marketplaceEntitlementsRetrieve**
> Entitlement marketplaceEntitlementsRetrieve()

Retrieve an entitlement. GET /entitlements/{id}

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this entitlement. (default to undefined)

const { status, data } = await apiInstance.marketplaceEntitlementsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this entitlement. | defaults to undefined|


### Return type

**Entitlement**

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

# **marketplaceEntitlementsRevokeCreate**
> Entitlement marketplaceEntitlementsRevokeCreate(entitlement)

Revoke an entitlement (provider side). POST /entitlements/{id}/revoke

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Entitlement
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this entitlement. (default to undefined)
let entitlement: Entitlement; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceEntitlementsRevokeCreate(
    id,
    entitlement,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **entitlement** | **Entitlement**|  | |
| **id** | [**string**] | A UUID string identifying this entitlement. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Entitlement**

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

# **marketplaceListingsCreate**
> ListingCreate marketplaceListingsCreate(listingCreate)

Create a new listing. POST /marketplace/listings All mutations go through MarketplaceService; business rules run in service.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    ListingCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let listingCreate: ListingCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceListingsCreate(
    listingCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **listingCreate** | **ListingCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ListingCreate**

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

# **marketplaceListingsDestroy**
> marketplaceListingsDestroy()

Delete a listing (soft delete). DELETE /marketplace/listings/{id} All mutations go through MarketplaceService; business rules run in service.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)

const { status, data } = await apiInstance.marketplaceListingsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|


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

# **marketplaceListingsList**
> PaginatedListingList marketplaceListingsList()

API endpoints for managing Marketplace Listings.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceListingsList(
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

**PaginatedListingList**

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

# **marketplaceListingsPartialUpdate**
> ListingUpdate marketplaceListingsPartialUpdate()

API endpoints for managing Marketplace Listings.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    PatchedListingUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedListingUpdate: PatchedListingUpdate; // (optional)

const { status, data } = await apiInstance.marketplaceListingsPartialUpdate(
    id,
    idempotencyKey,
    patchedListingUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedListingUpdate** | **PatchedListingUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ListingUpdate**

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

# **marketplaceListingsRetrieve**
> Listing marketplaceListingsRetrieve()

Retrieve a listing with caching.  GET /marketplace/listings/{id}

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)

const { status, data } = await apiInstance.marketplaceListingsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|


### Return type

**Listing**

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

# **marketplaceListingsSearchRetrieve**
> Listing marketplaceListingsSearchRetrieve()

Search public listings. GET /marketplace/listings/search

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

const { status, data } = await apiInstance.marketplaceListingsSearchRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Listing**

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

# **marketplaceListingsUpdate**
> ListingUpdate marketplaceListingsUpdate()

Update a listing. PATCH /marketplace/listings/{id} All mutations go through MarketplaceService; business rules run in service.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    ListingUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let listingUpdate: ListingUpdate; // (optional)

const { status, data } = await apiInstance.marketplaceListingsUpdate(
    id,
    idempotencyKey,
    listingUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **listingUpdate** | **ListingUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ListingUpdate**

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

# **marketplaceOrdersApproveCreate**
> Order marketplaceOrdersApproveCreate(order)

Approve an order (provider side). POST /marketplace/orders/{id}/approve

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersApproveCreate(
    id,
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersCancelCreate**
> Order marketplaceOrdersCancelCreate(order)

Cancel an order (consumer side). POST /marketplace/orders/{id}/cancel

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersCancelCreate(
    id,
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersConfirmPaymentCreate**
> Order marketplaceOrdersConfirmPaymentCreate(order)

POST /marketplace/orders/{id}/confirm-payment/

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersConfirmPaymentCreate(
    id,
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersCreate**
> OrderCreate marketplaceOrdersCreate(orderCreate)

Create a new order. POST /marketplace/orders

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    OrderCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let orderCreate: OrderCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersCreate(
    orderCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **orderCreate** | **OrderCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**OrderCreate**

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

# **marketplaceOrdersDestroy**
> marketplaceOrdersDestroy()

API endpoints for managing Marketplace Orders.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|


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

# **marketplaceOrdersList**
> PaginatedOrderList marketplaceOrdersList()

List orders. GET /marketplace/orders

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersList(
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

**PaginatedOrderList**

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

# **marketplaceOrdersPartialUpdate**
> Order marketplaceOrdersPartialUpdate()

API endpoints for managing Marketplace Orders.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    PatchedOrder
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedOrder: PatchedOrder; // (optional)

const { status, data } = await apiInstance.marketplaceOrdersPartialUpdate(
    id,
    idempotencyKey,
    patchedOrder
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedOrder** | **PatchedOrder**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersPurchaseCreate**
> Order marketplaceOrdersPurchaseCreate(order)

Create order with payment processing and entitlement creation (internal purchase). POST /marketplace/orders/purchase  This endpoint: 1. Creates an order 2. Processes payment via payment gateway 3. Approves the order 4. Creates entitlement 5. Returns order, payment, and entitlement details

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersPurchaseCreate(
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersRefundCreate**
> Order marketplaceOrdersRefundCreate(refund)

POST /marketplace/orders/{id}/refund/

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Refund
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let refund: Refund; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersRefundCreate(
    id,
    refund,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **refund** | **Refund**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersRejectCreate**
> Order marketplaceOrdersRejectCreate(order)

Reject an order (provider side). POST /marketplace/orders/{id}/reject

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersRejectCreate(
    id,
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersRetrieve**
> Order marketplaceOrdersRetrieve()

Retrieve an order. GET /marketplace/orders/{id}

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|


### Return type

**Order**

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

# **marketplaceOrdersUpdate**
> Order marketplaceOrdersUpdate(order)

API endpoints for managing Marketplace Orders.

### Example

```typescript
import {
    MarketplaceApi,
    Configuration,
    Order
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this order. (default to undefined)
let order: Order; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.marketplaceOrdersUpdate(
    id,
    order,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **order** | **Order**|  | |
| **id** | [**string**] | A UUID string identifying this order. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Order**

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

# **previewMarketplaceListing**
> DataPreviewResponse previewMarketplaceListing()

Preview data before purchase.  GET /api/v1/marketplace/listings/{id}/preview/  Returns sample data, quality metrics, and schema preview for a marketplace listing. Performance target: < 2000ms p95

### Example

```typescript
import {
    MarketplaceApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new MarketplaceApi(configuration);

let id: string; //A UUID string identifying this listing. (default to undefined)

const { status, data } = await apiInstance.previewMarketplaceListing(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this listing. | defaults to undefined|


### Return type

**DataPreviewResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

