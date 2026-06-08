# ApiApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**apiSearchRetrieve**](#apisearchretrieve) | **GET** /api/search/ | |

# **apiSearchRetrieve**
> apiSearchRetrieve()

GET /api/search/?q=<term>&types=assets,contracts  Queries Asset and Contract models directly via their PostgreSQL search_vector fields (Phase 18.2).  Results are ranked by ts_rank and scoped to the authenticated user\'s tenant.  Query parameters ---------------- q      : search term (required) types  : comma-separated subset of ``assets``, ``contracts``          (default: both) page   : page number (StandardPageNumberPagination, page_size=50)  Response schema (per item) -------------------------- {     \"type\":  \"asset\" | \"contract\",     \"id\":    \"<uuid>\",     \"name\":  \"<string>\",     \"rank\":  <float> }

### Example

```typescript
import {
    ApiApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ApiApi(configuration);

const { status, data } = await apiInstance.apiSearchRetrieve();
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

