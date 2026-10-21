"""
Phase 250.3.B.6 + 250.3.B.8 — deprecation-window response headers
for the Asset visibility property migration.

Mounted in ``MIDDLEWARE`` as
``hub.apps.assets.middleware.AssetVisibilityDeprecationHeadersMiddleware``.
The middleware runs on every response but only mutates headers when
the request path matches ``/api/v[0-9]+/assets/``. Two header
contracts are exposed:

1. **Deprecation headers (RFC 8594)** — ``Deprecation: true``,
   ``Sunset: <RFC-7231 date>``, and ``Link: ...rel="deprecation"``
   so the frontend ``deprecationInterceptor.ts`` (Phase 250.3.B.6)
   can detect the deprecation window and surface a one-time toast
   to admin users without parsing the body.

2. **Cache-Control no-cache window (Phase 250.3.B.8 / B2-8)** —
   ``Cache-Control: no-cache, no-store, must-revalidate`` for the
   first 7 days post-deploy so cached pre-deploy responses (which
   carried the legacy stored ``visibility`` column) don't surface
   stale values to admins. After the 7-day window expires the
   middleware falls back to whatever ``Cache-Control`` the
   downstream view already set (or nothing — Django doesn't add a
   default).

The 7-day window is gated by the
``ASSET_VISIBILITY_DEPRECATION_NO_CACHE_UNTIL`` setting (a
``datetime`` object, MUST be timezone-aware). If the setting is
unset, the no-cache window is treated as expired (no header).

The Sunset date is gated by
``ASSET_VISIBILITY_DEPRECATION_SUNSET_DATE`` (datetime; defaults
to the deploy date + 90 days if unset, which lines up with the
3-release-cycle phase-2 column-drop schedule from D250.4).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from django.conf import settings

_ASSETS_PATH_RE = re.compile(r"^/api/v[0-9]+/assets/")

#: RFC-7231 IMF-fixdate format used by both ``Date`` and ``Sunset``
#: response headers (e.g. ``"Wed, 21 Oct 2026 07:28:00 GMT"``).
_RFC7231_FORMAT: str = "%a, %d %b %Y %H:%M:%S GMT"

#: Default phase-2 sunset offset from "now" if the
#: ``ASSET_VISIBILITY_DEPRECATION_SUNSET_DATE`` setting is unset.
#: 90 days lines up with the D250.4 three-release-cycle gate.
_DEFAULT_SUNSET_OFFSET_DAYS: int = 90


def _format_rfc7231(dt: datetime) -> str:
    """Format a timezone-aware datetime as an RFC-7231 IMF-fixdate."""
    if dt.tzinfo is None:
        # Defensive: treat naive datetimes as UTC. RFC-7231 requires GMT.
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime(_RFC7231_FORMAT)


def _resolve_sunset_date() -> str:
    """Return the RFC-7231 sunset date for the visibility deprecation."""
    configured: datetime | None = getattr(
        settings, "ASSET_VISIBILITY_DEPRECATION_SUNSET_DATE", None
    )
    if configured is not None:
        return _format_rfc7231(configured)
    fallback = datetime.now(UTC) + timedelta(days=_DEFAULT_SUNSET_OFFSET_DAYS)
    return _format_rfc7231(fallback)


def _no_cache_window_active() -> bool:
    """True iff the post-deploy no-cache window is still open."""
    until: datetime | None = getattr(settings, "ASSET_VISIBILITY_DEPRECATION_NO_CACHE_UNTIL", None)
    if until is None:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return datetime.now(UTC) < until


class AssetVisibilityDeprecationHeadersMiddleware:
    """Append deprecation + (conditional) no-cache headers to /assets/
    responses for the Phase 250.3.B deprecation window."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path or ""
        if not _ASSETS_PATH_RE.match(path):
            return response

        # Phase 250.3.B.6 — RFC 8594 deprecation signals. ``Deprecation:
        # true`` is the load-bearing flag for the FE interceptor; the
        # ``Sunset`` date tells the interceptor when phase-2 hits so
        # it can change the toast severity (warning → error) as the
        # date approaches.
        response["Deprecation"] = "true"
        response["Sunset"] = _resolve_sunset_date()
        # The Link header carries the deprecation-doc URL so admins
        # can read the migration guide directly from the response.
        response["Link"] = (
            "</docs/api/migrations/visibility-deprecation.md>; "
            'rel="deprecation"; type="text/markdown"'
        )

        # Phase 250.3.B.8 / B2-8 — 7-day post-deploy no-cache window.
        # We OVERWRITE any pre-existing Cache-Control value — the
        # downstream cache-headers middleware sets short TTLs that
        # would otherwise serve stale visibility values from CDN /
        # browser caches during the rollout.
        if _no_cache_window_active():
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response


class DataFirstBodyCapMiddleware:
    """Phase 250.1.A.11 — Content-Length / chunked body cap BEFORE auth.

    Rejects oversized or chunked POST requests to
    ``/api/v*/assets/data-first/`` solely from the Content-Length and
    Transfer-Encoding headers — never reading the raw body — so
    chunked uploads cannot force buffering before rejection.

    Mounted early in ``MIDDLEWARE`` (before ``AuthenticationMiddleware``).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import JsonResponse

        from hub.apps.assets.data_first_body_guard import (
            evaluate_data_first_body_headers,
            is_data_first_post,
        )

        if is_data_first_post(request):
            rejection = evaluate_data_first_body_headers(
                content_length_raw=request.META.get("CONTENT_LENGTH"),
                transfer_encoding=request.META.get("HTTP_TRANSFER_ENCODING", "") or "",
            )
            if rejection is not None:
                status_code, payload = rejection
                response = JsonResponse(payload, status=status_code)
                # DRF test client and middleware downstream expect .data on
                # responses.  JsonResponse is a raw Django HttpResponse and
                # does not carry .data, so we attach the payload dict as an
                # attribute for compatibility with DRF's test client and any
                # logging/audit middleware that reads response_data.
                response.data = payload
                return response

        return self.get_response(request)
