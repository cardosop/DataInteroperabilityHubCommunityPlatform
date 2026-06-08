# TenantOntology

Serialiser for the TenantOntology model.  ``rdf_content`` is write-only on POST (uploads carry the body) but read-only on GET — listing endpoints exclude the body to avoid 10 MB-per-row response payloads. ``named_graph_uri`` is derived and read-only.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Short, URL-safe name used as the Fuseki named-graph suffix (&#x60;&#x60;urn:tenant:{id}:ontology:{name}&#x60;&#x60;). MUST be unique per tenant. | [default to undefined]
**namespace_iri** | **string** | The ontology\&#39;s declared namespace IRI (the prefix used in tenant SPARQL queries). MUST be unique per tenant and MUST NOT collide with the reserved Meshant namespace &#x60;&#x60;https://meshant.com/ontology/&#x60;&#x60;. | [default to undefined]
**format** | **string** | Serialisation format of &#x60;&#x60;rdf_content&#x60;&#x60;. Determines the rdflib parser used for validation.  * &#x60;turtle&#x60; - Turtle * &#x60;rdf_xml&#x60; - RDF/XML * &#x60;json_ld&#x60; - JSON-LD | [optional] [default to undefined]
**rdf_content** | **string** | Raw uploaded RDF body. Capped at 10 MB by the validator. | [default to undefined]
**triple_count** | **number** | Cached triple count after rdflib parse. Capped at 100,000; rows above the cap are rejected. | [optional] [readonly] [default to undefined]
**validation_status** | **string** | * &#x60;PENDING&#x60; - Pending * &#x60;VALIDATING&#x60; - Validating * &#x60;VALID&#x60; - Valid * &#x60;INVALID&#x60; - Invalid * &#x60;LOAD_FAILED&#x60; - Load Failed | [optional] [readonly] [default to undefined]
**validation_errors** | **any** | List of {code, message, ...} dicts populated when validation fails. Empty list when validation_status&#x3D;VALID. | [optional] [readonly] [default to undefined]
**is_active** | **boolean** | When True, the ontology is loaded into the Fuseki named graph. Setting False drops the named graph. | [optional] [default to undefined]
**activated_at** | **string** | When the ontology was last activated. NULL when never activated; tracked separately from updated_at so a metadata-only PATCH (e.g. validation_errors) does not shift the activation timestamp. | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**named_graph_uri** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { TenantOntology } from './api';

const instance: TenantOntology = {
    id,
    name,
    namespace_iri,
    format,
    rdf_content,
    triple_count,
    validation_status,
    validation_errors,
    is_active,
    activated_at,
    created_at,
    updated_at,
    named_graph_uri,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
