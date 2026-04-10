# Meshant Semantic API

The Semantic API exposes the Meshant knowledge graph and linked-data
capabilities. It resolves semantic URIs to their metadata, accepts
SPARQL queries for advanced graph traversal, and serves JSON-LD
context documents that enable interoperability with external systems.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/semantic/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /semantic/resolve/ | Resolve a semantic URI to its metadata |
| POST | /semantic/sparql/ | Execute a SPARQL query against the knowledge graph |
| GET | /semantic/contexts/ | List available JSON-LD context documents |
| GET | /semantic/contexts/{id}/ | Get a specific JSON-LD context |
| POST | /semantic/contexts/ | Create a custom JSON-LD context |
| PUT | /semantic/contexts/{id}/ | Update a JSON-LD context |
| DELETE | /semantic/contexts/{id}/ | Delete a custom JSON-LD context |
| GET | /semantic/ontologies/ | List registered ontologies |
| POST | /semantic/ontologies/ | Register a new ontology |
| GET | /semantic/graph/neighbors/ | Get neighbors of a node in the knowledge graph |

## Request / Response Examples

### GET /semantic/resolve/?uri=meshant://tenant/acme/dataset/q1-sales

**Response 200:**

```json
{
  "uri": "meshant://tenant/acme/dataset/q1-sales",
  "type": "dataset",
  "name": "Q1 Sales",
  "tenant": "acme",
  "resource_id": "ds_abc123",
  "metadata": {
    "format": "csv",
    "row_count": 15200,
    "domain": "finance"
  }
}
```

### POST /semantic/sparql/

**Request body:**

```json
{
  "query": "SELECT ?asset ?domain WHERE { ?asset a meshant:DataAsset ; meshant:domain ?domain . } LIMIT 10"
}
```

**Response 200:**

```json
{
  "columns": ["asset", "domain"],
  "rows": [
    ["meshant://tenant/acme/asset/q1-sales", "finance"],
    ["meshant://tenant/acme/asset/customer-events", "marketing"]
  ]
}
```

## Common Parameters

- `uri` (string) -- The semantic URI to resolve (query param for resolve endpoint).
- `format` (string) -- Response format: `json`, `jsonld`, `turtle` (default: `json`).
- `page` (int) -- Page number for paginated results.
- `page_size` (int) -- Items per page (default: 20, max: 100).

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `SEMANTIC_QUERY_INVALID` | SPARQL query has syntax errors |
| 404 | `SEMANTIC_URI_NOT_FOUND` | The requested URI does not resolve to any resource |
| 404 | `SEMANTIC_CONTEXT_NOT_FOUND` | JSON-LD context ID does not exist |
| 408 | `SEMANTIC_QUERY_TIMEOUT` | SPARQL query exceeded the execution time limit |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub semantic`](../cli-reference/semantic.md)
- SDK: [`SemanticAPI`](../sdk-reference/python/semantic.md)
