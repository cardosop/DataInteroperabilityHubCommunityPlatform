# MarketplaceConnection

Serializer for MarketplaceConnection model (read operations).  Security: The ``config`` field is **never** exposed in read responses. It contains encrypted credentials (API keys, connection strings, tokens). The field is omitted from Meta.fields (positive allowlist) and also listed in Meta.extra_kwargs as write_only for defense-in-depth.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the marketplace connection | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant ID | [optional] [readonly] [default to undefined]
**tenant_name** | **string** | Tenant name | [optional] [readonly] [default to undefined]
**marketplace_type** | **string** | Type of marketplace (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)  * &#x60;SNOWFLAKE_DATA_MARKETPLACE&#x60; - Snowflake Data Marketplace * &#x60;AWS_DATA_EXCHANGE&#x60; - Aws Data Exchange * &#x60;DATABRICKS_MARKETPLACE&#x60; - Databricks Marketplace * &#x60;GOOGLE_CLOUD_MARKETPLACE&#x60; - Google Cloud Marketplace * &#x60;AZURE_MARKETPLACE&#x60; - Azure Marketplace * &#x60;DATA_WORLD&#x60; - Data World * &#x60;KAGGLE&#x60; - Kaggle * &#x60;QUANDL&#x60; - Quandl * &#x60;APIS_GURU&#x60; - Apis Guru * &#x60;RAPIDAPI&#x60; - Rapidapi * &#x60;PROGRAMMABLE_WEB&#x60; - Programmable Web * &#x60;DATA_GOV&#x60; - Data Gov * &#x60;EUROPEAN_DATA_PORTAL&#x60; - European Data Portal * &#x60;CKAN_INSTANCE&#x60; - Ckan Instance * &#x60;CUSTOM&#x60; - Custom * &#x60;IN_MEMORY_FAKE&#x60; - In Memory Fake | [default to undefined]
**marketplace_type_display** | **string** | Human-readable marketplace type | [optional] [readonly] [default to undefined]
**name** | **string** | Human-readable name for this connection (unique per tenant) | [default to undefined]
**is_active** | **boolean** | Whether this connection is active and can be used | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { MarketplaceConnection } from './api';

const instance: MarketplaceConnection = {
    id,
    tenant,
    tenant_name,
    marketplace_type,
    marketplace_type_display,
    name,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
