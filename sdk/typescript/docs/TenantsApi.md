# TenantsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**getMeConfig**](#getmeconfig) | **GET** /api/v1/tenants/config/me/config/ | Get current tenant configuration|
|[**getMeConfig2**](#getmeconfig2) | **PATCH** /api/v1/tenants/config/me/config/ | Get current tenant configuration|
|[**getMeConfig3**](#getmeconfig3) | **GET** /api/v1/tenants/me/config/ | Get current tenant configuration|
|[**getMeConfig4**](#getmeconfig4) | **PATCH** /api/v1/tenants/me/config/ | Get current tenant configuration|
|[**getMeUsage**](#getmeusage) | **GET** /api/v1/tenants/config/me/usage/ | Get current tenant usage|
|[**getMeUsage2**](#getmeusage2) | **GET** /api/v1/tenants/me/usage/ | Get current tenant usage|
|[**getTenantConfig**](#gettenantconfig) | **GET** /api/v1/tenants/config/{tenant_id}/ | Get tenant configuration|
|[**getTenantConfig2**](#gettenantconfig2) | **GET** /api/v1/tenants/{tenant_id}/config/ | Get tenant configuration|
|[**tenantsConfigMeFeatureFlagHistoryRetrieve**](#tenantsconfigmefeatureflaghistoryretrieve) | **GET** /api/v1/tenants/config/me/feature-flag-history/ | |
|[**tenantsConfigMeFeatureFlagsPartialUpdate**](#tenantsconfigmefeatureflagspartialupdate) | **PATCH** /api/v1/tenants/config/me/feature-flags/ | |
|[**tenantsConfigMeFeatureFlagsRetrieve**](#tenantsconfigmefeatureflagsretrieve) | **GET** /api/v1/tenants/config/me/feature-flags/ | |
|[**tenantsConfigOnboardingCreate**](#tenantsconfigonboardingcreate) | **POST** /api/v1/tenants/config/onboarding/ | |
|[**tenantsCreate**](#tenantscreate) | **POST** /api/v1/tenants/ | |
|[**tenantsDestroy**](#tenantsdestroy) | **DELETE** /api/v1/tenants/{id}/ | |
|[**tenantsList**](#tenantslist) | **GET** /api/v1/tenants/ | |
|[**tenantsMeFeatureFlagHistoryRetrieve**](#tenantsmefeatureflaghistoryretrieve) | **GET** /api/v1/tenants/me/feature-flag-history/ | |
|[**tenantsMeFeatureFlagsPartialUpdate**](#tenantsmefeatureflagspartialupdate) | **PATCH** /api/v1/tenants/me/feature-flags/ | |
|[**tenantsMeFeatureFlagsRetrieve**](#tenantsmefeatureflagsretrieve) | **GET** /api/v1/tenants/me/feature-flags/ | |
|[**tenantsOnboardingCreate**](#tenantsonboardingcreate) | **POST** /api/v1/tenants/onboarding/ | |
|[**tenantsPartialUpdate**](#tenantspartialupdate) | **PATCH** /api/v1/tenants/{id}/ | |
|[**tenantsReactivateCreate**](#tenantsreactivatecreate) | **POST** /api/v1/tenants/{id}/reactivate/ | |
|[**tenantsRetrieve**](#tenantsretrieve) | **GET** /api/v1/tenants/{id}/ | |
|[**tenantsSparqlEndpointsCreate**](#tenantssparqlendpointscreate) | **POST** /api/v1/tenants/{tenant_id}/sparql-endpoints/ | |
|[**tenantsSparqlEndpointsDestroy**](#tenantssparqlendpointsdestroy) | **DELETE** /api/v1/tenants/{tenant_id}/sparql-endpoints/{id}/ | |
|[**tenantsSparqlEndpointsList**](#tenantssparqlendpointslist) | **GET** /api/v1/tenants/{tenant_id}/sparql-endpoints/ | |
|[**tenantsSparqlEndpointsPartialUpdate**](#tenantssparqlendpointspartialupdate) | **PATCH** /api/v1/tenants/{tenant_id}/sparql-endpoints/{id}/ | |
|[**tenantsSparqlEndpointsRetrieve**](#tenantssparqlendpointsretrieve) | **GET** /api/v1/tenants/{tenant_id}/sparql-endpoints/{id}/ | |
|[**tenantsSparqlEndpointsUpdate**](#tenantssparqlendpointsupdate) | **PUT** /api/v1/tenants/{tenant_id}/sparql-endpoints/{id}/ | |
|[**tenantsSuspendCreate**](#tenantssuspendcreate) | **POST** /api/v1/tenants/{id}/suspend/ | |
|[**tenantsUpdate**](#tenantsupdate) | **PUT** /api/v1/tenants/{id}/ | |
|[**updateTenantConfig**](#updatetenantconfig) | **PATCH** /api/v1/tenants/config/{tenant_id}/ | Update tenant configuration|
|[**updateTenantConfig2**](#updatetenantconfig2) | **PATCH** /api/v1/tenants/{tenant_id}/config/ | Update tenant configuration|

# **getMeConfig**
> TenantConfig getMeConfig()

Get tenant configuration for the authenticated user\'s tenant. Returns config with platform defaults for unset values.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.getMeConfig();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**TenantConfig**

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

# **getMeConfig2**
> TenantConfig getMeConfig2()

Get tenant configuration for the authenticated user\'s tenant. Returns config with platform defaults for unset values.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantConfigUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantConfigUpdate: PatchedTenantConfigUpdate; // (optional)

const { status, data } = await apiInstance.getMeConfig2(
    idempotencyKey,
    patchedTenantConfigUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantConfigUpdate** | **PatchedTenantConfigUpdate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantConfig**

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

# **getMeConfig3**
> TenantConfig getMeConfig3()

Get tenant configuration for the authenticated user\'s tenant. Returns config with platform defaults for unset values.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.getMeConfig3();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**TenantConfig**

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

# **getMeConfig4**
> TenantConfig getMeConfig4()

Get tenant configuration for the authenticated user\'s tenant. Returns config with platform defaults for unset values.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantConfigUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantConfigUpdate: PatchedTenantConfigUpdate; // (optional)

const { status, data } = await apiInstance.getMeConfig4(
    idempotencyKey,
    patchedTenantConfigUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantConfigUpdate** | **PatchedTenantConfigUpdate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantConfig**

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

# **getMeUsage**
> TenantUsage getMeUsage()

Get usage metrics (storage, API calls, limits) for the authenticated user\'s tenant.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.getMeUsage();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**TenantUsage**

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

# **getMeUsage2**
> TenantUsage getMeUsage2()

Get usage metrics (storage, API calls, limits) for the authenticated user\'s tenant.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.getMeUsage2();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**TenantUsage**

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

# **getTenantConfig**
> TenantConfig getTenantConfig()

Get tenant configuration with platform defaults for any unset values. Returns configuration matching API spec §13.1.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.getTenantConfig(
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantId** | [**string**] |  | defaults to undefined|


### Return type

**TenantConfig**

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

# **getTenantConfig2**
> TenantConfig getTenantConfig2()

Get tenant configuration with platform defaults for any unset values. Returns configuration matching API spec §13.1.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.getTenantConfig2(
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantId** | [**string**] |  | defaults to undefined|


### Return type

**TenantConfig**

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

# **tenantsConfigMeFeatureFlagHistoryRetrieve**
> tenantsConfigMeFeatureFlagHistoryRetrieve()

Phase 250.6.E.1 — audit-log query for the settings page.  ``GET /api/v1/tenants/me/feature-flag-history/`` — returns ``TENANT_FEATURE_FLAG_UPDATED`` rows scoped to the calling tenant. The SPA renders these as \"User X changed flag Y from <previous> to <new> at <timestamp>\" beneath the flag form so the audit history is co-located with the action.  TENANT_ADMIN-only (250.6.E.2). Cross-tenant rows are excluded by the ``tenant=tenant`` filter (existence-leak protection).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.tenantsConfigMeFeatureFlagHistoryRetrieve();
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

# **tenantsConfigMeFeatureFlagsPartialUpdate**
> tenantsConfigMeFeatureFlagsPartialUpdate()

Phase 250.6.E.1 — per-tenant capability-flags admin surface.  ``GET`` returns the current flag values + descriptions, so the SPA can render a self-describing settings page without a separate \"schema\" round-trip:      {       \"flags\": [         {\"name\": \"asset_creation_enabled\", \"value\": true,          \"description\": \"When True (default), ...\"},         ...       ]     }  ``PATCH`` accepts a partial dict of ``{flag_name: bool}`` and flips the matching ``Tenant`` columns. Each flipped flag emits a ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the before/after values for the audit-log panel below the form. Unknown flag names return HTTP 400 + ``code=\"UNKNOWN_FLAG\"`` rather than silently ignoring them — admin actions need loud rejection on typos so the operator knows their change DIDN\'T land.  Both methods require TENANT_ADMIN role (per 250.6.E.2).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsConfigMeFeatureFlagsPartialUpdate(
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

# **tenantsConfigMeFeatureFlagsRetrieve**
> tenantsConfigMeFeatureFlagsRetrieve()

Phase 250.6.E.1 — per-tenant capability-flags admin surface.  ``GET`` returns the current flag values + descriptions, so the SPA can render a self-describing settings page without a separate \"schema\" round-trip:      {       \"flags\": [         {\"name\": \"asset_creation_enabled\", \"value\": true,          \"description\": \"When True (default), ...\"},         ...       ]     }  ``PATCH`` accepts a partial dict of ``{flag_name: bool}`` and flips the matching ``Tenant`` columns. Each flipped flag emits a ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the before/after values for the audit-log panel below the form. Unknown flag names return HTTP 400 + ``code=\"UNKNOWN_FLAG\"`` rather than silently ignoring them — admin actions need loud rejection on typos so the operator knows their change DIDN\'T land.  Both methods require TENANT_ADMIN role (per 250.6.E.2).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.tenantsConfigMeFeatureFlagsRetrieve();
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

# **tenantsConfigOnboardingCreate**
> tenantsConfigOnboardingCreate()

Tenant creation with first user (Platform Admin only).  POST /api/v1/tenants/onboarding/ Requires: IsAuthenticated + PLATFORM_ADMIN role. Body: {     \"name\": \"My Company\",     \"slug\": \"my-company\",     \"plan_slug\": \"free\",  # Optional, defaults to \"free\"     \"first_user\": {         \"email\": \"admin@example.com\",         \"password\": \"securepassword123\",         \"display_name\": \"Admin User\"  # Optional     },     \"region\": \"us-east-1\"  # Optional }  Creates: - Tenant with specified plan - First user (tenant admin) - TenantConfig with platform defaults - Stripe customer and subscription (if not FREE plan)

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsConfigOnboardingCreate(
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

# **tenantsCreate**
> TenantCreate tenantsCreate(tenantCreate)

Create a new tenant.  Creates tenant with ACTIVE status and UNVERIFIED KYC status. Default roles are created via signal. Events are published automatically via TenantService.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    TenantCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantCreate: TenantCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsCreate(
    tenantCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantCreate** | **TenantCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantCreate**

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

# **tenantsDestroy**
> tenantsDestroy()

Delete a tenant (soft delete).  Sets status to DELETED and blocks all access. Data retention period begins (default: 30 days). Events are published automatically via TenantService.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)

const { status, data } = await apiInstance.tenantsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|


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

# **tenantsList**
> PaginatedTenantList tenantsList()

List tenants (paginated)

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsList(
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

**PaginatedTenantList**

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

# **tenantsMeFeatureFlagHistoryRetrieve**
> tenantsMeFeatureFlagHistoryRetrieve()

Phase 250.6.E.1 — audit-log query for the settings page.  ``GET /api/v1/tenants/me/feature-flag-history/`` — returns ``TENANT_FEATURE_FLAG_UPDATED`` rows scoped to the calling tenant. The SPA renders these as \"User X changed flag Y from <previous> to <new> at <timestamp>\" beneath the flag form so the audit history is co-located with the action.  TENANT_ADMIN-only (250.6.E.2). Cross-tenant rows are excluded by the ``tenant=tenant`` filter (existence-leak protection).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.tenantsMeFeatureFlagHistoryRetrieve();
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

# **tenantsMeFeatureFlagsPartialUpdate**
> tenantsMeFeatureFlagsPartialUpdate()

Phase 250.6.E.1 — per-tenant capability-flags admin surface.  ``GET`` returns the current flag values + descriptions, so the SPA can render a self-describing settings page without a separate \"schema\" round-trip:      {       \"flags\": [         {\"name\": \"asset_creation_enabled\", \"value\": true,          \"description\": \"When True (default), ...\"},         ...       ]     }  ``PATCH`` accepts a partial dict of ``{flag_name: bool}`` and flips the matching ``Tenant`` columns. Each flipped flag emits a ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the before/after values for the audit-log panel below the form. Unknown flag names return HTTP 400 + ``code=\"UNKNOWN_FLAG\"`` rather than silently ignoring them — admin actions need loud rejection on typos so the operator knows their change DIDN\'T land.  Both methods require TENANT_ADMIN role (per 250.6.E.2).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsMeFeatureFlagsPartialUpdate(
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

# **tenantsMeFeatureFlagsRetrieve**
> tenantsMeFeatureFlagsRetrieve()

Phase 250.6.E.1 — per-tenant capability-flags admin surface.  ``GET`` returns the current flag values + descriptions, so the SPA can render a self-describing settings page without a separate \"schema\" round-trip:      {       \"flags\": [         {\"name\": \"asset_creation_enabled\", \"value\": true,          \"description\": \"When True (default), ...\"},         ...       ]     }  ``PATCH`` accepts a partial dict of ``{flag_name: bool}`` and flips the matching ``Tenant`` columns. Each flipped flag emits a ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the before/after values for the audit-log panel below the form. Unknown flag names return HTTP 400 + ``code=\"UNKNOWN_FLAG\"`` rather than silently ignoring them — admin actions need loud rejection on typos so the operator knows their change DIDN\'T land.  Both methods require TENANT_ADMIN role (per 250.6.E.2).

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

const { status, data } = await apiInstance.tenantsMeFeatureFlagsRetrieve();
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

# **tenantsOnboardingCreate**
> tenantsOnboardingCreate()

Tenant creation with first user (Platform Admin only).  POST /api/v1/tenants/onboarding/ Requires: IsAuthenticated + PLATFORM_ADMIN role. Body: {     \"name\": \"My Company\",     \"slug\": \"my-company\",     \"plan_slug\": \"free\",  # Optional, defaults to \"free\"     \"first_user\": {         \"email\": \"admin@example.com\",         \"password\": \"securepassword123\",         \"display_name\": \"Admin User\"  # Optional     },     \"region\": \"us-east-1\"  # Optional }  Creates: - Tenant with specified plan - First user (tenant admin) - TenantConfig with platform defaults - Stripe customer and subscription (if not FREE plan)

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsOnboardingCreate(
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

# **tenantsPartialUpdate**
> TenantUpdate tenantsPartialUpdate()

Update tenant (partial update).  Events are published automatically via TenantService.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantUpdate: PatchedTenantUpdate; // (optional)

const { status, data } = await apiInstance.tenantsPartialUpdate(
    id,
    idempotencyKey,
    patchedTenantUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantUpdate** | **PatchedTenantUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantUpdate**

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

# **tenantsReactivateCreate**
> Tenant tenantsReactivateCreate(tenant)

Reactivate a suspended tenant.  Sets status to ACTIVE and restores write operations. Sends notification to tenant admins.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    Tenant
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)
let tenant: Tenant; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsReactivateCreate(
    id,
    tenant,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenant** | **Tenant**|  | |
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Tenant**

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

# **tenantsRetrieve**
> Tenant tenantsRetrieve()

Retrieve tenant by ID

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)

const { status, data } = await apiInstance.tenantsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|


### Return type

**Tenant**

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

# **tenantsSparqlEndpointsCreate**
> TenantSparqlEndpoint tenantsSparqlEndpointsCreate(tenantSparqlEndpoint)

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    TenantSparqlEndpoint
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)
let tenantSparqlEndpoint: TenantSparqlEndpoint; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsSparqlEndpointsCreate(
    tenantId,
    tenantSparqlEndpoint,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantSparqlEndpoint** | **TenantSparqlEndpoint**|  | |
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantSparqlEndpoint**

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

# **tenantsSparqlEndpointsDestroy**
> tenantsSparqlEndpointsDestroy()

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; // (default to undefined)
let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.tenantsSparqlEndpointsDestroy(
    id,
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|
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
|**204** | No response body |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **tenantsSparqlEndpointsList**
> PaginatedTenantSparqlEndpointList tenantsSparqlEndpointsList()

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsSparqlEndpointsList(
    tenantId,
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantId** | [**string**] |  | defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|


### Return type

**PaginatedTenantSparqlEndpointList**

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

# **tenantsSparqlEndpointsPartialUpdate**
> TenantSparqlEndpoint tenantsSparqlEndpointsPartialUpdate()

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantSparqlEndpoint
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; // (default to undefined)
let tenantId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantSparqlEndpoint: PatchedTenantSparqlEndpoint; // (optional)

const { status, data } = await apiInstance.tenantsSparqlEndpointsPartialUpdate(
    id,
    tenantId,
    idempotencyKey,
    patchedTenantSparqlEndpoint
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantSparqlEndpoint** | **PatchedTenantSparqlEndpoint**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantSparqlEndpoint**

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

# **tenantsSparqlEndpointsRetrieve**
> TenantSparqlEndpoint tenantsSparqlEndpointsRetrieve()

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; // (default to undefined)
let tenantId: string; // (default to undefined)

const { status, data } = await apiInstance.tenantsSparqlEndpointsRetrieve(
    id,
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|
| **tenantId** | [**string**] |  | defaults to undefined|


### Return type

**TenantSparqlEndpoint**

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

# **tenantsSparqlEndpointsUpdate**
> TenantSparqlEndpoint tenantsSparqlEndpointsUpdate(tenantSparqlEndpoint)

CRUD over per-tenant SPARQL federation allowlist.  Mounted at ``/api/v1/tenants/<tenant_id>/sparql-endpoints/``. TENANT_ADMIN-only (PLATFORM_ADMIN inherits via the role check).  Cross-tenant attempts return ``404`` (info-leak hardening: a TENANT_ADMIN of tenant A SHALL NOT learn whether tenant B exists by poking this URL).  POST validates SSRF against the webhook guard\'s blocked-network frozenset and returns a JSON body with a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``) so the frontend can surface a user-friendly error.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    TenantSparqlEndpoint
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; // (default to undefined)
let tenantId: string; // (default to undefined)
let tenantSparqlEndpoint: TenantSparqlEndpoint; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsSparqlEndpointsUpdate(
    id,
    tenantId,
    tenantSparqlEndpoint,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantSparqlEndpoint** | **TenantSparqlEndpoint**|  | |
| **id** | [**string**] |  | defaults to undefined|
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantSparqlEndpoint**

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

# **tenantsSuspendCreate**
> Tenant tenantsSuspendCreate(tenant)

Suspend a tenant.  Sets status to SUSPENDED and blocks write operations. Sends notification to tenant admins.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    Tenant
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)
let tenant: Tenant; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsSuspendCreate(
    id,
    tenant,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenant** | **Tenant**|  | |
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Tenant**

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

# **tenantsUpdate**
> TenantUpdate tenantsUpdate(tenantUpdate)

Update tenant (full update).  Events are published automatically via TenantService.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    TenantUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let id: string; //A UUID string identifying this tenant. (default to undefined)
let tenantUpdate: TenantUpdate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.tenantsUpdate(
    id,
    tenantUpdate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **tenantUpdate** | **TenantUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this tenant. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantUpdate**

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

# **updateTenantConfig**
> TenantConfig updateTenantConfig()

Update tenant configuration (partial update). Updates only the provided fields, leaving others unchanged. Returns updated configuration matching API spec §13.2.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantConfigUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantConfigUpdate: PatchedTenantConfigUpdate; // (optional)

const { status, data } = await apiInstance.updateTenantConfig(
    tenantId,
    idempotencyKey,
    patchedTenantConfigUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantConfigUpdate** | **PatchedTenantConfigUpdate**|  | |
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantConfig**

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

# **updateTenantConfig2**
> TenantConfig updateTenantConfig2()

Update tenant configuration (partial update). Updates only the provided fields, leaving others unchanged. Returns updated configuration matching API spec §13.2.

### Example

```typescript
import {
    TenantsApi,
    Configuration,
    PatchedTenantConfigUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new TenantsApi(configuration);

let tenantId: string; // (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedTenantConfigUpdate: PatchedTenantConfigUpdate; // (optional)

const { status, data } = await apiInstance.updateTenantConfig2(
    tenantId,
    idempotencyKey,
    patchedTenantConfigUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedTenantConfigUpdate** | **PatchedTenantConfigUpdate**|  | |
| **tenantId** | [**string**] |  | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**TenantConfig**

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

