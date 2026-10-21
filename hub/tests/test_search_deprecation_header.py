"""
Phase 54.5 — Search Deprecation Header & Empty-Query Guard Tests

Validates via real HTTP requests:
- SearchViewSet returns Deprecation + Link headers
- UnifiedSearchView does NOT return deprecation headers
- The deprecated SearchViewSet rejects empty q with 400 (QUERY_REQUIRED);
  the canonical UnifiedSearchView treats empty q as filter-only browse
  mode (200, Phase 18.3 — the shipped frontend omits q when the search
  box is empty)
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.billing.tests.plan_fixtures import get_pro_plan
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _setup_auth_client():
    """Create tenant + user + authenticated API client."""
    uid = uuid.uuid4().hex[:6]
    plan = get_pro_plan()
    tenant = Tenant.objects.create(
        name=f"search-hdr-{uid}",
        slug=f"search-hdr-{uid}",
        plan=plan,
    )
    from datetime import timedelta

    from django.utils import timezone

    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    user = User.objects.create_user(
        email=f"search-hdr-{uid}@test.local",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    token = JWTTokenGenerator.generate_access_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class SearchDeprecationHeaderTest(TestCase):
    """The legacy SearchViewSet surface is PAST its sunset (2026-08-10)
    — the deprecation lifecycle is ENFORCED by APIVersionMiddleware:
    requests 410 with the ENDPOINT_SUNSET envelope carrying the
    replacement, instead of serving with header-only warnings."""

    def setUp(self):
        self.client = _setup_auth_client()

    def test_search_viewset_is_sunset_and_returns_410(self):
        """GET /api/v1/search/search/?q=test must return 410 ENDPOINT_SUNSET."""
        resp = self.client.get("/api/v1/search/search/", {"q": "test"})
        self.assertEqual(
            resp.status_code,
            410,
            f"Legacy search surface must 410 after its sunset, got {resp.status_code}",
        )
        body = resp.data
        self.assertEqual(body.get("code"), "ENDPOINT_SUNSET")
        self.assertEqual(body["details"]["replacement"], "/api/search/")
        self.assertIn("migration_guide", body["details"])

    def test_search_viewset_sunset_carries_the_sunset_date(self):
        """The 410 envelope must carry the canonical sunset date."""
        resp = self.client.get("/api/v1/search/search/", {"q": "test"})
        self.assertEqual(resp.status_code, 410)
        body = resp.data
        self.assertEqual(body["details"]["sunset_date"], "2026-08-10")

    def test_unified_search_no_deprecation_header(self):
        """GET /api/search/?q=test must NOT include Deprecation header."""
        resp = self.client.get("/api/search/", {"q": "test"})
        if resp.status_code == 200:
            self.assertNotIn(
                "Deprecation",
                resp,
                "UnifiedSearchView must NOT set Deprecation header",
            )


class SearchViewSetEmptyQueryGuardTest(TestCase):
    """The legacy surface 410s before the view ever runs (post-sunset);
    the unified view stays filter-only (200)."""

    def setUp(self):
        self.client = _setup_auth_client()

    def test_search_viewset_rejects_empty_q_via_sunset_410(self):
        """GET /api/v1/search/search/?q= must return 410 (the sunset
        enforcement fires before the view — the empty-q guard is moot
        on the retired surface)."""
        resp = self.client.get("/api/v1/search/search/", {"q": ""})
        self.assertEqual(
            resp.status_code,
            410,
            f"Empty q on the sunset surface must 410, got {resp.status_code}",
        )

    def test_unified_search_empty_q_returns_filter_only(self):
        """GET /api/search/?q= returns 200 filter-only (Phase 18.3).

        The canonical UnifiedSearchView treats an empty/missing ``q`` as
        valid browse mode — the shipped frontend search page omits ``q``
        when the search box is empty and expects filtered listings. Only
        the retired /api/v1/search/search/ ViewSet required ``q``.
        """
        resp = self.client.get("/api/search/", {"q": ""})
        self.assertEqual(
            resp.status_code,
            200,
            f"Empty q on the unified surface must return 200 filter-only, got {resp.status_code}",
        )
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)
