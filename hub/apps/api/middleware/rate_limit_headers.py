"""
Phase 277.B.101 — middleware that adds RFC-standard rate-limit headers.

Throttle classes set ``_ratelimit_*`` keys on ``request.META`` during
``throttled()``.  This middleware reads those keys and copies them to
the HTTP response headers before the response leaves the server.

Headers emitted (per IETF draft-ietf-httpapi-ratelimit-headers):
- ``RateLimit-Limit`` — the quota (requests per window)
- ``RateLimit-Remaining`` — remaining requests in current window
- ``RateLimit-Reset`` — seconds until the window resets
"""

from __future__ import annotations

_RATELIMIT_HEADER_MAP = [
    ("_ratelimit_limit", "RateLimit-Limit"),
    ("_ratelimit_remaining", "RateLimit-Remaining"),
    ("_ratelimit_reset", "RateLimit-Reset"),
]


class RateLimitHeadersMiddleware:
    """Inject RateLimit-* HTTP headers from request META into the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response is None:
            return response
        for meta_key, header_name in _RATELIMIT_HEADER_MAP:
            value = request.META.get(meta_key)
            if value is not None:
                response[header_name] = str(value)
        return response
