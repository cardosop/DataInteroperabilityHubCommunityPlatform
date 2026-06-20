"""
Phase 228 X (228.X.5 / REQ-LIN-X-005) — PII redaction at API
serialization for cross-tenant lineage viewers.

Pure-function module: takes the edge-owner tenant's redaction
patterns + the viewer's tenant id + a sequence of edge dicts, and
returns a copy with field names replaced by ``[REDACTED]`` when
the viewer is from a different tenant AND a pattern matches.

Spec rules (REQ-LIN-X-005):

  1. Patterns are matched against ``LineageEdge.source_field`` and
     ``LineageEdge.target_field`` only — model names + edge_type
     are not redacted (they're considered structural metadata).
  2. Redaction is NEVER applied for own-tenant viewers
     (``viewer_tenant_id == owner_tenant_id``) — same-tenant users
     see their own field names unredacted.
  3. Empty pattern list = no redaction (legacy behaviour preserved).

Patterns are compiled lazily + cached per-(tuple-of-patterns) so a
busy serialization path doesn't pay regex-compile cost per edge.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache

REDACTED_PLACEHOLDER = "[REDACTED]"


@lru_cache(maxsize=128)
def _compile_patterns(patterns: tuple[str, ...]) -> tuple[re.Pattern, ...]:
    out: list[re.Pattern] = []
    for raw in patterns:
        try:
            out.append(re.compile(raw))
        except re.error:
            # Malformed pattern — skip (logs in caller). We don't
            # want a bad regex on one tenant to crash every cross-
            # tenant view.
            continue
    return tuple(out)


def _matches_any(value: str, compiled: Sequence[re.Pattern]) -> bool:
    if not value:
        return False
    return any(p.search(value) for p in compiled)


def redact_edges_for_cross_tenant_viewer(
    *,
    edges: Iterable[dict],
    viewer_tenant_id: str | None,
    owner_tenant_id: str | None,
    patterns: Sequence[str],
) -> list[dict]:
    """Pure-function redaction. Returns a NEW list of edge dicts.

    Same-tenant viewers (`viewer_tenant_id == owner_tenant_id`) get
    the input back unchanged. Empty pattern list short-circuits
    similarly. Otherwise: source_field / target_field that match
    any pattern are replaced with ``[REDACTED]``.
    """
    edges_list = list(edges)
    if not patterns:
        return edges_list
    if viewer_tenant_id and owner_tenant_id and str(viewer_tenant_id) == str(owner_tenant_id):
        return edges_list
    compiled = _compile_patterns(tuple(patterns))
    if not compiled:
        return edges_list

    out: list[dict] = []
    for edge in edges_list:
        copied = dict(edge)
        for key in ("source_field", "target_field"):
            current = copied.get(key)
            if isinstance(current, str) and _matches_any(current, compiled):
                copied[key] = REDACTED_PLACEHOLDER
        out.append(copied)
    return out


__all__ = [
    "REDACTED_PLACEHOLDER",
    "redact_edges_for_cross_tenant_viewer",
]
