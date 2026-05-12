"""
MVP deployment mode: non-MVP /api/v1 areas are blocked at request time and omitted from OpenAPI.

Routes stay registered in URLconf (stable under Django settings reloads in tests). Enforcement:
``MvpModeApiGateMiddleware`` and ``openapi_mvp.postprocess_drop_mvp_gated_paths``.

Prefix list is relative to ``/api/v1/`` (tuple entries include a trailing slash).
"""

from __future__ import annotations

import os
from typing import Final


def _parse_bool_env(name: str) -> bool:
    """Parse a boolean environment variable using the same rules as ``env.bool``.

    Truthy values: ``true``, ``1``, ``yes``, ``on``, ``y``, ``t`` (case-insensitive).
    Everything else (including unset / empty) is False.

    This function is the **canonical** implementation. Phase 216 test helpers
    in ``cli/tests/_pytest_helpers.py`` and ``sdk/python/tests/_pytest_helpers.py``
    duplicate this function byte-for-byte (no shared module — see D129)
    and a drift test ast-parses this file to assert the bodies stay
    byte-equivalent.
    """
    value = os.environ.get(name, "")
    return value.strip().lower() in ("true", "1", "yes", "on", "y", "t")


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
    "scheduled-ingestions/",
    "scheduled-exports/",
    # Phase 5 (current PR): plug backend drift. Both prefixes were mounted in
    # hub/apps/api/urls.py but absent from this list, so they were reachable
    # under MVP_MODE=True despite the frontend hiding them.
    # Phase 273.1 — removed "search/" per spec REQ-MVP-001/002; /search is
    # permanently MVP-in-scope alongside /semantic (project_mvp_scope.md).
    "developer/",
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
