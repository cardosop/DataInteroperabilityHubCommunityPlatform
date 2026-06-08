# ContractsApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**contractsConvertCreate**](#contractsconvertcreate) | **POST** /api/v1/contracts/{id}/convert/ | Convert contract format|
|[**contractsCreate**](#contractscreate) | **POST** /api/v1/contracts/ | Create contract|
|[**contractsDestroy**](#contractsdestroy) | **DELETE** /api/v1/contracts/{id}/ | Delete contract|
|[**contractsDownloadRetrieve**](#contractsdownloadretrieve) | **GET** /api/v1/contracts/{id}/download/ | Download contract|
|[**contractsExportRetrieve**](#contractsexportretrieve) | **GET** /api/v1/contracts/{id}/export/ | Export contract|
|[**contractsFieldsLineageRetrieve**](#contractsfieldslineageretrieve) | **GET** /api/v1/contracts/{id}/fields/{field_name}/lineage/ | Get field-level lineage|
|[**contractsGenerateOdpsCreate**](#contractsgenerateodpscreate) | **POST** /api/v1/contracts/{id}/generate-odps/ | Generate ODPS document|
|[**contractsImpactAnalysisRetrieve**](#contractsimpactanalysisretrieve) | **GET** /api/v1/contracts/{id}/impact-analysis/ | Get impact analysis|
|[**contractsLineageContractsRetrieve**](#contractslineagecontractsretrieve) | **GET** /api/v1/contracts/{id}/lineage/contracts/ | Get contract-level lineage|
|[**contractsLineageDiffRetrieve**](#contractslineagediffretrieve) | **GET** /api/v1/contracts/{id}/lineage/diff/ | Diff lineage between two points in time|
|[**contractsLineageFullRetrieve**](#contractslineagefullretrieve) | **GET** /api/v1/contracts/{id}/lineage/full/ | Get hierarchical lineage|
|[**contractsLineagePartialUpdate**](#contractslineagepartialupdate) | **PATCH** /api/v1/contracts/{id}/lineage/ | |
|[**contractsLineageVisualizationRetrieve**](#contractslineagevisualizationretrieve) | **GET** /api/v1/contracts/{id}/lineage/visualization/ | Get lineage visualization|
|[**contractsLinkOdpsCreate**](#contractslinkodpscreate) | **POST** /api/v1/contracts/{id}/link-odps/ | Link ODPS contract to ODCS contract|
|[**contractsLinksRetrieve**](#contractslinksretrieve) | **GET** /api/v1/contracts/{id}/links/ | List contract links|
|[**contractsLintCreate**](#contractslintcreate) | **POST** /api/v1/contracts/{id}/lint/ | Lint contract|
|[**contractsList**](#contractslist) | **GET** /api/v1/contracts/ | List contracts|
|[**contractsMigrateCreate**](#contractsmigratecreate) | **POST** /api/v1/contracts/{id}/migrate/ | Migrate contract|
|[**contractsModelsLineageRetrieve**](#contractsmodelslineageretrieve) | **GET** /api/v1/contracts/{id}/models/{model_name}/lineage/ | Get model-level lineage|
|[**contractsPartialUpdate**](#contractspartialupdate) | **PATCH** /api/v1/contracts/{id}/ | |
|[**contractsPaymentGatewaysRetrieve**](#contractspaymentgatewaysretrieve) | **GET** /api/v1/contracts/{id}/payment-gateways/ | Get payment gateways|
|[**contractsProductDetailsRetrieve**](#contractsproductdetailsretrieve) | **GET** /api/v1/contracts/{id}/product-details/ | Get product details|
|[**contractsProductStrategyRetrieve**](#contractsproductstrategyretrieve) | **GET** /api/v1/contracts/{id}/product-strategy/ | Get product strategy|
|[**contractsProductsCreate**](#contractsproductscreate) | **POST** /api/v1/contracts/products/ | Create product|
|[**contractsProductsWorkflowsStatusRetrieve**](#contractsproductsworkflowsstatusretrieve) | **GET** /api/v1/contracts/products/workflows/{workflow_instance_id}/status/ | Get product creation workflow status|
|[**contractsRetrieve**](#contractsretrieve) | **GET** /api/v1/contracts/{id}/ | Retrieve contract|
|[**contractsSchemaEditorMetricsCreate**](#contractsschemaeditormetricscreate) | **POST** /api/v1/contracts/schema-editor/metrics | |
|[**contractsSchemaJsonSchemaRetrieve**](#contractsschemajsonschemaretrieve) | **GET** /api/v1/contracts/schema/json-schema/ | |
|[**contractsUnlinkOdpsCreate**](#contractsunlinkodpscreate) | **POST** /api/v1/contracts/{id}/unlink-odps/ | Unlink ODPS from ODCS contract|
|[**contractsUpdate**](#contractsupdate) | **PUT** /api/v1/contracts/{id}/ | Update contract|
|[**contractsValidateCreate**](#contractsvalidatecreate) | **POST** /api/v1/contracts/{id}/validate/ | Validate contract|
|[**contractsValidateDraftCreate**](#contractsvalidatedraftcreate) | **POST** /api/v1/contracts/validate-draft/ | Validate contract draft without persisting|

# **contractsConvertCreate**
> ContractConvertResponse contractsConvertCreate(contractConvertRequest)

         Convert a contract between JSON and YAML formats.          **Supported Formats:**         - `JSON`: Convert to JSON format         - `YAML`: Convert to YAML format         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ContractConvertRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let contractConvertRequest: ContractConvertRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsConvertCreate(
    id,
    contractConvertRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractConvertRequest** | **ContractConvertRequest**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ContractConvertResponse**

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
|**500** | Internal Server Error |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsCreate**
> Contract contractsCreate(contractCreate)

         Create a new contract from original contract content.          The contract will be automatically normalized to HubContract format.         All sections (owners, tags, quality, compliance, lifecycle, marketplace) will be extracted         from the original contract and stored in `hub_contract_json`.          **Supported Formats:**         - JSON (original_format: \"JSON\")         - YAML (original_format: \"YAML\")          **Supported Spec Types:**         - ODCS (original_spec_type: \"ODCS\") - Open Data Contract Standard v3.0.2+          If `original_spec_type` is not provided, it will be auto-detected.         Supported spec types: ODCS (Open Data Contract Standard) and ODPS (Open Data Product Standard).          **Phase 227 Wave 1 (227.L9.4) — Documented error codes:**          - `STRUCTURELESS_CONTRACT` (400) — payload has no resolvable           ``models[*].fields[]`` AND no ``schema.fields[]``. The           ``error.details.subcode`` carries one of:           `STRUCTURELESS_ODPS_NO_PORTS`,           `STRUCTURELESS_ODCS_NO_SCHEMA`,           `STRUCTURELESS_GENERIC`,           `STRUCTURELESS_CYCLIC_PORTS`.         - `VALIDATION_ERROR` (400) — Pydantic validation failure           (missing `info.name`, malformed JSON, etc.).         - `NORMALIZATION_FAILED` (400) — engine could not normalise           the document.         - `SCHEMA_TOO_DEEP` (400) — nested-properties walker hit the           configured `CONTRACTS_MAX_NESTING_DEPTH` (default 20).         - `INVALID_YAML` (400) — YAML deserialisation rejected an           unsafe construct (e.g., `!!python/object/apply:os.system`).         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ContractCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let contractCreate: ContractCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsCreate(
    contractCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractCreate** | **ContractCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Contract**

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

# **contractsDestroy**
> contractsDestroy()

         Delete a contract (soft delete: sets status to RETIRED).         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsDestroy(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


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
|**204** | Contract deleted successfully |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsDownloadRetrieve**
> File contractsDownloadRetrieve()

         Download a contract as a file in various formats (ODPS, ODCS, HubContract).          **Format Options:**         - `odps`: Download as ODPS (Open Data Product Standard) format         - `odcs`: Download as ODCS (Open Data Contract Standard) format (original or generated)         - `hubcontract`: Download as HubContract format (normalized internal format)          **Output Format Options:**         - `yaml`: Download in YAML format         - `json`: Download in JSON format          **Query Parameters:**         - `format` (optional): Specify the desired output format. Defaults to `hubcontract`.         - `output_format` (optional): Specify the desired serialization format (yaml or json). Defaults to `json`.         - `version` (optional): Specify the version for ODPS or ODCS format. For ODPS, defaults to `4.1`. For ODCS, defaults to detected version or `3.0.2`.          **Behavior:**         - For `odcs` format: Returns original_raw if available and matches requested version, otherwise generates from HubContract         - For `odps` format: Generates ODPS document from HubContract         - For `hubcontract` format: Returns hub_contract_json directly          Returns a file download with appropriate Content-Disposition header (filename includes version for ODCS format).         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let format: 'hubcontract' | 'odcs' | 'odps'; //Desired contract format for download. (optional) (default to 'hubcontract')
let outputFormat: 'json' | 'yaml'; //Desired output serialization format. (optional) (default to 'json')
let version: string; //Version for download (e.g., ODPS 4.1, ODCS 3.0.2). Only used when format=odps or format=odcs (default: latest for format) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsDownloadRetrieve(
    id,
    format,
    outputFormat,
    version
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **format** | [**&#39;hubcontract&#39; | &#39;odcs&#39; | &#39;odps&#39;**]**Array<&#39;hubcontract&#39; &#124; &#39;odcs&#39; &#124; &#39;odps&#39;>** | Desired contract format for download. | (optional) defaults to 'hubcontract'|
| **outputFormat** | [**&#39;json&#39; | &#39;yaml&#39;**]**Array<&#39;json&#39; &#124; &#39;yaml&#39;>** | Desired output serialization format. | (optional) defaults to 'json'|
| **version** | [**string**] | Version for download (e.g., ODPS 4.1, ODCS 3.0.2). Only used when format&#x3D;odps or format&#x3D;odcs (default: latest for format) | (optional) defaults to undefined|


### Return type

**File**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** | Contract file downloaded successfully. |  -  |
|**400** | Invalid format or output_format specified. |  -  |
|**404** | Contract not found. |  -  |
|**500** | Internal server error during download. |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsExportRetrieve**
> contractsExportRetrieve()

Export a contract in ODCS, ODPS, or HubContract format. Use `version` to request a specific spec version; downgrade warnings are returned via `X-Export-Downgrade-Warnings` header.

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let format: 'hubcontract' | 'odcs' | 'odps'; //Target format (default: hubcontract) (optional) (default to undefined)
let outputFormat: 'json' | 'yaml'; //Output serialization (default: json) (optional) (default to undefined)
let version: '2.2.2' | '3.0.0' | '3.0.1' | '3.0.2' | '3.1.0' | 'bitol-1.0.0'; //Target spec version (default: original spec version) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsExportRetrieve(
    id,
    format,
    outputFormat,
    version
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **format** | [**&#39;hubcontract&#39; | &#39;odcs&#39; | &#39;odps&#39;**]**Array<&#39;hubcontract&#39; &#124; &#39;odcs&#39; &#124; &#39;odps&#39;>** | Target format (default: hubcontract) | (optional) defaults to undefined|
| **outputFormat** | [**&#39;json&#39; | &#39;yaml&#39;**]**Array<&#39;json&#39; &#124; &#39;yaml&#39;>** | Output serialization (default: json) | (optional) defaults to undefined|
| **version** | [**&#39;2.2.2&#39; | &#39;3.0.0&#39; | &#39;3.0.1&#39; | &#39;3.0.2&#39; | &#39;3.1.0&#39; | &#39;bitol-1.0.0&#39;**]**Array<&#39;2.2.2&#39; &#124; &#39;3.0.0&#39; &#124; &#39;3.0.1&#39; &#124; &#39;3.0.2&#39; &#124; &#39;3.1.0&#39; &#124; &#39;bitol-1.0.0&#39;>** | Target spec version (default: original spec version) | (optional) defaults to undefined|


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
|**200** | Exported contract document |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsFieldsLineageRetrieve**
> FieldLineageResponse contractsFieldsLineageRetrieve()

         Get lineage for a specific field in a contract.          Returns lineage information including field references and entries.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let fieldName: string; // (default to undefined)
let id: string; //A UUID string identifying this contract. (default to undefined)
let modelName: string; //Model name (optional) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsFieldsLineageRetrieve(
    fieldName,
    id,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **fieldName** | [**string**] |  | defaults to undefined|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **modelName** | [**string**] | Model name (optional) | (optional) defaults to undefined|


### Return type

**FieldLineageResponse**

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

# **contractsGenerateOdpsCreate**
> GenerateODPSResponse contractsGenerateOdpsCreate()

         Generate ODPS (Open Data Product Standard) document from HubContract.          This endpoint generates an ODPS document from the contract\'s HubContract representation,         focusing on marketplace metadata. The generated ODPS document can be used for         marketplace listings and product catalogs.          **Request Body (optional):**         - `target_version` (string, optional): Target ODPS version (default: \"4.1\")         - `output_format` (string, optional): Output format - \"json\" or \"yaml\" (default: \"json\")         - `embed_odcs` (boolean, optional): If true and contract is ODCS, embed original ODCS           contract inline in product.contract.spec (default: true)          **Behavior:**         - Generates ODPS from HubContract (marketplace metadata)         - If contract is ODCS and has original_raw, optionally embeds ODCS in product.contract.spec         - Returns generated ODPS document in requested format          **Response:**         - Returns generated ODPS document as JSON or YAML         - Content-Type header set based on output_format         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    GenerateODPSRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

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

# **contractsImpactAnalysisRetrieve**
> contractsImpactAnalysisRetrieve()

         Analyze impact of changes to a contract, model, or field.          Performs reverse lineage traversal to find all resources that depend on         the specified contract/model/field.          **Query Parameters:**         - `depth`: Maximum traversal depth (default: 10)         - `model_name`: Optional model name for model-level impact         - `field_name`: Optional field name for field-level impact         - `include_fields`: Include field-level dependencies (default: true)         - `format`: Response format (json, csv, dot, mermaid, paths) (default: json)         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let depth: number; //Maximum traversal depth (default: 10) (optional) (default to undefined)
let fieldName: string; //Field name for field-level impact (optional) (default to undefined)
let format: string; //Response format: json, csv, dot, mermaid, paths (default: json) (optional) (default to undefined)
let includeFields: boolean; //Include field-level dependencies (default: true) (optional) (default to undefined)
let modelName: string; //Model name for model-level impact (optional) (default to undefined)

const { status, data } = await apiInstance.contractsImpactAnalysisRetrieve(
    id,
    depth,
    fieldName,
    format,
    includeFields,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **depth** | [**number**] | Maximum traversal depth (default: 10) | (optional) defaults to undefined|
| **fieldName** | [**string**] | Field name for field-level impact | (optional) defaults to undefined|
| **format** | [**string**] | Response format: json, csv, dot, mermaid, paths (default: json) | (optional) defaults to undefined|
| **includeFields** | [**boolean**] | Include field-level dependencies (default: true) | (optional) defaults to undefined|
| **modelName** | [**string**] | Model name for model-level impact | (optional) defaults to undefined|


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
|**200** | Impact analysis result |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLineageContractsRetrieve**
> ContractLineageResponse contractsLineageContractsRetrieve()

         Get contract-level lineage including contract references.          Returns contract references and lineage entries.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsLineageContractsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


### Return type

**ContractLineageResponse**

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

# **contractsLineageDiffRetrieve**
> contractsLineageDiffRetrieve()

Compute the set-arithmetic delta between the contract\'s lineage edge state at two anchors. Anchors accept ISO-8601 (`from=2026-04-30T00:00:00Z`) or version-int (`from_version=3`); ``to`` defaults to NOW() when omitted. Returns ``{added, removed, changed, unchanged, summary}`` with deterministic ordering. Pure function behind the response — driven by [lineage_diff.py](../lineage_diff.py).

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let from: string; //ISO-8601 timestamp for the older anchor. (optional) (default to undefined)
let fromVersion: number; //Contract version int → resolves to its created_at. (optional) (default to undefined)
let to: string; //ISO-8601 timestamp for the newer anchor; defaults to NOW(). (optional) (default to undefined)
let toVersion: number; //Contract version int → resolves to its created_at. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageDiffRetrieve(
    id,
    from,
    fromVersion,
    to,
    toVersion
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **from** | [**string**] | ISO-8601 timestamp for the older anchor. | (optional) defaults to undefined|
| **fromVersion** | [**number**] | Contract version int → resolves to its created_at. | (optional) defaults to undefined|
| **to** | [**string**] | ISO-8601 timestamp for the newer anchor; defaults to NOW(). | (optional) defaults to undefined|
| **toVersion** | [**number**] | Contract version int → resolves to its created_at. | (optional) defaults to undefined|


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
|**200** | Lineage diff body. |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLineageFullRetrieve**
> HierarchicalLineageResponse contractsLineageFullRetrieve()

         Get complete hierarchical lineage (contract, model, and field levels).          Returns full lineage traversal with all levels.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let maxContractDepth: number; //Maximum contract depth for traversal (default: 10) (optional) (default to undefined)
let maxFieldDepth: number; //Maximum field depth for traversal (default: 10) (optional) (default to undefined)
let maxModelDepth: number; //Maximum model depth for traversal (default: 10) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageFullRetrieve(
    id,
    maxContractDepth,
    maxFieldDepth,
    maxModelDepth
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **maxContractDepth** | [**number**] | Maximum contract depth for traversal (default: 10) | (optional) defaults to undefined|
| **maxFieldDepth** | [**number**] | Maximum field depth for traversal (default: 10) | (optional) defaults to undefined|
| **maxModelDepth** | [**number**] | Maximum model depth for traversal (default: 10) | (optional) defaults to undefined|


### Return type

**HierarchicalLineageResponse**

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

# **contractsLineagePartialUpdate**
> Contract contractsLineagePartialUpdate()

``PATCH /api/v1/contracts/{id}/lineage/`` — full-state lineage edit.  Request body shape (validated by :class:`LineageEditPatchSerializer`)::      {       \"edges\": [         {           \"source_contract\": \"<uuid>\",           \"source_model\": \"orders\",           \"source_field\": \"customer_id\",           \"target_contract\": \"<uuid>\",           \"target_model\": \"customer_aggregates\",           \"target_field\": \"customer_id\",           \"edge_type\": \"transformation\",           \"transformation_ref\": \"dbt_orders_v1\",           \"job_ref\": \"airflow_run_42\"         },         ...       ]     }  The full edge list is the desired post-patch state.  The view diffs against the current open edges, closes removed ones, opens new ones, and re-serialises ``hub_contract_json.lineage``.  Concurrency: ``If-Match`` (REQ-LIN-F2-002).  Idempotency: ``Idempotency-Key`` cached 24h via the existing bug-prevention idempotency layer.  Cap: 1000 edges per patch (413 over).  RBAC (F2.10): platform admin OR same-tenant tenant admin OR same-tenant user with ``EDIT_LINEAGE`` permission OR contract owner.  Returns 403 ``EDIT_LINEAGE_FORBIDDEN`` otherwise.

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    PatchedContract
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedContract: PatchedContract; // (optional)

const { status, data } = await apiInstance.contractsLineagePartialUpdate(
    id,
    idempotencyKey,
    patchedContract
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedContract** | **PatchedContract**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Contract**

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

# **contractsLineageVisualizationRetrieve**
> contractsLineageVisualizationRetrieve()

Get lineage graph in various visualization formats.  Supports JSON (D3.js), DOT (Graphviz), and Mermaid formats.  Phase 228 F5 (228.F5.2 / REQ-LIN-F5-001) — point-in-time knobs `?as_of=<ISO8601>` (direct historical cutoff) and `?version=<int>` (resolves to the contract\'s `created_at` for that version). Both knobs echo back in the response as `as_of` + `as_of_source ∈ {as_of, version}` so the UI can render the resolved cutoff without re-parsing query params. When both are supplied, `as_of` wins.

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let asOf: string; //ISO-8601 timestamp; renders the lineage at that historical cutoff. Mutually-permissive with `?version=`; when both provided, `as_of` wins. (optional) (default to undefined)
let format: string; //Visualization format: json, dot, or mermaid (default: json) (optional) (default to undefined)
let includeFields: boolean; //Phase 228.F2 (228.F2.3) — augment JSON visualization with field-level nodes derived from open LineageEdge rows. (optional) (default to undefined)
let maxDepth: number; //Maximum traversal depth (default: 10) (optional) (default to undefined)
let version: number; //Contract version int; resolves to that contract\'s `created_at` and uses it as the `as_of` cutoff. 404 when the version doesn\'t exist for the tenant. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLineageVisualizationRetrieve(
    id,
    asOf,
    format,
    includeFields,
    maxDepth,
    version
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **asOf** | [**string**] | ISO-8601 timestamp; renders the lineage at that historical cutoff. Mutually-permissive with &#x60;?version&#x3D;&#x60;; when both provided, &#x60;as_of&#x60; wins. | (optional) defaults to undefined|
| **format** | [**string**] | Visualization format: json, dot, or mermaid (default: json) | (optional) defaults to undefined|
| **includeFields** | [**boolean**] | Phase 228.F2 (228.F2.3) — augment JSON visualization with field-level nodes derived from open LineageEdge rows. | (optional) defaults to undefined|
| **maxDepth** | [**number**] | Maximum traversal depth (default: 10) | (optional) defaults to undefined|
| **version** | [**number**] | Contract version int; resolves to that contract\&#39;s &#x60;created_at&#x60; and uses it as the &#x60;as_of&#x60; cutoff. 404 when the version doesn\&#39;t exist for the tenant. | (optional) defaults to undefined|


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
|**200** | Lineage graph in requested format |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLinkOdpsCreate**
> Contract contractsLinkOdpsCreate()

         Link an ODPS contract to an ODCS contract.          Can link an existing ODPS contract or create a new one from raw content.         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ODPSLink
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let oDPSLink: ODPSLink; // (optional)

const { status, data } = await apiInstance.contractsLinkOdpsCreate(
    id,
    idempotencyKey,
    oDPSLink
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **oDPSLink** | **ODPSLink**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Contract**

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
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLinksRetrieve**
> contractsLinksRetrieve()

         List all links for a contract (ODPS links for ODCS contracts).          Returns linked contracts and their relationships.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsLinksRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


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
|**200** | List of linked contracts |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsLintCreate**
> ContractLintResponse contractsLintCreate(contract)

         Lint a contract using DataContract CLI.          Returns linting issues and recommendations for improving the contract.         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    Contract
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let contract: Contract; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsLintCreate(
    id,
    contract,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contract** | **Contract**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ContractLintResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**500** | Internal Server Error |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsList**
> PaginatedContractList contractsList()

         List contracts with enhanced filtering and sorting.          **Filtering:**         - `owner_email`: Filter by owner email (case-insensitive)         - `owner_name`: Filter by owner name (case-insensitive partial match)         - `tag`: Filter by tags (can specify multiple tags)         - `quality_profile`: Filter by quality profile key         - `compliance_regime`: Filter by compliance jurisdiction (e.g., GDPR, LGPD)          **Sorting:**         - `ordering`: Comma-separated list of fields to sort by         - Supported fields: `created_at`, `updated_at`, `quality_score`, `compliance_risk`         - Prefix with `-` for descending order (e.g., `-created_at`)         - Default: `-created_at` (newest first)          **Response includes computed fields:**         - `owners`: Array of owner objects (name, email) from `info.owners`         - `tags`: Array of tags from `info.tags`         - `quality_rules`: Array of quality rules from `quality.rules`         - `compliance_policy`: Compliance policy from `privacy_compliance`         - `lifecycle_policy`: Lifecycle policy from `lifecycle`         - `marketplace_policy`: Marketplace policy from `marketplace`         - `schema_fields`: Array of schema fields with all properties (format, pattern, enum, semantic_type, etc.)         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let complianceRegime: string; //Filter by compliance jurisdiction (e.g., GDPR, LGPD, CCPA) (optional) (default to undefined)
let contactEmail: string; //Filter by contact email (case-insensitive) (optional) (default to undefined)
let contactName: string; //Filter by contact name (case-insensitive partial match) (optional) (default to undefined)
let hasOdpsLink: boolean; //Filter by whether contract has an ODPS link (true/false). Only applies to ODCS contracts (optional) (default to undefined)
let maxLatencyMs: number; //Filter by maximum latency in milliseconds (from servicelevels) (optional) (default to undefined)
let minAvailability: number; //Filter by minimum availability (from servicelevels) (optional) (default to undefined)
let modelName: string; //Filter by model name (optional) (default to undefined)
let odpsVersion: string; //Filter by ODPS version (e.g., \'4.1\', \'4.0\'). Only applies to ODPS contracts. Prefer spec_version for new integrations. (optional) (default to undefined)
let ordering: string; //Comma-separated list of fields to sort by (e.g., -created_at,quality_score) (optional) (default to undefined)
let ownerEmail: string; //Filter by owner email (case-insensitive) (optional) (default to undefined)
let ownerName: string; //Filter by owner name (case-insensitive partial match) (optional) (default to undefined)
let page: number; //A page number within the paginated result set. (optional) (default to undefined)
let pageSize: number; //Number of results to return per page. (optional) (default to undefined)
let qualityProfile: string; //Filter by quality profile key (e.g., intake_basic) (optional) (default to undefined)
let serverType: string; //Filter by server type (e.g., S3, PostgreSQL, API) (optional) (default to undefined)
let serverUrl: string; //Filter by server URL (case-insensitive partial match) (optional) (default to undefined)
let specType: string; //Filter by original spec type (e.g., \'ODPS\', \'ODCS\') (optional) (default to undefined)
let specVersion: string; //Filter by original spec version. Works for both ODCS (e.g. \'3.1.0\', \'3.0.2\') and ODPS (e.g. \'4.1\', \'bitol-1.0.0\') (optional) (default to undefined)
let tag: string; //Filter by tag (can specify multiple times) (optional) (default to undefined)

const { status, data } = await apiInstance.contractsList(
    complianceRegime,
    contactEmail,
    contactName,
    hasOdpsLink,
    maxLatencyMs,
    minAvailability,
    modelName,
    odpsVersion,
    ordering,
    ownerEmail,
    ownerName,
    page,
    pageSize,
    qualityProfile,
    serverType,
    serverUrl,
    specType,
    specVersion,
    tag
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **complianceRegime** | [**string**] | Filter by compliance jurisdiction (e.g., GDPR, LGPD, CCPA) | (optional) defaults to undefined|
| **contactEmail** | [**string**] | Filter by contact email (case-insensitive) | (optional) defaults to undefined|
| **contactName** | [**string**] | Filter by contact name (case-insensitive partial match) | (optional) defaults to undefined|
| **hasOdpsLink** | [**boolean**] | Filter by whether contract has an ODPS link (true/false). Only applies to ODCS contracts | (optional) defaults to undefined|
| **maxLatencyMs** | [**number**] | Filter by maximum latency in milliseconds (from servicelevels) | (optional) defaults to undefined|
| **minAvailability** | [**number**] | Filter by minimum availability (from servicelevels) | (optional) defaults to undefined|
| **modelName** | [**string**] | Filter by model name | (optional) defaults to undefined|
| **odpsVersion** | [**string**] | Filter by ODPS version (e.g., \&#39;4.1\&#39;, \&#39;4.0\&#39;). Only applies to ODPS contracts. Prefer spec_version for new integrations. | (optional) defaults to undefined|
| **ordering** | [**string**] | Comma-separated list of fields to sort by (e.g., -created_at,quality_score) | (optional) defaults to undefined|
| **ownerEmail** | [**string**] | Filter by owner email (case-insensitive) | (optional) defaults to undefined|
| **ownerName** | [**string**] | Filter by owner name (case-insensitive partial match) | (optional) defaults to undefined|
| **page** | [**number**] | A page number within the paginated result set. | (optional) defaults to undefined|
| **pageSize** | [**number**] | Number of results to return per page. | (optional) defaults to undefined|
| **qualityProfile** | [**string**] | Filter by quality profile key (e.g., intake_basic) | (optional) defaults to undefined|
| **serverType** | [**string**] | Filter by server type (e.g., S3, PostgreSQL, API) | (optional) defaults to undefined|
| **serverUrl** | [**string**] | Filter by server URL (case-insensitive partial match) | (optional) defaults to undefined|
| **specType** | [**string**] | Filter by original spec type (e.g., \&#39;ODPS\&#39;, \&#39;ODCS\&#39;) | (optional) defaults to undefined|
| **specVersion** | [**string**] | Filter by original spec version. Works for both ODCS (e.g. \&#39;3.1.0\&#39;, \&#39;3.0.2\&#39;) and ODPS (e.g. \&#39;4.1\&#39;, \&#39;bitol-1.0.0\&#39;) | (optional) defaults to undefined|
| **tag** | [**string**] | Filter by tag (can specify multiple times) | (optional) defaults to undefined|


### Return type

**PaginatedContractList**

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

# **contractsMigrateCreate**
> contractsMigrateCreate()

         Migrate contract to a new HubContract version.          Supports ON_WRITE (persistent), ON_READ (lazy), and BACKGROUND (async) strategies.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsMigrateCreate(
    id,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
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
|**200** | Migration completed |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**202** | Migration job created |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsModelsLineageRetrieve**
> ModelLineageResponse contractsModelsLineageRetrieve()

         Get lineage for a specific model in a contract.          Returns lineage information including model references and entries.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let modelName: string; //Model name (default to undefined)

const { status, data } = await apiInstance.contractsModelsLineageRetrieve(
    id,
    modelName
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **modelName** | [**string**] | Model name | defaults to undefined|


### Return type

**ModelLineageResponse**

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

# **contractsPartialUpdate**
> Contract contractsPartialUpdate()

Contract ViewSet with caching and pagination support.  Features: - Caching for contract retrieval and lineage queries - Pagination for large result sets - Performance optimizations for large JSON - Enhanced filtering and sorting - All CRUD operations via ContractCRUDMixin - Lineage operations via ContractLineageMixin - Validation operations via ContractValidationMixin - ODPS operations via ContractODPSMixin - Migration operations via ContractMigrationMixin - Impact analysis via ContractImpactMixin - Export operations via ContractExportMixin - Product operations via ContractProductMixin  Note: Overrides initialize_request to handle format suffix conflicts for the lineage visualization endpoint.

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    PatchedContract
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let patchedContract: PatchedContract; // (optional)

const { status, data } = await apiInstance.contractsPartialUpdate(
    id,
    idempotencyKey,
    patchedContract
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **patchedContract** | **PatchedContract**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Contract**

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

# **contractsPaymentGatewaysRetrieve**
> PaymentGatewaysResponse contractsPaymentGatewaysRetrieve()

         Get payment gateways from ODPS contract.          Returns all payment gateways configured in the contract.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

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
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

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
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

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

# **contractsProductsCreate**
> ProductCreateResponse contractsProductsCreate(productCreate)

         Create product using Product-First flow (ODPS).          Creates a product from an ODPS document using workflow orchestration.         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ProductCreate
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let productCreate: ProductCreate; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsProductsCreate(
    productCreate,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **productCreate** | **ProductCreate**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ProductCreateResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**202** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsProductsWorkflowsStatusRetrieve**
> contractsProductsWorkflowsStatusRetrieve()

         Get status and results of a product creation workflow.          Returns workflow status, progress, and results if completed.         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let workflowInstanceId: string; //Workflow instance ID (default to undefined)

const { status, data } = await apiInstance.contractsProductsWorkflowsStatusRetrieve(
    workflowInstanceId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **workflowInstanceId** | [**string**] | Workflow instance ID | defaults to undefined|


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
|**200** | Workflow status |  -  |
|**404** | Not Found - Resource not found |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsRetrieve**
> Contract contractsRetrieve()

         Retrieve a contract by ID.          **Response includes all HubContract sections:**         - `hub_contract_json`: Complete normalized HubContract with all sections         - `owners`: Computed array of owners from `info.owners`         - `tags`: Computed array of tags from `info.tags`         - `quality_rules`: Computed array of quality rules from `quality.rules`         - `compliance_policy`: Computed compliance policy from `privacy_compliance`         - `lifecycle_policy`: Computed lifecycle policy from `lifecycle`         - `marketplace_policy`: Computed marketplace policy from `marketplace`         - `schema_fields`: Computed array of schema fields with all properties          **Normalization Status:**         - `NORMALIZED_OK`: Contract normalized successfully         - `NORMALIZED_WITH_WARNINGS`: Normalized with warnings         - `NORMALIZATION_FAILED`: Normalization failed         - `NOT_NORMALIZED`: Not yet normalized          **Validation Status:**         - `VALID`: Contract is valid         - `INVALID`: Contract has errors         - `WARNING_ONLY`: Contract has warnings but no errors         - `ERROR`: Validation error occurred         

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)

const { status, data } = await apiInstance.contractsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|


### Return type

**Contract**

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

# **contractsSchemaEditorMetricsCreate**
> contractsSchemaEditorMetricsCreate()

Receives schema-editor telemetry events from the frontend.  Auth-only (no tenant- or role-gated check beyond authentication because the metric labels are server-derived from ``request.user`` — no opportunity for cross-tenant pollution).

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsSchemaEditorMetricsCreate(
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

# **contractsSchemaJsonSchemaRetrieve**
> Contract contractsSchemaJsonSchemaRetrieve()

Return the JSON Schema describing valid HubContract payloads.  ``GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>``  The frontend Schema editor (Phase 227 L5.5) fetches this at load and uses it to drive client-side field-level validation — rejecting empty model names, duplicate fields within a model, and ``object``-typed fields with no nested ``fields[]`` BEFORE the user clicks Save. The schema returned is derived from the canonical ``HubContractModel.model_json_schema()`` so server + client speak the same Pydantic-defined contract.  Query params ------------ * ``spec`` — optional, ``odcs`` or ``odps``. Reserved for future   spec-specific narrowing; currently both values return the   same canonical HubContract schema (the editor compiles to   either ODCS or ODPS source via the client-side compiler).  Response -------- ::      {       \"spec\": \"odcs\" | \"odps\" | null,       \"schema\": <JSON-Schema dict>     }

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

const { status, data } = await apiInstance.contractsSchemaJsonSchemaRetrieve();
```

### Parameters
This endpoint does not have any parameters.


### Return type

**Contract**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/schema+json, application/json


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

# **contractsUnlinkOdpsCreate**
> contractsUnlinkOdpsCreate()

Remove the bidirectional link between an ODCS contract and its linked ODPS contract.

### Example

```typescript
import {
    ContractsApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsUnlinkOdpsCreate(
    id,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
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
|**200** | Successfully unlinked |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**404** | Not Found - Resource not found |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsUpdate**
> Contract contractsUpdate()

         Update a contract (partial update supported).          If `original_raw` is updated, the contract will be re-normalized.         All sections will be re-extracted and stored in `hub_contract_json`.          **Phase 227 Wave 1 (227.L9.4) — Documented error codes:**          - `STRUCTURELESS_CONTRACT` (400) — re-normalisation produced a           structureless payload; same subcode taxonomy as `create`.         - `VALIDATION_ERROR` (400) — Pydantic validation failure.         - `PRECONDITION_FAILED` (412) — `If-Match` header carries a           stale ETag; the response body and `ETag` header carry the           server\'s current value so the client can reconcile.         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ContractUpdate
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let contractUpdate: ContractUpdate; // (optional)

const { status, data } = await apiInstance.contractsUpdate(
    id,
    idempotencyKey,
    contractUpdate
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractUpdate** | **ContractUpdate**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Contract**

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
|**412** | Precondition failed: &#x60;&#x60;If-Match&#x60;&#x60; ETag mismatch. &#x60;&#x60;code&#x60;&#x60; is &#x60;&#x60;PRECONDITION_FAILED&#x60;&#x60;; the response carries the server\&#39;s current ETag for reconciliation. |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsValidateCreate**
> ContractValidateResponse contractsValidateCreate()

         Validate a contract using DataContract CLI.          Supports both synchronous and asynchronous validation.         

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ContractValidateRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let id: string; //A UUID string identifying this contract. (default to undefined)
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)
let contractValidateRequest: ContractValidateRequest; // (optional)

const { status, data } = await apiInstance.contractsValidateCreate(
    id,
    idempotencyKey,
    contractValidateRequest
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractValidateRequest** | **ContractValidateRequest**|  | |
| **id** | [**string**] | A UUID string identifying this contract. | defaults to undefined|
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ContractValidateResponse**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**202** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**500** | Internal Server Error |  -  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **contractsValidateDraftCreate**
> ContractValidateDraftResponse contractsValidateDraftCreate(contractValidateDraft)

Dry-run normalization of raw contract content. Returns detection results and normalization errors/warnings without creating a Contract record. Always returns 200.

### Example

```typescript
import {
    ContractsApi,
    Configuration,
    ContractValidateDraft
} from './api';

const configuration = new Configuration();
const apiInstance = new ContractsApi(configuration);

let contractValidateDraft: ContractValidateDraft; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.contractsValidateDraftCreate(
    contractValidateDraft,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **contractValidateDraft** | **ContractValidateDraft**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**ContractValidateDraftResponse**

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

