# HealthApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**healthCircuitBreakersRetrieve**](#healthcircuitbreakersretrieve) | **GET** /health/circuit-breakers/ | |

# **healthCircuitBreakersRetrieve**
> healthCircuitBreakersRetrieve()

Circuit breaker aggregate status endpoint for monitoring.  Phase 221.3.1 — Requires authentication (JWT or API key). Kubernetes probes use /health/ and /health/live/ which remain public.  Phase 221.3.2 — Returns only aggregate counts (total_breakers, open_breakers, status).  Individual service names and the ?service_name= query parameter have been removed to avoid exposing internal service architecture to authenticated but non-admin users.

### Example

```typescript
import {
    HealthApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new HealthApi(configuration);

const { status, data } = await apiInstance.healthCircuitBreakersRetrieve();
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

