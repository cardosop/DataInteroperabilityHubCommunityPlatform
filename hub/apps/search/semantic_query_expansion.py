"""
Phase 230.11.2 (REQ-SEM-SEARCH-EXPAND-001) — ontology-aware query expansion.

Pure-function module: given a user's free-text query and a tenant id,
return the set of *bridge terms* that the tenant's active ontologies
(plus the Meshant base ontology) link to the query terms via the
spec-listed relations.

The bridge relations:

* ``skos:altLabel``      — alternate lexical label.
* ``skos:related``       — semantically related concept.
* ``owl:equivalentClass``— logical equivalence.
* ``rdfs:subClassOf``    — superclass / subclass (depth ≤ 2 each
  direction).

The bridge set never includes the query term itself.  The label
returned for each bridge is either:

* the literal of an ``rdfs:label`` (preferred), or
* the literal of an ``skos:altLabel`` (when that's the relation), or
* the trailing local-name fragment of the IRI (fallback).

We use rdflib's local SPARQL engine rather than dispatching to the
semantic-service / Fuseki for two reasons:

1. The cost is amortised — the same module is hit on every
   ``?semantic=true`` search, and 100k-triple ontologies fit happily
   in a process-local rdflib graph (under 100 MB resident).
2. The expansion is read-only and tenant-isolated; routing through
   Fuseki would add a network hop + a federation surface for what
   amounts to local string manipulation.

The graph is rebuilt on every call.  Caching is deferred to a future
sub-phase — REQ-SEM-SEARCH-EXPAND-001 doesn't list a freshness SLA, so
the simplest correct implementation is to re-parse the active rows.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# The maximum subclass-walk depth per the spec ("depth ≤ 2").
MAX_SUBCLASS_DEPTH = 2

# rdflib formats keyed by the TenantOntology.format choices.  Keep the
# table in this module so a future format addition is one line.
_FORMAT_MAP = {
    "turtle": "turtle",
    "rdf_xml": "xml",
    "json_ld": "json-ld",
}


@dataclass(frozen=True)
class ExpansionBridge:
    """One bridge from a query term to a related ontology term.

    Attributes:
        label:    The expanded term as a free-text label (lower-case is
                  NOT applied — callers can lower-case if their backend
                  is case-sensitive).  This is the value the search
                  endpoint runs as a secondary FTS query.
        relation: Spec-defined edge label (one of
                  ``skos:altLabel`` / ``skos:related`` /
                  ``owl:equivalentClass`` / ``rdfs:subClassOf``).
        source_term: The original query token that produced this
                  bridge — used by callers that want to attribute the
                  match back to the user's literal input.
    """

    label: str
    relation: str
    source_term: str


def expand_query_terms(
    query: str,
    tenant_id,
) -> list[ExpansionBridge]:
    """Return the bridge terms that the tenant's ontologies link to
    the query.

    Args:
        query: free-text query.  Tokenised on whitespace; each token is
            looked up independently.  Empty string → empty bridge list.
        tenant_id: tenant UUID/PK.  When falsy or the tenant has no
            active ontologies, returns an empty list (no expansion).

    Returns:
        A list of :class:`ExpansionBridge` rows, deduped by
        ``(label.lower(), relation)``.  Order is stable — callers
        iterate in insertion order so deterministic ranking works.
    """
    if not query or not tenant_id:
        return []

    tokens = [t.strip() for t in query.split() if t.strip()]
    if not tokens:
        return []

    graph = _build_active_graph(tenant_id)
    if graph is None:
        return []

    seen: set[tuple] = set()
    out: list[ExpansionBridge] = []
    for token in tokens:
        for bridge in _bridges_for_token(graph, token):
            key = (bridge.label.lower(), bridge.relation)
            if key in seen:
                continue
            seen.add(key)
            out.append(bridge)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_active_graph(tenant_id):
    """Parse every active TenantOntology row + the Meshant base
    ontology into a single rdflib Graph.

    Returns ``None`` on import failure (rdflib missing) or when the
    tenant has no active ontologies (fast-path for the unset case).
    """
    try:
        from rdflib import Graph
    except ImportError:  # pragma: no cover — rdflib is a hard dep.
        logger.warning("semantic_expansion_no_rdflib")
        return None

    try:
        from hub.apps.semantic.models import (
            OntologyValidationStatus,
            TenantOntology,
        )
    except Exception as exc:  # pragma: no cover — import-time only.
        logger.warning("semantic_expansion_import_failed: %s", exc)
        return None

    rows = list(
        TenantOntology.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            validation_status=OntologyValidationStatus.VALID,
        ).values_list("rdf_content", "format")
    )
    if not rows:
        return None

    graph = Graph()
    for content, fmt in rows:
        rdflib_fmt = _FORMAT_MAP.get(fmt)
        if not rdflib_fmt or not content:
            continue
        try:
            graph.parse(data=content, format=rdflib_fmt)
        except Exception as exc:
            logger.warning(
                "semantic_expansion_parse_failed tenant=%s fmt=%s error=%s",
                tenant_id,
                fmt,
                exc,
            )

    # Best-effort load of the bundled Meshant base ontology (when the
    # operator has it on disk).  Never fail the search if it's missing
    # — the per-tenant graph is the load-bearing contributor.
    _load_base_ontology_into(graph)

    if len(graph) == 0:
        return None
    return graph


def _load_base_ontology_into(graph) -> None:
    """Attempt to load ``hub/apps/semantic/ontology.ttl`` (or the
    public Meshant ontology fallback) into the graph.  Silent on
    miss — the spec scenario is satisfied by per-tenant ontologies
    alone."""
    try:
        from pathlib import Path

        candidates = [
            Path(__file__).resolve().parents[1] / "semantic" / "ontology.ttl",
            Path(__file__).resolve().parents[1] / "semantic" / "ontology" / "meshant.ttl",
        ]
        for candidate in candidates:
            if candidate.is_file():
                graph.parse(source=str(candidate), format="turtle")
                return
    except Exception as exc:
        logger.debug("semantic_expansion_base_ontology_skip: %s", exc)


def _bridges_for_token(graph, token: str) -> Iterable[ExpansionBridge]:
    """Yield bridges for one query token via the four spec relations.

    The matching strategy: find IRIs in the graph whose ``rdfs:label``
    OR local-name (post-fragment) case-insensitively equals ``token``.
    For each such IRI, walk the four bridge relations and yield labels
    for the connected terms.
    """
    try:
        from rdflib import Literal, URIRef
        from rdflib.namespace import OWL, RDFS, SKOS
    except ImportError:  # pragma: no cover — rdflib is a hard dep.
        return []

    seeds = list(_iris_for_token(graph, token, RDFS=RDFS, SKOS=SKOS))
    if not seeds:
        return []

    bridges: list[ExpansionBridge] = []

    def _add(label: str | None, relation: str):
        if not label:
            return
        if label.strip().lower() == token.strip().lower():
            return  # never re-bridge to the input token itself
        bridges.append(
            ExpansionBridge(
                label=label,
                relation=relation,
                source_term=token,
            ),
        )

    for seed in seeds:
        # skos:altLabel — literal directly attached to the seed.
        for o in graph.objects(seed, SKOS.altLabel):
            if isinstance(o, Literal):
                _add(str(o), "skos:altLabel")

        # skos:related — symmetric (a related b ⇒ b related a in spec
        # spirit; rdflib doesn't auto-symmetrise so we walk both
        # directions explicitly).
        for partner in list(graph.objects(seed, SKOS.related)) + list(
            graph.subjects(SKOS.related, seed)
        ):
            if isinstance(partner, URIRef):
                _add(_label_for(graph, partner, RDFS), "skos:related")

        # owl:equivalentClass — symmetric (rdflib doesn't auto-symmetrise).
        for partner in list(graph.objects(seed, OWL.equivalentClass)) + list(
            graph.subjects(OWL.equivalentClass, seed)
        ):
            if isinstance(partner, URIRef):
                _add(_label_for(graph, partner, RDFS), "owl:equivalentClass")

        # rdfs:subClassOf — REQ-SEM-SEARCH-EXPAND-001 says "ancestors
        # at depth ≤ 2".  Walk seed → super only.
        for partner in _walk_subclass_ancestors(
            graph,
            seed,
            RDFS,
            MAX_SUBCLASS_DEPTH,
        ):
            _add(_label_for(graph, partner, RDFS), "rdfs:subClassOf")

    return bridges


def _iris_for_token(graph, token: str, *, RDFS, SKOS):
    """Yield IRIs whose label or local-name matches ``token`` case-
    insensitively."""
    from rdflib import Literal, URIRef

    target = token.strip().lower()
    if not target:
        return

    seen: set[URIRef] = set()

    # 1. By rdfs:label literal.
    for s, _, o in graph.triples((None, RDFS.label, None)):
        if isinstance(o, Literal) and str(o).strip().lower() == target:
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                yield s

    # 2. By skos:prefLabel literal — convention many ontologies use
    #    instead of (or alongside) rdfs:label.
    for s, _, o in graph.triples((None, SKOS.prefLabel, None)):
        if isinstance(o, Literal) and str(o).strip().lower() == target:
            if isinstance(s, URIRef) and s not in seen:
                seen.add(s)
                yield s

    # 3. By IRI local name fallback — concepts that don't carry an
    #    explicit label still match by their fragment / trailing
    #    path component.  Restrict to URIRef terms only — Literals
    #    and BNodes don't have a meaningful local name.
    iri_terms: set[URIRef] = set()
    for s in graph.subjects():
        if isinstance(s, URIRef):
            iri_terms.add(s)
    for o in graph.objects():
        if isinstance(o, URIRef):
            iri_terms.add(o)
    for term in iri_terms:
        if term in seen:
            continue
        local = _local_name(str(term))
        if local.lower() == target:
            seen.add(term)
            yield term


def _label_for(graph, iri, RDFS) -> str:
    """Return the best human label for an IRI.

    Preference: rdfs:label literal > local-name fragment.  Empty
    string when neither resolves (caller filters).
    """
    from rdflib import Literal

    for o in graph.objects(iri, RDFS.label):
        if isinstance(o, Literal):
            return str(o)
    return _local_name(str(iri))


def _local_name(iri: str) -> str:
    """Trailing fragment / path-component of an IRI.

    ``https://example.com/onto#Foo`` → ``Foo``.
    ``https://example.com/onto/Foo`` → ``Foo``.
    """
    if "#" in iri:
        return iri.rsplit("#", 1)[-1]
    if "/" in iri:
        return iri.rsplit("/", 1)[-1]
    return iri


def _walk_subclass_ancestors(graph, seed, RDFS, max_depth: int):
    """BFS the subClassOf graph upward (ancestors only) up to
    ``max_depth``.

    REQ-SEM-SEARCH-EXPAND-001 mandates ANCESTORS only (``seed → super``)
    — descendant traversal is intentionally NOT performed because the
    spec scenario "Synonym expansion surfaces equivalent-class match"
    pins the contract via owl:equivalentClass, not subclass
    specialisation, and pulling subclass children silently broadens
    recall beyond what the spec promises.
    """
    from rdflib import URIRef

    seen: set = {seed}
    frontier = [(seed, 0)]
    while frontier:
        node, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for partner in graph.objects(node, RDFS.subClassOf):
            if isinstance(partner, URIRef) and partner not in seen:
                seen.add(partner)
                yield partner
                frontier.append((partner, depth + 1))


__all__ = [
    "MAX_SUBCLASS_DEPTH",
    "ExpansionBridge",
    "expand_query_terms",
]
