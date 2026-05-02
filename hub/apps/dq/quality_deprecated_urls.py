"""
Phase 240.3.B.3 / 240.3.E.1 — deprecated dual-mount of DQ endpoints
under ``/api/v1/quality/*``.

Two ViewSets are exposed here:

* ``DQQualityViewSet`` (anomalies/trends/scorecards/root_cause_analysis)
  — canonical at ``/api/v1/dq/quality/``; mirrored at
  ``/api/v1/quality/`` with deprecation headers.
* ``DQRunViewSet`` (runs CRUD + ``runs/<id>/results/`` action)
  — canonical at ``/api/v1/dq/runs/``; mirrored at
  ``/api/v1/quality/runs/`` with deprecation headers (240.3.E.1).

Per Phase 227 conventions every alias response carries:

* ``Sunset``: HTTP-date 180 days from the merge anchor (RFC 8594).
* ``Deprecation``: HTTP-date of the merge anchor.
* ``Link``: ``<canonical>; rel="successor-version"`` (RFC 8288).

The headers are emitted by ``DeprecationHeadersMixin.finalize_response``
which subclasses both deprecated ViewSets — keeping the original
``DQQualityViewSet`` / ``DQRunViewSet`` free of any per-prefix
branching.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import DQQualityViewSet, DQRunViewSet

# Phase 240.3.B.3 — Sunset window per D240.10 ("180d from merge").
# Anchor date: 2026-05-01 (Phase 240 merge target). When the merge
# slips, bump this constant — its sole purpose is to give external
# integrators a stable RFC 8594 date in the response headers.
_DEPRECATION_DATE = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_SUNSET_DATE = _DEPRECATION_DATE + timedelta(days=180)


def _http_date(dt: datetime) -> str:
    """RFC 7231 IMF-fixdate, e.g. ``Sun, 06 Nov 1994 08:49:37 GMT``."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


class DeprecationHeadersMixin:
    """
    DRF ViewSet mixin that decorates every response with RFC 8594
    ``Sunset`` / ``Deprecation`` and RFC 8288 ``Link`` headers.

    Subclasses set :attr:`deprecated_to_canonical_prefix` to a
    ``(old_prefix, new_prefix)`` tuple. The ``Link`` header is
    computed by replacing the first occurrence of ``old_prefix`` in
    ``request.path`` with ``new_prefix`` so the successor URL
    reflects the actual sub-path the client called (e.g. ``/runs/``,
    ``/runs/<id>/``, ``/runs/<id>/results/``) rather than just the
    ViewSet root.

    Headers are emitted on EVERY response — including 4xx/5xx — so
    a client polling a failing alias still sees the migration
    warning and can react. This matches RFC 8594's "Sunset on every
    response" guidance.
    """

    deprecated_to_canonical_prefix: Tuple[str, str] = (
        "/api/v1/quality/",
        "/api/v1/dq/quality/",
    )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        old_prefix, new_prefix = self.deprecated_to_canonical_prefix
        request_path = request.path
        if request_path.startswith(old_prefix):
            successor_path = request_path.replace(old_prefix, new_prefix, 1)
        else:
            # Defensive: if a future re-mount changes the alias prefix
            # without updating the mixin's class attribute, still
            # emit a usable Link to the ViewSet root rather than a
            # broken header.
            successor_path = new_prefix
        response["Sunset"] = _http_date(_SUNSET_DATE)
        response["Deprecation"] = _http_date(_DEPRECATION_DATE)
        response["Link"] = f'<{successor_path}>; rel="successor-version"'
        return response


class DeprecatedDQQualityViewSet(DeprecationHeadersMixin, DQQualityViewSet):
    """``DQQualityViewSet`` mounted under the deprecated alias."""
    deprecated_to_canonical_prefix = (
        "/api/v1/quality/", "/api/v1/dq/quality/",
    )


class DeprecatedDQRunViewSet(DeprecationHeadersMixin, DQRunViewSet):
    """
    ``DQRunViewSet`` mounted under ``/api/v1/quality/runs/`` (Phase
    240.3.E.1).

    The canonical mount is ``/api/v1/dq/runs/`` — the ``Link`` header
    is built by replacing ``/api/v1/quality/`` with ``/api/v1/dq/``
    (no nested ``/quality/`` segment, unlike the advanced-quality
    ViewSet which lives under ``/dq/quality/``).

    Subclassing ``DQRunViewSet`` directly keeps tenant isolation,
    AUDITOR write-blocking, and all other view-level behaviour
    identical to the canonical mount — the alias is purely a URL
    surface, not a permissions side-channel.
    """
    deprecated_to_canonical_prefix = (
        "/api/v1/quality/", "/api/v1/dq/",
    )


# ---------------------------------------------------------------------
# URL wiring
# ---------------------------------------------------------------------
#
# Two routing styles in play, matched to each ViewSet's surface:
#
# * Quality-advanced endpoints — manually pinned ``path(...)`` per
#   action so the URL is ``/api/v1/quality/<action>/`` (no nested
#   ``quality/quality/`` doubling that a full router would produce).
# * Runs — ``SimpleRouter`` (NOT ``DefaultRouter``) so all five CRUD
#   verbs + the ``results`` ``@action`` resolve via the framework
#   without the framework also registering an API root view at
#   ``/api/v1/quality/``. The root-view shortcut WOULD bypass the
#   ``DeprecationHeadersMixin`` (the root view is
#   ``rest_framework.routers.APIRootView``, NOT a subclass of our
#   deprecated ViewSets), so a client probing ``/api/v1/quality/``
#   would get 200 + the route-listing JSON with NO Sunset header —
#   exposing the alias structure without the migration warning.
#   ``SimpleRouter`` skips the root view; ``/api/v1/quality/``
#   stays 404 (unchanged from pre-Phase-240.3.E behaviour).

_runs_router = SimpleRouter()
_runs_router.register(r"runs", DeprecatedDQRunViewSet, basename="dq-run-deprecated")

urlpatterns = [
    # 240.3.E.1 — runs CRUD + results @action.
    path("", include(_runs_router.urls)),

    # 240.3.B.3 — advanced quality endpoints.
    path(
        "anomalies/",
        DeprecatedDQQualityViewSet.as_view({"get": "anomalies"}),
        name="dq-quality-deprecated-anomalies",
    ),
    path(
        "trends/",
        DeprecatedDQQualityViewSet.as_view({"get": "trends"}),
        name="dq-quality-deprecated-trends",
    ),
    path(
        "scorecards/",
        DeprecatedDQQualityViewSet.as_view({"get": "scorecards"}),
        name="dq-quality-deprecated-scorecards",
    ),
    path(
        "root_cause_analysis/",
        DeprecatedDQQualityViewSet.as_view({"get": "root_cause_analysis"}),
        name="dq-quality-deprecated-root-cause",
    ),
]
