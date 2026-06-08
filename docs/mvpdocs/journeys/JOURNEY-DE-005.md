# JOURNEY-DE-005: Upload and Activate Custom Ontology

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-SEM-ONTO-001
**Phase:** 284 (GA Promotion)
**Status:** Implemented
**E2E:** `custom-ontology.spec.ts`
**Routes:** `/semantic?tab=custom-ontologies`

## Overview

A Data Engineer uploads a custom RDF ontology (Turtle, RDF/XML, or JSON-LD) to extend the tenant's knowledge graph with domain-specific classes and properties. The ontology is validated against namespace constraints, uploaded to the semantic store, and activated to load it into the tenant's named graph in Fuseki for SPARQL querying and inference.

## Journey Steps

1. **Navigate to custom ontologies** — From the Semantic page, the DE clicks the "Custom Ontologies" tab (TENANT_ADMIN only). The `OntologyManager` component renders with upload form and list of existing ontologies.
2. **Upload ontology** — Fill name (URL-safe slug), namespace IRI, select format (turtle/rdf_xml/json_ld), attach RDF body file (≤10 MB). POSTs to `POST /api/v1/semantic/ontologies/`. Backend validates: parse success, namespace match, file size ≤10 MB, no reserved namespace collision. Returns created ontology with status UPLOADED.
3. **List ontologies** — The manager lists all tenant ontologies with name, namespace, format, status (UPLOADED/ACTIVE/INACTIVE), and upload date.
4. **Activate ontology** — Clicks "Activate" → `PATCH /api/v1/semantic/ontologies/{id}/` with `is_active: true`. Backend loads the ontology into the tenant's Fuseki named graph at `urn:tenant:{id}:ontology:{name}`. Status transitions to ACTIVE.
5. **Deactivate ontology** — Clicks "Deactivate" → `PATCH /api/v1/semantic/ontologies/{id}/` with `is_active: false`. Drops the Fuseki named graph. Status transitions to INACTIVE.

## Error Handling

- **Parse failure** — Backend returns 400 with `ONTOLOGY_PARSE_ERROR` and the specific parse error location.
- **Namespace mismatch** — Declared namespace IRI doesn't match the RDF body's `@prefix` / `xmlns` declarations.
- **Reserved namespace** — Attempt to use a Meshant-reserved namespace (e.g., `urn:meshant:`) returns 400 `RESERVED_NAMESPACE`.
- **File too large** — >10 MB returns 413 with size limit in the error detail.
- **Upload network failure** — `<ErrorDisplay>` with retry; file input state preserved.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `ONTOLOGY_UPLOADED` | New ontology uploaded | 90 days |
| `ONTOLOGY_ACTIVATED` | Ontology activated into Fuseki | 90 days |
| `ONTOLOGY_DEACTIVATED` | Ontology deactivated | 90 days |

## Success Criteria

- DE can upload a valid Turtle file and activate it in under 60 seconds.
- Invalid RDF is rejected with a specific, actionable error message.
- Activated ontology triples are queryable via SPARQL within 10 seconds.
- Deactivation drops the named graph and triples are no longer returned by queries.
- Cross-tenant ontology isolation: tenant A's ontology is never visible to tenant B.

## Related

- E2E: `frontend/e2e/journeys/ai-ml-semantic/custom-ontology.spec.ts`
- Runbook: [semantic-ontology.md](../../runbooks/semantic-ontology.md)
- Components: `OntologyManager`
- CLI: `datahub semantic custom-ontology upload/list/activate/deactivate`
- SDK: `client.semantic.upload_custom_ontology/list_custom_ontologies/activate_ontology/deactivate_ontology`
- Phase: 230.10, 284.B (GA promotion)
