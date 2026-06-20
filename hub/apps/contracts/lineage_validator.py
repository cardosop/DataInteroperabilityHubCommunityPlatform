"""
Phase 228.F2 (REQ-LIN-F2-001 / F2.6) — Field-level lineage validator.

Three concerns, three pure functions:

* :func:`detect_cycle` — given the existing edge set + a new edge,
  return True if the new edge would close a cycle.  O(V+E) DFS over
  the existing graph, then a single reachability check from the
  new edge's target to its source.

* :func:`validate_field_exists` — given a contract + (model_name,
  field_name), return True if the field is declared in
  ``hub_contract_json.models[*].fields[*]`` (recursive into nested
  ``object``/``array`` shapes per the L2.2 walker).  Empty model
  name (``""``) means "the contract's top-level schema.fields[]".

* :func:`validate_type_compatibility` — given (source_type,
  target_type), return True if a column-level mapping between
  them is type-compatible per the lineage type-compatibility
  matrix.  Defaults to **conservative** rejection: only widening
  conversions are allowed without an explicit transformation_ref.

These are PURE functions — no DB access — so they're cheap to
property-test with hypothesis (F2.12) and the same call-site
binds the endpoint AND the integration test surface.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


# An edge-tuple-key for the in-memory graph.  Dictionaries / model
# instances would each have their own id semantics; reducing to a
# string-tuple keeps the cycle test deterministic.
EdgeKey = tuple[str, str, str, str]
"""(source_contract_id, source_field_qname, target_contract_id, target_field_qname)"""


def _qname(model: str, field: str) -> str:
    """Compose a model+field qname.  Empty model ⇒ schema-level field."""
    return f"{model}.{field}" if model else field


def _edge_key(edge: dict[str, Any]) -> EdgeKey:
    """Project an edge dict to its cycle-relevant key tuple."""
    return (
        str(edge.get("source_contract") or ""),
        _qname(
            str(edge.get("source_model") or ""),
            str(edge.get("source_field") or ""),
        ),
        str(edge.get("target_contract") or ""),
        _qname(
            str(edge.get("target_model") or ""),
            str(edge.get("target_field") or ""),
        ),
    )


def detect_cycle(
    edges: Iterable[dict[str, Any]],
    new_edge: dict[str, Any],
) -> list[str] | None:
    """Return the cycle path if adding ``new_edge`` to ``edges`` closes one.

    Args
    ----
    edges
        Existing edges that will REMAIN after the patch (i.e. the
        edges that aren't being removed).  The caller is expected
        to pre-filter — passing the full pre-patch edge list would
        produce false positives if an edge being removed in the
        same patch closes a cycle with the new one.
    new_edge
        The candidate edge to add.

    Returns
    -------
    ``None`` if the new edge does NOT close a cycle.  Otherwise the
    cycle path as a list of node identifiers — strings of the form
    ``"<contract_id>:<model>.<field>"`` (or ``"<contract_id>:<field>"``
    for schema-level fields).  The list starts and ends at the same
    node (``[A, B, C, A]``), per REQ-LIN-F2-002 spec scenario.

    Algorithm
    ---------
    Build the directed adjacency list from ``edges`` keyed on the
    qname pair (contract_id + qname for both endpoints), then ask:
    "is there a path from ``new_edge.target`` back to ``new_edge.source``?"
    DFS with a parent map; O(V+E).  When the search reaches
    ``new_src_node``, walk the parent map back to reconstruct the
    cycle path and return it.
    """
    new_src_node = (
        str(new_edge.get("source_contract") or ""),
        _qname(
            str(new_edge.get("source_model") or ""),
            str(new_edge.get("source_field") or ""),
        ),
    )
    new_tgt_node = (
        str(new_edge.get("target_contract") or ""),
        _qname(
            str(new_edge.get("target_model") or ""),
            str(new_edge.get("target_field") or ""),
        ),
    )

    def _format(node: tuple[str, str]) -> str:
        cid, qname = node
        return f"{cid}:{qname}" if cid else qname

    # Self-loop is a cycle by definition.
    if new_src_node == new_tgt_node:
        return [_format(new_src_node), _format(new_src_node)]

    # Build adjacency.
    adj: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        key = _edge_key(edge)
        src = (key[0], key[1])
        tgt = (key[2], key[3])
        adj[src].append(tgt)

    # Reachability from new_tgt to new_src with parent tracking.  If
    # reachable, the new edge (src → tgt) would close the loop
    # tgt → ... → src → tgt; the path is reconstructed from the
    # parent map.
    visited: set[tuple[str, str]] = set()
    parent: dict[tuple[str, str], tuple[str, str]] = {}
    stack: list[tuple[str, str]] = [new_tgt_node]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if node == new_src_node:
            # Reconstruct the path: src → ... → tgt → src
            # Walk parent map from new_src_node back to new_tgt_node,
            # then prepend the new edge (new_src → new_tgt) to close
            # the cycle.
            path: list[tuple[str, str]] = [new_src_node]
            cursor = new_src_node
            while cursor in parent and parent[cursor] != new_tgt_node:
                cursor = parent[cursor]
                path.append(cursor)
            path.append(new_tgt_node)
            path.append(new_src_node)
            return [_format(n) for n in path]
        for neighbour in adj.get(node, ()):
            if neighbour not in visited:
                parent[neighbour] = node
                stack.append(neighbour)
    return None


# ---------------------------------------------------------------------------
# Field-exists check
# ---------------------------------------------------------------------------


def validate_field_exists(
    contract_payload: dict[str, Any],
    model_name: str,
    field_name: str,
) -> bool:
    """Return True if ``field_name`` is declared on ``contract_payload``.

    Walks the canonical HubContract shape:

    * ``model_name == ""`` → search ``schema.fields[*].name``
      (schema-level fields, the legacy ODCS shape).
    * ``model_name != ""`` → search ``models[*].fields[*].name``
      where ``models[*].name == model_name``.

    Recursive into nested ``object``/``array`` shapes — a field
    ``customer.address.street`` resolves through three levels of
    ``fields[*].fields`` walk.  This matches the L2.2 walker that
    populates the canonical shape on contract creation.
    """
    if not isinstance(contract_payload, dict):
        return False

    if not model_name:
        schema = contract_payload.get("schema") or {}
        if not isinstance(schema, dict):
            return False
        return _field_present(schema.get("fields") or [], field_name)

    for model in contract_payload.get("models") or []:
        if not isinstance(model, dict):
            continue
        if model.get("name") == model_name:
            return _field_present(model.get("fields") or [], field_name)
    return False


def _field_present(fields: list[dict[str, Any]], qname: str) -> bool:
    """Recursive search for ``qname`` (dot-separated) in a fields tree."""
    if not isinstance(fields, list) or not qname:
        return False
    head, _, rest = qname.partition(".")
    for field in fields:
        if not isinstance(field, dict):
            continue
        if field.get("name") != head:
            continue
        if not rest:
            return True
        # Walk into nested object / array.
        nested = field.get("fields")
        if nested is None:
            items = field.get("items")
            if isinstance(items, dict):
                nested = items.get("fields")
        if isinstance(nested, list) and _field_present(nested, rest):
            return True
    return False


# ---------------------------------------------------------------------------
# Type compatibility matrix
# ---------------------------------------------------------------------------


# Conservative widening matrix.  Each row is a source type; each
# value is the set of target types that accept it WITHOUT an explicit
# ``transformation_ref``.  Other combinations require the caller to
# provide a transformation_ref to document the lossy / explicit
# conversion (or fail the F2.6.3 validator).
#
# The matrix is deliberately small.  Phase 228.F2 v1 is a column-level
# mapping editor, not a transformation-language designer; we don't
# want to encode every possible JDBC widening rule.  A future v2 can
# extend the matrix without API churn since it lives in code.
TYPE_COMPAT_MATRIX: dict[str, set[str]] = {
    "string": {"string"},
    "integer": {"integer", "long", "decimal", "number"},
    "long": {"long", "decimal", "number"},
    "decimal": {"decimal", "number"},
    "number": {"number", "decimal"},
    "float": {"float", "double", "number", "decimal"},
    "double": {"double", "number", "decimal"},
    "boolean": {"boolean"},
    "date": {"date", "string"},
    "timestamp": {"timestamp", "string", "date"},
    "object": {"object"},
    "array": {"array"},
}


def validate_type_compatibility(
    source_type: str | None,
    target_type: str | None,
    *,
    transformation_ref: str = "",
) -> bool:
    """Return True if a source→target column mapping is type-compatible.

    Args
    ----
    source_type
        Source field's ``data_type`` (canonical Pydantic name) or
        ``type`` (alias).  None treated as "unknown" → always
        accepted (we don't have the data to reject).
    target_type
        Target field's data type.  Same conventions.
    transformation_ref
        When non-empty, the caller is asserting the conversion is
        explicit (e.g. ``"CAST(x AS string)"``) and the validator
        accepts the mapping.  This is the escape hatch for lossy
        conversions the matrix doesn't permit.

    Returns
    -------
    True if the mapping is type-compatible; False otherwise.
    """
    if transformation_ref:
        # Explicit transformations bypass the widening matrix —
        # the matrix is for "no-op casts" only.
        return True
    if not source_type or not target_type:
        return True
    src = source_type.lower().strip()
    tgt = target_type.lower().strip()
    if src == tgt:
        return True
    return tgt in TYPE_COMPAT_MATRIX.get(src, set())


__all__ = [
    "TYPE_COMPAT_MATRIX",
    "_edge_key",
    "_qname",
    "detect_cycle",
    "validate_field_exists",
    "validate_type_compatibility",
]
