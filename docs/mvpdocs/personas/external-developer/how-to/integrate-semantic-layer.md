# How-To: Integrate the Semantic Layer

Meshant exposes a semantic layer built on JSON-LD metadata and a SPARQL
query endpoint. This guide shows how to query the knowledge graph, work
with linked data, and validate resources against SHACL shapes.


## Overview

The semantic layer enriches Meshant resources (assets, contracts, datasets)
with machine-readable metadata:

- **JSON-LD annotations** on every resource provide linked-data context.
- **SPARQL endpoint** allows graph queries across the entire knowledge
  layer.
- **SHACL shapes** define validation constraints for resource metadata.
- **Ontology explorer** lets you browse the Meshant ontology (classes,
  properties, relationships).


## Querying with SPARQL

### Via the CLI

```bash
datahub-cli semantic sparql query \
  --query "SELECT ?asset ?name WHERE { ?asset a :DataAsset ; :name ?name . } LIMIT 10" \
  --format table
```

For complex queries, write the SPARQL to a file:

```bash
datahub-cli semantic sparql query \
  --file my-query.sparql \
  --accept "application/sparql-results+json" \
  --format json
```

### Via the API

```bash
curl -X POST https://meshant-internal.example.com/api/v1/semantic/sparql/query/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  -d 'SELECT ?asset ?name WHERE { ?asset a :DataAsset ; :name ?name . } LIMIT 10'
```

### Via the SDK

```python
from datahub_interoperability import DataHubClient

client = DataHubClient.from_env()

results = client.semantic.sparql_query(
    query="SELECT ?asset ?name WHERE { ?asset a :DataAsset ; :name ?name . } LIMIT 10",
    accept="application/sparql-results+json",
)

for binding in results["results"]["bindings"]:
    print(f"{binding['asset']['value']}  {binding['name']['value']}")
```


## Working with JSON-LD

Every asset response includes a `@context` and `@type` field when you
request JSON-LD format:

```bash
curl -H "Accept: application/ld+json" \
  -H "Authorization: Api-Key YOUR_KEY" \
  https://meshant-internal.example.com/api/v1/assets/<asset-id>/
```

Example response:

```json
{
  "@context": "https://meshant-internal.example.com/api/v1/semantic/context/",
  "@type": "DataAsset",
  "@id": "https://meshant-internal.example.com/api/v1/assets/a1b2c3d4/",
  "name": "Customer Demographics",
  "domain": "marketing",
  "qualityStatus": "PASSED",
  "complianceStatus": "COMPLIANT",
  "datePublished": "2026-03-15T10:00:00Z"
}
```

Use the `@context` URL to resolve property definitions in the Meshant
ontology.


## Browsing the Ontology

The ontology defines the classes (e.g., `DataAsset`, `DataContract`,
`QualityCheck`) and properties (e.g., `name`, `domain`, `qualityStatus`)
used in Meshant's knowledge graph.

### Via the CLI

```bash
# List ontology classes
datahub-cli semantic ontology classes --format table

# List properties for a class
datahub-cli semantic ontology properties --class DataAsset --format table
```

### Via the API

```bash
curl -H "Authorization: Api-Key YOUR_KEY" \
  https://meshant-internal.example.com/api/v1/semantic/ontology/classes/
```


## Validating with SHACL

SHACL (Shapes Constraint Language) shapes define validation rules for
resource metadata. Use SHACL validation to verify that your programmatically
created resources conform to the expected schema before publishing.

### Via the CLI

```bash
datahub-cli semantic shacl validate \
  --data my-asset.jsonld \
  --format table
```

### Via the API

```bash
curl -X POST https://meshant-internal.example.com/api/v1/semantic/shacl/validate/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/ld+json" \
  -d @my-asset.jsonld
```

The response indicates whether the data conforms and, if not, which
constraints were violated.


## Use Cases for Semantic Integration

| Use Case | Approach |
|----------|----------|
| Build a knowledge graph dashboard | SPARQL queries against the endpoint |
| Auto-classify assets by domain | Query JSON-LD `@type` and `domain` properties |
| Cross-reference assets with external catalogs | Use `@id` URIs for linked-data joins |
| Validate metadata before publishing | SHACL validation endpoint |
| Power a recommendation engine | SPARQL graph traversal (related assets, shared domains) |


## See Also

- [How-To: Authenticate and Authorize](authenticate-and-authorize.md)
- [How-To: Handle Webhooks](handle-webhooks.md)
- [External Developer Reference](../reference.md)
