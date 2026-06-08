# UC-SEM-004: Query with Inference Rules

**ID:** UC-SEM-004
**Title:** Query with Inference Rules
**Persona:** Data Engineer (DE)
**Priority:** Medium
**Phase:** 283.4 (GA)
**Feature Flag:** `semantic_inference_enabled` (OFF by default, opt-in power-user)

## Summary

A Data Engineer executes SPARQL queries with materialised inference enabled,
allowing the query to return triples derived from the tenant's ontology
reasoner in addition to explicitly asserted triples.

## Preconditions

- Tenant has `semantic_inference_enabled = True`
- User has DE or TENANT_ADMIN role
- Tenant has at least one active ontology loaded

## Main Flow

1. DE navigates to the SPARQL query builder
2. DE writes a SPARQL query targeting a class or property
3. DE enables "Materialised Inference" toggle
4. Hub executes the query against the reasoner, which expands the results
   with inferred triples (subClassOf, equivalentClass, subPropertyOf, etc.)
5. Results are returned with an indicator distinguishing asserted vs inferred
6. DE can export results in JSON, CSV, or TSV format

## Acceptance Criteria

- Inference toggle available when flag is enabled
- Query results include inferred triples
- Inferred triples are visually distinguishable from asserted
- SPARQL query timeout enforced with appropriate error messaging
