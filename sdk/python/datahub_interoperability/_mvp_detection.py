"""
Pure functions for detecting MVP-gated paths and extracting environment info.

Mirrors ``cli/datahub_cli/_mvp_detection.py``. Side-effect-free so unit tests
can exhaustively parametrize without HTTP, mock, or fixture machinery.

Phase 215.2 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

from ._mvp_gates import (
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_PREFIXES,
)

_API_V1_PREFIX = "/api/v1/"


def _normalize_relative(path: str) -> str:
    """Strip an optional ``/api/v1/`` (or full URL) and return the relative
    path component used for prefix matching. See CLI counterpart for details.
    """
    if not path:
        return ""
    if _API_V1_PREFIX in path:
        return path.split(_API_V1_PREFIX, 1)[1]
    return path.lstrip("/")


def detect_mvp_gated_feature(path: str) -> Optional[Tuple[str, str]]:
    """Return ``(prefix, feature)`` if ``path`` matches a gated prefix, else None.

    Longest-prefix-wins tiebreak guards against future overlapping prefixes.
    """
    relative = _normalize_relative(path)
    if not relative:
        return None
    matches = [p for p in MVP_GATED_PREFIXES if relative.startswith(p)]
    if not matches:
        return None
    prefix = max(matches, key=lambda p: (len(p), p))
    feature = MVP_GATED_FEATURE_NAMES.get(prefix, prefix.rstrip("/").replace("-", " ").title())
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
