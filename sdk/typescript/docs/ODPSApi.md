# ODPSApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**contractsGenerateOdpsCreate**](#contractsgenerateodpscreate) | **POST** /api/v1/contracts/{id}/generate-odps/ | Generate ODPS document|
|[**contractsPaymentGatewaysRetrieve**](#contractspaymentgatewaysretrieve) | **GET** /api/v1/contracts/{id}/payment-gateways/ | Get payment gateways|
|[**contractsProductDetailsRetrieve**](#contractsproductdetailsretrieve) | **GET** /api/v1/contracts/{id}/product-details/ | Get product details|
|[**contractsProductStrategyRetrieve**](#contractsproductstrategyretrieve) | **GET** /api/v1/contracts/{id}/product-strategy/ | Get product strategy|

# **contractsGenerateOdpsCreate**
> GenerateODPSResponse contractsGenerateOdpsCreate()

         Generate ODPS (Open Data Product Standard) document from HubContract.          This endpoint generates an ODPS document from the contract\'s HubContract representation,         focusing on marketplace metadata. The generated ODPS document can be used for         marketplace listings and product catalogs.          **Request Body (optional):**         - `target_version` (string, optional): Target ODPS version (default: \"4.1\")         - `output_format` (string, optional): Output format - \"json\" or \"yaml\" (default: \"json\")         - `embed_odcs` (boolean, optional): If true and contract is ODCS, embed original ODCS           contract inline in product.contract.spec (default: true)          **Behavior:**         - Generates ODPS from HubContract (marketplace metadata)         - If contract is ODCS and has original_raw, optionally embeds ODCS in product.contract.spec         - Returns generated ODPS document in requested format          **Response:**         - Returns generated ODPS document as JSON or YAML         - Content-Type header set based on output_format         

### Example

```typescript
import {
    ODPSApi,
    Configuration,
    GenerateODPSRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new ODPSApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let generateODPSRequest: GenerateODPSRequest; // (optional)

const { status, data } = await apiInstance.contractsGenerateOdpsCreate(
    id,
    idempotencyKey,
    generateODPSRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **generateODPSRequest** | **GenerateODPSRequest**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**GenerateODPSResponse**

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
|**500** | Internal Server Error |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsPaymentGatewaysRetrieve**
> PaymentGatewaysResponse contractsPaymentGatewaysRetrieve()

         Get payment gateways from ODPS contract.          Returns all payment gateways configured in the contract.         

### Example

```typescript
import {
    ODPSApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ODPSApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsPaymentGatewaysRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


### Return type

**PaymentGatewaysResponse**

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

# **contractsProductDetailsRetrieve**
> ProductDetailsResponse contractsProductDetailsRetrieve()

         Get product details from an ODPS contract for a specific language.          Returns the product details configured in the contract for the specified language.         

### Example

```typescript
import {
    ODPSApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ODPSApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let lang: string; //Language code (ISO 639-1, e.g., \'en\', \'fi\', \'es\') (default to undefined)

const { status, data } = await apiInstance.contractsProductDetailsRetrieve(
    id,
    lang
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **lang** | [**string**] | Language code (ISO 639-1, e.g., \&#39;en\&#39;, \&#39;fi\&#39;, \&#39;es\&#39;) | defaults to undefined|


### Return type

**ProductDetailsResponse**

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

# **contractsProductStrategyRetrieve**
> ProductStrategyResponse contractsProductStrategyRetrieve()

         Get product strategy from an ODPS contract (ODPS 4.1+).          Returns the product strategy configured in the contract.         

### Example

```typescript
import {
    ODPSApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ODPSApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsProductStrategyRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


### Return type

**ProductStrategyResponse**

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

