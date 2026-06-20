"""
Phase 250.1.A.11 — header-only body policy for ``POST .../assets/data-first/``.

Used by :class:`~hub.apps.assets.middleware.DataFirstBodyCapMiddleware`
(early in ``MIDDLEWARE``, before auth) and by
:class:`~hub.apps.assets.views.AssetViewSet.data_first` as defence in depth.

Only ``Content-Length`` + ``Transfer-Encoding`` are consulted — never the raw
body — so chunked uploads cannot force buffering before rejection.
"""

from __future__ import annotations

import re
from typing import Any

from django.http import HttpRequest

DATA_FIRST_MAX_BODY_BYTES: int = 100 * 1024 * 1024

_DATA_FIRST_PATH_RE = re.compile(r"^/api/v[0-9]+/assets/data-first/?$")


def is_data_first_post(request: HttpRequest) -> bool:
    """True when this request targets the data-first asset-creation endpoint."""
    path = request.path or ""
    return bool(request.method == "POST" and _DATA_FIRST_PATH_RE.match(path))


def evaluate_data_first_body_headers(
    *,
    content_length_raw: str | None,
    transfer_encoding: str,
) -> tuple[int, dict[str, Any]] | None:
    """Apply Length Required / bad CL / payload-too-large rules.

    Returns ``(http_status, json_serializable_dict)`` when the request must be
    rejected, otherwise ``None``.
    """
    transfer_encoding_norm = (transfer_encoding or "").lower()
    if "chunked" in transfer_encoding_norm or not (content_length_raw or "").strip():
        return (
            411,
            {
                "error": (
                    "Content-Length header is required on "
                    "POST /assets/data-first/ (chunked uploads "
                    "are rejected to prevent memory-exhaustion DoS)."
                ),
                "code": "LENGTH_REQUIRED",
                "details": {
                    "max_bytes": DATA_FIRST_MAX_BODY_BYTES,
                },
            },
        )
    try:
        body_size = int(content_length_raw)
    except (TypeError, ValueError):
        return (
            400,
            {
                "error": "Invalid Content-Length header.",
                "code": "BAD_REQUEST",
            },
        )
    if body_size < 0:
        return (
            400,
            {
                "error": "Negative Content-Length is invalid.",
                "code": "BAD_REQUEST",
            },
        )
    if body_size > DATA_FIRST_MAX_BODY_BYTES:
        return (
            413,
            {
                "error": (
                    f"Request body too large "
                    f"({body_size} bytes); max "
                    f"{DATA_FIRST_MAX_BODY_BYTES} bytes."
                ),
                "code": "PAYLOAD_TOO_LARGE",
                "details": {
                    "max_bytes": DATA_FIRST_MAX_BODY_BYTES,
                    "received_bytes": body_size,
                },
            },
        )
    return None
