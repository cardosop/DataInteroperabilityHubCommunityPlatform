# UC-SEM-006: Search with Semantic Facets

**ID:** UC-SEM-006
**Title:** Search with Semantic Facets
**Persona:** Data Consumer (DC)
**Priority:** Medium
**Phase:** 284.D (GA)
**Feature Flag:** `semantic_search_enabled` (OFF by default, opt-in power-user)

## Summary

A Data Consumer uses the catalogue search with ontology-aware query expansion
and semantic facets (ontology type filter, RDF class faceting) to discover
data products through their semantic relationships rather than keyword matching
alone.

## Preconditions

- Tenant has `semantic_search_enabled = True`
- Tenant has semantic mappings for catalogue assets
- User has DC role

## Main Flow

1. DC navigates to the Search page
2. DC enters a search term (e.g., "customer")
3. DC enables "Ontology-aware search" toggle
4. Hub expands the query using tenant ontology relations (synonyms,
   equivalent classes, parent/child concepts)
5. Semantic facets appear: Ontology Type filter (dcat:Dataset, foaf:Document)
   and RDF Class faceting (schema:CreativeWork, owl:Thing) with result counts
6. DC clicks a facet to filter results by ontology type or RDF class
7. Results update to show only matching items
8. On SPARQL timeout, a retry button appears

## Acceptance Criteria

- Ontology-aware toggle visible and functional
- Semantic facets render with result counts per facet
- Facet selection filters search results
- SPARQL timeout shows retry UI
- Facets gracefully hidden when flag is disabled
