# Threat Model — Semantic Phase 1 (foundational SPARQL surface)

**Phase:** 230 (covers 230.0 — 230.7)
**Status:** Coverage notice — no NEW attack surface vs prior security doctrine.
**Owners:** Platform Security

## Scope

This file documents the security-review status of the Phase 230
sub-phases that operate on the platform's existing SPARQL +
dereference + tombstone surfaces:

- **230.1** Canonical IRI surfacing — read-only UI affordance over
  data already exposed via the dereference endpoint.
- **230.2** Bulk RDF export — read scope identical to existing
  SPARQL CONSTRUCT, throttled (5 req / 5 min / user) and capped
  (100M triples / response).
- **230.3** Tombstone lifecycle + 410 Gone — terminal-state
  semantics; reduces information disclosure (tombstoned IRIs
  return structural 410 instead of leaking the original triples).
- **230.4** Memento Accept-Datetime — read-only versioned access
  to the SAME tenant graph already covered by SPARQL ACL.
- **230.5** Contract relationships endpoint — tenant-scoped
  wrapper around an existing internal SPARQL path.
- **230.6** /context route alias — byte-identical bytes to the
  existing /context.jsonld; same auth, same caching.
- **230.7** Per-tenant OWL/RDFS reasoning — the inferred dataset
  binds to the SAME on-disk TDB2 store; no new write surface.

## Why no separate STRIDE table

Each of the surfaces above is either:

1. A read-only projection of data already covered by the platform's
   tenant-isolation ACL (every SPARQL query is tenant-scoped via
   `urn:tenant:{id}` named-graph filtering), or
2. A read-side cap or terminal-state transition that REDUCES
   attack surface relative to the prior state (export caps,
   throttles, 410 short-circuits).

The threats already enumerated in the platform's foundational
security review (cross-tenant fingerprinting, SPARQL injection,
named-graph escape) apply unchanged. No NEW threat vectors have
been introduced; no new mitigations are required.

## When to extend this document

Re-open this threat model if any of the following lands:

- A NEW write surface (e.g. a SPARQL UPDATE endpoint exposed to
  external partners — `230.2` is read-only by design).
- A NEW data-classification boundary (e.g. cross-region
  replication of tenant graphs).
- A change to the tenant-isolation primitive itself (e.g.
  switching from `urn:tenant:{id}` named graphs to a different
  isolation model).

The Phase 230.8 (federation) and Phase 230.12 (LDN) surfaces ARE
new attack surfaces and have their own threat models:

- `docs/security/threat-model-semantic-2.md` — federation (230.8).
- `docs/security/threat-model-semantic-3.md` — W3C LDN (230.12).

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-*/spec.md`
- Tasks: `openspec/changes/preprod01/tasks.md` § 230.0 — 230.7
- Existing platform security doctrine: `docs/security/`
