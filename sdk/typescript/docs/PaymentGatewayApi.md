# PaymentGatewayApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**getPaymentGatewayWebhookUrl**](#getpaymentgatewaywebhookurl) | **GET** /api/v1/marketplace/payment-gateways/webhook-url/ | |
|[**linkPaymentGatewayWebhook**](#linkpaymentgatewaywebhook) | **POST** /api/v1/marketplace/payment-gateways/link-webhook/ | |
|[**listPaymentGateways**](#listpaymentgateways) | **GET** /api/v1/marketplace/payment-gateways/list/ | |

# **getPaymentGatewayWebhookUrl**
> PaymentGatewayWebhookUrlResponse getPaymentGatewayWebhookUrl()

Get webhook URL for a payment gateway in an ODPS contract.  GET /api/v1/marketplace/payment-gateways/webhook-url?contract_id={uuid}&gateway_id={gateway_id}  Returns: {     \"contract_id\": \"uuid\",     \"gateway_id\": \"stripe\",     \"webhook_url\": \"https://example.com/webhooks/stripe\"  # or null if not linked }

### Example

```typescript
import {
    PaymentGatewayApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new PaymentGatewayApi(configuration);

const { status, data } = await apiInstance.getPaymentGatewayWebhookUrl();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**PaymentGatewayWebhookUrlResponse**

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
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **linkPaymentGatewayWebhook**
> PaymentGatewayResponse linkPaymentGatewayWebhook(paymentGatewayLinkWebhook)

Link webhook URL to a payment gateway in an ODPS contract.  POST /api/v1/marketplace/payment-gateways/link-webhook/  Request Body: {     \"contract_id\": \"uuid\",     \"gateway_id\": \"stripe\",     \"webhook_url\": \"https://example.com/webhooks/stripe\",     \"validate\": true  # optional, default: true }  Returns: {     \"gateway_id\": \"stripe\",     \"webhook_url\": \"https://example.com/webhooks/stripe\",     \"gateway_type\": \"stripe\",     \"gateway_name\": \"Stripe Payment Gateway\",     ... }

### Example

```typescript
import {
    PaymentGatewayApi,
    Configuration,
    PaymentGatewayLinkWebhook
} from './api';

const configuration = new Configuration();
const apiInstance = new PaymentGatewayApi(configuration);

let paymentGatewayLinkWebhook: PaymentGatewayLinkWebhook; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.linkPaymentGatewayWebhook(
    paymentGatewayLinkWebhook,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **paymentGatewayLinkWebhook** | **PaymentGatewayLinkWebhook**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**PaymentGatewayResponse**

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
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **listPaymentGateways**
> PaymentGatewaysListResponse listPaymentGateways()

List all payment gateways in an ODPS contract.  GET /api/v1/marketplace/payment-gateways/list?contract_id={uuid}  Returns: {     \"contract_id\": \"uuid\",     \"gateways\": {         \"stripe\": {...},         \"paypal\": {...}     } }

### Example

```typescript
import {
    PaymentGatewayApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new PaymentGatewayApi(configuration);

const { status, data } = await apiInstance.listPaymentGateways();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**PaymentGatewaysListResponse**

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
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

