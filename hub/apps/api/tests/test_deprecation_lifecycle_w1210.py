"""
W12.10 (oss-release-remediation) — deprecation-lifecycle veracity pins.

The named liars: the SearchViewSet's deprecation headers were HARDCODED
in the view (a `Sunset` of 2026-08-10 with a docstring claiming
"removed after 30 days" — no enforcement existed), while the
APIVersionManager registry carried FIVE stale entries whose paths
(/api/v1/search/, track-click, rebuild-index) never matched the real
routes and whose sunset date (2026-04-18) disagreed with the view's
advertised date.

Root fix: ONE lifecycle mechanism — the APIVersionManager registry
holds the REAL routes with the canonical dates (deprecated_since
2026-05-12, sunset 2026-08-10, replacement /api/search/), the
middleware emits the full deprecation header contract (Deprecation,
Deprecation-Date, Sunset, Link successor-version, X-API-Deprecated,
Warning), and past-sunset enforcement 410s (the W12.7 machinery).

Pins run against the REAL registry, the REAL middleware, and REAL
requests — no mocks.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.api.versioning import APIVersionManager, DeprecatedEndpoint
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.billing.tests.plan_fixtures import get_pro_plan
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SEARCH_APPS = _REPO_ROOT / "hub" / "apps" / "search" / "apps.py"
_SEARCH_VIEWS = _REPO_ROOT / "hub" / "apps" / "search" / "views.py"
_VERSIONING = _REPO_ROOT / "hub" / "apps" / "api" / "versioning.py"

# The canonical deprecation contract for the legacy SearchViewSet.
CANONICAL_SUNSET = "2026-08-10"
CANONICAL_DEPRECATED_SINCE = "2026-05-12"
CANONICAL_REPLACEMENT = "/api/search/"

REAL_SEARCH_ROUTES = [
    ("GET", "/api/v1/search/search/"),
    ("GET", "/api/v1/search/suggestions/"),
    ("POST", "/api/v1/search/track_click/"),
    ("GET", "/api/v1/search/analytics/"),
    ("POST", "/api/v1/search/rebuild_index/"),
]

STALE_PATHS = [
    "/api/v1/search/",
    "/api/v1/search/track-click/",
    "/api/v1/search/rebuild-index/",
]


class RegistryContractTest(TestCase):
    """The registry holds the REAL routes with the canonical dates."""

    def test_registry_covers_the_real_search_routes(self):
        for method, path in REAL_SEARCH_ROUTES:
            endpoint = APIVersionManager.get_deprecated_endpoint(path, method)
            assert endpoint is not None, f"{method} {path} must be registered"
            assert endpoint.sunset_date == CANONICAL_SUNSET, (
                f"{method} {path}: sunset must be {CANONICAL_SUNSET}, "
                f"got {endpoint.sunset_date}"
            )
            assert endpoint.replacement == CANONICAL_REPLACEMENT
            assert endpoint.deprecated_since == CANONICAL_DEPRECATED_SINCE

    def test_stale_mismatched_entries_are_gone(self):
        for path in STALE_PATHS:
            methods = APIVersionManager.DEPRECATED_ENDPOINTS.keys()
            matches = [k for k in methods if k.endswith(f":{path}")]
            assert not matches, f"stale registry entry for {path}: {matches}"

    def test_registration_source_names_the_real_routes(self):
        source = _SEARCH_APPS.read_text(encoding="utf-8")
        # The paths are built as f"/api/v1/search/{action}/" — the pin
        # asserts the ACTION names and the canonical dates instead of
        # the interpolated literal.
        assert '"track_click"' in source
        assert '"rebuild_index"' in source
        assert '"suggestions"' in source
        assert '"analytics"' in source
        assert CANONICAL_SUNSET in source
        assert CANONICAL_DEPRECATED_SINCE in source
        assert '"track-click"' not in source
        assert '"rebuild-index"' not in source


class SingleSourceTest(TestCase):
    """The view no longer hand-rolls deprecation headers; the middleware
    emits the full contract from the registry."""

    def test_view_has_no_hardcoded_deprecation_headers(self):
        source = _SEARCH_VIEWS.read_text(encoding="utf-8")
        assert 'response["Deprecation"]' not in source, (
            "the view must not hardcode deprecation headers — the "
            "middleware owns the contract"
        )
        assert 'response["Sunset"]' not in source
        assert 'response["Deprecation-Date"]' not in source

    def test_middleware_emits_the_full_header_contract(self):
        source = _VERSIONING.read_text(encoding="utf-8")
        assert 'response["Deprecation"] = "true"' in source
        assert 'response["Deprecation-Date"]' in source
        assert 'response["Sunset"]' in source
        assert 'response["Link"]' in source


class RealRequestTest(TestCase):
    """Real requests against the enforced lifecycle: the legacy
    SearchViewSet surface is PAST its sunset (2026-08-10 < today) and
    must 410 with the replacement; a future-dated deprecated endpoint
    must carry the full header contract."""

    def setUp(self):
        uid = uuid.uuid4().hex[:6]
        plan = get_pro_plan()
        self.tenant = Tenant.objects.create(
            name=f"deprec-{uid}",
            slug=f"deprec-{uid}",
            plan=plan,
        )
        self.user = User.objects.create_user(
            email=f"deprec-{uid}@test.local",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        token = JWTTokenGenerator.generate_access_token(self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_past_sunset_route_returns_410_with_replacement(self):
        """The lifecycle is ENFORCED: the legacy surface 410s with the
        ENDPOINT_SUNSET envelope carrying the replacement + guide."""
        resp = self.client.get("/api/v1/search/search/", {"q": "test"})
        assert resp.status_code == 410, resp.data
        body = resp.data
        assert body["code"] == "ENDPOINT_SUNSET"
        assert body["details"]["replacement"] == CANONICAL_REPLACEMENT
        assert body["details"]["sunset_date"] == CANONICAL_SUNSET
        assert "migration_guide" in body["details"]

    def test_future_dated_endpoint_carries_the_full_header_contract(self):
        """A not-yet-sunset deprecated endpoint must carry the full
        header contract from the middleware (the registry is the single
        source — registered here through the real API, on a fictional
        path, then removed)."""
        from hub.apps.api.versioning import APIVersionManager

        path = f"/api/v1/w1210-future-{uuid.uuid4().hex[:6]}/"
        key = f"GET:{path}"
        APIVersionManager.register_deprecated_endpoint(
            DeprecatedEndpoint(
                path=path,
                method="GET",
                deprecated_since="2026-01-01",
                sunset_date="2099-01-01",
                replacement="/api/search/",
                migration_guide="W12.10 pin",
            )
        )
        try:
            resp = self.client.get(path)
            # The middleware emits the contract on ANY response (the
            # path has no view — 404 — the headers must still be there).
            assert resp.status_code == 404
            assert resp["Deprecation"] == "true"
            assert "Sunset" in resp
            assert "successor-version" in resp.get("Link", "")
            assert resp["X-API-Deprecated"] == "true"
            assert "Warning" in resp
            assert "Deprecation-Date" in resp
        finally:
            APIVersionManager.DEPRECATED_ENDPOINTS.pop(key, None)

    def test_unified_search_route_has_no_deprecation_headers(self):
        resp = self.client.get("/api/search/", {"q": ""})
        assert resp.status_code == 200, resp.data
        assert "Deprecation" not in resp
        assert "Sunset" not in resp
        assert "X-API-Deprecated" not in resp
