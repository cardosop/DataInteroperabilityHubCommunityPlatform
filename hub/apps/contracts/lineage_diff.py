"""
Phase 228 F5 (REQ-LIN-F5-002 / 228.F5.4) — pure-function lineage diff.

Computes the set-arithmetic delta between two snapshots of the
``LineageEdge`` open-row state. The function is intentionally pure
(no DB, no signals, no side effects) so it can be:

* Unit-tested with fabricated dicts (see :mod:`test_lineage_diff`).
* Driven by the time-travel diff endpoint (F5.3).
* Re-used by the diff frontend (the JSON shape this returns IS the
  API response shape — the view does not re-shape the result).

Diff identity (spec: REQ-LIN-F5-002)
------------------------------------
Two edges are considered the SAME edge when the full edge tuple
matches — including ``transformation_ref`` and ``job_ref``. Per the
spec: "modified is always empty because SCD Type 2 represents
modifications as close-and-reopen". A change to ``transformation_ref``
under SCD-2 closes the old row + opens a new one, so the diff sees
two distinct edges (one removed + one added) — NOT a "modified"
entry. The response shape carries ``modified: []`` so callers (the
React UI in particular) have a stable contract.

Determinism
-----------
``added`` / ``removed`` lists are sorted by the canonical scope tuple
so two diff calls on the same input produce byte-identical output —
required by the UI's React Query cache + by JSON-snapshot tests in
the frontend.
"""
from __future__ import annotations

from typing import Any, Iterable


# Spec-compliant identity tuple — every field that participates in
# row identity under SCD Type 2. A change to ANY of these fields
# produces a NEW row (close-and-reopen), so the diff sees the old
# row in ``removed`` and the new row in ``added``. Per spec:
# "modified is always empty because SCD Type 2 represents
# modifications as close-and-reopen".
_IDENTITY_KEYS = (
    "source_contract",
    "target_contract",
    "source_model",
    "source_field",
    "target_model",
    "target_field",
    "edge_type",
    "transformation_ref",
    "job_ref",
)


def _identity(edge: dict) -> tuple:
    """Build the canonical scope tuple. Treats missing optional keys
    as empty-string so callers don't need to normalize before
    handing rows in."""
    return tuple(str(edge.get(k) or "") for k in _IDENTITY_KEYS)


def compute_diff(
    *,
    left: Iterable[dict[str, Any]],
    right: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Pure-function lineage diff (REQ-LIN-F5-002).

    Args:
        left: Edge snapshot at the older anchor (``from`` in the API).
            Iterable of dicts matching ``LineageService._edges_at``'s
            return shape.
        right: Edge snapshot at the newer anchor (``to`` in the API).

    Returns:
        Spec-compliant dict with keys
        ``{added, removed, modified, unchanged, summary}``.
        ``added``/``removed``/``unchanged`` are lists of edge dicts.
        ``modified`` is ALWAYS ``[]`` per the spec (SCD Type 2
        represents modifications as close-and-reopen → the diff
        sees two distinct rows: one removed + one added).
        ``summary`` carries the four cardinalities.

    Determinism:
        ``added`` / ``removed`` are sorted by ``_identity`` so two
        invocations on identical inputs yield byte-identical output.
    """
    left_list = list(left)
    right_list = list(right)

    left_index: dict[tuple, dict] = {}
    for edge in left_list:
        left_index[_identity(edge)] = edge
    right_index: dict[tuple, dict] = {}
    for edge in right_list:
        right_index[_identity(edge)] = edge

    added: list[dict] = []
    removed: list[dict] = []
    unchanged: list[dict] = []

    all_keys = sorted(set(left_index) | set(right_index))
    for key in all_keys:
        before = left_index.get(key)
        after = right_index.get(key)
        if before is None:
            added.append(after)  # type: ignore[arg-type]
            continue
        if after is None:
            removed.append(before)
            continue
        # Same identity tuple AND present in both snapshots → unchanged.
        unchanged.append(after)

    summary = {
        "added": len(added),
        "removed": len(removed),
        # Spec: modified is always empty under SCD-2 close-and-reopen.
        "modified": 0,
        "unchanged": len(unchanged),
    }
    return {
        "added": added,
        "removed": removed,
        "modified": [],  # Spec-mandated empty list.
        "unchanged": unchanged,
        "summary": summary,
    }


__all__ = ["compute_diff"]
