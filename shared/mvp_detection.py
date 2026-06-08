"""
Pure functions for detecting MVP-gated paths and extracting environment info.

Shared between ``cli/`` and ``sdk/python/`` (278.AA.15).  Side-effect-free
so unit tests can exhaustively parametrize without HTTP, mock, or fixture
machinery.

The prefix list and feature-name mapping are injected as parameters rather
than imported from a module — this lets the CLI and SDK each supply their
own ``_mvp_gates`` constants (which may use different variable names)
without forcing a naming convention on the shared code.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple
from urllib.parse import urlparse

_API_V1_PREFIX = "/api/v1/"


def _normalize_relative(path: str) -> str:
    """Strip an optional ``/api/v1/`` (or full URL) and return the relative
    path component used for prefix matching.
    """
    if not path:
        return ""
    if _API_V1_PREFIX in path:
        return path.split(_API_V1_PREFIX, 1)[1]
    return path.lstrip("/")


def detect_mvp_gated_feature(
    path: str,
    *,
    gated_prefixes: FrozenSet[str],
    feature_names: Dict[str, str],
) -> Optional[Tuple[str, str]]:
    """Return ``(prefix, feature)`` if ``path`` matches a gated prefix, else None.

    Longest-prefix-wins tiebreak guards against future overlapping prefixes.

    Args:
        path: A relative path, absolute API path, or full request URL.
        gated_prefixes: FrozenSet of prefix strings to match against.
        feature_names: Dict mapping prefix → human-readable feature name.

    Returns:
        ``(matched_prefix, feature_name)`` or ``None``.
    """
    relative = _normalize_relative(path)
    if not relative:
        return None
    matches = [p for p in gated_prefixes if relative.startswith(p)]
    if not matches:
        return None
    prefix = max(matches, key=lambda p: (len(p), p))
    feature = feature_names.get(
        prefix, prefix.rstrip("/").replace("-", " ").title()
    )
    return (prefix, feature)


def extract_environment_url(request_url: str) -> str:
    """Return the ``scheme://netloc`` origin of ``request_url``.

    Uses :func:`urllib.parse.urlparse` directly. ``urlparse`` does not raise
    on malformed input, so this function MUST NOT wrap the call in a bare
    ``except``. Falls back to the trimmed input when scheme/netloc are missing.
    """
    if not request_url:
        return ""
    parsed = urlparse(request_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return request_url.strip()
