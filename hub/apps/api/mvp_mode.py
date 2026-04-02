"""
MVP deployment mode: non-MVP /api/v1 areas are blocked at request time and omitted from OpenAPI.

Routes stay registered in URLconf (stable under Django settings reloads in tests). Enforcement:
``MvpModeApiGateMiddleware`` and ``openapi_mvp.postprocess_drop_mvp_gated_paths``.

Prefix list is relative to ``/api/v1/`` (tuple entries include a trailing slash).
"""

from __future__ import annotations

from typing import Final

# Path segments under /api/v1/ that are disabled when MVP_MODE is True.
MVP_GATED_RELATIVE_PREFIXES: Final[tuple[str, ...]] = (
    "mesh/",
    "virtualization/",
    "integrations/",
    "baas/",
    "ml/",
    "ai/",
    "transformation/",
    "social/",
)

API_V1_PREFIX: Final[str] = "/api/v1/"


def api_v1_relative_path(request_path: str) -> str | None:
    """Return the sub-path after /api/v1/, or None if this is not an API v1 path."""
    if not request_path.startswith(API_V1_PREFIX):
        return None
    return request_path[len(API_V1_PREFIX) :]


def is_mvp_gated_api_v1_path(request_path: str) -> bool:
    """True if this request targets a non-MVP area (only meaningful when MVP_MODE is on)."""
    rel = api_v1_relative_path(request_path)
    if rel is None:
        return False
    return any(rel.startswith(p) for p in MVP_GATED_RELATIVE_PREFIXES)


def openapi_path_is_mvp_gated(path_key: str) -> bool:
    """True if an OpenAPI paths key refers to a gated /api/v1/ area.

    Handles keys that include the full ``/api/v1/...`` prefix and keys that are
    already prefix-stripped (``SCHEMA_PATH_PREFIX`` / spectacular may emit either).
    """
    normalized = path_key if path_key.startswith("/") else f"/{path_key}"
    if "/api/v1/" in normalized:
        idx = normalized.index("/api/v1/") + len("/api/v1/")
        rel = normalized[idx:]
        if any(rel.startswith(p) for p in MVP_GATED_RELATIVE_PREFIXES):
            return True
    tail = normalized.lstrip("/")
    return any(tail.startswith(p) for p in MVP_GATED_RELATIVE_PREFIXES)
