# JOURNEY-DC-004: Search Catalogue with Semantic Facets

**Persona:** [Data Consumer](../personas/data-consumer/)
**Use Cases:** UC-SEM-SEARCH-001
**Phase:** 284 (GA Promotion — 284.D)
**Status:** Implemented
**E2E:** `semantic-search.spec.ts`
**Routes:** `/search` (with semantic facets active)

## Overview

A Data Consumer searches the Meshant catalogue using keyword search enhanced with semantic facets. When the tenant has `semantic_search_enabled=True`, the search results page renders ontology type filters and RDF class faceting alongside standard keyword results. The DC can filter by ontology type, drill into RDF classes, and see result counts per facet — all powered by SPARQL queries against the tenant's named graph.

## Journey Steps

1. **Enter keyword search** — From the catalogue page (`/search`), the DC enters a keyword (e.g., "customer behavior"). Standard keyword search runs against assets, datasets, and contracts.
2. **Semantic facets render** — If `semantic_search_enabled=True`, the `SemanticSearchFacets` component renders below the search bar with:
   - **Ontology type filter** — checkboxes for each ontology type found in results (e.g., `dcat:Dataset`, `prov:Entity`) with per-type result counts.
   - **RDF class faceting** — expandable tree of RDF classes with instance counts.
3. **Filter by ontology type** — The DC clicks an ontology type checkbox. Results are filtered to only resources of that RDF type. The facet updates counts to reflect the filtered set.
4. **Click result** — Clicks a search result card to navigate to the resource detail page.
5. **SPARQL timeout handling** — If the SPARQL query backing the facets exceeds the 10s timeout, the facet panel shows a retry button and falls back to keyword-only results.

## Error Handling

- **SPARQL timeout** — Facets show `<ErrorDisplay>` with retry button; keyword results remain visible.
- **SPARQL rate limit (429)** — Facets show "Search facets temporarily unavailable — retry in N seconds."
- **Empty semantic index** — Facets render "No semantic metadata indexed for this tenant — upload assets with RDF annotations to enable faceting."
- **Tenant flag off** — `semantic_search_enabled=False` → facets are not rendered; keyword search works normally.

## Success Criteria

- Semantic facets render within 3 seconds for tenants with <10,000 indexed triples.
- Ontology type filter correctly narrows results to resources of the selected type.
- RDF class counts are accurate and update on filter change.
- SPARQL timeout does not block keyword search results.
- Dark mode renders facets with correct contrast (Phase 282 palette).

## Related

- E2E: `frontend/e2e/journeys/ai-ml-semantic/semantic-search.spec.ts` (284.D.3)
- Components: `SemanticSearchFacets`
- Feature flag: `semantic_search_enabled` (GA, opt-in, default_new=False)
- Phase: 230.14, 284.D (CANARY→GA promotion)
