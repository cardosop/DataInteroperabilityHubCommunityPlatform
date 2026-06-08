"""
277.B.110 — rate limit on the version discovery endpoint.

The ``GET /api/v1/`` endpoint is public (no auth required) and is the
first thing an API consumer hits, so it's vulnerable to naive polling.
A per-IP rate cap (scope ``version_discovery``) prevents abuse without
affecting legitimate callers. The scope is registered in
``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``.
"""

from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle


class VersionDiscoveryRateThrottle(AnonRateThrottle):
    """Per-IP rate throttle scoped to ``version_discovery``.

    Uses DRF's ``AnonRateThrottle`` so the key is the client IP.
    The actual rate is read from
    ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['version_discovery']``.
    """

    scope = "version_discovery"
