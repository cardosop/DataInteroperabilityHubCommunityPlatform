"""
Pure functions for detecting MVP-gated paths and extracting environment info.

These are deliberately side-effect-free so they can be exhaustively
parametrized in unit tests without any HTTP, mock, or fixture machinery.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from urllib.parse import urlparse

from ._mvp_gates import (
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_RELATIVE_PREFIXES,
)

_API_V1_PREFIX = "/api/v1/"


def _normalize_relative(path: str) -> str:
    """Strip an optional leading ``/api/v1/`` (or full URL) and return the
    relative path component used for prefix matching.

    Accepts any of:
      - ``"mesh/clusters"``                 (already relative)
      - ``"/api/v1/mesh/clusters"``         (absolute API path)
      - ``"https://host/api/v1/mesh/..."``  (full request URL)

    Leading slashes on the relative form are tolerated and stripped.
    """
    if not path:
        return ""
    if _API_V1_PREFIX in path:
        return path.split(_API_V1_PREFIX, 1)[1].lstrip("/")
    return path.lstrip("/")


def detect_mvp_gated_feature(path: str) -> tuple[str, str] | None:
    """Return ``(prefix, feature)`` if ``path`` matches a gated prefix, else None.

    The longest matching prefix wins (so ``mesh/clusters/abc`` matches
    ``mesh/`` deterministically). The prefix list is sourced from
    ``MVP_GATED_RELATIVE_PREFIXES`` to keep this function in lock-step with
    the canonical hub backend list.
    """
    relative = _normalize_relative(path)
    if not relative:
        return None
    matches = [p for p in MVP_GATED_RELATIVE_PREFIXES if relative.startswith(p)]
    if not matches:
        return None
    # Deterministic tiebreak: longest prefix first, then lexicographic.
    prefix = max(matches, key=lambda p: (len(p), p))
    feature = MVP_GATED_FEATURE_NAMES.get(prefix, prefix.rstrip("/").replace("-", " ").title())
    return (prefix, feature)


def extract_environment_url(request_url: str) -> str:
    """Return the ``scheme://netloc`` origin of ``request_url``.

    Uses :func:`urllib.parse.urlparse` directly. ``urlparse`` does not raise
    on malformed input — it returns empty fields — so this function MUST NOT
    wrap the call in a bare ``except``. If the URL has no scheme or netloc
    we fall back to the original input (trimmed) so the caller still sees
    something useful in the rendered error message.
    """
    if not request_url:
        return ""
    parsed = urlparse(request_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return request_url.strip()
