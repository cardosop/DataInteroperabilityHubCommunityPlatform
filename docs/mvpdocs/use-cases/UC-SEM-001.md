# UC-SEM-001: Upload Custom Ontology

**ID:** UC-SEM-001
**Title:** Upload Custom Ontology
**Persona:** Data Engineer (DE)
**Priority:** Medium
**Phase:** 283.4 (GA)
**Feature Flag:** `semantic_custom_ontology_enabled` (OFF by default, opt-in power-user)

## Summary

A Data Engineer uploads a custom OWL/RDF ontology (Turtle, RDF/XML, or JSON-LD)
to extend the tenant's semantic model with domain-specific concepts and
relationships.

## Preconditions

- Tenant has `semantic_custom_ontology_enabled = True`
- User has DE or TENANT_ADMIN role
- Ontology file is valid RDF (≤10 MB), parsed by rdflib

## Main Flow

1. DE navigates to Ontology Manager
2. DE uploads a Turtle/RDF-XML/JSON-LD file with declared namespace IRI
3. Hub validates: file size (≤10 MB), rdflib parse, namespace uniqueness,
   reserved-namespace rejection
4. On success, the ontology is registered as a `TenantOntology` row and
   the triple count is recorded
5. DE can activate the ontology to include it in the tenant's reasoning scope
6. Hub enqueues async validation job (`ONTOLOGY_VALIDATE`) to compute
   triple count and structural checks

## Acceptance Criteria

- Upload accepts Turtle, RDF/XML, JSON-LD formats
- Validation rejects oversized, malformed, or reserved-namespace ontologies
- Activated ontologies contribute to SPARQL inference scope
- Ontology list shows status, triple count, and activation state
