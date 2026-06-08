# SSOApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**authSsoOidcCallbackCreate**](#authssooidccallbackcreate) | **POST** /api/v1/auth/sso/oidc/callback/ | OIDC authentication callback|
|[**authSsoOidcLoginUrlRetrieve**](#authssooidcloginurlretrieve) | **GET** /api/v1/auth/sso/oidc/login-url/ | Get OIDC login URL|
|[**authSsoSamlCallbackCreate**](#authssosamlcallbackcreate) | **POST** /api/v1/auth/sso/saml/callback/ | SAML authentication callback|
|[**authSsoSamlLoginUrlRetrieve**](#authssosamlloginurlretrieve) | **GET** /api/v1/auth/sso/saml/login-url/ | Get SAML login URL|

# **authSsoOidcCallbackCreate**
> authSsoOidcCallbackCreate()

Handle OIDC authentication callback. Tenant is resolved from signed `state` payload; request-body `tenant_id` is deprecated and ignored when matching state (mismatch is rejected).

### Example

```typescript
import {
    SSOApi,
    Configuration,
    AuthSsoOidcCallbackCreateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SSOApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let authSsoOidcCallbackCreateRequest: AuthSsoOidcCallbackCreateRequest; // (optional)

const { status, data } = await apiInstance.authSsoOidcCallbackCreate(
    idempotencyKey,
    authSsoOidcCallbackCreateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **authSsoOidcCallbackCreateRequest** | **AuthSsoOidcCallbackCreateRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Authentication successful |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **authSsoOidcLoginUrlRetrieve**
> authSsoOidcLoginUrlRetrieve()

Get OIDC SSO login URL for redirect

### Example

```typescript
import {
    SSOApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SSOApi(configuration);

let redirectUri: string; //Redirect URI after authentication (default to undefined)
let tenantId: string; //Tenant UUID (default to undefined)

const { status, data } = await apiInstance.authSsoOidcLoginUrlRetrieve(
    redirectUri,
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **redirectUri** | [**string**] | Redirect URI after authentication | defaults to undefined|
| **tenantId** | [**string**] | Tenant UUID | defaults to undefined|


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
|**200** | OIDC login URL |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **authSsoSamlCallbackCreate**
> authSsoSamlCallbackCreate()

Handle SAML authentication callback

### Example

```typescript
import {
    SSOApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SSOApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let sAMLResponse: string; // (optional) (default to undefined)
let relayState: string; // (optional) (default to undefined)

const { status, data } = await apiInstance.authSsoSamlCallbackCreate(
    idempotencyKey,
    sAMLResponse,
    relayState
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|
| **sAMLResponse** | [**string**] |  | (optional) defaults to undefined|
| **relayState** | [**string**] |  | (optional) defaults to undefined|


### Return type

void (empty response body)

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Authentication successful |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **authSsoSamlLoginUrlRetrieve**
> authSsoSamlLoginUrlRetrieve()

Get SAML SSO login URL for redirect

### Example

```typescript
import {
    SSOApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SSOApi(configuration);

let redirectUri: string; //Redirect URI after authentication (default to undefined)
let tenantId: string; //Tenant UUID (default to undefined)

const { status, data } = await apiInstance.authSsoSamlLoginUrlRetrieve(
    redirectUri,
    tenantId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **redirectUri** | [**string**] | Redirect URI after authentication | defaults to undefined|
| **tenantId** | [**string**] | Tenant UUID | defaults to undefined|


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
|**200** | SAML login URL |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

