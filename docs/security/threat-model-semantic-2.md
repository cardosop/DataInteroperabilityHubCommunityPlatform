# Threat Model — Semantic Phase 2 (federation, ontology, search, SEO)

**Phase:** 230 (covers 230.8 — 230.11)
**Status:** Per-sub-phase notice; full STRIDE pending sub-phase landings.
**Owners:** Platform Security

## Scope

This file tracks the security-review status of the Phase 230
sub-phases that introduce inbound write surfaces or new external
egress paths beyond the foundational SPARQL surface (covered by
`threat-model-semantic-1.md`).

### 230.8 SPARQL federation (`SERVICE <url>`)

**Status:** STRIDE table maintained inline in the federation-
service module's docstring (`hub/apps/semantic/federation.py`)
because the surface is small + isolated to one module.

**Headline mitigations:**

- Per-tenant `TenantSparqlEndpoint` allowlist — `SERVICE` clauses
  with URLs not in the allowlist are REJECTED at validation time
  with structured error `SPARQL_FEDERATION_NOT_ALLOWED`.
- Outbound timeout cap of 30s — bounds slow-loris exposure on
  malicious / slow partner endpoints.
- Audit emission on EVERY federated query (success + failure +
  denied) so allowlist drift is reconstructable from the audit log.

### 230.10 Custom ontology registration

**Status:** No separate threat-model needed. The surface is
TENANT_ADMIN-only, capability-flag-gated, with all writes scoped
to per-tenant Fuseki named graphs (`urn:tenant:{id}:ontology:{name}`).
No cross-tenant data flow.

**Inline mitigations** (documented in
`docs/runbooks/semantic-ontology.md`):

- Size cap (10 MB raw / 100k triples).
- Reserved-namespace rejection (no tenant can claim
  `https://meshant.com/ontology/`).
- Per-tenant namespace + name UniqueConstraints at DB layer.
- Validation runs BEFORE Fuseki write — invalid bodies never
  reach the triple store.

### 230.9 Schema.org SEO markup

**Status:** No threat surface. The injected `<script
type="application/ld+json">` is data-only (browsers don't execute
it per W3C HTML "valid script types" set), public-page-only by
design (auth-gated pages don't emit), and Schema.org structured
data is intentionally crawler-discoverable.

### 230.11 Semantic search promotion

**Status:** PENDING — re-open this section when 230.11 lands. The
expected attack surface is read-side (query expansion via SPARQL
CONSTRUCT against tenant ontologies) so the threat profile mirrors
230.8 federation rather than 230.12 LDN.

## When to extend this document

Re-open the relevant section if:

- A new partner-discovery mechanism is added to federation (e.g.
  cross-tenant SERVICE bridging without explicit allowlisting).
- Custom ontologies gain a federation surface (e.g. partner-driven
  ontology fetch over the public internet).
- Search expansion gains a write surface (e.g. user-defined
  expansion rules executed at query time).

The Phase 230.12 (LDN) surface is independently threat-modelled in
`docs/security/threat-model-semantic-3.md`.

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-{federation,ontology,seo,search}/spec.md`
- Tasks: `openspec/changes/preprod01/tasks.md` § 230.8 — 230.11
- Federation runbook: `docs/runbooks/semantic-federation.md` (ships with 230.8)
- Ontology runbook: `docs/runbooks/semantic-ontology.md`
