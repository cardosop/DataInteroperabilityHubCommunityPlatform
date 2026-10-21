# UC-SEM-005: Execute GraphQL-LD Query

**ID:** UC-SEM-005
**Title:** Execute GraphQL-LD Query
**Persona:** External Developer (DEV)
**Priority:** Low
**Phase:** 284.B (GA)
**Feature Flag:** `semantic_graphql_ld_enabled` (OFF by default, opt-in power-user)

## Summary

An External Developer uses the tenant's GraphQL-LD endpoint to query the
semantic knowledge graph using GraphQL syntax with JSON-LD context,
combining the familiarity of GraphQL with the semantic richness of RDF.

## Preconditions

- Tenant has `semantic_graphql_ld_enabled = True`
- User has DEV role with API access
- Tenant has semantic data loaded (assets, contracts with RDF mappings)

## Main Flow

1. DEV sends an authenticated POST request to the GraphQL-LD endpoint
2. The request includes a GraphQL query and an optional JSON-LD context
3. Hub validates the query against the GraphQL schema derived from the
   tenant's ontology
4. Hub executes the query, translating GraphQL field selections to SPARQL
   patterns internally
5. Results are returned as JSON-LD with the requested fields and context

## Acceptance Criteria

- GraphQL-LD endpoint accepts authenticated queries
- Query complexity limits enforced (max depth, max node count)
- Results returned as valid JSON-LD
- Rate limiting applied (60 queries/min per user)
- Unauthenticated requests return 401
