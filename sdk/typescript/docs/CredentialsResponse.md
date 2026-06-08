# CredentialsResponse


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**scheduled_ingestion_id** | **string** |  | [default to undefined]
**source_type** | **string** |  | [default to undefined]
**credential_version** | **number** |  | [optional] [default to 1]
**last_tested_at** | **string** |  | [default to undefined]
**last_test_result** | **string** |  | [default to undefined]
**masked_credentials** | **{ [key: string]: any; }** |  | [default to undefined]
**metadata** | **{ [key: string]: any; }** |  | [default to undefined]

## Example

```typescript
import { CredentialsResponse } from './api';

const instance: CredentialsResponse = {
    scheduled_ingestion_id,
    source_type,
    credential_version,
    last_tested_at,
    last_test_result,
    masked_credentials,
    metadata,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
