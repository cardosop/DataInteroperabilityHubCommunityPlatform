# Contract

Enhanced serializer for Contract model with computed fields (GAP-9.2.1).  **Computed Fields:** All computed fields are extracted from `hub_contract_json`: - `owners`: From `info.owners` - `tags`: From `info.tags` - `quality_rules`: From `quality.rules` - `compliance_policy`: From `privacy_compliance` - `lifecycle_policy`: From `lifecycle` - `marketplace_policy`: From `marketplace` - `schema_fields`: From `schema.fields` with constraint flags (is_primary_key, is_unique, is_indexed)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this contract belongs to | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset ID (UUID string) this contract belongs to | [optional] [readonly] [default to undefined]
**asset_id** | **string** | Same as asset; included for clients that expect asset_id | [optional] [readonly] [default to undefined]
**version** | **number** | Per-asset contract version counter | [optional] [readonly] [default to undefined]
**status** | **string** | Contract lifecycle status: DRAFT, ACTIVE, RETIRED  * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;RETIRED&#x60; - Retired | [optional] [default to undefined]
**original_spec_type** | **string** | Original spec type: ODCS (Open Data Contract Standard) or ODPS (Open Data Product Standard)  * &#x60;ODCS&#x60; - ODCS * &#x60;ODPS&#x60; - ODPS | [default to undefined]
**original_spec_version** | **string** | Original spec version (e.g., 3.0.2, 2.2.2) | [default to undefined]
**original_format** | **string** | Original format: JSON or YAML  * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [default to undefined]
**original_raw** | **string** | Original contract file content (verbatim) | [default to undefined]
**hub_contract_version** | **string** | HubContract version (e.g., 1.0.0) | [optional] [readonly] [default to undefined]
**hub_contract_json** | **any** | Normalized HubContract JSON | [optional] [readonly] [default to undefined]
**normalization_status** | **string** | Normalization status  * &#x60;NOT_NORMALIZED&#x60; - Not Normalized * &#x60;NORMALIZED_OK&#x60; - Normalized OK * &#x60;NORMALIZED_WITH_WARNINGS&#x60; - Normalized With Warnings * &#x60;NORMALIZATION_FAILED&#x60; - Normalization Failed | [optional] [readonly] [default to undefined]
**normalization_errors** | **any** | Normalization errors (JSON array) | [optional] [readonly] [default to undefined]
**normalization_warnings** | **any** | Normalization warnings (JSON array) | [optional] [readonly] [default to undefined]
**validation_status** | **string** | CLI validation status: VALID, INVALID, WARNING_ONLY, ERROR  * &#x60;VALID&#x60; - Valid * &#x60;INVALID&#x60; - Invalid * &#x60;WARNING_ONLY&#x60; - Warning Only * &#x60;ERROR&#x60; - Error * &#x60;SKIPPED&#x60; - Skipped | [optional] [readonly] [default to undefined]
**validation_errors** | **any** | Validation errors (JSON array) | [optional] [readonly] [default to undefined]
**validation_warnings** | **any** | Validation warnings (JSON array) | [optional] [readonly] [default to undefined]
**cli_version** | **string** | DataContract CLI version used | [optional] [readonly] [default to undefined]
**last_validated_at** | **string** | Last validation timestamp | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created the contract | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**owners** | **Array&lt;{ [key: string]: any; }&gt;** | Array of contract owners (extracted from info.owners) | [optional] [readonly] [default to undefined]
**tags** | **Array&lt;string&gt;** | Array of tags (extracted from info.tags) | [optional] [readonly] [default to undefined]
**quality_rules** | **Array&lt;{ [key: string]: any; }&gt;** | Array of quality rules (extracted from quality.rules) | [optional] [readonly] [default to undefined]
**compliance_policy** | **{ [key: string]: any; }** | Compliance policy (extracted from privacy_compliance) | [optional] [readonly] [default to undefined]
**lifecycle_policy** | **{ [key: string]: any; }** | Lifecycle policy (extracted from lifecycle) | [optional] [readonly] [default to undefined]
**marketplace_policy** | **{ [key: string]: any; }** | Marketplace policy (extracted from marketplace) | [optional] [readonly] [default to undefined]
**schema_fields** | **Array&lt;{ [key: string]: any; }&gt;** | Array of schema fields with all properties and constraint flags | [optional] [readonly] [default to undefined]
**schema_relationships** | **Array&lt;{ [key: string]: any; }&gt;** | Object-level relationships from schema (ODCS v3.1.0) | [optional] [readonly] [default to undefined]
**has_relationships** | **boolean** | Whether the contract has schema relationships | [optional] [readonly] [default to undefined]
**contact** | **Array&lt;{ [key: string]: any; }&gt;** | Support/contact channels extracted from contact | [optional] [readonly] [default to undefined]
**support** | **Array&lt;{ [key: string]: any; }&gt;** | Support channels extracted from support | [optional] [readonly] [default to undefined]
**servers** | **Array&lt;{ [key: string]: any; }&gt;** | Server endpoints extracted from servers | [optional] [readonly] [default to undefined]
**servicelevels** | **Array&lt;{ [key: string]: any; }&gt;** | Service level objectives extracted from servicelevels | [optional] [readonly] [default to undefined]
**terms** | **{ [key: string]: any; }** | Terms of use extracted from terms | [optional] [readonly] [default to undefined]
**definitions** | **Array&lt;{ [key: string]: any; }&gt;** | Definitions extracted from definitions | [optional] [readonly] [default to undefined]
**models** | **Array&lt;{ [key: string]: any; }&gt;** | Models extracted from models | [optional] [readonly] [default to undefined]
**roles** | **Array&lt;{ [key: string]: any; }&gt;** | Access roles extracted from roles | [optional] [readonly] [default to undefined]
**team** | **Array&lt;{ [key: string]: any; }&gt;** | Team memberships extracted from team | [optional] [readonly] [default to undefined]
**pricing** | **{ [key: string]: any; }** | Pricing information extracted from price/pricing | [optional] [readonly] [default to undefined]
**lineage** | **{ [key: string]: any; }** | Lineage extracted from transformSourceObjects/transformLogic | [optional] [readonly] [default to undefined]
**quality_type** | **string** | Quality framework type extracted from quality.type | [optional] [readonly] [default to undefined]
**quality_specification** | **string** | Quality specification extracted from quality.specification | [optional] [readonly] [default to undefined]
**canonical_iri** | **string** | Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/contract/{id}. Stable identifier for JSON-LD dereference. See Phase 226 G7a. | [optional] [readonly] [default to undefined]
**latest_compliance_run** | **string** | Latest SUCCEEDED compliance run for this contract\&#39;s bound asset (Phase 231.3). | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Contract } from './api';

const instance: Contract = {
    id,
    tenant,
    asset,
    asset_id,
    version,
    status,
    original_spec_type,
    original_spec_version,
    original_format,
    original_raw,
    hub_contract_version,
    hub_contract_json,
    normalization_status,
    normalization_errors,
    normalization_warnings,
    validation_status,
    validation_errors,
    validation_warnings,
    cli_version,
    last_validated_at,
    created_by,
    created_at,
    updated_at,
    owners,
    tags,
    quality_rules,
    compliance_policy,
    lifecycle_policy,
    marketplace_policy,
    schema_fields,
    schema_relationships,
    has_relationships,
    contact,
    support,
    servers,
    servicelevels,
    terms,
    definitions,
    models,
    roles,
    team,
    pricing,
    lineage,
    quality_type,
    quality_specification,
    canonical_iri,
    latest_compliance_run,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
