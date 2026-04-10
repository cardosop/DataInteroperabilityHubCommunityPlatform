# How to Use Semantic Queries (SPARQL and JSON-LD)

Meshant exposes asset metadata as linked data. You can query it using SPARQL
for complex graph traversals or retrieve JSON-LD representations for
machine-readable metadata integration.

## Prerequisites

- An API token with the **data_engineer** role.
- At least one published asset with metadata (schema, lineage, domain).
- Familiarity with basic SPARQL syntax (helpful but not required -- examples
  are provided below).

## Understanding the Semantic Layer

Meshant models metadata using a lightweight ontology:

- **meshant:Asset** -- a data product.
- **meshant:Contract** -- schema and quality contract attached to an asset.
- **meshant:Domain** -- organizational domain that owns assets.
- **meshant:Lineage** -- upstream/downstream relationships between assets.

These are exposed at the `/api/v1/semantic` endpoint.

## Step 1 -- Retrieve JSON-LD for an Asset

JSON-LD is the simplest way to get structured metadata for a single asset.

**REST API:**

```bash
curl https://meshant-internal.example.com/api/v1/semantic/assets/<ASSET_ID> \
  -H "Authorization: Bearer $MESHANT_TOKEN" \
  -H "Accept: application/ld+json"
```

Response:

```json
{
  "@context": "https://meshant-internal.example.com/api/v1/semantic/context",
  "@type": "meshant:Asset",
  "@id": "meshant:asset/<ASSET_ID>",
  "meshant:name": "clickstream-events",
  "meshant:domain": "product-analytics",
  "meshant:schema": {
    "meshant:fields": [
      {"meshant:name": "event_id", "meshant:type": "string"},
      {"meshant:name": "user_id", "meshant:type": "string"}
    ]
  }
}
```

**SDK:**

```python
from datahub_sdk import MeshantClient

client = MeshantClient()
jsonld = client.semantic.get_asset_jsonld(asset_id="<ASSET_ID>")
print(jsonld)
```

## Step 2 -- Run a SPARQL Query

Use SPARQL to answer questions that span multiple assets, domains, or
lineage edges.

**Example: Find all assets in the "finance" domain:**

```sparql
PREFIX meshant: <https://meshant.com/ontology/>

SELECT ?asset ?name
WHERE {
  ?asset a meshant:Asset ;
         meshant:domain "finance" ;
         meshant:name ?name .
}
ORDER BY ?name
```

**Submit via REST API:**

```bash
curl -X POST https://meshant-internal.example.com/api/v1/semantic/sparql \
  -H "Authorization: Bearer $MESHANT_TOKEN" \
  -H "Content-Type: application/sparql-query" \
  --data-binary @query.sparql
```

**Submit via CLI:**

```bash
datahub semantic query --file query.sparql --format table
```

**Submit via SDK:**

```python
results = client.semantic.sparql("""
    PREFIX meshant: <https://meshant.com/ontology/>
    SELECT ?asset ?name
    WHERE {
      ?asset a meshant:Asset ;
             meshant:domain "finance" ;
             meshant:name ?name .
    }
""")

for row in results.bindings:
    print(f"{row['name']} -> {row['asset']}")
```

## Step 3 -- Trace Lineage

Find all upstream dependencies for a given asset:

```sparql
PREFIX meshant: <https://meshant.com/ontology/>

SELECT ?upstream ?name
WHERE {
  <meshant:asset/ASSET_ID> meshant:dependsOn+ ?upstream .
  ?upstream meshant:name ?name .
}
```

The `+` operator performs a transitive closure, following the `dependsOn`
edges recursively.

## Step 4 -- Integrate into Your Data Catalog

Use the JSON-LD output to feed external catalogs (DataHub, Amundsen, OpenMetadata)
or build custom search indices. The `@context` URL provides the full
vocabulary mapping for automated ingestion.

## Troubleshooting

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| Empty SPARQL results | No assets published yet | Publish at least one asset and retry |
| `406 Not Acceptable` | Missing `Accept` header for JSON-LD | Add `Accept: application/ld+json` |
| Timeout on complex query | Too many triples traversed | Add `LIMIT` clause or narrow the `WHERE` filter |

## Next Steps

- [Automate Contract Validation in CI/CD](automate-contract-validation.md)
- [Trigger DQ Checks via the API](trigger-dq-checks-via-api.md)
- [Semantic Resources Concept](../../../concepts/semantic-resources.md)
