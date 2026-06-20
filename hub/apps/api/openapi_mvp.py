"""Strip MVP-gated paths from OpenAPI schema when MVP_MODE is True."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from hub.apps.api.mvp_mode import openapi_path_is_mvp_gated


def postprocess_drop_mvp_gated_paths(
    result: dict[str, Any],
    generator: Any,
    request: Any,
    public: bool,
) -> dict[str, Any]:
    if not getattr(settings, "MVP_MODE", False):
        return result
    paths = result.get("paths")
    if not isinstance(paths, dict):
        return result
    result["paths"] = {k: v for k, v in paths.items() if not openapi_path_is_mvp_gated(k)}
    return result
