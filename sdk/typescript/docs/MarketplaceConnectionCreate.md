# MarketplaceConnectionCreate

Serializer for creating a marketplace connection.  Validates marketplace type, name uniqueness, and config structure.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**marketplace_type** | **string** | Type of marketplace (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)  * &#x60;SNOWFLAKE_DATA_MARKETPLACE&#x60; - Snowflake Data Marketplace * &#x60;AWS_DATA_EXCHANGE&#x60; - Aws Data Exchange * &#x60;DATABRICKS_MARKETPLACE&#x60; - Databricks Marketplace * &#x60;GOOGLE_CLOUD_MARKETPLACE&#x60; - Google Cloud Marketplace * &#x60;AZURE_MARKETPLACE&#x60; - Azure Marketplace * &#x60;DATA_WORLD&#x60; - Data World * &#x60;KAGGLE&#x60; - Kaggle * &#x60;QUANDL&#x60; - Quandl * &#x60;APIS_GURU&#x60; - Apis Guru * &#x60;RAPIDAPI&#x60; - Rapidapi * &#x60;PROGRAMMABLE_WEB&#x60; - Programmable Web * &#x60;DATA_GOV&#x60; - Data Gov * &#x60;EUROPEAN_DATA_PORTAL&#x60; - European Data Portal * &#x60;CKAN_INSTANCE&#x60; - Ckan Instance * &#x60;CUSTOM&#x60; - Custom * &#x60;IN_MEMORY_FAKE&#x60; - In Memory Fake | [default to undefined]
**name** | **string** | Human-readable name (empty/whitespace rejected by service layer) | [default to undefined]
**config** | **any** | Connection configuration dictionary (API keys, endpoints, etc.). Will be encrypted at rest. | [default to undefined]
**is_active** | **boolean** | Whether this connection is active and can be used | [optional] [default to true]

## Example

```typescript
import { MarketplaceConnectionCreate } from './api';

const instance: MarketplaceConnectionCreate = {
    marketplace_type,
    name,
    config,
    is_active,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
