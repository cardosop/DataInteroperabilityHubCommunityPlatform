# ADR: Semantic Feature Flags — Opt-In Default (`default_new=False`)

**Date:** 2026-05-16
**Phase:** 283.6.7
**Status:** Accepted
**Author:** Platform Engineering

## Context

Four semantic feature flags are GA-stage with `default_new=False`:
- `semantic_memento_enabled`
- `semantic_inference_enabled`
- `semantic_custom_ontology_enabled`
- `semantic_ldn_enabled`

These are opt-in power-user features. This ADR documents the rationale, satisfying
the `check_stale_defaults.py` CI gate (283.6.7).

## Decision

`default_new=False` is correct for all four flags. These are power-user features
that should not be default-on for new tenants.

## Rationale (per flag)

### `semantic_memento_enabled` — opt-in
Memento datetime negotiation adds snapshot write overhead on every dataset/asset/contract
edit. New tenants without semantic-archive requirements should not pay this cost.

### `semantic_inference_enabled` — opt-in
Materialised inference via the reasoner adds query latency (SPARQL queries fan out to
inferred triples). New tenants should opt in after assessing their ontology complexity
and query performance needs.

### `semantic_custom_ontology_enabled` — opt-in
Uploading custom ontology TTLs requires domain expertise in OWL/RDF ontology curation.
New tenants without semantic engineering resources should not be exposed to this
surface by default.

### `semantic_ldn_enabled` — opt-in
Linked Data Notifications require the tenant to operate an LDN consumer infrastructure.
New tenants without W3C LDN setup should not have an inbox reachable by default.

## Consequences

- New tenants do not see semantic power-user features until explicitly enabled.
- `check_stale_defaults.py` CI gate passes for all four flags.
- Registry entries carry `related_audit_report="docs/adr/semantic-flags-opt-in-default.md"`.

## Related

- `hub/apps/tenants/feature_flag_registry.py` — Flag definitions
- `scripts/check_stale_defaults.py` — CI enforcement
