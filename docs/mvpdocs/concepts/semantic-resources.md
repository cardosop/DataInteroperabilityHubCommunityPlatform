# Semantic Resources

Semantic resources in Meshant expose platform metadata as linked data, enabling machine-readable discovery and interoperability with external knowledge graphs and data catalogs. Every [asset](assets.md), [contract](contracts.md), and dataset is assigned a stable URI and described using JSON-LD context. A SPARQL endpoint allows external systems to query Meshant metadata using standard Semantic Web protocols.

The semantic layer bridges the gap between Meshant's operational data management and the broader data ecosystem. Organizations that already use RDF-based catalogs, ontology registries, or knowledge graphs can integrate Meshant metadata without custom API integrations.

## Lifecycle

Semantic resources mirror the lifecycle of the entities they describe:

| Stage | Description |
|---|---|
| `minted` | A URI has been assigned to the entity at creation time. The URI is stable and will not change. |
| `published` | JSON-LD metadata is available at the URI. The SPARQL endpoint returns triples for this resource. |
| `updated` | The entity's metadata has changed. The RDF representation is updated. Previous versions are available via content negotiation (Accept-Datetime header). |
| `tombstoned` | The underlying entity has been archived or deleted. The URI returns a 410 Gone status with a tombstone record indicating when and why the resource was removed. |

URIs follow the pattern: `https://meshant-internal.example.com/semantic/{tenant_id}/{resource_type}/{resource_id}`

## JSON-LD Context

All Meshant semantic resources use a shared JSON-LD context that maps platform fields to standard vocabularies:

| Vocabulary | Prefix | Usage |
|---|---|---|
| DCAT | `dcat:` | Dataset and distribution metadata (format, size, access URL). |
| Dublin Core | `dcterms:` | Title, description, creator, date, rights. |
| ODRL | `odrl:` | Licensing and usage policies for marketplace listings. |
| Schema.org | `schema:` | Organization, person, and rating information. |
| PROV-O | `prov:` | Provenance and lineage relationships (wasDerivedFrom, wasGeneratedBy). |
| Meshant | `meshant:` | Platform-specific properties (quality score, compliance status, contract binding). |

Content negotiation on any resource URI supports `application/ld+json`, `text/turtle`, and `application/rdf+xml`.

## SPARQL Endpoint

The SPARQL endpoint (`https://meshant-internal.example.com/semantic/sparql`) supports read-only queries over the full semantic graph of a tenant. Queries are authenticated and tenant-scoped -- a query can only access resources within the authenticated user's tenant.

Example query -- find all assets with a DQ score above 80:

```sparql
PREFIX meshant: <https://meshant.com/ontology/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>

SELECT ?asset ?name ?score
WHERE {
  ?asset a dcat:Dataset ;
         dcterms:title ?name ;
         meshant:qualityScore ?score .
  FILTER (?score > 80)
}
ORDER BY DESC(?score)
```

## Relationships

- **Assets** -- Every [asset](assets.md) is a semantic resource with a stable URI and JSON-LD metadata. Asset properties (name, domain, quality score, compliance status) are expressed as RDF triples.
- **Contracts** -- [Contracts](contracts.md) are described as semantic resources, with schema definitions and quality rules mapped to standard vocabularies.
- **Search** -- The [search](search.md) system indexes semantic annotations, enabling ontology-aware queries that match synonyms and related concepts.
- **Lineage** -- [Lineage](lineage.md) relationships are expressed using PROV-O vocabulary (prov:wasDerivedFrom, prov:wasGeneratedBy), making the lineage graph queryable via SPARQL.
- **Marketplace Listings** -- [Listings](marketplace-listings.md) include ODRL licensing metadata, allowing external catalogs to discover data products with specific usage rights.
- **Governance** -- [Governance](governance.md) policies can reference semantic categories (e.g., "all resources classified as prov:Collection must have lineage").

## MVP Scope

**Available at launch:**

- Stable URI assignment for all assets, contracts, and datasets.
- JSON-LD metadata at each resource URI.
- Content negotiation: JSON-LD, Turtle, RDF/XML.
- Read-only SPARQL endpoint with tenant-scoped access.
- DCAT, Dublin Core, and PROV-O vocabulary mappings.
- Tombstone responses for archived resources.
- API endpoint for bulk RDF export (N-Triples format).

**Post-MVP:**

- SPARQL federation with external endpoints.
- Custom ontology registration per tenant.
- OWL reasoning for inferred relationships.
- Schema.org markup in the web UI for SEO and external discovery.
- Linked data notifications (W3C LDN) for cross-catalog synchronization.
- GraphQL-LD endpoint as an alternative to SPARQL for developers unfamiliar with RDF.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Get resource RDF | `GET /api/v1/semantic/{type}/{id}` | `meshant semantic get <type> <id>` | `client.semantic.get(type, id)` |
| SPARQL query | `POST /api/v1/semantic/sparql` | `meshant semantic query "<sparql>"` | `client.semantic.query(sparql)` |
| Bulk export | `POST /api/v1/semantic/export` | `meshant semantic export` | `client.semantic.export()` |
| Get JSON-LD context | `GET /api/v1/semantic/context` | `meshant semantic context` | `client.semantic.context()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for content negotiation headers and SPARQL query limits.
