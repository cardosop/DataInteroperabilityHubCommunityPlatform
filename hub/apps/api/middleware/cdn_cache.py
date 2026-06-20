"""
281.A.7.4 — CDN Edge Cache Middleware for API GET Responses.

Adds ``Cache-Control`` headers to idempotent GET responses so CDN edge
nodes can serve cached responses, reducing origin load.  Mutations
(POST/PUT/PATCH/DELETE) emit cache-invalidation signals via Redis pub/sub
so that CDN edge caches are purged within seconds of a data change.

Behaviour:
  - GET requests → ``Cache-Control: public, max-age=60, s-maxage=300``
    (public = CDN-cacheable; 60s browser, 300s CDN edge).
  - Authenticated GETs → ``Cache-Control: private, max-age=0``
    (authenticated responses must not be cached by shared CDN).
  - POST/PUT/PATCH/DELETE → emit ``cdn:invalidate:<path_prefix>`` event
    to Redis pub/sub so the CDN purge worker can act on it.

Configuration (in settings.py):
  ``CDN_CACHE_ENABLED`` (bool, default=True) — master kill-switch.
  ``CDN_CACHE_MAX_AGE`` (int, default=300) — CDN edge TTL in seconds.
  ``CDN_CACHE_BROWSER_MAX_AGE`` (int, default=60) — browser TTL.

Activation:
  Add ``hub.apps.api.middleware.cdn_cache.CDNCacheMiddleware`` to
  ``MIDDLEWARE`` in settings.py, AFTER ``AuthenticationMiddleware``
  so ``request.user`` is available for the authenticated-GET check.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

# ── Redis pub/sub for cache invalidation ──────────────────────────────────

try:
    from hub.apps.core.redis_pools import get_redis_events_client

    def _publish_invalidation(path_prefix: str) -> None:
        """Publish a CDN cache invalidation event to Redis."""
        try:
            client = get_redis_events_client()
            client.publish("cdn:invalidate", path_prefix)
        except Exception:
            pass  # Cache invalidation is best-effort; never break the response
except ImportError:

    def _publish_invalidation(_path_prefix: str) -> None:
        pass


class CDNCacheMiddleware:
    """Add CDN-aware Cache-Control headers to API GET responses."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Master kill-switch
        if not getattr(settings, "CDN_CACHE_ENABLED", True):
            return response

        # Only cache API paths
        if not request.path.startswith("/api/"):
            return response

        method = request.method.upper()

        # ── Mutations: emit invalidation signals ──────────────────────
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            if 200 <= response.status_code < 300:
                # Invalidate the collection path for this resource.
                # POST /api/v1/assets/        → publish /api/v1/assets/
                # PATCH /api/v1/assets/<id>/  → publish /api/v1/assets/
                # DELETE /api/v1/assets/<id>/ → publish /api/v1/assets/
                parts = request.path.strip("/").split("/")
                # Take everything except the last segment if it looks like an
                # ID (UUID, numeric, or slug) — otherwise keep the full path.
                if len(parts) >= 4 and parts[-1]:
                    # Check if the last segment is a resource ID (UUID / numeric / k6- prefix)
                    last = parts[-1]
                    if len(last) >= 32 or last.isdigit() or last.startswith("k6-") or "-" in last:
                        prefix = "/" + "/".join(parts[:-1]) + "/"
                    else:
                        prefix = "/" + "/".join(parts) + "/"
                else:
                    prefix = "/" + "/".join(parts) + "/"
                _publish_invalidation(prefix)
            return response

        # ── GET/HEAD: add Cache-Control ───────────────────────────────
        if method not in ("GET", "HEAD"):
            return response

        # Authenticated requests must never be CDN-cached.
        # Skip error responses (>= 400) — views intentionally set
        # Cache-Control on terminal responses (e.g. tombstone 410
        # returns max-age=86400 per REQ-SEM-TOMBSTONE-001).
        if hasattr(request, "user") and request.user.is_authenticated:
            if response.status_code < 400:
                response["Cache-Control"] = "private, max-age=0, no-cache"
            return response

        # Only cache successful GET responses
        if 200 <= response.status_code < 300:
            browser_ttl = getattr(settings, "CDN_CACHE_BROWSER_MAX_AGE", 60)
            cdn_ttl = getattr(settings, "CDN_CACHE_MAX_AGE", 300)
            response["Cache-Control"] = f"public, max-age={browser_ttl}, s-maxage={cdn_ttl}"
            response["Vary"] = "Accept-Encoding, Origin"

        return response


# ── Cache invalidation helper (call from service layers on mutation) ──────

# Mapping of short resource name → API path prefix.
# The CDNCacheMiddleware publishes invalidation events under path prefixes;
# service-layer callers use the short names for ergonomics.
CACHEABLE_PATH_PREFIXES: dict[str, str] = {
    "assets": "/api/v1/assets",
    "contracts": "/api/v1/contracts",
    "marketplace": "/api/v1/marketplace",
    "search": "/api/v1/search",
    "datasets": "/api/v1/datasets",
    "files": "/api/v1/files",
    "compliance": "/api/v1/compliance",
    "governance": "/api/v1/governance",
    "semantic": "/api/v1/semantic",
}

# Reverse map for the middleware's path-based invalidation lookup
_PATH_TO_RESOURCE: dict[str, str] = {v: k for k, v in CACHEABLE_PATH_PREFIXES.items()}


def invalidate_cdn_cache(resource_type: str, resource_id: str = "") -> None:
    """Invalidate CDN cache for a resource type and optional specific resource.

    Call this from service-layer mutation methods after successful writes.
    Uses short resource names (e.g. ``"assets"``, ``"contracts"``) that map
    to API path prefixes defined in ``CACHEABLE_PATH_PREFIXES``.

    Example:
        invalidate_cdn_cache("assets", asset_id)
        invalidate_cdn_cache("contracts")
    """
    path_prefix = CACHEABLE_PATH_PREFIXES.get(resource_type)
    if path_prefix is None:
        return

    if resource_id:
        path_prefix = f"{path_prefix}/{resource_id}"

    _publish_invalidation(path_prefix)
