# DataQualityApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**getDqQualityRootCauseAnalysis**](#getdqqualityrootcauseanalysis) | **GET** /api/v1/dq/quality/root_cause_analysis/ | |
|[**getDqQualityRootCauseAnalysis2**](#getdqqualityrootcauseanalysis2) | **GET** /api/v1/quality/root_cause_analysis/ | |
|[**getDqQualityScorecard**](#getdqqualityscorecard) | **GET** /api/v1/dq/quality/scorecards/ | |
|[**getDqQualityScorecard2**](#getdqqualityscorecard2) | **GET** /api/v1/quality/scorecards/ | |
|[**getDqRunResults**](#getdqrunresults) | **GET** /api/v1/dq/runs/{id}/results/ | |
|[**getDqRunResults2**](#getdqrunresults2) | **GET** /api/v1/quality/runs/{id}/results/ | |
|[**listDqQualityAnomalies**](#listdqqualityanomalies) | **GET** /api/v1/dq/quality/anomalies/ | |
|[**listDqQualityAnomalies2**](#listdqqualityanomalies2) | **GET** /api/v1/quality/anomalies/ | |
|[**listDqQualityTrends**](#listdqqualitytrends) | **GET** /api/v1/dq/quality/trends/ | |
|[**listDqQualityTrends2**](#listdqqualitytrends2) | **GET** /api/v1/quality/trends/ | |

# **getDqQualityRootCauseAnalysis**
> getDqQualityRootCauseAnalysis()

Return a root-cause analysis report for a DQ run.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; //If supplied without ``dq_run_id``, the latest SUCCEEDED run for the asset is analysed. (optional) (default to undefined)
let dqRunId: string; //Analyse a specific DQ run.  Mutually exclusive with ``asset_id``. (optional) (default to undefined)
let lookbackDays: number; //Window of historical context (1–365).  Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.getDqQualityRootCauseAnalysis(
    assetId,
    dqRunId,
    lookbackDays
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | If supplied without &#x60;&#x60;dq_run_id&#x60;&#x60;, the latest SUCCEEDED run for the asset is analysed. | (optional) defaults to undefined|
| **dqRunId** | [**string**] | Analyse a specific DQ run.  Mutually exclusive with &#x60;&#x60;asset_id&#x60;&#x60;. | (optional) defaults to undefined|
| **lookbackDays** | [**number**] | Window of historical context (1–365).  Default 30. | (optional) defaults to undefined|


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
|**200** | Root-cause analysis payload |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **getDqQualityRootCauseAnalysis2**
> getDqQualityRootCauseAnalysis2()

Return a root-cause analysis report for a DQ run.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; //If supplied without ``dq_run_id``, the latest SUCCEEDED run for the asset is analysed. (optional) (default to undefined)
let dqRunId: string; //Analyse a specific DQ run.  Mutually exclusive with ``asset_id``. (optional) (default to undefined)
let lookbackDays: number; //Window of historical context (1–365).  Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.getDqQualityRootCauseAnalysis2(
    assetId,
    dqRunId,
    lookbackDays
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | If supplied without &#x60;&#x60;dq_run_id&#x60;&#x60;, the latest SUCCEEDED run for the asset is analysed. | (optional) defaults to undefined|
| **dqRunId** | [**string**] | Analyse a specific DQ run.  Mutually exclusive with &#x60;&#x60;asset_id&#x60;&#x60;. | (optional) defaults to undefined|
| **lookbackDays** | [**number**] | Window of historical context (1–365).  Default 30. | (optional) defaults to undefined|


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
|**200** | Root-cause analysis payload |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **getDqQualityScorecard**
> getDqQualityScorecard()

Return an executive dashboard or per-asset scorecard.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; //If supplied, returns asset-level scorecard; else tenant-level executive dashboard. (optional) (default to undefined)
let timeRange: number; //Lookback window in days (1–365). Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.getDqQualityScorecard(
    assetId,
    timeRange
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | If supplied, returns asset-level scorecard; else tenant-level executive dashboard. | (optional) defaults to undefined|
| **timeRange** | [**number**] | Lookback window in days (1–365). Default 30. | (optional) defaults to undefined|


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
|**200** | Scorecard payload |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **getDqQualityScorecard2**
> getDqQualityScorecard2()

Return an executive dashboard or per-asset scorecard.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; //If supplied, returns asset-level scorecard; else tenant-level executive dashboard. (optional) (default to undefined)
let timeRange: number; //Lookback window in days (1–365). Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.getDqQualityScorecard2(
    assetId,
    timeRange
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | If supplied, returns asset-level scorecard; else tenant-level executive dashboard. | (optional) defaults to undefined|
| **timeRange** | [**number**] | Lookback window in days (1–365). Default 30. | (optional) defaults to undefined|


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
|**200** | Scorecard payload |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **getDqRunResults**
> DQRunResultsResponse getDqRunResults()

Get enhanced DQ run results with detailed check information.  GET /api/v1/dq/runs/{id}/results/  Returns detailed DQ results including: - Detailed check results with pass/fail status - Quality score breakdown by check category - Trend analysis (if available) - Anomaly detection results (if available) - Recommendations for improvement

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)

const { status, data } = await apiInstance.getDqRunResults(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|


### Return type

**DQRunResultsResponse**

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

# **getDqRunResults2**
> DQRunResultsResponse getDqRunResults2()

Get enhanced DQ run results with detailed check information.  GET /api/v1/dq/runs/{id}/results/  Returns detailed DQ results including: - Detailed check results with pass/fail status - Quality score breakdown by check category - Trend analysis (if available) - Anomaly detection results (if available) - Recommendations for improvement

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let id: string; //A UUID string identifying this dq run. (default to undefined)

const { status, data } = await apiInstance.getDqRunResults2(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this dq run. | defaults to undefined|


### Return type

**DQRunResultsResponse**

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

# **listDqQualityAnomalies**
> DQQualityAnomaliesResponse listDqQualityAnomalies()

List detected DQ anomalies for the requesting tenant.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; // (optional) (default to undefined)
let datasetId: string; // (optional) (default to undefined)
let severity: string; //One of CRITICAL / HIGH / MEDIUM / LOW (optional) (default to undefined)
let since: string; //ISO-8601 timestamp; only anomalies detected at or after this point are returned (optional) (default to undefined)

const { status, data } = await apiInstance.listDqQualityAnomalies(
    assetId,
    datasetId,
    severity,
    since
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] |  | (optional) defaults to undefined|
| **datasetId** | [**string**] |  | (optional) defaults to undefined|
| **severity** | [**string**] | One of CRITICAL / HIGH / MEDIUM / LOW | (optional) defaults to undefined|
| **since** | [**string**] | ISO-8601 timestamp; only anomalies detected at or after this point are returned | (optional) defaults to undefined|


### Return type

**DQQualityAnomaliesResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **listDqQualityAnomalies2**
> DQQualityAnomaliesResponse listDqQualityAnomalies2()

List detected DQ anomalies for the requesting tenant.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; // (optional) (default to undefined)
let datasetId: string; // (optional) (default to undefined)
let severity: string; //One of CRITICAL / HIGH / MEDIUM / LOW (optional) (default to undefined)
let since: string; //ISO-8601 timestamp; only anomalies detected at or after this point are returned (optional) (default to undefined)

const { status, data } = await apiInstance.listDqQualityAnomalies2(
    assetId,
    datasetId,
    severity,
    since
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] |  | (optional) defaults to undefined|
| **datasetId** | [**string**] |  | (optional) defaults to undefined|
| **severity** | [**string**] | One of CRITICAL / HIGH / MEDIUM / LOW | (optional) defaults to undefined|
| **since** | [**string**] | ISO-8601 timestamp; only anomalies detected at or after this point are returned | (optional) defaults to undefined|


### Return type

**DQQualityAnomaliesResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **listDqQualityTrends**
> DQQualityTrendsResponse listDqQualityTrends()

Compute / list quality trends for an asset or dataset.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; // (optional) (default to undefined)
let datasetId: string; // (optional) (default to undefined)
let metricType: string; //Default: ``quality_score`` (optional) (default to undefined)
let periodType: string; //HOURLY / DAILY / WEEKLY / MONTHLY. Default DAILY. (optional) (default to undefined)
let timeRange: number; //Lookback window in days (1–365). Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.listDqQualityTrends(
    assetId,
    datasetId,
    metricType,
    periodType,
    timeRange
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] |  | (optional) defaults to undefined|
| **datasetId** | [**string**] |  | (optional) defaults to undefined|
| **metricType** | [**string**] | Default: &#x60;&#x60;quality_score&#x60;&#x60; | (optional) defaults to undefined|
| **periodType** | [**string**] | HOURLY / DAILY / WEEKLY / MONTHLY. Default DAILY. | (optional) defaults to undefined|
| **timeRange** | [**number**] | Lookback window in days (1–365). Default 30. | (optional) defaults to undefined|


### Return type

**DQQualityTrendsResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **listDqQualityTrends2**
> DQQualityTrendsResponse listDqQualityTrends2()

Compute / list quality trends for an asset or dataset.

### Example

```typescript
import {
    DataQualityApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new DataQualityApi(configuration);

let assetId: string; // (optional) (default to undefined)
let datasetId: string; // (optional) (default to undefined)
let metricType: string; //Default: ``quality_score`` (optional) (default to undefined)
let periodType: string; //HOURLY / DAILY / WEEKLY / MONTHLY. Default DAILY. (optional) (default to undefined)
let timeRange: number; //Lookback window in days (1–365). Default 30. (optional) (default to undefined)

const { status, data } = await apiInstance.listDqQualityTrends2(
    assetId,
    datasetId,
    metricType,
    periodType,
    timeRange
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] |  | (optional) defaults to undefined|
| **datasetId** | [**string**] |  | (optional) defaults to undefined|
| **metricType** | [**string**] | Default: &#x60;&#x60;quality_score&#x60;&#x60; | (optional) defaults to undefined|
| **periodType** | [**string**] | HOURLY / DAILY / WEEKLY / MONTHLY. Default DAILY. | (optional) defaults to undefined|
| **timeRange** | [**number**] | Lookback window in days (1–365). Default 30. | (optional) defaults to undefined|


### Return type

**DQQualityTrendsResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

