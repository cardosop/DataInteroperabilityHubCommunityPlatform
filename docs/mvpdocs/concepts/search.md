# Search

Search in Meshant provides full-text and faceted discovery across [assets](assets.md), [contracts](contracts.md), [datasets](datasets.md), and [marketplace listings](marketplace-listings.md). It enables data consumers to find relevant data products quickly, using keyword queries, domain filters, quality score ranges, compliance status, and other metadata facets. Search is the primary discovery mechanism for both internal teams and marketplace buyers.

The search system maintains two isolated index domains: a tenant-internal index (scoped to the querying user's tenant) and a marketplace index (containing only published listings visible to the querying tenant). This isolation is enforced at the infrastructure level, not just query-time filtering.

## Lifecycle

Search indexes are maintained automatically. There is no user-managed lifecycle, but understanding the indexing pipeline helps set expectations:

| Stage | Description |
|---|---|
| `real-time` | Asset metadata changes are indexed within seconds of the write operation. Keyword search reflects the latest state. |
| `near-real-time` | Facet aggregations and quality score histograms are recomputed every 30 seconds. |
| `batch` | Semantic embeddings for semantic search are regenerated every 15 minutes or when a significant metadata change occurs. |

## Query Types

| Type | Description |
|---|---|
| Keyword search | Standard full-text search across asset names, descriptions, tags, and contract rule names. Supports quoted phrases and boolean operators. |
| Faceted filtering | Filter results by domain, data format, quality score range, compliance status, owner, and creation date range. Facets return counts for refinement. |
| Semantic search | Find assets by meaning rather than exact keywords. Uses vector embeddings to match queries like "customer purchase history" to assets tagged as "transaction logs". |
| Saved searches | Users can save search queries with filters for repeated use. Saved searches can be shared within the tenant. |

## Facets

| Facet | Description |
|---|---|
| `domain` | The business domain the asset belongs to (e.g., finance, marketing, operations). |
| `format` | The data format (CSV, Parquet, JSON, Avro, etc.). |
| `quality_score` | Range filter on the most recent DQ run score (0-100). |
| `compliance_status` | Filter by risk level from the most recent compliance run (low, medium, high, critical). |
| `owner` | The user or team that owns the asset. |
| `created_at` | Date range filter on asset creation date. |
| `updated_at` | Date range filter on last modification date. |
| `tags` | User-defined tags applied to the asset. |
| `has_contract` | Whether the asset has at least one bound contract. |
| `lifecycle_state` | The current lifecycle state of the asset. |

## Relationships

- **Assets** -- [Assets](assets.md) are the primary searchable entity. All asset metadata fields are indexed.
- **Contracts** -- [Contracts](contracts.md) are searchable by name, domain, rule types, and schema column names.
- **Datasets** -- [Dataset](datasets.md) metadata (format, size, row count) contributes to search facets.
- **Marketplace Listings** -- Published [listings](marketplace-listings.md) are indexed in the marketplace search domain, including pricing and rating information.
- **Semantic Resources** -- The [semantic layer](semantic-resources.md) enriches search with linked data annotations, enabling ontology-aware queries.
- **DQ Runs** -- The most recent [DQ run](dq-runs.md) score is a searchable facet.
- **Compliance Runs** -- The most recent [compliance run](compliance-runs.md) risk level is a searchable facet.

## MVP Scope

**Available at launch:**

- Full-text keyword search with relevance ranking.
- Faceted filtering across all listed facets.
- Tenant-isolated search indexes.
- Marketplace search index for published listings.
- Pagination with cursor-based iteration.
- Search result highlighting (matching terms emphasized in results).
- Sort by relevance, name, quality score, creation date, or update date.
- Search via API, CLI, and SDK.

- Typeahead/autocomplete suggestions (trigram similarity).

**Post-MVP:**

- Semantic search using vector embeddings.
- Saved searches with sharing and notification on new matches.
- Search analytics (popular queries, zero-result queries, click-through rates).
- Federated search across multiple tenants (for platform-admin use).
- Natural language search with query intent parsing.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Search assets | `GET /api/v1/search/assets` | `meshant search assets <query>` | `client.search.assets(query)` |
| Search contracts | `GET /api/v1/search/contracts` | `meshant search contracts <query>` | `client.search.contracts(query)` |
| Search marketplace | `GET /api/v1/search/marketplace` | `meshant search marketplace <query>` | `client.search.marketplace(query)` |
| Get facets | `GET /api/v1/search/facets` | `meshant search facets` | `client.search.facets()` |
| Save search | `POST /api/v1/search/saved` | `meshant search save <name>` | `client.search.save(name, query)` |
| List saved searches | `GET /api/v1/search/saved` | `meshant search saved` | `client.search.saved()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for query syntax and facet parameter details.
