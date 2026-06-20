"""
285.8.3.16 — Request size limiting middleware.

Rejects requests exceeding DATA_UPLOAD_MAX_MEMORY_SIZE before body parse.
Returns HTTP 413 with Retry-After header.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response

_MAX_SIZE = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024)


class RequestSizeLimitMiddleware:
    """285.8.3.16 — Reject oversized requests at the middleware layer."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                size = int(content_length)
                if size > _MAX_SIZE:
                    return Response(
                        {
                            "detail": f"Request body exceeds maximum size of {_MAX_SIZE // (1024 * 1024)} MB",
                            "code": "REQUEST_TOO_LARGE",
                        },
                        status=413,
                        headers={"Retry-After": "3600"},
                    )
            except (ValueError, TypeError):
                pass
        return self.get_response(request)
