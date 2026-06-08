# AccessCertificationApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**governanceAccessCertificationsExpiringRetrieve**](#governanceaccesscertificationsexpiringretrieve) | **GET** /api/v1/governance/access/certifications/expiring/ | Get expiring certifications|
|[**governanceAccessCertificationsInitiateReviewCreate**](#governanceaccesscertificationsinitiatereviewcreate) | **POST** /api/v1/governance/access/certifications/initiate-review/ | Initiate periodic review|
|[**governanceAccessCertificationsReviewCreate**](#governanceaccesscertificationsreviewcreate) | **POST** /api/v1/governance/access/certifications/{id}/review/ | Review certification|
|[**governanceAccessCertificationsSummaryRetrieve**](#governanceaccesscertificationssummaryretrieve) | **GET** /api/v1/governance/access/certifications/summary/ | Get certification summary|
|[**governanceCertificationsExpiringRetrieve**](#governancecertificationsexpiringretrieve) | **GET** /api/v1/governance/certifications/expiring/ | Get expiring certifications|
|[**governanceCertificationsInitiateReviewCreate**](#governancecertificationsinitiatereviewcreate) | **POST** /api/v1/governance/certifications/initiate-review/ | Initiate periodic review|
|[**governanceCertificationsReviewCreate**](#governancecertificationsreviewcreate) | **POST** /api/v1/governance/certifications/{id}/review/ | Review certification|
|[**governanceCertificationsSummaryRetrieve**](#governancecertificationssummaryretrieve) | **GET** /api/v1/governance/certifications/summary/ | Get certification summary|

# **governanceAccessCertificationsExpiringRetrieve**
> governanceAccessCertificationsExpiringRetrieve()

Get certifications expiring within specified days

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let daysAhead: number; //Days ahead to check (default: 30) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceAccessCertificationsExpiringRetrieve(
    daysAhead
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **daysAhead** | [**number**] | Days ahead to check (default: 30) | (optional) defaults to undefined|


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
|**200** | List of expiring certifications |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessCertificationsInitiateReviewCreate**
> governanceAccessCertificationsInitiateReviewCreate()

Initiate a periodic access review for a user

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration,
    GovernanceAccessCertificationsInitiateReviewCreateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let governanceAccessCertificationsInitiateReviewCreateRequest: GovernanceAccessCertificationsInitiateReviewCreateRequest; // (optional)

const { status, data } = await apiInstance.governanceAccessCertificationsInitiateReviewCreate(
    idempotencyKey,
    governanceAccessCertificationsInitiateReviewCreateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **governanceAccessCertificationsInitiateReviewCreateRequest** | **GovernanceAccessCertificationsInitiateReviewCreateRequest**|  | |
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
|**201** | Review initiated |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessCertificationsReviewCreate**
> governanceAccessCertificationsReviewCreate()

Review and approve/reject a certification

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration,
    GovernanceAccessCertificationsReviewCreateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let governanceAccessCertificationsReviewCreateRequest: GovernanceAccessCertificationsReviewCreateRequest; // (optional)

const { status, data } = await apiInstance.governanceAccessCertificationsReviewCreate(
    id,
    idempotencyKey,
    governanceAccessCertificationsReviewCreateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **governanceAccessCertificationsReviewCreateRequest** | **GovernanceAccessCertificationsReviewCreateRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
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
|**200** | Certification reviewed |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceAccessCertificationsSummaryRetrieve**
> governanceAccessCertificationsSummaryRetrieve()

Get certification summary statistics

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

const { status, data } = await apiInstance.governanceAccessCertificationsSummaryRetrieve();
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
|**200** | Certification summary |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceCertificationsExpiringRetrieve**
> governanceCertificationsExpiringRetrieve()

Get certifications expiring within specified days

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let daysAhead: number; //Days ahead to check (default: 30) (optional) (default to undefined)

const { status, data } = await apiInstance.governanceCertificationsExpiringRetrieve(
    daysAhead
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **daysAhead** | [**number**] | Days ahead to check (default: 30) | (optional) defaults to undefined|


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
|**200** | List of expiring certifications |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceCertificationsInitiateReviewCreate**
> governanceCertificationsInitiateReviewCreate()

Initiate a periodic access review for a user

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration,
    GovernanceAccessCertificationsInitiateReviewCreateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let governanceAccessCertificationsInitiateReviewCreateRequest: GovernanceAccessCertificationsInitiateReviewCreateRequest; // (optional)

const { status, data } = await apiInstance.governanceCertificationsInitiateReviewCreate(
    idempotencyKey,
    governanceAccessCertificationsInitiateReviewCreateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **governanceAccessCertificationsInitiateReviewCreateRequest** | **GovernanceAccessCertificationsInitiateReviewCreateRequest**|  | |
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
|**201** | Review initiated |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceCertificationsReviewCreate**
> governanceCertificationsReviewCreate()

Review and approve/reject a certification

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration,
    GovernanceAccessCertificationsReviewCreateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

let id: string; //A UUID string identifying this access certification. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let governanceAccessCertificationsReviewCreateRequest: GovernanceAccessCertificationsReviewCreateRequest; // (optional)

const { status, data } = await apiInstance.governanceCertificationsReviewCreate(
    id,
    idempotencyKey,
    governanceAccessCertificationsReviewCreateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **governanceAccessCertificationsReviewCreateRequest** | **GovernanceAccessCertificationsReviewCreateRequest**|  | |
| **id** | [**string**] | A UUID string identifying this access certification. | defaults to undefined|
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
|**200** | Certification reviewed |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **governanceCertificationsSummaryRetrieve**
> governanceCertificationsSummaryRetrieve()

Get certification summary statistics

### Example

```typescript
import {
    AccessCertificationApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new AccessCertificationApi(configuration);

const { status, data } = await apiInstance.governanceCertificationsSummaryRetrieve();
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
|**200** | Certification summary |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

