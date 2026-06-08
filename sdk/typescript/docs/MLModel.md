# MLModel

Serializer for MLModel model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this model belongs to | [optional] [readonly] [default to undefined]
**odh_model_id** | **string** | ODH Model Registry model ID | [default to undefined]
**odh_model_name** | **string** | ODH Model Registry model name | [default to undefined]
**odh_model_version** | **string** | ODH Model Registry model version | [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**contract_id** | **string** |  | [optional] [readonly] [default to undefined]
**model_type** | **string** | Type of ML model  * &#x60;CLASSIFICATION&#x60; - Classification * &#x60;REGRESSION&#x60; - Regression * &#x60;CLUSTERING&#x60; - Clustering * &#x60;NLP&#x60; - Natural Language Processing * &#x60;COMPUTER_VISION&#x60; - Computer Vision * &#x60;RECOMMENDATION&#x60; - Recommendation * &#x60;TIME_SERIES&#x60; - Time Series * &#x60;ANOMALY_DETECTION&#x60; - Anomaly Detection * &#x60;OTHER&#x60; - Other | [default to undefined]
**status** | **string** | Model lifecycle status  * &#x60;TRAINING&#x60; - Training * &#x60;TRAINED&#x60; - Trained * &#x60;DEPLOYED&#x60; - Deployed * &#x60;FAILED&#x60; - Failed * &#x60;ARCHIVED&#x60; - Archived | [optional] [default to undefined]
**training_dataset_id** | **string** | Primary training dataset ID (from Hub datasets) | [optional] [default to undefined]
**training_job_id** | **string** | ODH Training Operator job ID | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { MLModel } from './api';

const instance: MLModel = {
    id,
    tenant,
    odh_model_id,
    odh_model_name,
    odh_model_version,
    asset_id,
    contract_id,
    model_type,
    status,
    training_dataset_id,
    training_job_id,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
